import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from dpdispatcher import Job, Resources, Submission, Task
from dpdispatcher.utils.job_status import JobStatus


class TestTerminalFailedJobs(unittest.TestCase):
    def _job(self, *, state: JobStatus, command: str = "false") -> Job:
        task = Task(command, ".", backward_files=["result"])
        job = Job(job_task_list=[task], resources=Resources(1, 1, 0, "", 1))
        job.job_state = state
        task.task_state = state
        job.machine = MagicMock()
        job.machine.retry_count = 0
        job.machine.get_job_error.return_value = "application failed"
        job.machine.context.check_file_exists.return_value = False
        return job

    def test_retry_exhaustion_becomes_durable_terminal_state(self) -> None:
        job = self._job(state=JobStatus.terminated)

        job.handle_unexpected_job_state()

        self.assertEqual(job.job_state, JobStatus.failed)
        self.assertEqual(job.job_task_list[0].task_state, JobStatus.failed)
        self.assertIn("application failed", job.failure_reason or "")
        job.machine.do_submit.assert_not_called()

        restored = Job.deserialize(job.serialize())
        self.assertEqual(restored.job_state, JobStatus.failed)
        self.assertEqual(restored.job_task_list[0].task_state, JobStatus.failed)
        self.assertEqual(restored.failure_reason, job.failure_reason)

    def test_download_filters_failed_outputs_and_restores_submission(self) -> None:
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
                self.assertEqual(selected.belonging_jobs, [job])
                self.assertEqual(selected.belonging_tasks, [finished])
                for task in selected.belonging_jobs[0].job_task_list:
                    path = Path(local_root) / task.task_work_path / "result.txt"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(task.task_work_path)

            context.download.side_effect = download_archive
            submission.machine = MagicMock(context=context)
            submission.download_jobs()

            self.assertTrue((Path(local_root) / "finished" / "result.txt").is_file())
            self.assertFalse((Path(local_root) / "failed" / "result.txt").exists())

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
            submission.run_submission(clean=False, check_interval=0)

        self.assertEqual(failed.job_state, JobStatus.failed)
        self.assertEqual(running.job_state, JobStatus.finished)
        submission.try_download_result.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
