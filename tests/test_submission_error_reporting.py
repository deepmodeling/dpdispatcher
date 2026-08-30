import unittest
from unittest.mock import MagicMock, patch

from dpdispatcher.submission import Submission


class TestSubmissionErrorReporting(unittest.TestCase):
    """Retry exhaustion details remain visible in the outer public exception."""

    @patch("dpdispatcher.submission.record")
    def test_outer_error_includes_underlying_job_diagnostic(
        self, mock_record: MagicMock
    ) -> None:
        submission = Submission.__new__(Submission)
        submission.machine = MagicMock()
        submission.machine.context.remote_root = "/remote/submission"
        submission.submission_hash = "submission-hash"
        submission.submission_to_json = MagicMock()
        mock_record.write.return_value = "/local/submission-hash.json"

        job = MagicMock()
        job.handle_unexpected_job_state.side_effect = RuntimeError(
            "job abc 123 failed 3 times.\n"
            "Possible remote error message: CUDA out of memory"
        )
        submission.belonging_jobs = [job]

        with self.assertRaises(RuntimeError) as raised:
            submission.handle_unexpected_submission_state()

        message = str(raised.exception)
        self.assertIn("Underlying job error: job abc 123 failed 3 times", message)
        self.assertIn("CUDA out of memory", message)
        self.assertIn("dpdisp submission submission-hash", message)
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)


if __name__ == "__main__":
    unittest.main()
