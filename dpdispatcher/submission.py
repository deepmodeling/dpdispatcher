# %%
"""Define submissions, tasks, generated jobs, and resource requests."""

import asyncio
import copy
import functools
import glob
import json
import os
import pathlib
import random
import re
import time
import uuid
from collections.abc import Sequence
from hashlib import sha1
from typing import TYPE_CHECKING, Any, Optional, cast

import yaml
from dargs.dargs import Argument, Variant

from dpdispatcher.dlog import dlog
from dpdispatcher.machine import Machine
from dpdispatcher.utils.job_status import JobStatus
from dpdispatcher.utils.record import record

if TYPE_CHECKING:
    from dpdispatcher.base_context import BaseContext

# %%
default_strategy = dict(if_cuda_multi_devices=False, ratio_unfinished=0.0)


class Submission:
    """Coordinate a collection of tasks that share a working directory.

    A submission groups tasks into scheduler jobs, stages common files, monitors
    execution, downloads declared results, and records state for recovery.

    Parameters
    ----------
    work_base : path-like
        Local base directory containing all task working directories.
    machine : Machine, optional
        Batch backend and execution context. It may be bound later with
        :meth:`bind_machine`.
    resources : Resources, optional
        Resource request copied into every generated job.
    forward_common_files : list of path-like, optional
        Files shared by all tasks and staged before execution.
    backward_common_files : list of path-like, optional
        Shared result files downloaded after execution.
    task_list : list of Task, optional
        Tasks to register when the submission is created.
    previous_submission_hash : str, optional
        SHA-1 hash of a compatible prior submission whose finished-task state
        should be reused after a resource-only change.
    continue_on_failure : bool, default=False
        Continue monitoring other jobs after one job exhausts its retries.
        The default preserves the historical fail-fast behavior.
    """

    def __init__(
        self,
        work_base: str,
        machine: Optional["Machine"] = None,
        resources: Optional["Resources"] = None,
        forward_common_files: list[str] = [],
        backward_common_files: list[str] = [],
        *,
        task_list: list["Task"] = [],
        previous_submission_hash: str | None = None,
        continue_on_failure: bool = False,
    ) -> None:
        """Initialize submission configuration and an optional recovery locator."""
        self.local_root = None
        self.work_base = work_base
        self._abs_work_base = os.path.abspath(work_base)

        self.resources = resources
        self.forward_common_files = (
            sorted(forward_common_files)
            if isinstance(forward_common_files, list)
            else forward_common_files
        )
        self.backward_common_files = (
            sorted(backward_common_files)
            if isinstance(backward_common_files, list)
            else backward_common_files
        )

        self.submission_hash = None
        if previous_submission_hash is not None and not re.fullmatch(
            r"[0-9a-f]{40}", previous_submission_hash
        ):
            raise ValueError("previous_submission_hash must be a 40-character SHA-1")
        self.previous_submission_hash = previous_submission_hash
        # warning: can not remote .copy() or there will be bugs
        # self.belonging_tasks = task_list
        self.belonging_tasks = task_list.copy()
        self.belonging_jobs = list()
        self.continue_on_failure = continue_on_failure

        self.bind_machine(machine)

    def __repr__(self) -> str:
        return json.dumps(self.serialize(), indent=4)

    def __eq__(self, other: object) -> bool:
        """Compare submissions while ignoring mutable job runtime information.

        Job state, scheduler IDs, and failure counts do not affect equality.
        """
        return json.dumps(self.serialize(if_static=True)) == json.dumps(
            other.serialize(if_static=True)  # type: ignore[attr-defined]
        )

    def __getitem__(self, key: str) -> Any:  # noqa: ANN401
        return self.serialize()[key]

    @classmethod
    def deserialize(
        cls,
        submission_dict: dict[str, Any],
        machine: Optional["Machine"] = None,
        *,
        bind_context: bool = True,
    ) -> "Submission":  # noqa: ANN401
        """Reconstruct a submission from serialized state.

        Parameters
        ----------
        submission_dict : dict
            Serialized submission configuration and job state.
        machine : Machine, optional
            Machine to bind instead of reconstructing the serialized machine.

        Returns
        -------
        Submission
            Reconstructed submission.
        """
        serialized_tasks = submission_dict.get("belonging_tasks")
        task_list = (
            [Task.deserialize(task_dict) for task_dict in serialized_tasks]
            if serialized_tasks is not None
            else []
        )
        submission = cls(
            work_base=submission_dict["work_base"],
            resources=Resources.deserialize(
                resources_dict=submission_dict["resources"]
            ),
            forward_common_files=submission_dict["forward_common_files"],
            backward_common_files=submission_dict["backward_common_files"],
            task_list=task_list,
            previous_submission_hash=submission_dict.get("previous_submission_hash"),
            continue_on_failure=submission_dict.get("continue_on_failure", False),
        )
        # Preserve the original absolute path when a record is resumed from a
        # different working directory. Older records do not have this field and
        # retain the constructor's backwards-compatible fallback.
        if "_abs_work_base" in submission_dict:
            submission._abs_work_base = submission_dict["_abs_work_base"]
        submission.belonging_jobs = [
            Job.deserialize(job_dict=job_dict)
            for job_dict in submission_dict["belonging_jobs"]
        ]
        if submission.belonging_jobs:
            # Generated jobs are the canonical serialized representation of their
            # tasks. Reuse those task objects so task and job state stay linked.
            submission.belonging_tasks = [
                task for job in submission.belonging_jobs for task in job.job_task_list
            ]
        if machine is None:
            machine = Machine.deserialize(machine_dict=submission_dict["machine"])
        # ``get_hash`` includes the machine configuration.  Set it before binding
        # so a fresh process derives the same hash that was persisted by the
        # original submission instead of hashing an unbound placeholder machine.
        submission.machine = machine
        submission.submission_hash = submission.get_hash()
        submission.bind_machine(machine=machine, bind_context=bind_context)
        return submission

    def serialize(self, if_static: bool = False) -> dict[str, Any]:  # noqa: ANN401
        """Return a JSON-compatible representation of the submission.

        Parameters
        ----------
        if_static : bool, default=False
            Exclude job IDs, states, failure counts, and runtime failure policy
            when true. The policy is intentionally excluded from the static
            identity so enabling continuation does not change job hashes.

        Returns
        -------
        dict
            Submission configuration and, unless excluded, current runtime state.
        """
        assert self.resources is not None
        submission_dict = {}
        # if if_none_local_root:
        #     submission_dict['local_root'] = None
        # else:
        #     submission_dict['local_root'] = self.local_root

        submission_dict["work_base"] = self.work_base
        submission_dict["_abs_work_base"] = self._abs_work_base
        machine = getattr(self, "machine", None)
        if machine is None:
            submission_dict["machine"] = {}
        else:
            submission_dict["machine"] = machine.serialize()
        submission_dict["resources"] = self.resources.serialize()
        submission_dict["forward_common_files"] = self.forward_common_files
        submission_dict["backward_common_files"] = self.backward_common_files
        if not self.belonging_jobs:
            # Before jobs are generated, tasks are not represented elsewhere in
            # the record. Keep this optional for compatibility with old records
            # and avoid duplicating task data for generated submissions.
            submission_dict["belonging_tasks"] = [
                task.serialize() for task in self.belonging_tasks
            ]
        if not if_static:
            # Persist this lifecycle policy so recovery resumes with the same
            # failure semantics instead of silently changing behavior.
            submission_dict["continue_on_failure"] = self.continue_on_failure
        submission_dict["belonging_jobs"] = [
            job.serialize(if_static=if_static) for job in self.belonging_jobs
        ]
        if not if_static:
            submission_dict["previous_submission_hash"] = self.previous_submission_hash
        return submission_dict

    def register_task(self, task: "Task") -> None:
        """Append one task before jobs have been generated."""
        if self.belonging_jobs:
            raise RuntimeError(
                f"Not allowed to register tasks after generating jobs. submission hash error {self}"
            )
        self.belonging_tasks.append(task)

    def register_task_list(self, task_list: list["Task"]) -> None:
        """Append multiple tasks before jobs have been generated."""
        if self.belonging_jobs:
            raise RuntimeError(
                f"Not allowed to register tasks after generating jobs. submission hash error {self}"
            )
        self.belonging_tasks.extend(task_list)

    def get_hash(self) -> str:
        """Return the stable hash of the submission's static configuration."""
        return sha1(
            json.dumps(self.serialize(if_static=True)).encode("utf-8")
        ).hexdigest()

    def bind_machine(
        self,
        machine: Optional["Machine"],
        *,
        bind_context: bool = True,
    ) -> "Submission":
        """Bind a machine and initialize submission-specific context paths.

        Parameters
        ----------
        machine : Machine or None
            Machine to use for generated jobs and file operations.

        Returns
        -------
        Submission
            This submission, for convenient chained configuration.
        """
        self.machine = machine
        for job in self.belonging_jobs:
            job.machine = machine
        # ``serialize`` includes the bound machine. Set it first so the hash used
        # by context roots is the same hash reported by ``get_hash`` and records.
        self.submission_hash = self.get_hash()
        if machine is not None:
            if bind_context:
                # The previous hash is an explicit remote-state locator, not part of
                # the new submission's identity. Bind the context to that directory
                # while preserving the current hash used for new jobs and records.
                current_hash = self.submission_hash
                if self.previous_submission_hash is not None:
                    self.submission_hash = self.previous_submission_hash
                try:
                    machine.context.bind_submission(self)
                finally:
                    self.submission_hash = current_hash
            self.local_root = machine.context.temp_local_root
        return self

    def _require_machine(self) -> "Machine":
        """Return the bound machine or fail with an actionable lifecycle error."""
        if self.machine is None:
            raise RuntimeError("Submission must be bound to a machine before execution")
        return self.machine

    def run_submission(
        self,
        *,
        dry_run: bool = False,
        exit_on_submit: bool = False,
        clean: bool | str = True,
        check_interval: int = 30,
        continue_on_failure: bool | None = None,
    ) -> dict[str, Any]:  # noqa: ANN401
        """Execute the submission and monitor it until completion.

        The lifecycle recovers compatible state, stages files, submits or retries
        jobs, polls their status, downloads declared results, persists recovery
        state, and optionally cleans the execution directory.

        Parameters
        ----------
        dry_run : bool, default=False
            Upload inputs and generated scripts without submitting jobs.
        exit_on_submit : bool, default=False
            Return after jobs have been submitted instead of waiting for them.
        clean : bool, default=True
            Remove the submission-specific execution directory after download.
        check_interval : int or float, default=30
            Seconds between scheduler status checks.
        continue_on_failure : bool, optional
            Continue monitoring remaining jobs after retry exhaustion. If omitted,
            use the policy stored on this submission (which defaults to ``False``).
            An explicit value overrides the persisted policy for this run.

        Returns
        -------
        dict
            Serialized submission state at the point this method returns.
        """
        assert self.resources is not None
        machine = self._require_machine()
        policy_override = continue_on_failure
        if policy_override is not None:
            self.continue_on_failure = policy_override
        else:
            # Objects assembled by older callers or lightweight tests may not
            # have gone through ``__init__``; retain the historical default.
            self.continue_on_failure = getattr(self, "continue_on_failure", False)
        # Fail-fast: reject invalid clean strategies before recovery/upload/submission.
        self._should_clean(clean, all_genuinely_finished=False)
        if not self.belonging_jobs:
            self.generate_jobs()
        # This remains false when ratio-based early termination rewrites killed
        # jobs as finished, so on_success never mistakes that state for success.
        all_jobs_genuinely_finished = False
        try:
            self.try_recover_from_json()
            # Recovery records created by opt-in runs carry their policy. An
            # explicit runtime argument always wins over that persisted value.
            if policy_override is not None:
                self.continue_on_failure = policy_override
            continue_on_failure = self.continue_on_failure
            if not continue_on_failure and self.failed_jobs():
                # A caller explicitly selecting fail-fast must not silently
                # accept a terminal failure restored from an older record.
                self.raise_for_failed_jobs(continue_on_failure=False)
            self.update_submission_state()
            if self.check_all_finished():
                dlog.info("check_all_finished: True")
            else:
                dlog.info("check_all_finished: False")
                self.upload_jobs()
                if dry_run is True:
                    dlog.info(f"submission succeeded: {self.submission_hash}")
                    dlog.info(f"at {machine.context.remote_root}")
                    return self.serialize()
                if continue_on_failure:
                    self.handle_unexpected_submission_state(continue_on_failure=True)
                else:
                    self.handle_unexpected_submission_state()
                self.submission_to_json()
                time.sleep(1)
                self.update_submission_state()
                self.check_all_finished()
                if continue_on_failure:
                    self.handle_unexpected_submission_state(continue_on_failure=True)
                else:
                    self.handle_unexpected_submission_state()

            ratio_unfinished = self.resources.strategy["ratio_unfinished"]
            while not self.check_all_finished():
                if exit_on_submit is True:
                    dlog.info(f"submission succeeded: {self.submission_hash}")
                    dlog.info(f"at {machine.context.remote_root}")
                    return self.serialize()
                if ratio_unfinished > 0.0 and self.check_ratio_unfinished(
                    ratio_unfinished
                ):
                    self.remove_unfinished_tasks()
                    break

                try:
                    time.sleep(check_interval)
                except (Exception, KeyboardInterrupt, SystemExit) as e:
                    self.submission_to_json()
                    record_path = record.write(self)
                    dlog.exception(e)
                    dlog.info(f"submission exit: {self.submission_hash}")
                    dlog.info(f"at {machine.context.remote_root}")
                    dlog.info(f"Submission information is saved in {str(record_path)}.")
                    dlog.debug(self.serialize())
                    raise e
                else:
                    self.update_submission_state()
                    if continue_on_failure:
                        self.handle_unexpected_submission_state(
                            continue_on_failure=True
                        )
                    else:
                        self.handle_unexpected_submission_state()
            else:
                # The loop condition became false without ratio-based early exit.
                all_jobs_genuinely_finished = (
                    not continue_on_failure or not self.failed_jobs()
                )
            if continue_on_failure:
                self.handle_unexpected_submission_state(continue_on_failure=True)
            else:
                self.handle_unexpected_submission_state()
            results_downloaded = self.try_download_result()
            all_jobs_genuinely_finished = (
                all_jobs_genuinely_finished and results_downloaded
            )
        finally:
            # Cover recovery, initial submission, polling, and final download
            # failures so exhausted retries always preserve diagnostics.
            try:
                self.try_download_error_info()
            except Exception:
                pass
        self.submission_to_json()

        # Determine whether to clean remote workdir
        should_clean = self._should_clean(clean, all_jobs_genuinely_finished)
        failed_jobs = self.failed_jobs() if continue_on_failure else []
        if should_clean and not failed_jobs:
            self.clean_jobs()
        elif should_clean and failed_jobs:
            # Preserve failed-job artifacts for the explicit post-mortem
            # ``dpdisp submission --download-terminated-log`` flow.  Before
            # retry exhaustion became a durable state, failures raised before
            # reaching cleanup; retaining that behavior keeps stderr and other
            # terminal logs available while still allowing a later explicit
            # ``clean`` action to remove the remote workdir.
            dlog.info(
                "preserving remote workdir for failed jobs at: "
                f"{machine.context.remote_root}"
            )
        elif clean == "on_success":
            dlog.info(
                "clean='on_success': some jobs did not finish successfully, "
                "preserving remote workdir for debugging at: "
                f"{machine.context.remote_root}"
            )
        if continue_on_failure:
            self.raise_for_failed_jobs()
        return self.serialize()

    def failed_jobs(self) -> list["Job"]:
        """Return jobs that exhausted retries and reached a terminal failure."""
        return [job for job in self.belonging_jobs if job.job_state == JobStatus.failed]

    def raise_for_failed_jobs(self, *, continue_on_failure: bool = True) -> None:
        """Report all terminal failures after other jobs and downloads finish."""
        failed_jobs = self.failed_jobs()
        if not failed_jobs:
            return
        # ``clean_jobs`` removes the local record along with the remote workdir.
        # Re-create it before raising so callers can still inspect diagnostics
        # and use ``dpdisp submission`` to download logs or retry the submission.
        # Failure persistence is best effort: never hide the original job error
        # if a custom/incomplete submission object cannot be serialized.
        try:
            record.write(self)
        except Exception:  # noqa: BLE001 - persistence must not mask the job failure
            dlog.exception("Unable to persist failed submission record")
        details = "\n\n".join(
            job.failure_reason
            or f"job {job.job_hash} {job.job_id} failed without diagnostics"
            for job in failed_jobs
        )
        if continue_on_failure:
            message = (
                f"{len(failed_jobs)} job(s) failed after retries were exhausted; "
                "all remaining jobs were monitored to completion."
            )
        else:
            message = (
                f"{len(failed_jobs)} job(s) had already failed after retries "
                "were exhausted."
            )
        raise RuntimeError(f"{message}\n{details}")

    def _should_clean(
        self, clean: bool | str, all_genuinely_finished: bool = True
    ) -> bool:
        """Determine whether remote workdir should be cleaned.

        Parameters
        ----------
        clean : Union[bool, str]
            - True or "always": always clean
            - False or "never": never clean
            - "on_success": clean only when all jobs genuinely finished
              (not killed by ratio_unfinished early-exit)
        all_genuinely_finished : bool
            Whether all jobs completed successfully without intervention.
            When ratio_unfinished triggers remove_unfinished_tasks(), this
            is False even though job states have been mutated to "finished".

        Returns
        -------
        bool
            Whether to perform clean.

        Raises
        ------
        ValueError
            If clean is not a recognized strategy.
        """
        if clean is True or clean == "always":
            return True
        if clean is False or clean == "never":
            return False
        if clean == "on_success":
            return all_genuinely_finished
        raise ValueError(
            f"Unknown clean strategy '{clean}'. "
            f"Valid options: True, False, 'always', 'never', 'on_success'."
        )

    def try_download_error_info(self) -> None:
        """Download error diagnostic files for failed/terminated jobs.

        For each job that did not finish successfully, attempts to download
        the ``{job_hash}_last_err_file`` from the remote root to the local root.
        This preserves error diagnostics even when ``clean=True`` deletes the
        remote workdir afterward.

        The error file contains the last 1000 bytes of stderr from the most
        recently failed task in the job, written by the generated bash script.
        """
        if self.machine is None:
            return
        for job in self.belonging_jobs:
            if job.job_state in (
                JobStatus.terminated,
                JobStatus.failed,
                JobStatus.unknown,
            ):
                err_file_name = job.job_hash + "_last_err_file"
                try:
                    err_content = self.machine.get_job_error(job)
                    if err_content is not None:
                        # Write to local root for post-mortem access
                        local_err_path = os.path.join(
                            self.machine.context.local_root, err_file_name
                        )
                        os.makedirs(os.path.dirname(local_err_path), exist_ok=True)
                        with open(local_err_path, "w") as f:
                            f.write(err_content)
                        dlog.info(
                            f"Downloaded error info for job {job.job_hash} to "
                            f"{local_err_path}"
                        )
                        # Also log the error content for immediate visibility
                        dlog.warning(
                            f"Job {job.job_hash} failed. Last error output:\n"
                            f"{err_content}"
                        )
                except Exception as e:
                    dlog.debug(
                        f"Could not download error file for job {job.job_hash}: {e}"
                    )

    def try_download_result(self) -> bool:
        """Download results, retrying transient failures for up to 24 hours."""
        start_time = time.time()
        retry_interval = 60  # retry every 1 minute
        success = False
        while not success:
            try:
                self.download_jobs()
                success = True
            except FileNotFoundError as e:
                # retry will never success if the file is not found
                raise e
            except (EOFError, Exception) as e:
                dlog.exception(e)
                elapsed_time = time.time() - start_time
                if elapsed_time < 3600:  # in 1 h
                    dlog.info("Retrying in 1 minute...")
                    time.sleep(retry_interval)
                elif elapsed_time < 86400:  # 1 h ~ 24 h
                    retry_interval = 600  # retry every 10 min
                    dlog.info("Retrying in 10 minutes...")
                    time.sleep(retry_interval)
                else:  # > 24 h
                    dlog.info("Maximum retries time reached. Exiting.")
                    break
        return success

    async def async_run_submission(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Run :meth:`run_submission` in an executor.

        Cleanup defaults to false for asynchronous submissions so concurrent
        work does not remove shared context data unexpectedly. Explicitly pass
        ``clean=True`` only when each submission has an isolated execution root.

        Examples
        --------
        >>> import asyncio
        >>> async def run_all(submissions):
        ...     return await asyncio.gather(
        ...         *(
        ...             submission.async_run_submission(check_interval=2)
        ...             for submission in submissions
        ...         )
        ...     )
        """
        kwargs = {**{"clean": False}, **kwargs}
        if self._should_clean(kwargs["clean"]):
            dlog.warning(
                "Using async submission with a clean strategy that can delete "
                "the remote workdir. Jobs may fail in queue systems."
            )
        loop = asyncio.get_event_loop()
        wrapped_submission = functools.partial(self.run_submission, **kwargs)
        return await loop.run_in_executor(None, wrapped_submission)

    def update_submission_state(self) -> None:
        """Refresh every unfinished job's state from its machine backend.

        Notes
        -----
        This method only queries state. It does not submit or retry jobs.
        """
        for job in self.belonging_jobs:
            if job.job_state in (JobStatus.finished, JobStatus.failed):
                # Terminal jobs remain terminal and no longer need scheduler queries.
                continue
            job.get_job_state()
            dlog.debug(
                f"update_submission_state: job: {job.job_hash}, {job.job_id}, {job.job_state}"
            )

    def handle_unexpected_submission_state(
        self, *, continue_on_failure: bool = False
    ) -> None:
        """Submit unsubmitted jobs and retry unexpectedly terminated jobs.

        Unknown states and exhausted retries are persisted for recovery before
        the error is propagated.
        """
        machine = self._require_machine()
        try:
            for job in self.belonging_jobs:
                if continue_on_failure:
                    job.handle_unexpected_job_state(continue_on_failure=True)
                else:
                    job.handle_unexpected_job_state()
        except Exception as e:
            self.submission_to_json()
            record_path = record.write(self)
            raise RuntimeError(
                "Failed while handling an unexpected submission state.\n"
                f"Underlying job error: {e}\n"
                f"Debug information: remote_root=={machine.context.remote_root}.\n"
                f"Debug information: submission_hash=={self.submission_hash}.\n"
                f"Please check error messages above and in remote_root. "
                f"The submission information is saved in {str(record_path)}.\n"
                "For further actions, run the following command with proper flags: "
                f"dpdisp submission {self.submission_hash}"
            ) from e

    def check_ratio_unfinished(self, ratio_unfinished: float) -> bool:
        """Return whether the allowed unfinished-task threshold is satisfied.

        Parameters
        ----------
        ratio_unfinished : float
            Maximum fraction of tasks that may remain unfinished.

        Returns
        -------
        bool
            True when the finished fraction is at least ``1 - ratio_unfinished``.
        """
        assert self.resources is not None
        machine = self._require_machine()
        if self.resources.group_size == 1:
            # if group size is 1, calculate job state is enough and faster
            status_list = [job.job_state for job in self.belonging_jobs]
        else:
            # get task state is more accurate
            status_list = []
            for task in self.belonging_tasks:
                task.get_task_state(machine.context)
                status_list.append(task.task_state)
        finished_num = status_list.count(JobStatus.finished)
        return finished_num / len(self.belonging_tasks) >= (1 - ratio_unfinished)

    def remove_unfinished_tasks(self) -> None:
        """Stop unfinished work while preserving durable failed records.

        A failed job is terminal evidence that must remain available to
        ``raise_for_failed_jobs`` and post-mortem download handling.  Only
        non-terminal jobs are converted to finished after the ratio threshold
        is reached; failed jobs and their failed tasks stay in the submission.
        """
        machine = self._require_machine()
        dlog.info("Remove unfinished tasks")
        # Kill all jobs that are not already terminal.  In particular, do not
        # rewrite JobStatus.failed: doing so hides the failure from callers.
        for job in self.belonging_jobs:
            if job.job_state not in (JobStatus.finished, JobStatus.failed):
                machine.kill(job)
                job.job_state = JobStatus.finished
        # Keep failed tasks alongside successful tasks so diagnostics and
        # explicit terminated-log downloads can still address them.
        retained_tasks = [
            task
            for task in self.belonging_tasks
            if task.task_state in (JobStatus.finished, JobStatus.failed)
        ]
        self.belonging_tasks = retained_tasks
        # Remove only tasks that were intentionally stopped from each job.
        for job in self.belonging_jobs:
            job.job_task_list = [
                task
                for task in job.job_task_list
                if task.task_state in (JobStatus.finished, JobStatus.failed)
            ]

    def check_all_finished(self) -> bool:
        """Return whether every generated job has finished successfully.

        Notes
        -----
        This method does not submit, retry, or otherwise change job states.
        """
        # self.update_submission_state()
        if any(
            (
                job.job_state
                in [JobStatus.terminated, JobStatus.failed, JobStatus.unknown]
            )
            for job in self.belonging_jobs
        ):
            self.submission_to_json()
        # A newly generated job starts with ``None`` until the backend is
        # queried. Treat every state other than ``finished`` as unfinished so
        # an uninitialized job cannot be mistaken for successful completion.
        # Explicit continuation treats a retry-exhausted ``failed`` job as
        # terminal for monitoring purposes; ``run_submission`` reports it only
        # after all other jobs have reached a terminal state.
        continue_on_failure = getattr(self, "continue_on_failure", False)
        return all(
            job.job_state == JobStatus.finished
            or (continue_on_failure and job.job_state == JobStatus.failed)
            for job in self.belonging_jobs
        )

    def generate_jobs(self) -> None:
        """Generate jobs after tasks are registered.

        Tasks are shuffled with a fixed seed before grouping to distribute task
        cost while preserving deterministic job hashes for recovery. Each job
        contains at most ``resources.group_size`` tasks; zero groups all tasks.
        """
        assert self.resources is not None
        if self.belonging_jobs:
            raise RuntimeError(
                f"Can not generate jobs when submission.belonging_jobs is not empty. debug:{self}"
            )
        group_size = self.resources.group_size
        if (group_size < 0) or (not isinstance(group_size, int)):
            raise RuntimeError("group_size must be a positive number")
        task_num = len(self.belonging_tasks)
        if task_num == 0:
            raise RuntimeError("submission must have at least 1 task")
        if group_size == 0:
            # 0 means infinity
            group_size = task_num
        random.seed(42)
        random_task_index = list(range(task_num))
        random.shuffle(random_task_index)
        random_task_index_ll = [
            random_task_index[ii : ii + group_size]
            for ii in range(0, task_num, group_size)
        ]

        for ii in random_task_index_ll:
            job_task_list = [self.belonging_tasks[jj] for jj in ii]
            job = Job(
                job_task_list=job_task_list,
                machine=self.machine,
                resources=copy.deepcopy(self.resources),
            )
            self.belonging_jobs.append(job)

        if self.machine is not None:
            self.bind_machine(self.machine)

        self.submission_hash = self.get_hash()

    def upload_jobs(self) -> None:
        """Upload submission inputs through the bound context."""
        self._require_machine().context.upload(self)

    def download_jobs(self, include_failed: bool = False) -> None:
        """Download selected task outputs, optionally including failed jobs.

        Normal result downloads omit failed jobs so missing outputs do not mask
        successful work.  Explicit terminated-log requests need the original
        failed tasks, however, and set ``include_failed=True`` to bypass that
        success-only filtering.
        """
        context = self._require_machine().context
        if include_failed or not self.failed_jobs():
            # Terminated-log requests may include a configured stdout file that
            # was never created (for example, a command that fails before
            # producing output).  Ask contexts to skip absent files while still
            # transferring any logs that do exist, such as stderr diagnostics.
            context.download(
                self,
                check_exists=include_failed,
                mark_failure=False,
            )
            return

        # Temporarily expose only successful work so missing outputs from
        # terminal failures cannot mask results produced by other jobs.
        original_tasks = self.belonging_tasks
        original_jobs = self.belonging_jobs
        selected_tasks = [
            task for task in original_tasks if task.task_state == JobStatus.finished
        ]
        downloads_by_job = getattr(context, "downloads_by_job", False) is True
        if downloads_by_job and not getattr(
            context, "supports_partial_job_download", True
        ):
            # Job archives that require all tasks to succeed do not exist for a
            # failed grouped job.  Restrict both lists to complete jobs and
            # avoid invoking the backend when there is no archive to fetch.
            selected_jobs = [
                job for job in original_jobs if job.job_state == JobStatus.finished
            ]
            selected_hashes = {
                task.task_hash for job in selected_jobs for task in job.job_task_list
            }
            selected_tasks = [
                task for task in selected_tasks if task.task_hash in selected_hashes
            ]
        elif downloads_by_job:
            # Cloud archives are keyed by parent job rather than task. Retain a
            # mixed-state parent whenever it contains selected finished tasks;
            # the task-level cleanup below removes outputs of failed siblings.
            selected_hashes = {task.task_hash for task in selected_tasks}
            selected_jobs = [
                job
                for job in original_jobs
                if job.job_state == JobStatus.finished
                or any(task.task_hash in selected_hashes for task in job.job_task_list)
            ]
        else:
            selected_jobs = [
                job for job in original_jobs if job.job_state == JobStatus.finished
            ]
        if downloads_by_job and not selected_jobs:
            return
        self.belonging_tasks = selected_tasks
        self.belonging_jobs = selected_jobs
        try:
            context.download(self)
        finally:
            self.belonging_tasks = original_tasks
            self.belonging_jobs = original_jobs
        if downloads_by_job:
            self._remove_unselected_task_outputs(
                original_jobs,
                selected_tasks,
                getattr(context, "last_downloaded_files", None),
            )

    def _remove_unselected_task_outputs(
        self,
        jobs: list["Job"],
        selected_tasks: list["Task"],
        downloaded_files: set[str] | None,
    ) -> None:
        """Remove outputs of failed siblings after a mixed cloud archive download.

        Cloud contexts retrieve one archive per parent job and cannot apply the
        task-level selection used by filesystem contexts. For a mixed-state
        parent, remove only configured backward files that the current archive
        actually extracted. Explicit include_failed=True downloads take a
        separate path and intentionally retain those files.
        """
        context = self._require_machine().context
        if not isinstance(downloaded_files, set):
            # Older/custom cloud contexts do not report an extraction manifest;
            # guessing from backward_files could delete unrelated local data.
            return
        try:
            local_root = os.path.realpath(
                os.path.abspath(os.fspath(context.local_root))
            )
        except (AttributeError, TypeError):
            return

        extracted_paths: set[str] = set()
        for filename in downloaded_files:
            if not isinstance(filename, str) or not filename:
                continue
            path = (
                filename
                if os.path.isabs(filename)
                else os.path.join(local_root, filename)
            )
            path = os.path.realpath(os.path.abspath(path))
            try:
                is_inside_root = os.path.commonpath((local_root, path)) == local_root
            except ValueError:
                is_inside_root = False
            if is_inside_root and path != local_root and os.path.lexists(path):
                extracted_paths.add(path)

        if not extracted_paths:
            return

        def matches_task_output(task: "Task", path: str) -> bool:
            """Return whether an extracted path matches a task output pattern."""
            task_root = os.path.realpath(
                os.path.abspath(os.path.join(local_root, task.task_work_path))
            )
            try:
                if os.path.commonpath((local_root, task_root)) != local_root:
                    return False
            except ValueError:
                return False
            for pattern in task.backward_files:
                if pattern in ("", ".", "./"):
                    continue
                for matched in glob.glob(
                    os.path.join(task_root, pattern), recursive=True
                ):
                    matched = os.path.realpath(os.path.abspath(matched))
                    try:
                        if os.path.commonpath((local_root, matched)) != local_root:
                            continue
                    except ValueError:
                        continue
                    if matched == path:
                        return True
                    if os.path.isdir(matched):
                        try:
                            if os.path.commonpath((matched, path)) == matched:
                                return True
                        except ValueError:
                            continue
            return False

        selected_hashes = {task.task_hash for task in selected_tasks}
        # A path referenced by both a successful task and a failed sibling is
        # shared output. Preserve it even when the archive contained the path.
        protected_paths = {
            path
            for path in extracted_paths
            if any(matches_task_output(task, path) for task in selected_tasks)
        }
        for job in jobs:
            if not any(task.task_hash in selected_hashes for task in job.job_task_list):
                continue
            for task in job.job_task_list:
                if task.task_hash in selected_hashes:
                    continue
                for path in extracted_paths:
                    if path in protected_paths or not matches_task_output(task, path):
                        continue
                    # The extraction manifest contains files, not whole output
                    # trees. Remove only those files so pre-existing siblings
                    # inside a configured output directory remain untouched.
                    if os.path.isfile(path) or os.path.islink(path):
                        os.remove(path)
        # for job in self.belonging_jobs:
        #     job.tag_finished()
        # self.machine.context.write_file(self.machine.finish_tag_name, write_str="")

    def clean_jobs(self) -> None:
        """Remove remote working data and the local recovery record."""
        self._require_machine().context.clean()
        assert self.submission_hash is not None
        record.remove(self.submission_hash)

    def submission_to_json(self) -> None:
        # self.update_submission_state()
        """Write current submission state to the execution root as JSON."""
        write_str = json.dumps(self.serialize(), indent=4, default=str)
        submission_file_name = f"{self.submission_hash}.json"
        self._require_machine().context.write_file(
            submission_file_name, write_str=write_str
        )

    @classmethod
    def submission_from_json(
        cls, json_file_name: str = "submission.json"
    ) -> "Submission":
        """Load a submission, including machine state, from a local JSON file."""
        with open(json_file_name) as f:
            submission_dict = json.load(f)
        submission = cls.deserialize(submission_dict=submission_dict, machine=None)
        return submission

    def try_recover_from_json(self) -> None:
        """Restore compatible job state from the remote submission JSON file."""
        machine = self._require_machine()
        recovery_hash = self.previous_submission_hash or self.submission_hash
        submission_file_name = f"{recovery_hash}.json"
        if_recover = machine.context.check_file_exists(submission_file_name)
        if self.previous_submission_hash is not None and not if_recover:
            raise FileNotFoundError(
                "Previous submission state was not found for explicit "
                f"previous_submission_hash={self.previous_submission_hash}"
            )
        submission = None
        submission_dict = {}
        if if_recover:
            submission_dict_str = machine.context.read_file(fname=submission_file_name)
            submission_dict = json.loads(submission_dict_str)
            if self.previous_submission_hash is not None:
                self._recover_finished_tasks_from_previous(submission_dict)
                self._bind_recovered_submission()
                return
            # Reuse the authenticated machine that read the recovery file. Creating a
            # second SSHContext here can fail for one-time authentication methods such
            # as TOTP, and the reconstructed machine would be discarded immediately.
            # The machine/session can be reused safely, but the shared context must
            # remain bound to the active submission until recovery data is validated.
            submission = Submission.deserialize(
                submission_dict=submission_dict,
                machine=self.machine,
                bind_context=False,
            )
            if self == submission:
                self.belonging_jobs = submission.belonging_jobs
                self.belonging_tasks = [
                    task for job in self.belonging_jobs for task in job.job_task_list
                ]
                if "continue_on_failure" in submission_dict:
                    self.continue_on_failure = bool(
                        submission_dict["continue_on_failure"]
                    )
                self.bind_machine(machine=self.machine)
                dlog.info(
                    f"Find old submission; recover submission from json file;"
                    f"submission.submission_hash:{submission.submission_hash}; "
                    f"machine.context.remote_root:{machine.context.remote_root}; "
                    f"submission.work_base:{submission.work_base};"
                )
            else:
                print(self.serialize())
                print(submission.serialize())
                raise RuntimeError("Recover failed.")

    def _bind_recovered_submission(self) -> None:
        """Move a recovered work directory under this submission's new hash.

        Explicit resource-only resumes initially bind the context to the
        previous hash so completion tags can be inspected.  Once recovery is
        validated, the directory must follow the new hash; otherwise the next
        fresh process cannot locate the persisted ``H1.json`` state.  SSH
        contexts perform the remote rename in ``bind_submission``; local
        filesystem contexts are migrated here before rebinding.
        """
        machine = self._require_machine()
        context = machine.context
        old_remote_root = getattr(context, "remote_root", None)
        current_hash = self.submission_hash
        if current_hash is None:
            raise RuntimeError("Recovered submission has no submission hash")

        previous_hash = self.previous_submission_hash
        new_remote_root: str | None = None
        migration_hook: Any = None
        migration_performed = False
        try:
            temp_remote_root = getattr(context, "temp_remote_root", None)
            if isinstance(old_remote_root, str) and isinstance(temp_remote_root, str):
                new_remote_root = os.path.join(temp_remote_root, current_hash)
                if old_remote_root != new_remote_root:
                    migration_hook = getattr(context, "migrate_recovery_root", None)
                    if callable(migration_hook):
                        # Contexts such as HDFS must move state through their
                        # backend API; local os.path/os.replace cannot address URIs.
                        migration_performed = (
                            migration_hook(old_remote_root, new_remote_root)
                            is not False
                        )
                    elif not hasattr(context, "_recover_remote_root"):
                        # LocalContext/Shell use ordinary filesystem paths and do
                        # not implement SSHContext's remote rename hook.
                        if os.path.isdir(old_remote_root):
                            # A pre-existing destination can contain state from a
                            # concurrent or earlier resume.  Do not silently bind
                            # to it while abandoning completion tags in the source.
                            if os.path.lexists(new_remote_root):
                                raise FileExistsError(
                                    "Cannot migrate recovered submission: both old "
                                    f"and new roots exist ({old_remote_root}, "
                                    f"{new_remote_root})"
                                )
                            os.replace(old_remote_root, new_remote_root)
                            migration_performed = True

            # SSHContext performs its root migration from inside bind_machine().
            # Clear the one-time locator only for that bind attempt so a failed
            # migration or rebind remains retryable from the original root.
            self.previous_submission_hash = None
            self.bind_machine(machine)
        except Exception:
            # SSHContext performs its rename inside bind_submission, so consult
            # its explicit move marker after a later mkdir or transport failure.
            migration_performed = migration_performed or bool(
                getattr(context, "_last_recovery_moved", False)
            )
            state_bound_to_new_root = (
                isinstance(new_remote_root, str)
                and getattr(context, "remote_root", None) == new_remote_root
            )
            roots_conflict = bool(getattr(context, "_last_recovery_conflict", False))
            if (
                not roots_conflict
                and isinstance(old_remote_root, str)
                and isinstance(new_remote_root, str)
                and not hasattr(context, "_recover_remote_root")
                and os.path.lexists(old_remote_root)
                and os.path.lexists(new_remote_root)
            ):
                roots_conflict = True
            already_at_destination = bool(
                getattr(context, "_last_recovery_already_at_destination", False)
            )
            if (
                state_bound_to_new_root
                and not migration_performed
                and not roots_conflict
                and isinstance(old_remote_root, str)
                and isinstance(new_remote_root, str)
                and not hasattr(context, "_recover_remote_root")
                and not os.path.lexists(old_remote_root)
                and os.path.lexists(new_remote_root)
            ):
                already_at_destination = True
            rollback_succeeded = True
            if (
                migration_performed
                and isinstance(old_remote_root, str)
                and isinstance(new_remote_root, str)
                and old_remote_root != new_remote_root
            ):
                try:
                    rollback_hook = getattr(context, "rollback_recovery_root", None)
                    if callable(rollback_hook):
                        rollback_succeeded = (
                            rollback_hook(
                                new_remote_root,
                                old_remote_root,
                            )
                            is not False
                        )
                    elif callable(migration_hook):
                        # Preserve compatibility with third-party contexts that
                        # predate the optional force-aware rollback hook.
                        rollback_succeeded = (
                            migration_hook(new_remote_root, old_remote_root)
                            is not False
                        )
                    else:
                        # SSHContext exposes the same atomic rename primitive via
                        # its private recovery helper; point it at the old root
                        # before reversing the move. Resolve the optional
                        # attribute dynamically and narrow it with ``callable``
                        # so type checkers do not treat an arbitrary context
                        # attribute as invocable.
                        recover_root = getattr(context, "_recover_remote_root", None)
                        if callable(recover_root):
                            context.remote_root = old_remote_root
                            rollback_succeeded = bool(recover_root(new_remote_root))
                        elif os.path.lexists(new_remote_root):
                            if os.path.lexists(old_remote_root):
                                raise FileExistsError(
                                    "Cannot roll back recovered submission: both old "
                                    f"and new roots exist ({old_remote_root}, "
                                    f"{new_remote_root})"
                                )
                            os.replace(new_remote_root, old_remote_root)
                except Exception as rollback_error:
                    rollback_succeeded = False
                    dlog.error(
                        "Failed to roll back recovered submission root from %s to %s: %s",
                        new_remote_root,
                        old_remote_root,
                        rollback_error,
                    )

            if rollback_succeeded and not already_at_destination:
                self.previous_submission_hash = previous_hash
                if isinstance(old_remote_root, str):
                    context.remote_root = old_remote_root
            else:
                # The state is now known to live under the new hash.  Do not
                # restore a locator that points at a root we could not recover.
                self.previous_submission_hash = None
                if isinstance(new_remote_root, str):
                    context.remote_root = new_remote_root
            raise

    def _recover_finished_tasks_from_previous(self, previous: dict[str, Any]) -> None:
        """Reuse task completion tags after an explicitly selected resource change.

        The previous scheduler jobs themselves cannot be reused because their scripts,
        resource requests, and hashes may differ. Instead, this validates every
        non-resource part of the submission and marks only tasks with an existing
        completion tag as finished. New jobs are then submitted only for groups that
        still contain unfinished tasks.
        """
        machine = self._require_machine()
        expected_machine = machine.serialize()
        compatibility_checks = {
            "work_base": (previous.get("work_base"), self.work_base),
            "machine": (previous.get("machine"), expected_machine),
            "forward_common_files": (
                previous.get("forward_common_files"),
                self.forward_common_files,
            ),
            "backward_common_files": (
                previous.get("backward_common_files"),
                self.backward_common_files,
            ),
            "task grouping": (
                [
                    job_data[next(iter(job_data))]["job_task_list"]
                    for job_data in previous.get("belonging_jobs", [])
                ],
                [
                    [task.serialize() for task in job.job_task_list]
                    for job in self.belonging_jobs
                ],
            ),
        }
        # ``_abs_work_base`` was added after the initial recovery format.  A
        # legacy record without this optional field remains compatible; when it
        # is present, compare it to prevent resuming state from a different
        # absolute work directory.
        previous_abs_work_base = previous.get("_abs_work_base")
        if previous_abs_work_base is not None:
            compatibility_checks["absolute work_base"] = (
                previous_abs_work_base,
                self._abs_work_base,
            )
        mismatches = [
            name for name, (old, new) in compatibility_checks.items() if old != new
        ]
        if mismatches:
            raise RuntimeError(
                "Cannot resume previous submission because these non-resource "
                f"fields changed: {', '.join(mismatches)}"
            )

        finished_count = 0
        supports_task_tags = getattr(
            machine.context, "supports_task_completion_tags", True
        )
        previous_jobs = previous.get("belonging_jobs", [])
        for job_index, job in enumerate(self.belonging_jobs):
            previous_job_state = None
            previous_job_id: str | int = ""
            if job_index < len(previous_jobs):
                previous_job = previous_jobs[job_index]
                if previous_job:
                    previous_job_data = previous_job[next(iter(previous_job))]
                    previous_job_state = previous_job_data.get("job_state")
                    previous_job_id = previous_job_data.get("job_id", "")
            for task in job.job_task_list:
                # Cloud contexts cannot inspect task tags.  A persisted
                # finished job is the strongest available signal there; cloud
                # archives are job-scoped, so partial grouped-job recovery is
                # intentionally not inferred from unavailable task paths.
                if (
                    not supports_task_tags and previous_job_state == JobStatus.finished
                ) or (supports_task_tags and task.has_finished_tag(machine.context)):
                    task.task_state = JobStatus.finished
                    finished_count += 1
                else:
                    task.task_state = JobStatus.unsubmitted
            job.job_state = (
                JobStatus.finished
                if all(
                    task.task_state == JobStatus.finished for task in job.job_task_list
                )
                else JobStatus.unsubmitted
            )
            # Cloud contexts cannot inspect per-task completion tags.  Preserve
            # the persisted scheduler ID for a finished cloud job so its result
            # archive can still be downloaded and the job is not re-uploaded.
            job.job_id = (
                previous_job_id
                if not supports_task_tags and previous_job_state == JobStatus.finished
                else ""
            )
            job.fail_count = 0

        dlog.info(
            "Recovered %d completed tasks from previous submission %s; "
            "new resource configuration uses submission %s",
            finished_count,
            self.previous_submission_hash,
            self.submission_hash,
        )


class Task:
    """Represent a sequential command and its staged files.

    A task records the files it depends on and the results to transfer back.

    Parameters
    ----------
    command : str
        Shell command to execute.
    task_work_path : path-like
        Working directory relative to the submission's ``work_base``.
    forward_files : list of path-like, optional
        Task-specific input files staged before execution.
    backward_files : list of path-like, optional
        Task-specific result files downloaded after execution.
    outlog : str or None, default="log"
        File that receives standard output, or ``None`` to leave it attached.
    errlog : str or None, default="err"
        File that receives standard error, or ``None`` to leave it attached.
    task_name : str or None, optional
        Scheduler-visible name when this task is submitted as a one-task job.
    """

    def __init__(
        self,
        command: str,
        task_work_path: str,
        forward_files: Sequence[str] | None = None,
        backward_files: Sequence[str] | None = None,
        outlog: str | None = "log",
        errlog: str | None = "err",
        task_name: str | None = None,
    ) -> None:
        self.command = command
        self.task_work_path = task_work_path
        # Detach task state from caller-owned lists and constructor defaults.
        self.forward_files = list(forward_files) if forward_files is not None else []
        self.backward_files = list(backward_files) if backward_files is not None else []
        self.outlog = outlog
        self.errlog = errlog
        self.task_name = task_name

        # self.task_need_resources = task_need_resources

        self.task_hash = self.get_hash()
        # self.task_need_resources="<to be completed in the future>"
        # self.uuid =
        self.task_state = JobStatus.unsubmitted

    def __repr__(self) -> str:
        return str(self.serialize())

    def __eq__(self, other: object) -> bool:
        return json.dumps(self.serialize()) == json.dumps(other.serialize())  # type: ignore[attr-defined]

    def __getitem__(self, key: str) -> Any:  # noqa: ANN401
        return self.serialize()[key]

    def get_hash(self) -> str:
        """Return the stable hash of the task configuration."""
        return sha1(json.dumps(self.serialize()).encode("utf-8")).hexdigest()

    @classmethod
    def load_from_json(cls, json_file: str, allow_ref: bool = False) -> "Task":
        """Load a Task from a JSON file.

        Parameters
        ----------
        json_file : str
            Path to task JSON file.
        allow_ref : bool, default=False
            Whether to allow loading external JSON/YAML snippets via ``$ref``.
            Disabled by default for security.
        """
        with open(json_file) as f:
            task_dict = json.load(f)
        return cls.load_from_dict(task_dict, allow_ref=allow_ref)

    @classmethod
    def load_from_yaml(cls, yaml_file: str, allow_ref: bool = False) -> "Task":
        """Load a Task from a YAML file.

        Parameters
        ----------
        yaml_file : str
            Path to task YAML file.
        allow_ref : bool, default=False
            Whether to allow loading external JSON/YAML snippets via ``$ref``.
            Disabled by default for security.
        """
        with open(yaml_file) as f:
            task_dict = yaml.safe_load(f)
        task = cls.load_from_dict(task_dict=task_dict, allow_ref=allow_ref)
        return task

    @classmethod
    def load_from_dict(cls, task_dict: dict, allow_ref: bool = False) -> "Task":
        """Load a Task from a dict.

        Parameters
        ----------
        task_dict : dict
            Task configuration dict.
        allow_ref : bool, default=False
            Whether to allow loading external JSON/YAML snippets via ``$ref``.
            Disabled by default for security.
        """
        # check dict
        base = cls.arginfo()
        task_dict = base.normalize_value(
            task_dict, trim_pattern="_*", allow_ref=allow_ref
        )
        base.check_value(task_dict, strict=False, allow_ref=allow_ref)

        task = cls.deserialize(task_dict=task_dict)
        return task

    @classmethod
    def deserialize(cls, task_dict: dict[str, Any]) -> "Task":  # noqa: ANN401
        """Reconstruct a task from a serialized dictionary.

        Parameters
        ----------
        task_dict : dict
            Task configuration.

        Returns
        -------
        Task
            Reconstructed task.
        """
        task = cls(**task_dict)
        return task

    def serialize(self) -> dict[str, Any]:  # noqa: ANN401
        """Return the task configuration as a JSON-compatible dictionary."""
        task_dict = {}
        task_dict["command"] = self.command
        task_dict["task_work_path"] = self.task_work_path
        task_dict["forward_files"] = self.forward_files
        task_dict["backward_files"] = self.backward_files
        task_dict["outlog"] = self.outlog
        task_dict["errlog"] = self.errlog
        if self.task_name is not None:
            task_dict["task_name"] = self.task_name
        # task_dict['task_need_resources'] = self.task_need_resources
        return task_dict

    @staticmethod
    def arginfo() -> Argument:
        """Build the dargs schema for task configuration."""
        doc_command = (
            "Shell command executed for this task. A zero exit code is treated as success. "
            "If the real application may fail before useful artifacts are synchronized, consider "
            "wrapping it and saving diagnostics to files that are listed in backward_files."
        )
        doc_task_work_path = (
            "Working directory of this task, specified as a relative path inside submission.work_base. "
            "Absolute paths are not supported and may break staging or remote execution. For the smallest "
            "local example, use '.'. If you use a subdirectory such as 'task1/', the command runs inside "
            "that subdirectory."
        )
        doc_forward_files = (
            "Files to upload for this task before execution. Paths are resolved relative to this "
            "task's task_work_path. Put per-task inputs here; files shared by all tasks belong in "
            "submission.forward_common_files."
        )
        doc_backward_files = (
            "Files to download for this task after execution. Paths are collected from this task's "
            "task_work_path on the execution side and synchronized back to the same relative task "
            "directory under the local staging root (typically machine.local_root/work_base)."
        )
        doc_outlog = (
            "Filename used to redirect stdout inside task_work_path while the task runs. If this file is "
            "downloaded or synchronized back, it typically appears under the same relative task directory on the local side. "
            "Set this to null to inherit stdout without creating a task output log."
        )
        doc_errlog = (
            "Filename used to redirect stderr inside task_work_path while the task runs. If this file is "
            "downloaded or synchronized back, it typically appears under the same relative task directory on the local side. "
            "Set this to null to inherit stderr without creating a task error log; automatic last-error excerpts are then disabled."
        )
        doc_task_name = (
            "Optional scheduler-visible name. DPDispatcher uses it only when the "
            "generated scheduler job contains exactly this one task. Grouped jobs "
            "retain the existing hash-based scheduler fallback because one task name "
            "cannot unambiguously represent several tasks. Names are normalized and "
            "truncated to each scheduler's portable limit."
        )

        task_args = [
            Argument("command", str, optional=False, doc=doc_command),
            Argument("task_work_path", str, optional=False, doc=doc_task_work_path),
            Argument(
                "forward_files",
                list[str],
                optional=True,
                doc=doc_forward_files,
                default=[],
            ),
            Argument(
                "backward_files",
                list[str],
                optional=True,
                doc=doc_backward_files,
                default=[],
            ),
            Argument(
                "outlog",
                [type(None), str],
                optional=True,
                doc=doc_outlog,
                default="log",
            ),
            Argument(
                "errlog",
                [type(None), str],
                optional=True,
                doc=doc_errlog,
                default="err",
            ),
            Argument(
                "task_name",
                [type(None), str],
                optional=True,
                doc=doc_task_name,
                default=None,
            ),
        ]
        task_format = Argument("task", dict, task_args)
        return task_format

    def get_task_state(self, context: "BaseContext") -> None:
        """Get the task state by checking the tag file.

        Parameters
        ----------
        context : Context
            the context of the task
        """
        if self.task_state in (JobStatus.finished, JobStatus.unsubmitted):
            # finished task should always be finished
            # unsubmitted task do not need to check tag
            return
        # check tag
        if self.has_finished_tag(context):
            self.task_state = JobStatus.finished

    def has_finished_tag(self, context: "BaseContext") -> bool:
        """Return whether the remote completion tag for this task exists."""
        task_tag_finished = (
            pathlib.PurePath(self.task_work_path)
            / (self.task_hash + "_task_tag_finished")
        ).as_posix()
        return context.check_file_exists(task_tag_finished)


class Job:
    """Represent one scheduler job generated from a group of tasks.

    Applications normally let :class:`Submission` create jobs. A job owns a
    resource request, generates scheduler scripts through its machine, and
    stores scheduler ID, state, and retry information for recovery.

    Parameters
    ----------
    job_task_list : list of Task
        Tasks grouped into this scheduler job.
    resources : Resources
        Resource request copied from the parent submission.
    machine : Machine, optional
        Backend used to generate, submit, and monitor the job.
    """

    def __init__(
        self,
        job_task_list: list["Task"],
        *,
        resources: "Resources",
        machine: Optional["Machine"] = None,
    ) -> None:
        """Initialize a grouped scheduler job and its runtime state."""
        self.job_task_list = job_task_list
        # self.job_work_base = job_work_base
        self.resources = resources
        self.machine = machine
        self.job_state: JobStatus | None = None  # JobStatus.unsubmitted
        self.job_id: str | int = ""
        # Cloud backends attach these identifiers while staging and submitting.
        self.upload_path = ""
        self.jgid: str | int | None = None
        self.fail_count = 0
        self.failure_reason: str | None = None
        self.job_uuid = uuid.uuid4()

        self.job_hash = self.get_hash()
        # Keep generated scheduler artifacts in the work root for compatibility with
        # existing contexts, but hide them from normal directory listings.
        self.script_file_name = f".{self.job_hash}.sub"

    def __repr__(self) -> str:
        return str(self.serialize())

    def __eq__(self, other: object) -> bool:
        """Compare jobs while ignoring mutable scheduler runtime information.

        Job state, scheduler IDs, and failure counts do not affect equality.
        """
        return json.dumps(self.serialize(if_static=True)) == json.dumps(
            other.serialize(if_static=True)  # type: ignore[attr-defined]
        )

    @classmethod
    def deserialize(
        cls, job_dict: dict[str, Any], machine: Optional["Machine"] = None
    ) -> "Job":  # noqa: ANN401
        """Reconstruct a job and its tasks from serialized state.

        Parameters
        ----------
        job_dict : dict
            Single-entry mapping from job hash to configuration and runtime data.
        machine : Machine, optional
            Machine to bind to the reconstructed job.

        Returns
        -------
        Job
            Reconstructed job.
        """
        if len(job_dict.keys()) != 1:
            raise RuntimeError(
                f"json file may be broken, len(job_dict.keys()) must be 1. {job_dict}"
            )
        job_hash = list(job_dict.keys())[0]

        job_task_list = [
            Task.deserialize(task_dict)
            for task_dict in job_dict[job_hash]["job_task_list"]
        ]
        job = Job(
            job_task_list=job_task_list,
            resources=Resources.deserialize(
                resources_dict=job_dict[job_hash]["resources"]
            ),
            machine=machine,
        )

        # job.job_runtime_info=job_dict[job_hash]['job_runtime_info']
        job.job_state = job_dict[job_hash]["job_state"]
        job.job_id = job_dict[job_hash]["job_id"]
        job.fail_count = job_dict[job_hash]["fail_count"]
        job.failure_reason = job_dict[job_hash].get("failure_reason")
        # job.job_uuid = job_dict[job_hash]['job_uuid']
        task_states = job_dict[job_hash].get("task_states")
        for index, task in enumerate(job.job_task_list):
            task.task_state = (
                task_states[index]
                if task_states is not None and index < len(task_states)
                else job.job_state or JobStatus.unsubmitted
            )
        return job

    def get_job_state(self) -> None:
        """Query the backend and update this job and its unfinished tasks.

        Notes
        -----
        This method does not submit or retry the job.
        """
        dlog.debug(
            f"query database; self.job_hash:{self.job_hash}; self.job_id:{self.job_id}"
        )
        assert self.machine is not None
        job_state = self.machine.check_status(self)
        self.job_state = job_state
        # update general task_state, which should be faster than checking tags
        for task in self.job_task_list:
            # only update if the task is not finished
            if task.task_state != JobStatus.finished:
                task.task_state = job_state

    def handle_unexpected_job_state(self, *, continue_on_failure: bool = False) -> None:
        """Submit or retry a job according to its current state.

        Retry exhaustion remains fail-fast by default. Callers that need to
        monitor sibling jobs must explicitly opt in with ``continue_on_failure``.
        """
        job_state = self.job_state

        if job_state == JobStatus.failed:
            return

        if job_state == JobStatus.unknown:
            raise RuntimeError(f"job_state for job {self} is unknown")

        if job_state == JobStatus.terminated:
            self.fail_count += 1
            dlog.info(
                f"job {self.job_hash} {self.job_id} terminated; "
                f"fail_cout is {self.fail_count}; resubmitting job"
            )
            retry_count = 3
            assert self.machine is not None
            if hasattr(self.machine, "retry_count") and self.machine.retry_count >= 0:
                retry_count = self.machine.retry_count + 1
            if (self.fail_count) > 0 and (self.fail_count % retry_count == 0):
                last_error_message = self.get_last_error_message()
                err_msg = (
                    f"job {self.job_hash} {self.job_id} failed {self.fail_count} times."
                )
                if last_error_message is not None:
                    err_msg += f"\nPossible remote error message: {last_error_message}"
                if continue_on_failure:
                    self._mark_failed(err_msg)
                    return
                raise RuntimeError(err_msg)
            # Re-upload forward files before retry to handle cases where remote
            # workdir was cleaned or files were removed between attempts.
            # A failed restoration must stop the retry: submitting without the
            # required inputs only hides the actionable staging error and causes
            # another predictable job failure.
            self._ensure_forward_files_on_retry()
            self.submit_job()
            if self.job_state != JobStatus.unsubmitted:
                dlog.info(
                    f"job {self.job_hash} re-submit after terminated; new job_id is {self.job_id}"
                )
                time.sleep(0.2)
                self.get_job_state()
                dlog.info(
                    f"job {self.job_hash} job_id:{self.job_id} after re-submitting; the state now is {repr(self.job_state)}"
                )
                self.handle_unexpected_job_state(
                    continue_on_failure=continue_on_failure
                )
            if self.resources.wait_time != 0:
                time.sleep(self.resources.wait_time)

        if job_state == JobStatus.unsubmitted:
            dlog.debug(f"job {self.job_hash} unsubmitted; submit it")
            # if self.fail_count > 3:
            #     raise RuntimeError("job:job {job} failed 3 times".format(job=self))
            self.submit_job()
            if self.job_state != JobStatus.unsubmitted:
                dlog.info(f"job {self.job_hash} was submitted; job_id is {self.job_id}")
            if self.resources.wait_time != 0:
                time.sleep(self.resources.wait_time)
            # self.get_job_state()

    def get_hash(self) -> str:
        """Return the stable hash used as this job's identifier."""
        return str(list(self.serialize(if_static=True).keys())[0])

    def get_scheduler_name(
        self, max_length: int, *, require_alpha_prefix: bool = False
    ) -> str | None:
        """Return a portable task-derived name for a one-task scheduler job.

        A grouped job deliberately returns ``None`` so each backend keeps its
        established hash-based/default name instead of presenting one task as if it
        represented the whole group. User-provided names are reduced to a conservative
        ASCII subset accepted by Slurm, PBS, LSF, and SGE. Truncation retains a hash
        suffix so long names that share a prefix remain distinguishable.
        """
        if len(self.job_task_list) != 1:
            return None
        raw_name = self.job_task_list[0].task_name
        if raw_name is None:
            return None

        normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw_name).strip("._-")
        if not normalized:
            normalized = f"dp-{self.job_hash[:8]}"
        if require_alpha_prefix and not normalized[0].isalpha():
            normalized = f"j-{normalized}"
        if len(normalized) <= max_length:
            return normalized

        suffix = f"-{sha1(raw_name.encode('utf-8')).hexdigest()[:8]}"
        prefix = normalized[: max_length - len(suffix)].rstrip("._-")
        if require_alpha_prefix and (not prefix or not prefix[0].isalpha()):
            prefix = "j"
        return f"{prefix}{suffix}"

    def serialize(self, if_static: bool = False) -> dict[str, Any]:  # noqa: ANN401
        """Return a hash-keyed, JSON-compatible representation of the job.

        Parameters
        ----------
        if_static : bool, default=False
            Exclude job ID, state, and failure count when true.

        Returns
        -------
        dict
            Mapping from the deterministic job hash to job data.
        """
        job_content_dict = {}
        # for task in self.job_task_list:
        job_content_dict["job_task_list"] = [
            task.serialize() for task in self.job_task_list
        ]
        job_content_dict["resources"] = self.resources.serialize()
        # job_content_dict['job_work_base'] = self.job_work_base
        job_hash = sha1(json.dumps(job_content_dict).encode("utf-8")).hexdigest()
        if not if_static:
            job_content_dict["job_state"] = self.job_state
            job_content_dict["job_id"] = self.job_id
            job_content_dict["fail_count"] = self.fail_count
            job_content_dict["failure_reason"] = self.failure_reason
            job_content_dict["task_states"] = [
                task.task_state for task in self.job_task_list
            ]
            # job_content_dict['job_uuid'] = self.job_uuid
        return {job_hash: job_content_dict}

    def register_job_id(self, job_id: str | int) -> None:
        """Store the identifier returned by the scheduler."""
        self.job_id = job_id

    def submit_job(self) -> None:
        """Submit the job through its machine and update its local state."""
        assert self.machine is not None
        job_id = self.machine.do_submit(self)
        self.register_job_id(job_id)
        if job_id:
            self.job_state = JobStatus.waiting
        else:
            self.job_state = JobStatus.unsubmitted

    def job_to_json(self) -> None:
        """Write current job state to the execution root as JSON."""
        write_str = json.dumps(self.serialize(), indent=2, default=str)
        assert self.machine is not None
        self.machine.context.write_file(
            self.job_hash + "_job.json", write_str=write_str
        )

    def get_last_error_message(self) -> str | None:
        """Get last error message when the job is terminated."""
        assert self.machine is not None
        last_error_message = self.machine.get_job_error(self)
        if last_error_message is not None:
            # red color
            last_error_message = "\033[31m" + last_error_message + "\033[0m"
            return last_error_message

    def _mark_failed(self, reason: str) -> None:
        """Persist retry exhaustion while preserving per-task completion tags."""
        assert self.machine is not None
        for task in self.job_task_list:
            task.get_task_state(self.machine.context)
            if task.task_state != JobStatus.finished:
                task.task_state = JobStatus.failed
        self.failure_reason = reason
        self.job_state = JobStatus.failed
        dlog.error(reason)

    def _ensure_forward_files_on_retry(self) -> None:
        """Re-upload forward files before retry by delegating to context.upload().

        When a job is retried after termination, forward files may have been
        removed from the remote workdir. This method re-uploads them using the
        same upload mechanism as the initial submission, which correctly handles
        all context types (Local, SSH, HDFS, etc.), glob patterns, binary files,
        and directory creation.

        Uses context.submission (set during bind_machine) to access both per-task
        forward_files and forward_common_files.
        """
        if self.machine is None:
            return
        context = self.machine.context
        submission = getattr(context, "submission", None)
        if submission is None:
            return
        # Build a lightweight object with only this job's tasks for upload.
        # context.upload() expects .belonging_tasks and .forward_common_files.

        class _RetryPayload:
            belonging_tasks: list["Task"]
            belonging_jobs: list["Job"]
            forward_common_files: list[str]
            preserve_existing_forward_common_files: bool

        payload = _RetryPayload()
        payload.belonging_tasks = self.job_task_list
        payload.belonging_jobs = [self]
        payload.forward_common_files = submission.forward_common_files
        payload.preserve_existing_forward_common_files = True
        # Upload contexts intentionally consume this structural subset of a
        # Submission; the cast records that duck-typed boundary for the checker.
        context.upload(cast(Submission, payload))


