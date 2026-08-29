"""Regression test for retry upload with forwarded directories.

Verifies that `_copy_from_local_to_remote` and `context.upload()` handle
existing remote directories correctly without raising `IsADirectoryError`.
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher.contexts.local_context import LocalContext
from dpdispatcher.submission import Job


class TestCopyFromLocalToRemoteDirectory(unittest.TestCase):
    """Unit tests for _copy_from_local_to_remote with directory targets."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.local_root = os.path.join(self.tmpdir, "local")
        self.remote_root = os.path.join(self.tmpdir, "remote")
        os.makedirs(self.local_root)
        os.makedirs(self.remote_root)

        self.ctx = LocalContext.__new__(LocalContext)
        self.ctx.local_root = self.local_root
        self.ctx.remote_root = self.remote_root
        self.ctx.symlink = False

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_replace_existing_directory(self):
        """Existing remote directory is replaced without IsADirectoryError."""
        # Create local directory with files
        local_dir = os.path.join(self.local_root, "inputs")
        os.makedirs(local_dir)
        with open(os.path.join(local_dir, "data.txt"), "w") as f:
            f.write("hello")
        with open(os.path.join(local_dir, "config.json"), "w") as f:
            f.write('{"key": "value"}')

        # Create remote directory (simulating partial state — missing a file)
        remote_dir = os.path.join(self.remote_root, "inputs")
        os.makedirs(remote_dir)
        with open(os.path.join(remote_dir, "data.txt"), "w") as f:
            f.write("stale")
        # config.json is missing on remote — this is the partial failure case

        # Should NOT raise IsADirectoryError
        self.ctx._copy_from_local_to_remote(local_dir, remote_dir)

        # Verify the directory was fully re-uploaded
        self.assertTrue(os.path.isdir(remote_dir))
        self.assertTrue(os.path.exists(os.path.join(remote_dir, "data.txt")))
        self.assertTrue(os.path.exists(os.path.join(remote_dir, "config.json")))
        with open(os.path.join(remote_dir, "data.txt")) as f:
            self.assertEqual(f.read(), "hello")
        with open(os.path.join(remote_dir, "config.json")) as f:
            self.assertEqual(f.read(), '{"key": "value"}')

    def test_replace_existing_file(self):
        """Existing remote file is still replaced correctly."""
        local_file = os.path.join(self.local_root, "script.sh")
        with open(local_file, "w") as f:
            f.write("#!/bin/bash\necho new")

        remote_file = os.path.join(self.remote_root, "script.sh")
        with open(remote_file, "w") as f:
            f.write("#!/bin/bash\necho old")

        self.ctx._copy_from_local_to_remote(local_file, remote_file)

        with open(remote_file) as f:
            self.assertEqual(f.read(), "#!/bin/bash\necho new")

    def test_copy_new_directory(self):
        """Copying a directory when remote doesn't exist works normally."""
        local_dir = os.path.join(self.local_root, "newdir")
        os.makedirs(local_dir)
        with open(os.path.join(local_dir, "file.txt"), "w") as f:
            f.write("content")

        remote_dir = os.path.join(self.remote_root, "newdir")

        self.ctx._copy_from_local_to_remote(local_dir, remote_dir)

        self.assertTrue(os.path.isdir(remote_dir))
        with open(os.path.join(remote_dir, "file.txt")) as f:
            self.assertEqual(f.read(), "content")

    def test_nested_directory_replaced(self):
        """Nested directory structure is fully replaced."""
        local_dir = os.path.join(self.local_root, "inputs")
        os.makedirs(os.path.join(local_dir, "subdir"))
        with open(os.path.join(local_dir, "top.txt"), "w") as f:
            f.write("top")
        with open(os.path.join(local_dir, "subdir", "nested.txt"), "w") as f:
            f.write("nested")

        # Remote has partial content (missing subdir/nested.txt)
        remote_dir = os.path.join(self.remote_root, "inputs")
        os.makedirs(remote_dir)
        with open(os.path.join(remote_dir, "top.txt"), "w") as f:
            f.write("stale_top")

        self.ctx._copy_from_local_to_remote(local_dir, remote_dir)

        self.assertTrue(os.path.exists(os.path.join(remote_dir, "top.txt")))
        self.assertTrue(
            os.path.exists(os.path.join(remote_dir, "subdir", "nested.txt"))
        )
        with open(os.path.join(remote_dir, "subdir", "nested.txt")) as f:
            self.assertEqual(f.read(), "nested")

    def test_replace_live_directory_symlink(self):
        """The default symlink mode replaces an existing directory symlink."""
        self.ctx.symlink = True
        local_dir = os.path.join(self.local_root, "inputs")
        os.makedirs(local_dir)
        with open(os.path.join(local_dir, "new.txt"), "w") as f:
            f.write("new")

        old_target = os.path.join(self.tmpdir, "old-inputs")
        os.makedirs(old_target)
        remote_dir = os.path.join(self.remote_root, "inputs")
        os.symlink(old_target, remote_dir)

        self.ctx._copy_from_local_to_remote(local_dir, remote_dir)

        self.assertTrue(os.path.islink(remote_dir))
        self.assertEqual(os.path.realpath(remote_dir), os.path.realpath(local_dir))
        self.assertTrue(os.path.exists(os.path.join(remote_dir, "new.txt")))

    def test_replace_broken_symlink(self):
        """A broken destination symlink is removed before retry upload."""
        self.ctx.symlink = True
        local_file = os.path.join(self.local_root, "input.txt")
        with open(local_file, "w") as f:
            f.write("new")

        remote_file = os.path.join(self.remote_root, "input.txt")
        os.symlink(os.path.join(self.tmpdir, "missing-target"), remote_file)
        self.assertTrue(os.path.lexists(remote_file))
        self.assertFalse(os.path.exists(remote_file))

        self.ctx._copy_from_local_to_remote(local_file, remote_file)

        self.assertTrue(os.path.islink(remote_file))
        self.assertEqual(os.path.realpath(remote_file), os.path.realpath(local_file))
        with open(remote_file) as f:
            self.assertEqual(f.read(), "new")


