import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"

from .context import run
from dpdispatcher.run import create_submission


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
                "task_list": [
                    {
                        "command": "echo hello",
                        "task_work_path": "*",
                        "forward_files": [],
                        "backward_files": [],
                        "outlog": "log",
                        "errlog": "err",
                    }
                ],
            }

            calls = []

            def _record_allow_ref(task_dict, allow_ref=False):
                calls.append(allow_ref)
                return task_dict

            with patch("dpdispatcher.run.Task.load_from_dict", side_effect=_record_allow_ref):
                with patch("dpdispatcher.run.Submission", return_value=object()):
                    create_submission(metadata, script_hash="abc", allow_ref=True)

            self.assertTrue(calls)
            self.assertTrue(all(calls))
