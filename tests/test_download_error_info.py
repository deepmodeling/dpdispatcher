"""Test PR4: automatic download of error diagnostic files for failed jobs."""

import os
import sys
import tempfile
import unittest
from typing import List, Optional
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher.submission import Submission
from dpdispatcher.utils.job_status import JobStatus


class TestDownloadErrorInfo(unittest.TestCase):
    """Unit tests for Submission.try_download_error_info()."""

    def _make_submission(
        self,
        job_states: List[JobStatus],
        err_file_exists: bool = True,
        err_content: str = "LAMMPS error: lost atoms",
    ) -> Submission:
        """Create a Submission with mocked machine/context and jobs."""
        submission = Submission.__new__(Submission)
        submission.belonging_jobs = []
        submission.machine = MagicMock()

        # Create a real temp dir as local_root
        self._tmpdir = tempfile.mkdtemp()
        submission.machine.context.local_root = self._tmpdir

        def mock_get_job_error(job: object) -> Optional[str]:
            return err_content if err_file_exists else None

        submission.machine.get_job_error = MagicMock(side_effect=mock_get_job_error)

        for i, state in enumerate(job_states):
            job = MagicMock()
            job.job_state = state
            job.job_hash = f"hash_{i:04d}"
            submission.belonging_jobs.append(job)

        return submission

    def tearDown(self) -> None:
        import shutil

        if hasattr(self, "_tmpdir") and os.path.exists(self._tmpdir):
            shutil.rmtree(self._tmpdir)

    def test_downloads_error_for_terminated_job(self) -> None:
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

    def test_no_download_for_finished_job(self) -> None:
        """Finished job → no error file downloaded."""
        sub = self._make_submission([JobStatus.finished])
        sub.try_download_error_info()

        local_err_path = os.path.join(self._tmpdir, "hash_0000_last_err_file")
        self.assertFalse(os.path.exists(local_err_path))

    def test_no_error_file_on_remote(self) -> None:
        """Terminated job but no error file on remote → graceful no-op."""
        sub = self._make_submission(
            [JobStatus.terminated],
            err_file_exists=False,
        )
        # Should not raise
        sub.try_download_error_info()

        local_err_path = os.path.join(self._tmpdir, "hash_0000_last_err_file")
        self.assertFalse(os.path.exists(local_err_path))

    def test_multiple_jobs_mixed_states(self) -> None:
        """Mixed finished/terminated → only download for failed ones."""
        sub = self._make_submission(
            [JobStatus.finished, JobStatus.terminated, JobStatus.finished],
            err_content="segfault",
        )
        sub.try_download_error_info()

        # Only job 1 (terminated) should have error file
        self.assertFalse(
            os.path.exists(os.path.join(self._tmpdir, "hash_0000_last_err_file"))
        )
        self.assertTrue(
            os.path.exists(os.path.join(self._tmpdir, "hash_0001_last_err_file"))
        )
        self.assertFalse(
            os.path.exists(os.path.join(self._tmpdir, "hash_0002_last_err_file"))
        )

    def test_context_exception_does_not_crash(self) -> None:
        """If context raises during error download, it's caught gracefully."""
        sub = self._make_submission([JobStatus.terminated])
        sub.machine.get_job_error = MagicMock(side_effect=OSError("network error"))

        # Should not raise
        sub.try_download_error_info()

    def test_no_machine_is_noop(self) -> None:
        """If machine is None, try_download_error_info is a no-op."""
        submission = Submission.__new__(Submission)
        submission.machine = None
        submission.belonging_jobs = []
        # Should not raise
        submission.try_download_error_info()


