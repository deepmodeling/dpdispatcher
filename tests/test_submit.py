import json
import os
import shutil
import subprocess as sp
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
from .context import setUpModule  # noqa: F401


class TestSubmitCommand(unittest.TestCase):
    """Test dpdisp submit command."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.json_file = os.path.join(self.tmpdir, "submission.json")
        self.work_dir = os.path.join(self.tmpdir, "test_work")
        self.task_dir = os.path.join(self.work_dir, "task1")
        os.makedirs(self.task_dir)

        # Create a simple submission JSON file
        submission_dict = {
            "work_base": "test_work/",
            "machine": {
                "batch_type": "Shell",
                "local_root": self.tmpdir,
                "context_type": "LazyLocalContext",
            },
            "resources": {
                "number_node": 1,
                "cpu_per_node": 1,
                "gpu_per_node": 0,
                "queue_name": "",
                "group_size": 1,
            },
            "forward_common_files": [],
            "backward_common_files": [],
            "task_list": [
                {
                    "command": "echo hello",
                    "task_work_path": "task1/",
                    "forward_files": [],
                    "backward_files": [],
                    "outlog": "log",
                    "errlog": "err",
                }
            ],
        }
        with open(self.json_file, "w") as f:
            json.dump(submission_dict, f)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_submit_help(self):
        """Test dpdisp submit --help."""
        sp.check_output(["dpdisp", "submit", "-h"])

    def test_submit_dry_run(self):
        """Test dpdisp submit --dry-run."""
        output = sp.check_output(
            ["dpdisp", "submit", "--dry-run", self.json_file],
            cwd=self.tmpdir,
            stderr=sp.STDOUT,
        )
        self.assertIn(b"submission succeeded", output)

    def test_submit_invalid_json(self):
        """Test dpdisp submit with invalid JSON (missing required field)."""
        invalid_json_file = os.path.join(self.tmpdir, "invalid.json")
        invalid_dict = {
            "work_base": "test_work/",
            "machine": {
                "batch_type": "Shell",
                "local_root": self.tmpdir,
                "context_type": "LazyLocalContext",
            },
            "resources": {
                "number_node": 1,
                # missing group_size which is required
            },
            "task_list": [
                {
                    "command": "echo hello",
                    "task_work_path": "task1/",
                }
            ],
        }
        with open(invalid_json_file, "w") as f:
            json.dump(invalid_dict, f)

        with self.assertRaises(sp.CalledProcessError):
            sp.check_output(
                ["dpdisp", "submit", "--dry-run", invalid_json_file],
                cwd=self.tmpdir,
                stderr=sp.STDOUT,
            )

    def test_submit_and_run(self):
        """Test dpdisp submit and run to completion."""
        output = sp.check_output(
            ["dpdisp", "submit", self.json_file],
            cwd=self.tmpdir,
            stderr=sp.STDOUT,
        )
        # Check that the job was submitted and finished
        self.assertIn(b"was submitted", output)
        self.assertIn(b"finished", output)
        # Check that the task was executed
        log_file = os.path.join(self.task_dir, "log")
        self.assertTrue(os.path.exists(log_file))
        with open(log_file) as f:
            content = f.read()
        self.assertIn("hello", content)
