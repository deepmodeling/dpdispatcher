"""Test PR3: clean strategy (always / never / on_success) in Submission.run_submission()."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher.submission import Submission
from dpdispatcher.utils.job_status import JobStatus


class TestShouldClean(unittest.TestCase):
    """Unit tests for Submission._should_clean() logic."""

    def _make_submission_with_jobs(self, job_states):
        """Create a Submission with mocked jobs in given states."""
        submission = Submission.__new__(Submission)
        submission.belonging_jobs = []
        for state in job_states:
            job = MagicMock()
            job.job_state = state
            submission.belonging_jobs.append(job)
        return submission

    def test_clean_true_always_cleans(self):
        """clean=True (legacy) should always return True regardless of job states."""
        sub = self._make_submission_with_jobs(
            [JobStatus.finished, JobStatus.terminated]
        )
        self.assertTrue(sub._should_clean(True, all_genuinely_finished=False))

    def test_clean_false_never_cleans(self):
        """clean=False (legacy) should always return False."""
        sub = self._make_submission_with_jobs([JobStatus.finished])
        self.assertFalse(sub._should_clean(False, all_genuinely_finished=True))

    def test_clean_always_string(self):
        """clean='always' behaves same as True."""
        sub = self._make_submission_with_jobs([JobStatus.terminated])
        self.assertTrue(sub._should_clean("always", all_genuinely_finished=False))

    def test_clean_never_string(self):
        """clean='never' behaves same as False."""
        sub = self._make_submission_with_jobs([JobStatus.finished])
        self.assertFalse(sub._should_clean("never", all_genuinely_finished=True))

    def test_on_success_genuinely_finished(self):
        """clean='on_success' with all_genuinely_finished=True → should clean."""
        sub = self._make_submission_with_jobs([JobStatus.finished, JobStatus.finished])
        self.assertTrue(sub._should_clean("on_success", all_genuinely_finished=True))

    def test_on_success_not_genuinely_finished(self):
        """clean='on_success' with all_genuinely_finished=False → should NOT clean.

        This covers the ratio_unfinished path where remove_unfinished_tasks()
        kills jobs and mutates their state to 'finished', but the submission
        did not genuinely succeed.
        """
        sub = self._make_submission_with_jobs([JobStatus.finished, JobStatus.finished])
        # Even though all job_states are "finished" (mutated by remove_unfinished_tasks),
        # we explicitly know not all jobs genuinely completed.
        self.assertFalse(sub._should_clean("on_success", all_genuinely_finished=False))

    def test_on_success_default_genuinely_finished(self):
        """Default all_genuinely_finished=True for backward compat (normal exit path)."""
        sub = self._make_submission_with_jobs([JobStatus.finished])
        # When called without the second arg, defaults to True
        self.assertTrue(sub._should_clean("on_success"))

    def test_unknown_strategy_raises(self):
        """Unknown clean value should raise ValueError (fail loudly, not silently clean)."""
        sub = self._make_submission_with_jobs([JobStatus.finished])
        with self.assertRaises(ValueError) as ctx:
            sub._should_clean("invalid_value")
        self.assertIn("Unknown clean strategy", str(ctx.exception))
        self.assertIn("invalid_value", str(ctx.exception))


class TestInvalidStrategyFailsFast(unittest.TestCase):
    """Invalid clean strategy must raise ValueError BEFORE upload_jobs() is called."""

    def test_invalid_strategy_raises_before_upload(self):
        """Passing an invalid clean strategy raises ValueError without calling upload_jobs."""
        sub = Submission.__new__(Submission)
        sub.belonging_jobs = []
        sub.belonging_tasks = []
        sub.submission_hash = "test_hash"
        sub.machine = MagicMock()
        sub.resources = MagicMock()
        sub.resources.strategy = {"ratio_unfinished": 0.0}
        sub.resources.wait_time = 0

        with patch.object(Submission, "upload_jobs") as mock_upload:
            with self.assertRaises(ValueError) as ctx:
                sub.run_submission(clean="on_sucess", check_interval=0)
            self.assertIn("Unknown clean strategy", str(ctx.exception))
            mock_upload.assert_not_called()


class TestDownloadResult(unittest.TestCase):
    """Result-download status must distinguish success from retry exhaustion."""

    def test_successful_download_returns_true(self):
        sub = Submission.__new__(Submission)
        sub.download_jobs = MagicMock()

        self.assertTrue(sub.try_download_result())
        sub.download_jobs.assert_called_once_with()

    def test_retry_exhaustion_returns_false(self):
        sub = Submission.__new__(Submission)
        sub.download_jobs = MagicMock(side_effect=OSError("temporary failure"))

        # Mock the module logger as well as the clock: older Python logging
        # implementations call ``time.time()`` while formatting this expected
        # retry error, which would otherwise consume the test clock values.
        with patch("dpdispatcher.submission.dlog"), patch(
            "dpdispatcher.submission.time.time", side_effect=[0, 86400]
        ), patch("dpdispatcher.submission.time.sleep") as mock_sleep:
            self.assertFalse(sub.try_download_result())

        sub.download_jobs.assert_called_once_with()
        mock_sleep.assert_not_called()

    def test_retry_exhaustion_prevents_on_success_cleanup(self):
        sub = Submission.__new__(Submission)
        sub.belonging_jobs = [MagicMock(job_state=JobStatus.finished)]
        sub.belonging_tasks = []
        sub.submission_hash = "test_hash"
        sub.machine = MagicMock()
        sub.machine.context.remote_root = "/tmp/fake_remote"
        sub.resources = MagicMock()
        sub.resources.strategy = {"ratio_unfinished": 0.0}
        sub.resources.wait_time = 0

        sub.try_recover_from_json = MagicMock()
        sub.update_submission_state = MagicMock()
        sub.check_all_finished = MagicMock(return_value=True)
        sub.handle_unexpected_submission_state = MagicMock()
        sub.try_download_result = MagicMock(return_value=False)
        sub.try_download_error_info = MagicMock()
        sub.submission_to_json = MagicMock()
        sub.clean_jobs = MagicMock()
        sub.serialize = MagicMock(return_value={})

        sub.run_submission(clean="on_success", check_interval=0)

        sub.try_download_result.assert_called_once_with()
        sub.clean_jobs.assert_not_called()


class TestCleanWithRatioUnfinished(unittest.TestCase):
    """Integration test: on_success should NOT clean when ratio_unfinished triggers early exit.

    This tests the full run_submission path where remove_unfinished_tasks()
    is triggered, mutating job states to 'finished'. The clean='on_success'
    strategy must still recognize that some tasks were killed (not genuinely
    successful) and preserve the remote workdir.
    """

    def test_ratio_unfinished_prevents_clean_on_success(self):
        """ratio_unfinished early-exit → clean='on_success' must NOT clean."""
        sub = Submission.__new__(Submission)
        sub.belonging_jobs = []
        sub.belonging_tasks = []
        sub.submission_hash = "test_hash"

        # Mock machine and context
        sub.machine = MagicMock()
        sub.machine.context.remote_root = "/tmp/fake_remote"
        sub.machine.context.local_root = "/tmp/fake_local"

        # Mock resources with ratio_unfinished > 0
        sub.resources = MagicMock()
        sub.resources.strategy = {"ratio_unfinished": 0.5}
        sub.resources.wait_time = 0

        # Create 4 jobs: 2 finished, 2 running (will be killed by ratio_unfinished)
        for i in range(4):
            job = MagicMock()
            job.job_hash = f"job_{i}"
            job.job_id = str(i)
            if i < 2:
                job.job_state = JobStatus.finished
            else:
                job.job_state = JobStatus.running
            sub.belonging_jobs.append(job)

        # Create tasks matching job states
        for i in range(4):
            task = MagicMock()
            if i < 2:
                task.task_state = JobStatus.finished
            else:
                task.task_state = JobStatus.running
            sub.belonging_tasks.append(task)

        # Mock methods called by run_submission
        sub.generate_jobs = MagicMock()
        sub.try_recover_from_json = MagicMock()
        sub.upload_jobs = MagicMock()
        sub.handle_unexpected_submission_state = MagicMock()
        sub.submission_to_json = MagicMock()
        sub.try_download_result = MagicMock()
        sub.clean_jobs = MagicMock()
        sub.serialize = MagicMock(return_value={})

        # Make update_submission_state a no-op (states are manually set)
        sub.update_submission_state = MagicMock()

        # check_all_finished is called multiple times in run_submission:
        #   1. Line 234: if self.check_all_finished() — initial check
        #   2. Line 246: self.check_all_finished() — after upload (return discarded)
        #   3. Line 256: while not self.check_all_finished() — loop condition
        #   Inside loop: ratio_unfinished triggers break
        call_count = [0]

        def mock_check_all_finished():
            call_count[0] += 1
            # Calls 1-3: not all finished (jobs 2,3 still running)
            if call_count[0] <= 3:
                return False
            return True

        sub.check_all_finished = mock_check_all_finished

        # check_ratio_unfinished returns True (triggers early exit)
        sub.check_ratio_unfinished = MagicMock(return_value=True)

        # Run with clean="on_success"
        sub.run_submission(clean="on_success", check_interval=0)

        # clean_jobs should NOT have been called because not all genuinely finished
        sub.clean_jobs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
