import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call, patch

from dpdispatcher.machines.fugaku import Fugaku
from dpdispatcher.utils.job_status import JobStatus


class AttrDict(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        return self[name]


def _status_response(text: str) -> tuple[int, None, MagicMock, MagicMock]:
    stdout = MagicMock()
    stdout.read.return_value = text.encode("utf-8")
    stderr = MagicMock()
    stderr.read.return_value = b""
    return 0, None, stdout, stderr


class TestFugaku(unittest.TestCase):
    def setUp(self) -> None:
        self.context = MagicMock()
        self.context.remote_root = "/tmp/remote root"
        self.machine = Fugaku(context=self.context)
        self.resources = AttrDict(
            number_node=2,
            cpu_per_node=8,
            queue_name="small",
            strategy={"customized_script_header_template_file": None},
        )
        self.job = SimpleNamespace(
            resources=self.resources,
            job_hash="job123",
            script_file_name="job script.sub",
            job_id="123",
        )

    @patch("dpdispatcher.machine.Machine.gen_script", return_value="generated")
    def test_gen_script_delegates_to_base(self, base_gen_script: MagicMock) -> None:
        self.assertEqual(self.machine.gen_script(self.job), "generated")
        base_gen_script.assert_called_once_with(self.job)

    def test_default_and_empty_queue_headers(self) -> None:
        header = self.machine.gen_script_header(self.job)
        self.assertIn('#PJM -L "rscgrp=small"', header)
        self.assertIn('#PJM -L "node=2"', header)
        self.assertIn('#PJM --mpi "max-proc-per-node=8"', header)

        self.resources.queue_name = ""
        header = self.machine.gen_script_header(self.job)
        self.assertNotIn("rscgrp=", header)
        self.assertIn('#PJM -L "node=2"', header)

    @patch(
        "dpdispatcher.machines.fugaku.customized_script_header_template",
        return_value="custom header",
    )
    def test_custom_header(self, customized: MagicMock) -> None:
        self.resources["strategy"]["customized_script_header_template_file"] = (
            "header.in"
        )
        self.assertEqual(self.machine.gen_script_header(self.job), "custom header")
        customized.assert_called_once_with("header.in", self.resources)

    def test_do_submit_writes_scripts_and_job_id(self) -> None:
        self.machine.gen_script = MagicMock(return_value="submission script")
        self.machine.gen_script_command = MagicMock(return_value="run script")
        stdout = MagicMock()
        stdout.readlines.return_value = ["a b c d e 456\n"]
        self.context.block_checkcall.return_value = (None, stdout, MagicMock())

        job_id = self.machine.do_submit(self.job)

        self.assertEqual(job_id, "456")
        self.assertEqual(
            self.context.write_file.call_args_list,
            [
                call(fname="job script.sub", write_str="submission script"),
                call(fname="job script.sub.run", write_str="run script"),
                call("job123_job_id", "456"),
            ],
        )
        self.context.block_checkcall.assert_called_once_with(
            "cd '/tmp/remote root' && pjsub 'job script.sub'"
        )

    def test_check_status_unsubmitted_waiting_running_and_unknown(self) -> None:
        self.job.job_id = ""
        self.assertEqual(self.machine.check_status(self.job), JobStatus.unsubmitted)

        for status_word, expected in (
            ("QUE", JobStatus.waiting),
            ("HLD", JobStatus.waiting),
            ("RUN", JobStatus.running),
            ("RNE", JobStatus.running),
            ("MYSTERY", JobStatus.unknown),
        ):
            with self.subTest(status_word=status_word):
                self.job.job_id = "123"
                self.context.block_call.return_value = _status_response(
                    f"header\n0 a b {status_word}\n"
                )
                self.assertEqual(self.machine.check_status(self.job), expected)

    def test_check_status_history_terminal_states(self) -> None:
        for finish_tag, expected in (
            (True, JobStatus.finished),
            (False, JobStatus.terminated),
        ):
            with self.subTest(finish_tag=finish_tag):
                self.context.block_call.side_effect = [
                    _status_response(""),
                    _status_response("header\n0 a b EXT\n"),
                ]
                self.context.check_file_exists.return_value = finish_tag
                self.assertEqual(self.machine.check_status(self.job), expected)

        self.context.block_call.side_effect = [
            _status_response(""),
            _status_response("header\n0 a b OTHER\n"),
        ]
        self.assertEqual(self.machine.check_status(self.job), JobStatus.unknown)

    def test_check_finish_tag(self) -> None:
        self.context.check_file_exists.return_value = True
        self.assertTrue(self.machine.check_finish_tag(self.job))
        self.context.check_file_exists.assert_called_once_with(
            "job123_job_tag_finished"
        )


if __name__ == "__main__":
    unittest.main()
