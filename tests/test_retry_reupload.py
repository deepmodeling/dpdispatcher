"""Test _ensure_forward_files_on_retry for PR #629."""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher.submission import Job
from dpdispatcher.utils.job_status import JobStatus


class TestEnsureForwardFilesOnRetry(unittest.TestCase):
    """Tests for Job._ensure_forward_files_on_retry()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.local_root = os.path.join(self.tmpdir, "local")
        self.remote_root = os.path.join(self.tmpdir, "remote")
        os.makedirs(self.local_root)
        os.makedirs(self.remote_root)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_job_with_context(self, forward_files, task_work_path="task0"):
        """Create a Job with LocalContext-like mock."""
        job = Job.__new__(Job)
        job.machine = MagicMock()
        job.machine.context.remote_root = self.remote_root
        job.machine.context.local_root = self.local_root

        # LocalContext: has _copy_from_local_to_remote
        def copy_fn(src, dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

        job.machine.context._copy_from_local_to_remote = copy_fn

        def check_exists(fname):
            return os.path.isfile(os.path.join(self.remote_root, fname))

        job.machine.context.check_file_exists = check_exists

        # Create task
        task = MagicMock()
        task.task_work_path = task_work_path
        task.forward_files = forward_files
        job.job_task_list = [task]
        job._submission = None

        return job

    def test_reupload_missing_text_file(self):
        """Missing text file on remote gets re-uploaded."""
        job = self._make_job_with_context(["input.lammps"])

        # Create local file
        local_task = os.path.join(self.local_root, "task0")
        os.makedirs(local_task)
        with open(os.path.join(local_task, "input.lammps"), "w") as f:
            f.write("pair_style deepmd\n")

        # Remote task dir exists but file missing
        os.makedirs(os.path.join(self.remote_root, "task0"))

        job._ensure_forward_files_on_retry()

        # File should now exist on remote
        remote_file = os.path.join(self.remote_root, "task0", "input.lammps")
        self.assertTrue(os.path.exists(remote_file))
        with open(remote_file) as f:
            self.assertEqual(f.read(), "pair_style deepmd\n")

    def test_reupload_binary_file_not_corrupted(self):
        """Binary .pb file must not be corrupted during re-upload."""
        job = self._make_job_with_context(["frozen_model.pb"])

        local_task = os.path.join(self.local_root, "task0")
        os.makedirs(local_task)
        # Write binary content (simulating a protobuf model file)
        binary_content = bytes(range(256)) * 100  # 25.6 KB binary
        with open(os.path.join(local_task, "frozen_model.pb"), "wb") as f:
            f.write(binary_content)

        os.makedirs(os.path.join(self.remote_root, "task0"))

        job._ensure_forward_files_on_retry()

        remote_file = os.path.join(self.remote_root, "task0", "frozen_model.pb")
        self.assertTrue(os.path.exists(remote_file))
        with open(remote_file, "rb") as f:
            self.assertEqual(f.read(), binary_content)

    def test_glob_pattern_expanded(self):
        """Glob patterns like '*.pb' in forward_files are properly expanded."""
        job = self._make_job_with_context(["*.pb"])

        local_task = os.path.join(self.local_root, "task0")
        os.makedirs(local_task)
        for name in ["graph.000.pb", "graph.001.pb"]:
            with open(os.path.join(local_task, name), "wb") as f:
                f.write(b"model_data")

        os.makedirs(os.path.join(self.remote_root, "task0"))

        job._ensure_forward_files_on_retry()

        for name in ["graph.000.pb", "graph.001.pb"]:
            remote_file = os.path.join(self.remote_root, "task0", name)
            self.assertTrue(os.path.exists(remote_file), f"{name} not re-uploaded")

    def test_already_exists_not_recopied(self):
        """Files already on remote should not be re-uploaded."""
        job = self._make_job_with_context(["input.lammps"])

        local_task = os.path.join(self.local_root, "task0")
        os.makedirs(local_task)
        with open(os.path.join(local_task, "input.lammps"), "w") as f:
            f.write("local version")

        remote_task = os.path.join(self.remote_root, "task0")
        os.makedirs(remote_task)
        with open(os.path.join(remote_task, "input.lammps"), "w") as f:
            f.write("remote version")

        job._ensure_forward_files_on_retry()

        # Remote file should NOT be overwritten
        with open(os.path.join(remote_task, "input.lammps")) as f:
            self.assertEqual(f.read(), "remote version")

    def test_no_machine_is_noop(self):
        """If machine is None, method is a no-op."""
        job = Job.__new__(Job)
        job.machine = None
        job.job_task_list = []
        # Should not raise
        job._ensure_forward_files_on_retry()

    def test_missing_locally_and_remotely_logs_warning(self):
        """File missing both locally and remotely — should not crash."""
        job = self._make_job_with_context(["nonexistent.txt"])

        os.makedirs(os.path.join(self.local_root, "task0"))
        os.makedirs(os.path.join(self.remote_root, "task0"))

        # Should not raise (just logs warning internally via glob finding nothing)
        job._ensure_forward_files_on_retry()


if __name__ == "__main__":
    unittest.main()
