import unittest
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
