"""Test _ensure_forward_files_on_retry for PR #629.

Tests verify that:
1. context.upload() is called on retry with the job's tasks
2. forward_common_files from submission are included
3. Exceptions don't crash the retry loop (handled at call site)
4. No-machine case is a no-op
5. Binary files are uploaded intact (integration test with real LocalContext)
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher.submission import Job


class TestEnsureForwardFilesOnRetry(unittest.TestCase):
    """Unit tests for Job._ensure_forward_files_on_retry()."""

    def _make_job(self, task_list=None, forward_common_files=None):
        """Create a Job with mocked machine/context."""
        job = Job.__new__(Job)
        job.machine = MagicMock()
        job.machine.context.upload = MagicMock()

        mock_submission = MagicMock()
        mock_submission.forward_common_files = forward_common_files or []
        job.machine.context.submission = mock_submission

        if task_list is None:
            task = MagicMock()
            task.task_work_path = "task0"
            task.forward_files = ["input.lammps", "frozen_model.pb"]
            task_list = [task]
        job.job_task_list = task_list
        return job

    def test_calls_context_upload(self):
        """Calls context.upload() exactly once."""
        job = self._make_job()
        job._ensure_forward_files_on_retry()
        job.machine.context.upload.assert_called_once()

    def test_payload_contains_job_tasks(self):
        """Upload payload contains this job's task list."""
        task = MagicMock()
        task.task_work_path = "task0"
        task.forward_files = ["*.pb"]
        job = self._make_job(task_list=[task])
        job._ensure_forward_files_on_retry()
        payload = job.machine.context.upload.call_args[0][0]
        self.assertEqual(payload.belonging_tasks, [task])

    def test_payload_contains_forward_common_files(self):
        """Upload payload includes forward_common_files from submission."""
        job = self._make_job(forward_common_files=["shared_model.pb"])
        job._ensure_forward_files_on_retry()
        payload = job.machine.context.upload.call_args[0][0]
        self.assertEqual(payload.forward_common_files, ["shared_model.pb"])

    def test_no_submission_on_context(self):
        """If context has no submission attr, method returns early (no-op)."""
        job = self._make_job()
        del job.machine.context.submission
        job._ensure_forward_files_on_retry()
        job.machine.context.upload.assert_not_called()

    def test_no_machine_is_noop(self):
        """If machine is None, method is a no-op."""
        job = Job.__new__(Job)
        job.machine = None
        job.job_task_list = []
        job._ensure_forward_files_on_retry()

    def test_upload_exception_propagates(self):
        """Exceptions from upload propagate (caught at call site, not here)."""
        job = self._make_job()
        job.machine.context.upload.side_effect = FileNotFoundError("gone")
        with self.assertRaises(FileNotFoundError):
            job._ensure_forward_files_on_retry()


class TestEnsureForwardFilesIntegration(unittest.TestCase):
    """Integration test with real LocalContext."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.local_root = os.path.join(self.tmpdir, "local")
        self.remote_root = os.path.join(self.tmpdir, "remote")
        os.makedirs(self.local_root)
        os.makedirs(self.remote_root)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_binary_file_integrity(self):
        """Binary .pb file is uploaded without corruption."""
        from dpdispatcher.contexts.local_context import LocalContext

        ctx = LocalContext.__new__(LocalContext)
        ctx.local_root = self.local_root
        ctx.remote_root = self.remote_root
        ctx.symlink = False
        ctx.submission = MagicMock()
        ctx.submission.forward_common_files = []

        local_task = os.path.join(self.local_root, "task0")
        os.makedirs(local_task)
        binary_content = bytes(range(256)) * 100
        with open(os.path.join(local_task, "frozen_model.pb"), "wb") as f:
            f.write(binary_content)

        job = Job.__new__(Job)
        job.machine = MagicMock()
        job.machine.context = ctx
        task = MagicMock()
        task.task_work_path = "task0"
        task.forward_files = ["frozen_model.pb"]
        job.job_task_list = [task]

        job._ensure_forward_files_on_retry()

        remote_file = os.path.join(self.remote_root, "task0", "frozen_model.pb")
        self.assertTrue(os.path.exists(remote_file))
        with open(remote_file, "rb") as f:
            self.assertEqual(f.read(), binary_content)

    def test_glob_expansion(self):
        """Glob patterns in forward_files are expanded correctly."""
        from dpdispatcher.contexts.local_context import LocalContext

        ctx = LocalContext.__new__(LocalContext)
        ctx.local_root = self.local_root
        ctx.remote_root = self.remote_root
        ctx.symlink = False
        ctx.submission = MagicMock()
        ctx.submission.forward_common_files = []

        local_task = os.path.join(self.local_root, "task0")
        os.makedirs(local_task)
        for name in ["graph.000.pb", "graph.001.pb"]:
            with open(os.path.join(local_task, name), "wb") as f:
                f.write(b"model")

        job = Job.__new__(Job)
        job.machine = MagicMock()
        job.machine.context = ctx
        task = MagicMock()
        task.task_work_path = "task0"
        task.forward_files = ["*.pb"]
        job.job_task_list = [task]

        job._ensure_forward_files_on_retry()

        for name in ["graph.000.pb", "graph.001.pb"]:
            self.assertTrue(
                os.path.exists(os.path.join(self.remote_root, "task0", name)),
                f"{name} not uploaded",
            )


if __name__ == "__main__":
    unittest.main()
