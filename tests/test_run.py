import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"

from dpdispatcher.run import create_submission

from .context import run


class TestRun(unittest.TestCase):
    def test_run(self):
        this_dir = Path(__file__).parent
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)
                run(filename=str(this_dir / "hello_world.py"))
                self.assertEqual(
                    (Path(temp_dir) / "log").read_text().strip(), "hello world!"
                )
            finally:
                os.chdir(cwd)

    def test_create_submission_glob_propagates_allow_ref(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            work_base = "work"
            task_dir = Path(temp_dir) / work_base
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "a").mkdir(exist_ok=True)
            (task_dir / "b").mkdir(exist_ok=True)

            task_ref = Path(temp_dir) / "task.json"
            task_ref.write_text(
                "{"
                '"command":"echo hello",'
                '"task_work_path":"*",'
                '"forward_files":[],"backward_files":[],"outlog":"log","errlog":"err"'
                "}"
            )

            metadata = {
                "work_base": work_base,
                "forward_common_files": [],
                "backward_common_files": [],
                "machine": {
                    "batch_type": "Shell",
                    "context_type": "LocalContext",
                    "local_root": temp_dir,
                    "remote_root": temp_dir,
                },
                "resources": {
                    "number_node": 1,
                    "cpu_per_node": 1,
                    "gpu_per_node": 0,
                    "queue_name": "",
                    "group_size": 1,
                },
                "task_list": [{"$ref": str(task_ref)}],
            }

            with self.assertRaises(Exception):
                create_submission(metadata, script_hash="abc", allow_ref=False)

            submission = create_submission(metadata, script_hash="abc", allow_ref=True)
            self.assertEqual(len(submission.task_list), 2)
            self.assertTrue(
                all(
                    task.command.endswith(" $REMOTE_ROOT/script_abc.py")
                    for task in submission.task_list
                )
            )
