"""Test PR4: automatic download of error diagnostic files for failed jobs."""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher.submission import Submission
from dpdispatcher.utils.job_status import JobStatus


class TestDownloadErrorInfo(unittest.TestCase):
    """Unit tests for Submission.try_download_error_info()."""

    def _make_submission(self, job_states, err_file_exists=True, err_content="LAMMPS error: lost atoms"):
        """Create a Submission with mocked machine/context and jobs."""
        submission = Submission.__new__(Submission)
        submission.belonging_jobs = []
        submission.machine = MagicMock()

        # Create a real temp dir as local_root
        self._tmpdir = tempfile.mkdtemp()
        submission.machine.context.local_root = self._tmpdir

        def mock_check_file_exists(fname):
            return err_file_exists

        def mock_read_file(fname):
            return err_content

        submission.machine.context.check_file_exists = mock_check_file_exists
        submission.machine.context.read_file = mock_read_file

        for i, state in enumerate(job_states):
            job = MagicMock()
            job.job_state = state
            job.job_hash = f"hash_{i:04d}"
            submission.belonging_jobs.append(job)

        return submission

    def tearDown(self):
        import shutil
        if hasattr(self, "_tmpdir") and os.path.exists(self._tmpdir):
            shutil.rmtree(self._tmpdir)

    def test_downloads_error_for_terminated_job(self):
        """Terminated job → error file should be downloaded to local root."""
        sub = self._make_submission(
            [JobStatus.terminated],
            err_content="ERROR: Lost atoms (lammps)",
        )
        sub.try_download_error_info()

        local_err_path = os.path.join(self._tmpdir, "hash_0000_last_err_file")
        self.assertTrue(os.path.exists(local_err_path))
        with open(local_err_path) as f:
            content = f.read()
        self.assertIn("Lost atoms", content)

    def test_no_download_for_finished_job(self):
        """Finished job → no error file downloaded."""
        sub = self._make_submission([JobStatus.finished])
        sub.try_download_error_info()

        local_err_path = os.path.join(self._tmpdir, "hash_0000_last_err_file")
        self.assertFalse(os.path.exists(local_err_path))

    def test_no_error_file_on_remote(self):
        """Terminated job but no error file on remote → graceful no-op."""
        sub = self._make_submission(
            [JobStatus.terminated],
            err_file_exists=False,
        )
        # Should not raise
        sub.try_download_error_info()

        local_err_path = os.path.join(self._tmpdir, "hash_0000_last_err_file")
        self.assertFalse(os.path.exists(local_err_path))

    def test_multiple_jobs_mixed_states(self):
        """Mixed finished/terminated → only download for failed ones."""
        sub = self._make_submission(
            [JobStatus.finished, JobStatus.terminated, JobStatus.finished],
            err_content="segfault",
        )
        sub.try_download_error_info()

        # Only job 1 (terminated) should have error file
        self.assertFalse(os.path.exists(
            os.path.join(self._tmpdir, "hash_0000_last_err_file")
        ))
        self.assertTrue(os.path.exists(
            os.path.join(self._tmpdir, "hash_0001_last_err_file")
        ))
        self.assertFalse(os.path.exists(
            os.path.join(self._tmpdir, "hash_0002_last_err_file")
        ))

    def test_context_exception_does_not_crash(self):
        """If context raises during error download, it's caught gracefully."""
        sub = self._make_submission([JobStatus.terminated])
        sub.machine.context.check_file_exists = MagicMock(side_effect=OSError("network error"))

        # Should not raise
        sub.try_download_error_info()

    def test_no_machine_is_noop(self):
        """If machine is None, try_download_error_info is a no-op."""
        submission = Submission.__new__(Submission)
        submission.machine = None
        submission.belonging_jobs = []
        # Should not raise
        submission.try_download_error_info()


if __name__ == "__main__":
    unittest.main()