class TestRetryUploadForwardDirectory(unittest.TestCase):
    """Integration test: retry upload with a forwarded directory via context.upload()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.local_root = os.path.join(self.tmpdir, "local")
        self.remote_root = os.path.join(self.tmpdir, "remote")
        os.makedirs(self.local_root)
        os.makedirs(self.remote_root)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_retry_reupload_forward_directory_partial_remote(self):
        """Retry upload successfully re-uploads a forward directory with partial remote state.

        Regression test: previously os.remove() raised IsADirectoryError when the
        remote destination was an existing directory.
        """
        ctx = LocalContext.__new__(LocalContext)
        ctx.local_root = self.local_root
        ctx.remote_root = self.remote_root
        ctx.symlink = False
        ctx.submission = MagicMock()
        ctx.submission.forward_common_files = []

        # Set up local task with a forward directory "inputs/"
        local_task = os.path.join(self.local_root, "task0")
        local_inputs = os.path.join(local_task, "inputs")
        os.makedirs(local_inputs)
        with open(os.path.join(local_inputs, "data.lammps"), "w") as f:
            f.write("pair_style deepmd frozen.pb\n")
        with open(os.path.join(local_inputs, "conf.lmp"), "w") as f:
            f.write("# LAMMPS configuration\n")

        # Simulate partial remote state: directory exists but a child is missing
        remote_task = os.path.join(self.remote_root, "task0")
        remote_inputs = os.path.join(remote_task, "inputs")
        os.makedirs(remote_inputs)
        with open(os.path.join(remote_inputs, "data.lammps"), "w") as f:
            f.write("pair_style deepmd frozen.pb\n")
        # conf.lmp is MISSING on remote — simulating the partial failure

        # Build a Job and trigger retry upload
        job = Job.__new__(Job)
        job.machine = MagicMock()
        job.machine.context = ctx

        task = MagicMock()
        task.task_work_path = "task0"
        task.forward_files = ["inputs/"]
        job.job_task_list = [task]

        # This should NOT raise IsADirectoryError
        job._ensure_forward_files_on_retry()

        # Verify both files exist on remote after re-upload
        self.assertTrue(os.path.exists(os.path.join(remote_inputs, "data.lammps")))
        self.assertTrue(os.path.exists(os.path.join(remote_inputs, "conf.lmp")))
        with open(os.path.join(remote_inputs, "conf.lmp")) as f:
            self.assertEqual(f.read(), "# LAMMPS configuration\n")

    def test_retry_reupload_forward_directory_no_existing_remote(self):
        """Retry upload works when remote directory doesn't exist yet."""
        ctx = LocalContext.__new__(LocalContext)
        ctx.local_root = self.local_root
        ctx.remote_root = self.remote_root
        ctx.symlink = False
        ctx.submission = MagicMock()
        ctx.submission.forward_common_files = []

        local_task = os.path.join(self.local_root, "task0")
        local_inputs = os.path.join(local_task, "inputs")
        os.makedirs(local_inputs)
        with open(os.path.join(local_inputs, "file.txt"), "w") as f:
            f.write("data")

        # Remote task dir exists but inputs/ does not
        remote_task = os.path.join(self.remote_root, "task0")
        os.makedirs(remote_task)

        job = Job.__new__(Job)
        job.machine = MagicMock()
        job.machine.context = ctx

        task = MagicMock()
        task.task_work_path = "task0"
        task.forward_files = ["inputs/"]
        job.job_task_list = [task]

        job._ensure_forward_files_on_retry()

        remote_inputs = os.path.join(remote_task, "inputs")
        self.assertTrue(os.path.isdir(remote_inputs))
        self.assertTrue(os.path.exists(os.path.join(remote_inputs, "file.txt")))


if __name__ == "__main__":
    unittest.main()
