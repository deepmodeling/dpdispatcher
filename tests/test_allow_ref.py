import tempfile
import unittest
from pathlib import Path

from dpdispatcher.entrypoints.submit import load_submission_from_json


class TestAllowRef(unittest.TestCase):
    def test_submit_json_allow_ref_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            work = tmp / "work"
            work.mkdir(parents=True, exist_ok=True)
            (work / "task1").mkdir(exist_ok=True)

            machine = tmp / "machine.json"
            machine.write_text(
                '{"batch_type":"Shell","context_type":"LazyLocalContext","local_root":"'
                + tmpdir
                + '","remote_root":"'
                + tmpdir
                + '"}'
            )
            submission = tmp / "submission.json"
            submission.write_text(
                "{"
                '"work_base":"work/",'
                '"machine":{"$ref":"machine.json"},'
                '"resources":{"number_node":1,"cpu_per_node":1,"gpu_per_node":0,"queue_name":"","group_size":1},'
                '"forward_common_files":[],"backward_common_files":[],'
                '"task_list":[{"command":"echo hello","task_work_path":"task1/","forward_files":[],"backward_files":[],"outlog":"log","errlog":"err"}]'
                "}"
            )

            with self.assertRaises(Exception):
                load_submission_from_json(str(submission), allow_ref=False)

            sub = load_submission_from_json(str(submission), allow_ref=True)
            self.assertEqual(sub.machine.__class__.__name__, "Shell")
