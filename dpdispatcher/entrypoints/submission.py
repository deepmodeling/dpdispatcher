from pathlib import Path
from typing import TYPE_CHECKING, List

from dpdispatcher.dlog import dlog
from dpdispatcher.submission import Submission
from dpdispatcher.utils.job_status import JobStatus
from dpdispatcher.utils.record import record

if TYPE_CHECKING:
    from dpdispatcher.submission import Task


def _configured_log_files(task: "Task") -> List[str]:
    """Return only task log filenames that are explicitly configured."""
    return [log_file for log_file in (task.outlog, task.errlog) if log_file is not None]


def handle_submission(
    *,
    submission_hash: str,
    download_terminated_log: bool = False,
    download_finished_task: bool = False,
    clean: bool = False,
    reset_fail_count: bool = False,
):
    """Handle terminated submission.

    Parameters
    ----------
    submission_hash : str
        Submission hash to download.
    download_terminated_log : bool, optional
        Download log files of terminated tasks.
    download_finished_task : bool, optional
        Download finished tasks.
    clean : bool, optional
        Clean submission.
    reset_fail_count : bool, optional
        Reset fail count of all jobs to zero.

    Raises
    ------
    ValueError
        At least one action should be specified.
    """
    if (
        int(download_terminated_log)
        + int(download_finished_task)
        + int(clean)
        + int(reset_fail_count)
        == 0
    ):
        raise ValueError("At least one action should be specified.")

    submission_file = record.get_submission(submission_hash)
    submission = Submission.submission_from_json(str(submission_file))
    submission.belonging_tasks = [
        task for job in submission.belonging_jobs for task in job.job_task_list
    ]
    # TODO: for unclear reason, the submission_hash may be changed
    submission.submission_hash = submission_hash
    submission.machine.context.bind_submission(submission)
    if reset_fail_count:
        for job in submission.belonging_jobs:
            job.fail_count = 0
        # save to remote and local
        submission.submission_to_json()
        record.write(submission)
    if int(download_terminated_log) + int(download_finished_task) + int(clean) == 0:
        # if only reset_fail_count, no need to update submission state (expensive)
        return
    submission.update_submission_state()
    submission.submission_to_json()
    record.write(submission)

    terminated_tasks = []
    finished_tasks = []
    for task in submission.belonging_tasks:
        task.get_task_state(submission.machine.context)
        if task.task_state == JobStatus.terminated:
            terminated_tasks.append(task)
        elif task.task_state == JobStatus.finished:
            finished_tasks.append(task)
    submission.belonging_tasks = []

    if download_terminated_log:
        for task in terminated_tasks:
            task.backward_files = _configured_log_files(task)
        submission.belonging_tasks += terminated_tasks
    if download_finished_task:
        submission.belonging_tasks += finished_tasks

    submission.download_jobs()

    if download_terminated_log:
        terminated_log_files = []
        for task in terminated_tasks:
            assert submission.local_root is not None
            for log_file in _configured_log_files(task):
                terminated_log_files.append(
                    Path(submission.local_root) / task.task_work_path / log_file
                )

        if terminated_log_files:
            dlog.info(
                "Terminated logs are downloaded into:\n  "
                + "\n  ".join([str(f) for f in terminated_log_files])
            )
        else:
            dlog.info("No terminated task log files are configured for download.")

    if clean:
        submission.clean_jobs()