class Resources:
    """Describe the resources and execution strategy for generated jobs.

    Parameters
    ----------
    number_node : int
        Number of nodes requested for each generated job.
    cpu_per_node : int
        Number of CPUs requested on each node.
    gpu_per_node : int
        Number of GPUs requested on each node.
    queue_name : str
        Queue or partition name passed to the batch backend.
    group_size : int
        Maximum number of tasks grouped into one scheduler job. Zero groups all
        tasks into one job.
    custom_flags : list of str, optional
        Extra scheduler directives inserted into the generated script header.
    strategy : dict, optional
        Script-generation strategy. Recognized keys include
        ``if_cuda_multi_devices``, ``ratio_unfinished``, and
        ``customized_script_header_template_file``.
    para_deg : int, default=1
        Number of task commands run concurrently inside one generated job.
    module_unload_list : list of str, optional
        Environment modules to unload before task execution.
    module_purge : bool, default=False
        Whether to purge loaded environment modules first.
    module_list : list of str, optional
        Environment modules to load before task execution.
    source_list : list of str, optional
        Shell files to source before task execution.
    envs : dict, optional
        Environment variables to export before task execution.
    prepend_script : list of str, optional
        Shell lines inserted before task commands.
    append_script : list of str, optional
        Shell lines inserted after all task commands finish.
    wait_time : int, default=0
        Delay in seconds after each job submission or resubmission.
    **kwargs
        Backend-specific resource options, stored in ``Resources.kwargs``.
    """

    def __init__(
        self,
        number_node: int,
        cpu_per_node: int,
        gpu_per_node: int,
        queue_name: str,
        group_size: int,
        *,
        custom_flags: Sequence[str] | None = None,
        strategy: dict[str, Any] | None = None,
        para_deg: int = 1,
        module_unload_list: Sequence[str] | None = None,
        module_purge: bool = False,
        module_list: Sequence[str] | None = None,
        source_list: Sequence[str] | None = None,
        envs: dict[str, Any] | None = None,
        prepend_script: Sequence[str] | None = None,
        append_script: Sequence[str] | None = None,
        wait_time: int = 0,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        self.number_node = number_node
        self.cpu_per_node = cpu_per_node
        self.gpu_per_node = gpu_per_node
        self.queue_name = queue_name
        self.group_size = group_size

        # self.extra_specification = extra_specification
        # Resource configuration is JSON-like, so deep copies also isolate
        # nested environment and backend options from later caller mutation.
        self.custom_flags = list(custom_flags) if custom_flags is not None else []
        self.strategy = copy.deepcopy(strategy) if strategy is not None else {}
        self.para_deg = para_deg
        self.module_purge = module_purge
        self.module_unload_list = (
            list(module_unload_list) if module_unload_list is not None else []
        )
        self.module_list = list(module_list) if module_list is not None else []
        self.source_list = list(source_list) if source_list is not None else []
        self.envs = copy.deepcopy(envs) if envs is not None else {}
        self.prepend_script = list(prepend_script) if prepend_script is not None else []
        self.append_script = list(append_script) if append_script is not None else []
        self.wait_time = wait_time
        # self.if_cuda_multi_devices = if_cuda_multi_devices

        self.kwargs = copy.deepcopy(kwargs.get("kwargs", kwargs))

        self.gpu_in_use = 0
        self.task_in_para = 0
        # self. = 0
        # if self.gpu_per_node > 1:
        # self.in_para_task_num = 0

        for kk, value in default_strategy.items():
            self.strategy.setdefault(kk, value)
        if self.strategy["if_cuda_multi_devices"] is True:
            if gpu_per_node < 1:
                raise RuntimeError(
                    "gpu_per_node can not be smaller than 1 when if_cuda_multi_devices is True"
                )
            if number_node != 1:
                raise RuntimeError(
                    "number_node must be 1 when if_cuda_multi_devices is True"
                )
        if self.strategy["ratio_unfinished"] >= 1.0:
            raise RuntimeError("ratio_unfinished must be smaller than 1.0")

    def __eq__(self, other: object) -> bool:
        return json.dumps(self.serialize()) == json.dumps(other.serialize())  # type: ignore[attr-defined]

    def serialize(self) -> dict[str, Any]:  # noqa: ANN401
        """Return the resource request as a JSON-compatible dictionary."""
        resources_dict = {}
        resources_dict["number_node"] = self.number_node
        resources_dict["cpu_per_node"] = self.cpu_per_node
        resources_dict["gpu_per_node"] = self.gpu_per_node
        resources_dict["queue_name"] = self.queue_name
        resources_dict["group_size"] = self.group_size

        resources_dict["custom_flags"] = self.custom_flags
        resources_dict["strategy"] = self.strategy
        resources_dict["para_deg"] = self.para_deg
        resources_dict["module_purge"] = self.module_purge
        resources_dict["module_unload_list"] = self.module_unload_list
        resources_dict["module_list"] = self.module_list
        resources_dict["source_list"] = self.source_list
        resources_dict["envs"] = self.envs
        resources_dict["prepend_script"] = self.prepend_script
        resources_dict["append_script"] = self.append_script
        resources_dict["wait_time"] = self.wait_time
        resources_dict["kwargs"] = self.kwargs
        return resources_dict

    @classmethod
    def deserialize(cls, resources_dict: dict[str, Any]) -> "Resources":  # noqa: ANN401
        """Reconstruct a resource request from a serialized dictionary."""
        resources = cls(
            number_node=resources_dict.get("number_node", 1),
            cpu_per_node=resources_dict.get("cpu_per_node", 1),
            gpu_per_node=resources_dict.get("gpu_per_node", 0),
            queue_name=resources_dict.get("queue_name", ""),
            group_size=resources_dict["group_size"],
            custom_flags=resources_dict.get("custom_flags"),
            strategy=resources_dict.get("strategy"),
            para_deg=resources_dict.get("para_deg", 1),
            module_purge=resources_dict.get("module_purge", False),
            module_unload_list=resources_dict.get("module_unload_list"),
            module_list=resources_dict.get("module_list"),
            source_list=resources_dict.get("source_list"),
            envs=resources_dict.get("envs"),
            prepend_script=resources_dict.get("prepend_script"),
            append_script=resources_dict.get("append_script"),
            wait_time=resources_dict.get("wait_time", 0),
            **resources_dict.get("kwargs", {}),
        )
        return resources

    def __getitem__(self, key: str) -> Any:  # noqa: ANN401
        return self.serialize()[key]

    @classmethod
    def load_from_json(cls, json_file: str) -> "Resources":
        """Load and validate a resource request from a JSON file."""
        with open(json_file) as f:
            resources_dict = json.load(f)
        resources = cls.load_from_dict(resources_dict=resources_dict)
        return resources

    @classmethod
    def load_from_yaml(cls, yaml_file: str) -> "Resources":
        """Load and validate a resource request from a YAML file."""
        with open(yaml_file) as f:
            resources_dict = yaml.safe_load(f)
        resources = cls.load_from_dict(resources_dict=resources_dict)
        return resources

    @classmethod
    def load_from_dict(
        cls, resources_dict: dict[str, Any], allow_ref: bool = False
    ) -> "Resources":  # noqa: ANN401
        """Load Resources from a dict.

        Parameters
        ----------
        resources_dict : dict
            Resources configuration dict.
        allow_ref : bool, default=False
            Whether to allow loading external JSON/YAML snippets via ``$ref``.
            Disabled by default for security.
        """
        # check dict
        base = cls.arginfo(detail_kwargs="batch_type" in resources_dict)
        resources_dict = base.normalize_value(
            resources_dict, trim_pattern="_*", allow_ref=allow_ref
        )
        base.check_value(resources_dict, strict=False, allow_ref=allow_ref)

        return cls.deserialize(resources_dict=resources_dict)

    @staticmethod
    def arginfo(detail_kwargs: bool = True) -> Argument:
        """Build the dargs schema for common and backend-specific resources."""
        doc_number_node = "Number of nodes requested for each scheduler job generated by DPDispatcher."
        doc_cpu_per_node = (
            "Number of CPUs requested on each node for each scheduler job."
        )
        doc_gpu_per_node = (
            "Number of GPUs requested on each node for each scheduler job."
        )
        doc_queue_name = (
            "Queue or partition name used by the selected batch system. For local Shell runs this is "
            "usually an empty string; for Slurm it typically maps to a partition."
        )
        doc_group_size = (
            "How many tasks are packed into one scheduler job. For example, 20 tasks with group_size=5 "
            "are typically split into 4 jobs. Use 1 for the simplest one-task workflow. 0 means no "
            "explicit upper limit in the grouping logic."
        )
        doc_custom_flags = (
            "Extra scheduler-header lines inserted into the generated submission script, typically for "
            "backend-specific options that are not covered by the standard fields."
        )
        doc_para_deg = (
            "How many tasks inside one generated job are run in parallel. This is different from group_size: "
            "group_size controls how many tasks are bundled into a job, while para_deg controls concurrency "
            "within that job. Keep para_deg=1 for the safest default."
        )
        doc_source_list = (
            "Static shell script names and optional arguments sourced before task commands run. Each entry is "
            "parsed into shell words and safely quoted; quote a path containing spaces inside the entry. Use "
            "prepend_script instead when shell operators or variable/command expansion is intentional. Empty "
            "entries are ignored for compatibility."
        )
        doc_module_purge = "Whether to run 'module purge' before applying module_unload_list and module_list. Mainly useful on HPC systems."
        doc_module_unload_list = "Modules to unload before loading the requested modules. Mainly relevant on HPC systems with environment modules."
        doc_module_list = "Modules to load before executing tasks. Mainly relevant on HPC systems with environment modules."
        doc_envs = (
            "Environment variables exported before executing tasks. Names must be valid POSIX identifiers and "
            "values are shell-quoted. A list value emits one export per item in order; an empty list emits none."
        )
        doc_prepend_script = (
            "Optional trusted shell lines inserted before task commands in the generated job script. Use this "
            "for intentional variable expansion, command substitution, or source commands that need shell syntax."
        )
        doc_append_script = "Optional shell lines inserted after task commands in the generated job script."
        doc_wait_time = (
            "Delay in seconds inserted after a job is submitted or resubmitted. Usually keep 0 unless the "
            "scheduler/site asks you to throttle submission pace."
        )
        doc_if_cuda_multi_devices = (
            "If a node has multiple NVIDIA GPUs, assign different tasks inside the same job to different GPUs "
            "by setting CUDA_VISIBLE_DEVICES automatically. Usually used together with para_deg > 1 and task-level "
            "resource awareness."
        )
        doc_ratio_unfinished = (
            "Maximum fraction of tasks allowed to remain unfinished when evaluating job completion. Use 0.0 for the "
            "strict default that requires every task to finish."
        )
        doc_customized_script_header_template_file = "Custom template file for the scheduler-header portion of generated submission scripts. Overrides the default template."

        strategy_args = [
            Argument(
                "if_cuda_multi_devices",
                bool,
                optional=True,
                default=False,
                doc=doc_if_cuda_multi_devices,
            ),
            Argument(
                "ratio_unfinished",
                float,
                optional=True,
                default=0.0,
                doc=doc_ratio_unfinished,
            ),
            Argument(
                "customized_script_header_template_file",
                str,
                optional=True,
                doc=doc_customized_script_header_template_file,
            ),
        ]
        doc_strategy = "Strategy options that affect how DPDispatcher generates and evaluates submission scripts."
        strategy_format = Argument(
            "strategy", dict, strategy_args, optional=True, doc=doc_strategy
        )

        resources_args = [
            Argument("number_node", int, optional=True, doc=doc_number_node, default=1),
            Argument(
                "cpu_per_node", int, optional=True, doc=doc_cpu_per_node, default=1
            ),
            Argument(
                "gpu_per_node", int, optional=True, doc=doc_gpu_per_node, default=0
            ),
            Argument("queue_name", str, optional=True, doc=doc_queue_name, default=""),
            Argument("group_size", int, optional=False, doc=doc_group_size),
            Argument("custom_flags", list[str], optional=True, doc=doc_custom_flags),
            # Argument("strategy", dict, optional=True, doc=doc_strategy,default=default_strategy),
            strategy_format,
            Argument("para_deg", int, optional=True, doc=doc_para_deg, default=1),
            Argument(
                "source_list", list[str], optional=True, doc=doc_source_list, default=[]
            ),
            Argument(
                "module_purge", bool, optional=True, doc=doc_module_purge, default=False
            ),
            Argument(
                "module_unload_list",
                list[str],
                optional=True,
                doc=doc_module_unload_list,
                default=[],
            ),
            Argument(
                "module_list", list[str], optional=True, doc=doc_module_list, default=[]
            ),
            Argument("envs", dict, optional=True, doc=doc_envs, default={}),
            Argument(
                "prepend_script",
                list[str],
                optional=True,
                doc=doc_prepend_script,
                default=[],
            ),
            Argument(
                "append_script",
                list[str],
                optional=True,
                doc=doc_append_script,
                default=[],
            ),
            Argument(
                "wait_time", [int, float], optional=True, doc=doc_wait_time, default=0
            ),
        ]

        if detail_kwargs:
            batch_variant = Variant(
                "batch_type",
                [
                    machine.resources_arginfo()
                    for machine in set(Machine.subclasses_dict.values())
                ],
                optional=False,
                doc="The batch job system type loaded from machine/batch_type.",
            )

            resources_format = Argument(
                "resources", dict, resources_args, [batch_variant]
            )
        else:
            resources_args.append(
                Argument(
                    "kwargs", dict, optional=True, doc="Vary by different machines."
                )
            )
            resources_args.append(
                Argument(
                    "batch_type",
                    str,
                    optional=True,
                    doc="Allow this key when strict checking.",
                )
            )
            resources_format = Argument("resources", dict, resources_args)
        return resources_format


# %%
