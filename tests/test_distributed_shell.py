import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call, patch

from dpdispatcher.machines.distributed_shell import DistributedShell
from dpdispatcher.utils.job_status import JobStatus


class AttrDict(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Expose dictionary values through attribute access in fixtures."""
        return self[name]


class TestDistributedShell(unittest.TestCase):
    def setUp(self) -> None:
        """Build a representative DistributedShell fixture."""
        self.context = MagicMock()
        self.context.remote_root = "/remote/root"
        self.context.submission.submission_hash = "submission123"
        self.machine = DistributedShell(context=self.context)
        self.resources = AttrDict(
            module_purge=True,
            module_unload_list=["old/module"],
            module_list=["new/module"],
            source_list=["activate env"],
            envs={"TEST_ENV": "value with space"},
            prepend_script=["echo before"],
            append_script=["echo after"],
            strategy={"customized_script_header_template_file": None},
            kwargs={
                "yarn_path": "/opt/hadoop",
                "img_name": "image:latest",
                "mem_limit": 4,
            },
            queue_name="default",
            cpu_per_node=8,
        )
        self.job = SimpleNamespace(
            resources=self.resources,
            job_hash="job123",
            script_file_name=".job123.sub",
            job_task_list=[
                SimpleNamespace(task_work_path="task1"),
                SimpleNamespace(task_work_path="task two"),
            ],
            job_id=123,
        )

    def test_gen_script_env(self) -> None:
        """Environment generation includes modules, exports, and staging."""
        script = self.machine.gen_script_env(self.job)
        self.assertIn("module purge", script)
        self.assertIn("module unload old/module", script)
        self.assertIn("module load new/module", script)
        self.assertIn("{ source activate env; }", script)
        self.assertIn("export TEST_ENV='value with space'", script)
        self.assertIn("echo before", script)
        self.assertIn("hadoop fs -get /remote/root/*.tgz", script)
        self.assertIn("submission123_upload.tgz", script)
        self.assertIn("job123_flag_if_job_task_fail", script)

    def test_gen_script_end(self) -> None:
        """Archive and completion commands quote task paths safely."""
        script = self.machine.gen_script_end(self.job)
        self.assertIn(
            "tar czf submission123_job123_download.tar.gz task1 'task two' ",
            script,
        )
        self.assertIn(
            "hadoop fs -put -f submission123_job123_download.tar.gz /remote/root",
            script,
        )
        self.assertIn("job123_job_tag_finished", script)
        self.assertIn("echo after", script)

    def test_default_and_custom_header(self) -> None:
        """Default and customized scheduler headers are supported."""
        self.assertIn("#!/bin/bash -l", self.machine.gen_script_header(self.job))

        self.resources["strategy"]["customized_script_header_template_file"] = (
            "header.in"
        )
        with patch(
            "dpdispatcher.machines.distributed_shell.customized_script_header_template",
            return_value="custom header",
        ) as customized:
            self.assertEqual(self.machine.gen_script_header(self.job), "custom header")
            customized.assert_called_once_with("header.in", self.resources)

    @patch("dpdispatcher.machines.distributed_shell.run_cmd_with_all_output")
    def test_do_submit(self, run_command: MagicMock) -> None:
        """Submission writes scripts and returns the YARN process identifier."""
        self.machine.gen_script = MagicMock(return_value="submission script")
        self.machine.gen_script_command = MagicMock(return_value="run script")
        run_command.return_value = (0, b"321\n", b"")

        job_id = self.machine.do_submit(self.job)

        self.assertEqual(job_id, 321)
        self.assertEqual(
            self.context.write_file.call_args_list,
            [
                call(fname=".job123.sub", write_str="submission script"),
                call(fname=".job123.sub.run", write_str="run script"),
                call("job123_job_id", "321"),
            ],
        )
        command = run_command.call_args.args[0]
        self.assertIn("hadoop-yarn-applications-distributedshell", command)
        self.assertIn("-queue default", command)
        self.assertIn(
            "-shell_env YARN_CONTAINER_RUNTIME_DOCKER_IMAGE=image:latest", command
        )
        self.assertIn("-container_resources memory-mb=4096,vcores=8", command)

    @patch("dpdispatcher.machines.distributed_shell.run_cmd_with_all_output")
    def test_do_submit_reports_command_failure(self, run_command: MagicMock) -> None:
        """Non-zero YARN submission commands raise an actionable error."""
        self.machine.gen_script = MagicMock(return_value="submission script")
        self.machine.gen_script_command = MagicMock(return_value="run script")
        run_command.return_value = (2, b"", b"submission failed")

        with self.assertRaisesRegex(RuntimeError, "submission failed"):
            self.machine.do_submit(self.job)

    @patch("dpdispatcher.machines.distributed_shell.run_cmd_with_all_output")
    def test_check_status(self, run_command: MagicMock) -> None:
        """Status checks report finished jobs when their tag exists."""
        self.job.job_id = ""
        self.assertEqual(self.machine.check_status(self.job), JobStatus.unsubmitted)

        self.job.job_id = 123
        self.context.check_file_exists.return_value = True
        run_command.return_value = (0, b"1\n", b"")
        self.assertEqual(self.machine.check_status(self.job), JobStatus.finished)

        self.context.check_file_exists.return_value = False
        self.assertEqual(self.machine.check_status(self.job), JobStatus.running)

        run_command.return_value = (0, b"", b"")
        self.assertEqual(self.machine.check_status(self.job), JobStatus.terminated)

        run_command.return_value = (1, b"", b"ps failed")
        with self.assertRaisesRegex(RuntimeError, "ps failed"):
            self.machine.check_status(self.job)

    def test_check_finish_tag(self) -> None:
        """Finish-tag checks use the expected job-specific marker."""
        self.context.check_file_exists.return_value = True
        self.assertTrue(self.machine.check_finish_tag(self.job))
        self.context.check_file_exists.assert_called_once_with(
            "job123_job_tag_finished"
        )


if __name__ == "__main__":
    unittest.main()
