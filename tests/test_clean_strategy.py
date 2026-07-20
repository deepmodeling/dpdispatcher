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
        """clean=True (legacy) should always return True."""
        sub = self._make_submission_with_jobs([JobStatus.finished, JobStatus.terminated])
        self.assertTrue(sub._should_clean(True))

    def test_clean_false_never_cleans(self):
        """clean=False (legacy) should always return False."""
        sub = self._make_submission_with_jobs([JobStatus.finished])
        self.assertFalse(sub._should_clean(False))

    def test_clean_always_string(self):
        """clean='always' behaves same as True."""
        sub = self._make_submission_with_jobs([JobStatus.terminated])
        self.assertTrue(sub._should_clean("always"))

    def test_clean_never_string(self):
        """clean='never' behaves same as False."""
        sub = self._make_submission_with_jobs([JobStatus.finished])
        self.assertFalse(sub._should_clean("never"))

    def test_on_success_all_finished(self):
        """clean='on_success' with all jobs finished → should clean."""
        sub = self._make_submission_with_jobs([JobStatus.finished, JobStatus.finished])
        self.assertTrue(sub._should_clean("on_success"))

    def test_on_success_some_terminated(self):
        """clean='on_success' with some terminated jobs → should NOT clean."""
        sub = self._make_submission_with_jobs([JobStatus.finished, JobStatus.terminated])
        self.assertFalse(sub._should_clean("on_success"))

    def test_on_success_all_terminated(self):
        """clean='on_success' with all terminated → should NOT clean."""
        sub = self._make_submission_with_jobs([JobStatus.terminated, JobStatus.terminated])
        self.assertFalse(sub._should_clean("on_success"))

    def test_unknown_strategy_warns_and_cleans(self):
        """Unknown clean value should warn and default to True."""
        sub = self._make_submission_with_jobs([JobStatus.finished])
        with self.assertLogs("dpdispatcher", level="WARNING") as cm:
            result = sub._should_clean("invalid_value")
        self.assertTrue(result)
        self.assertTrue(any("Unknown clean strategy" in msg for msg in cm.output))


if __name__ == "__main__":
    unittest.main()