class TestDownloadErrorInfoOnExhaustedRetries(unittest.TestCase):
    """Integration test: error files are downloaded even when retries are exhausted.

    When handle_unexpected_submission_state() raises RuntimeError (because a job
    exhausted its retry limit), the try/finally in run_submission() must still
    call try_download_error_info() before propagating the exception.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        import shutil

        if os.path.exists(self._tmpdir):
            shutil.rmtree(self._tmpdir)

    def _make_submission_for_run(
        self, err_content: str = "FATAL: out of memory"
    ) -> Submission:
        """Build a Submission wired to simulate exhausted retries in run_submission."""
        sub = Submission.__new__(Submission)

        # Resources with strategy
        sub.resources = MagicMock()
        sub.resources.strategy = {"ratio_unfinished": 0.0}

        # Machine/context mocks
        sub.machine = MagicMock()
        sub.machine.context.local_root = self._tmpdir
        sub.machine.context.remote_root = "/tmp/fake_remote"
        sub.machine.get_job_error = MagicMock(return_value=err_content)

        # Submission attributes
        sub.submission_hash = "test_hash_exhausted"

        # Create a terminated job
        job = MagicMock()
        job.job_state = JobStatus.terminated
        job.job_hash = "hash_retry_exhausted"
        # Make handle_unexpected_job_state raise to simulate exhausted retries
        job.handle_unexpected_job_state.side_effect = RuntimeError(
            "Job exceeded maximum retries"
        )
        sub.belonging_jobs = [job]

        return sub

    @patch("dpdispatcher.submission.record")
    def test_error_file_downloaded_when_retries_exhausted(
        self, mock_record: MagicMock
    ) -> None:
        """run_submission raises RuntimeError but error file is still written."""
        mock_record.write.return_value = "/tmp/fake_record.json"

        sub = self._make_submission_for_run(err_content="SEGFAULT in lammps")

        # Patch methods that run before the failure point
        sub.generate_jobs = MagicMock()
        sub.try_recover_from_json = MagicMock()
        sub.update_submission_state = MagicMock()
        sub.submission_to_json = MagicMock()
        sub.upload_jobs = MagicMock()
        sub.serialize = MagicMock(return_value={})
        sub.try_download_result = MagicMock()

        # check_all_finished: first call returns True (skips else branch),
        # every later call also returns True so the while loop exits immediately.
        # handle_unexpected_submission_state() after the loop then raises.
        call_count = {"n": 0}

        def fake_check_all_finished() -> bool:
            call_count["n"] += 1
            # 1st call (initial check): True → skip else branch
            if call_count["n"] == 1:
                return True
            # while condition: True → exit loop immediately,
            # then handle_unexpected_submission_state() fires
            return True

        sub.check_all_finished = fake_check_all_finished

        # The RuntimeError should propagate from handle_unexpected_submission_state
        with self.assertRaises(RuntimeError) as ctx:
            sub.run_submission(check_interval=0, clean=False)

        self.assertIn("unexpected submission state", str(ctx.exception).lower())

        # Despite the RuntimeError, the error file must have been downloaded
        local_err_path = os.path.join(
            self._tmpdir, "hash_retry_exhausted_last_err_file"
        )
        self.assertTrue(
            os.path.exists(local_err_path),
            f"Error file not found at {local_err_path}; "
            "try_download_error_info was not called on the failure path.",
        )
        with open(local_err_path) as f:
            content = f.read()
        self.assertIn("SEGFAULT in lammps", content)

    @patch("dpdispatcher.submission.record")
    def test_error_file_downloaded_when_retries_exhausted_in_loop(
        self, mock_record: MagicMock
    ) -> None:
        """Error in handle_unexpected inside the while-loop still downloads error file."""
        mock_record.write.return_value = "/tmp/fake_record.json"

        sub = self._make_submission_for_run(err_content="MPI_ABORT called")

        sub.generate_jobs = MagicMock()
        sub.try_recover_from_json = MagicMock()
        sub.update_submission_state = MagicMock()
        sub.submission_to_json = MagicMock()
        sub.upload_jobs = MagicMock()
        sub.serialize = MagicMock(return_value={})
        sub.try_download_result = MagicMock()

        call_count = {"n": 0}

        def fake_check_all_finished() -> bool:
            call_count["n"] += 1
            # 1st: initial check → True (skip else branch)
            if call_count["n"] == 1:
                return True
            # 2nd: while condition → False (enter loop)
            if call_count["n"] == 2:
                return False
            # Should not reach here since handle_unexpected raises in the loop
            return True

        sub.check_all_finished = fake_check_all_finished

        with self.assertRaises(RuntimeError):
            sub.run_submission(check_interval=0, clean=False)

        # Error file must still be present
        local_err_path = os.path.join(
            self._tmpdir, "hash_retry_exhausted_last_err_file"
        )
        self.assertTrue(
            os.path.exists(local_err_path),
            "try_download_error_info was not called when handle_unexpected "
            "raised inside the while-loop.",
        )
        with open(local_err_path) as f:
            self.assertIn("MPI_ABORT called", f.read())

    def test_recovered_terminated_job_downloads_error_before_reraise(self) -> None:
        """The first failure-handling call is inside the diagnostic guard."""
        sub = self._make_submission_for_run(err_content="recovered job stderr")

        sub.generate_jobs = MagicMock()
        sub.try_recover_from_json = MagicMock()
        sub.update_submission_state = MagicMock()
        sub.submission_to_json = MagicMock()
        sub.upload_jobs = MagicMock()
        sub.serialize = MagicMock(return_value={})
        sub.try_download_result = MagicMock()
        sub.check_all_finished = MagicMock(return_value=False)

        with self.assertRaises(RuntimeError):
            sub.run_submission(check_interval=0, clean=False)

        sub.try_recover_from_json.assert_called_once()
        sub.upload_jobs.assert_called_once()
        sub.try_download_result.assert_not_called()
        local_err_path = os.path.join(
            self._tmpdir, "hash_retry_exhausted_last_err_file"
        )
        self.assertTrue(
            os.path.exists(local_err_path),
            "Recovered-job diagnostics were not downloaded before re-raising.",
        )
        with open(local_err_path) as f:
            self.assertIn("recovered job stderr", f.read())


if __name__ == "__main__":
    unittest.main()
