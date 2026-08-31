import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from dpdispatcher import Job, Resources, Submission, Task
from dpdispatcher.entrypoints.submission import handle_submission
from dpdispatcher.utils.job_status import JobStatus


class TestTerminalFailedJobs(unittest.TestCase):
    def _job(self, *, state: JobStatus, command: str = "false") -> Job:
        """Create a minimal job whose state can be controlled by a test."""
        task = Task(command, ".", backward_files=["result"])
        job = Job(job_task_list=[task], resources=Resources(1, 1, 0, "", 1))
        job.job_state = state
        task.task_state = state
        job.machine = MagicMock()
        job.machine.retry_count = 0
        job.machine.get_job_error.return_value = "application failed"
        job.machine.context.check_file_exists.return_value = False
        return job

    def test_retry_exhaustion_remains_fail_fast_by_default(self) -> None:
        """Retry exhaustion keeps the historical immediate error behavior."""
        job = self._job(state=JobStatus.terminated)

        with self.assertRaisesRegex(RuntimeError, "failed 1 times"):
            job.handle_unexpected_job_state()

        self.assertEqual(job.job_state, JobStatus.terminated)
        self.assertEqual(job.job_task_list[0].task_state, JobStatus.terminated)
        self.assertIsNone(job.failure_reason)
        job.machine.do_submit.assert_not_called()

    def test_terminal_failed_state_is_fail_fast_by_default(self) -> None:
        """A restored failed job cannot leave the polling loop pending."""
        job = self._job(state=JobStatus.failed)

        with self.assertRaisesRegex(RuntimeError, "is in failed state"):
            job.handle_unexpected_job_state()

        job.machine.do_submit.assert_not_called()

    def test_retry_exhaustion_becomes_durable_terminal_state_when_opted_in(
        self,
    ) -> None:
        """Persist a retry-exhausted job as failed without resubmitting it."""
        job = self._job(state=JobStatus.terminated)

        job.handle_unexpected_job_state(continue_on_failure=True)

        self.assertEqual(job.job_state, JobStatus.failed)
        self.assertEqual(job.job_task_list[0].task_state, JobStatus.failed)
        self.assertIn("application failed", job.failure_reason or "")
        job.machine.do_submit.assert_not_called()

        restored = Job.deserialize(job.serialize())
        self.assertEqual(restored.job_state, JobStatus.failed)
        self.assertEqual(restored.job_task_list[0].task_state, JobStatus.failed)
        self.assertEqual(restored.failure_reason, job.failure_reason)

    def test_download_filters_failed_outputs_and_restores_submission(self) -> None:
        """Pass only successful jobs to ordinary result downloads."""
        finished = self._job(state=JobStatus.finished, command="true")
        failed = self._job(state=JobStatus.failed)
        submission = Submission.__new__(Submission)
        submission.machine = MagicMock()
        submission.belonging_jobs = [finished, failed]
        submission.belonging_tasks = [
            finished.job_task_list[0],
            failed.job_task_list[0],
        ]

        def inspect_selection(selected: Submission) -> None:
            """Assert the temporary success-only submission view."""
            self.assertEqual(selected.belonging_jobs, [finished])
            self.assertEqual(selected.belonging_tasks, [finished.job_task_list[0]])

        submission.machine.context.download.side_effect = inspect_selection
        submission.download_jobs()

        self.assertEqual(submission.belonging_jobs, [finished, failed])
        self.assertEqual(
            submission.belonging_tasks,
            [finished.job_task_list[0], failed.job_task_list[0]],
        )

    def test_download_include_failed_bypasses_success_filter(self) -> None:
        """Explicit terminated-log downloads retain failed task selection."""
        finished = self._job(state=JobStatus.finished, command="true")
        failed = self._job(state=JobStatus.failed)
        submission = Submission.__new__(Submission)
        submission.machine = MagicMock()
        submission.belonging_jobs = [finished, failed]
        submission.belonging_tasks = [
            finished.job_task_list[0],
            failed.job_task_list[0],
        ]

        def inspect_selection(selected: Submission, **kwargs: bool) -> None:
            """Assert that explicit diagnostic downloads retain all tasks."""
            self.assertEqual(selected.belonging_jobs, [finished, failed])
            self.assertEqual(
                selected.belonging_tasks,
                [finished.job_task_list[0], failed.job_task_list[0]],
            )
            self.assertEqual(kwargs, {"check_exists": True, "mark_failure": False})

        submission.machine.context.download.side_effect = inspect_selection
        submission.download_jobs(include_failed=True)

    def test_cloud_download_keeps_finished_tasks_in_mixed_job(self) -> None:
        """Cloud archive downloads retain selected outputs from mixed jobs only."""
        finished = Task("true", "finished", backward_files=["result.txt"])
        failed = Task("false", "failed", backward_files=["result.txt"])
        finished.task_state = JobStatus.finished
        failed.task_state = JobStatus.failed
        job = Job(
            job_task_list=[finished, failed],
            resources=Resources(1, 1, 0, "", 1),
        )
        job.job_state = JobStatus.failed
        submission = Submission.__new__(Submission)
        submission.belonging_jobs = [job]
        submission.belonging_tasks = [finished, failed]
        context = MagicMock()
        context.downloads_by_job = True
        with tempfile.TemporaryDirectory() as local_root:
            context.local_root = local_root

            def download_archive(selected: Submission) -> None:
                """Write only the selected finished task's archive output."""
                self.assertEqual(selected.belonging_jobs, [job])
                self.assertEqual(selected.belonging_tasks, [finished])
                downloaded_files = set()
                for task in selected.belonging_jobs[0].job_task_list:
                    path = Path(local_root) / task.task_work_path / "result.txt"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(task.task_work_path)
                    downloaded_files.add(path.relative_to(Path(local_root)).as_posix())
                context.last_downloaded_files = downloaded_files

            context.download.side_effect = download_archive
            submission.machine = MagicMock(context=context)
            submission.download_jobs()

            self.assertTrue((Path(local_root) / "finished" / "result.txt").is_file())
            self.assertFalse((Path(local_root) / "failed" / "result.txt").exists())

    def test_cloud_download_cleanup_only_removes_archive_outputs(self) -> None:
        """Pre-existing failed outputs survive an archive without that file."""
        finished = Task("true", "finished", backward_files=["result.txt"])
        failed = Task("false", "failed", backward_files=["result.txt"])
        finished.task_state = JobStatus.finished
        failed.task_state = JobStatus.failed
        job = Job(
            job_task_list=[finished, failed],
            resources=Resources(1, 1, 0, "", 1),
        )
        job.job_state = JobStatus.failed
        submission = Submission.__new__(Submission)
        submission.belonging_jobs = [job]
        submission.belonging_tasks = [finished, failed]
        context = MagicMock()
        context.downloads_by_job = True
        with tempfile.TemporaryDirectory() as local_root:
            context.local_root = local_root
            stale_output = Path(local_root) / "failed" / "result.txt"
            stale_output.parent.mkdir(parents=True)
            stale_output.write_text("pre-existing")

            def download_archive(_selected: Submission) -> None:
                """Write the finished output and expose its extraction manifest."""
                output = Path(local_root) / "finished" / "result.txt"
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text("downloaded")
                context.last_downloaded_files = {"finished/result.txt"}

            context.download.side_effect = download_archive
            submission.machine = MagicMock(context=context)
            submission.download_jobs()

            self.assertEqual(stale_output.read_text(), "pre-existing")
            self.assertEqual(
                (Path(local_root) / "finished" / "result.txt").read_text(),
                "downloaded",
            )

    def test_cloud_download_preserves_shared_selected_output(self) -> None:
        """A path shared with a successful task is never cleaned as failed."""
        finished = Task("true", ".", backward_files=["result.txt"])
        failed = Task("false", ".", backward_files=["result.txt"])
        finished.task_state = JobStatus.finished
        failed.task_state = JobStatus.failed
        job = Job(
            job_task_list=[finished, failed],
            resources=Resources(1, 1, 0, "", 1),
        )
        job.job_state = JobStatus.failed
        submission = Submission.__new__(Submission)
        submission.belonging_jobs = [job]
        submission.belonging_tasks = [finished, failed]
        context = MagicMock()
        context.downloads_by_job = True
        with tempfile.TemporaryDirectory() as local_root:
            context.local_root = local_root

            def download_archive(_selected: Submission) -> None:
                """Write a shared output and expose it in the extraction manifest."""
                output = Path(local_root) / "result.txt"
                output.write_text("shared")
                context.last_downloaded_files = {"result.txt"}

            context.download.side_effect = download_archive
            submission.machine = MagicMock(context=context)
            submission.download_jobs()

            self.assertEqual((Path(local_root) / "result.txt").read_text(), "shared")

    def test_job_archive_download_skips_mixed_jobs(self) -> None:
        """Archive backends must not request results for failed grouped jobs."""
        finished = self._job(state=JobStatus.finished, command="true")
        failed = self._job(state=JobStatus.failed)
        submission = Submission.__new__(Submission)
        submission.machine = MagicMock()
        submission.machine.context.downloads_by_job = True
        submission.machine.context.supports_partial_job_download = False
        submission.belonging_jobs = [failed]
        submission.belonging_tasks = failed.job_task_list

        submission.download_jobs()
        submission.machine.context.download.assert_not_called()

        def inspect_selection(selected: Submission) -> None:
            """Assert that complete jobs remain eligible for archive download."""
            self.assertEqual(selected.belonging_jobs, [finished])
            self.assertEqual(selected.belonging_tasks, finished.job_task_list)

        submission.machine.context.download.side_effect = inspect_selection
        submission.belonging_jobs = [finished, failed]
        submission.belonging_tasks = [
            finished.job_task_list[0],
            failed.job_task_list[0],
        ]
        submission.download_jobs()
        submission.machine.context.download.assert_called_once()

    def test_ratio_cleanup_preserves_failed_job_and_task(self) -> None:
        """Ratio-based early termination must not erase durable failures."""
        failed = self._job(state=JobStatus.failed)
        running = self._job(state=JobStatus.running, command="true")
        submission = Submission.__new__(Submission)
        submission.machine = MagicMock()
        submission.belonging_jobs = [failed, running]
        submission.belonging_tasks = [
            failed.job_task_list[0],
            running.job_task_list[0],
        ]

        submission.remove_unfinished_tasks()

        self.assertEqual(failed.job_state, JobStatus.failed)
        self.assertEqual(failed.job_task_list, [failed.job_task_list[0]])
        self.assertEqual(submission.belonging_tasks, [failed.job_task_list[0]])
        self.assertEqual(running.job_state, JobStatus.finished)
        submission.machine.kill.assert_called_once_with(running)

    @patch("dpdispatcher.submission.time.sleep")
    def test_submission_waits_for_other_jobs_before_reporting(
        self, _sleep: MagicMock
    ) -> None:
        """Monitor remaining jobs before raising the aggregate failure."""
        failed = self._job(state=JobStatus.terminated)
        running = self._job(state=JobStatus.running, command="true")
        submission = Submission.__new__(Submission)
        submission.resources = Resources(1, 1, 0, "", 1)
        submission.machine = MagicMock()
        submission.machine.context.remote_root = "/remote"
        submission.submission_hash = "submission-hash"
        submission.belonging_jobs = [failed, running]
        submission.belonging_tasks = [
            failed.job_task_list[0],
            running.job_task_list[0],
        ]
        failed.machine = submission.machine
        running.machine = submission.machine
        submission.machine.retry_count = 0
        submission.machine.get_job_error.return_value = "first job failed"
        submission.machine.context.check_file_exists.return_value = False

        update_count = 0

        def update_states() -> None:
            """Finish the second job after the failed job has been observed."""
            nonlocal update_count
            update_count += 1
            if update_count == 3:
                running.job_state = JobStatus.finished
                running.job_task_list[0].task_state = JobStatus.finished

        submission.update_submission_state = MagicMock(side_effect=update_states)
        submission.try_recover_from_json = MagicMock()
        submission.upload_jobs = MagicMock()
        submission.submission_to_json = MagicMock()
        submission.try_download_result = MagicMock(return_value=True)
        submission.try_download_error_info = MagicMock()
        submission.clean_jobs = MagicMock()

        with self.assertRaisesRegex(
            RuntimeError, "all remaining jobs were monitored to completion"
        ):
            submission.run_submission(
                clean=False,
                check_interval=0,
                continue_on_failure=True,
            )

        self.assertEqual(failed.job_state, JobStatus.failed)
        self.assertEqual(running.job_state, JobStatus.finished)
        submission.try_download_result.assert_called_once_with()

    def test_submission_serializes_failure_policy_and_legacy_defaults(self) -> None:
        """Persist opt-in policy while treating older records as fail-fast."""
        submission = Submission(
            work_base=".",
            resources=Resources(1, 1, 0, "", 1),
            continue_on_failure=True,
        )
        serialized = submission.serialize()
        self.assertTrue(serialized["continue_on_failure"])
        self.assertNotIn("continue_on_failure", submission.serialize(if_static=True))

        machine = MagicMock()
        # ``bind_machine`` hashes the submission after assigning the machine;
        # provide a JSON-compatible serialization just like a real backend.
        machine.serialize.return_value = {}

        restored = Submission.deserialize(serialized, machine=machine)
        self.assertTrue(restored.continue_on_failure)

        legacy = dict(serialized)
        legacy.pop("continue_on_failure")
        legacy_restored = Submission.deserialize(legacy, machine=machine)
        self.assertFalse(legacy_restored.continue_on_failure)

    def test_runtime_policy_overrides_persisted_policy(self) -> None:
        """An explicit run argument takes precedence over stored configuration."""
        finished = self._job(state=JobStatus.finished, command="true")
        submission = Submission.__new__(Submission)
        submission.continue_on_failure = True
        submission.resources = Resources(1, 1, 0, "", 1)
        submission.machine = MagicMock()
        submission.machine.context.remote_root = "/remote"
        submission.submission_hash = "submission-hash"
        submission.belonging_jobs = [finished]
        submission.belonging_tasks = finished.job_task_list
        finished.machine = submission.machine
        submission.try_recover_from_json = MagicMock()
        submission.update_submission_state = MagicMock()
        submission.check_all_finished = MagicMock(return_value=True)
        submission.handle_unexpected_submission_state = MagicMock()
        submission.try_download_result = MagicMock(return_value=True)
        submission.try_download_error_info = MagicMock()
        submission.submission_to_json = MagicMock()
        submission.serialize = MagicMock(return_value={})

        submission.run_submission(clean=False, continue_on_failure=False)

        self.assertFalse(submission.continue_on_failure)
        submission.handle_unexpected_submission_state.assert_called_once_with()

    def test_cleanup_ignores_missing_manifests_and_invalid_roots(self) -> None:
        """Avoid deleting files when a cloud context gives no safe manifest."""
        submission = Submission.__new__(Submission)
        context = MagicMock()
        submission.machine = MagicMock(context=context)

        submission._remove_unselected_task_outputs([], [], None)

        context.local_root = None
        submission._remove_unselected_task_outputs([], [], set())

    def test_cleanup_skips_invalid_manifest_entries_and_empty_matches(self) -> None:
        """Ignore empty or non-string manifest entries and empty manifests."""
        submission = Submission.__new__(Submission)
        context = MagicMock()
        submission.machine = MagicMock(context=context)
        with tempfile.TemporaryDirectory() as local_root:
            context.local_root = local_root
            submission._remove_unselected_task_outputs([], [], {"", 42})

    def test_cleanup_rejects_task_paths_outside_local_root(self) -> None:
        """Do not match outputs whose task root escapes the local root."""
        submission = Submission.__new__(Submission)
        with tempfile.TemporaryDirectory() as local_root:
            context = MagicMock()
            context.local_root = local_root
            submission.machine = MagicMock(context=context)
            extracted = Path(local_root) / "downloaded.txt"
            extracted.write_text("downloaded")
            task = Task("true", "../outside", backward_files=["result.txt"])
            job = Job(job_task_list=[task], resources=Resources(1, 1, 0, "", 1))
            submission._remove_unselected_task_outputs(
                [job], [task], {"downloaded.txt"}
            )
            self.assertTrue(extracted.exists())

    def test_cleanup_handles_directory_patterns_and_unselected_jobs(self) -> None:
        """Preserve shared directory outputs and skip jobs without selected tasks."""
        submission = Submission.__new__(Submission)
        with tempfile.TemporaryDirectory() as local_root:
            context = MagicMock()
            context.local_root = local_root
            submission.machine = MagicMock(context=context)
            output = Path(local_root) / "task" / "outdir" / "result.txt"
            output.parent.mkdir(parents=True)
            output.write_text("result")
            selected = Task("true", "task", backward_files=[".", "outdir"])
            failed = Task("false", "task", backward_files=["outdir"])
            job = Job(
                job_task_list=[selected, failed],
                resources=Resources(1, 1, 0, "", 1),
            )
            unrelated = Job(
                job_task_list=[Task("false", "other", backward_files=["other.txt"])],
                resources=Resources(1, 1, 0, "", 1),
            )
            submission._remove_unselected_task_outputs(
                [job, unrelated], [selected], {"task/outdir/result.txt"}
            )
            self.assertTrue(output.exists())

    def test_cleanup_handles_manifest_commonpath_errors(self) -> None:
        """Treat platform-specific path comparisons that fail as outside-root."""
        submission = Submission.__new__(Submission)
        with tempfile.TemporaryDirectory() as local_root:
            context = MagicMock()
            context.local_root = local_root
            submission.machine = MagicMock(context=context)
            extracted = Path(local_root) / "downloaded.txt"
            extracted.write_text("downloaded")
            with patch(
                "dpdispatcher.submission.os.path.commonpath",
                side_effect=ValueError,
            ):
                submission._remove_unselected_task_outputs([], [], {"downloaded.txt"})

    def test_cleanup_ignores_outside_glob_matches(self) -> None:
        """Ignore output globs that resolve outside the local root."""
        submission = Submission.__new__(Submission)
        with (
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as outside,
        ):
            context = MagicMock()
            context.local_root = local_root
            submission.machine = MagicMock(context=context)
            extracted = Path(local_root) / "downloaded.txt"
            extracted.write_text("downloaded")
            task = Task("true", "task", backward_files=["*.txt"])
            job = Job(job_task_list=[task], resources=Resources(1, 1, 0, "", 1))
            with (
                patch("dpdispatcher.submission.glob.glob", return_value=[outside]),
                patch(
                    "dpdispatcher.submission.os.path.commonpath",
                    side_effect=[local_root, local_root, ValueError],
                ),
            ):
                submission._remove_unselected_task_outputs(
                    [job], [task], {"downloaded.txt"}
                )

    def test_handle_submission_resets_failed_jobs_and_tasks(self) -> None:
        """Reset durable failures to terminated state for an explicit retry."""
        failed = self._job(state=JobStatus.failed)
        failed.failure_reason = "failed permanently"
        pending = self._job(state=JobStatus.unsubmitted)
        failed.fail_count = 4
        pending.fail_count = 2
        submission = MagicMock()
        submission.belonging_jobs = [failed, pending]
        submission._require_machine.return_value = MagicMock()

        with (
            patch("dpdispatcher.entrypoints.submission.record.get_submission"),
            patch("dpdispatcher.entrypoints.submission.record.write"),
            patch(
                "dpdispatcher.entrypoints.submission.Submission.submission_from_json",
                return_value=submission,
            ),
        ):
            handle_submission(
                submission_hash="submission-hash",
                reset_fail_count=True,
            )

        self.assertEqual(failed.fail_count, 0)
        self.assertEqual(failed.job_state, JobStatus.terminated)
        self.assertEqual(failed.failure_reason, None)
        self.assertEqual(failed.job_task_list[0].task_state, JobStatus.terminated)
        self.assertEqual(pending.fail_count, 0)
        submission.submission_to_json.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
