"""Regression tests for cloud error diagnostics."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock

from dpdispatcher.machines.dp_cloud_server import Bohrium
from dpdispatcher.machines.openapi import OpenAPI


class TestCloudJobError(unittest.TestCase):
    """Cloud machines retrieve diagnostics through the job interface."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.job = MagicMock(
            job_hash="cloud-job",
            job_id="123:job_group_id:456",
            job_task_list=[],
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_backward_lists_include_diagnostic(self):
        expected = "cloud-job_last_err_file"
        for machine_class in (OpenAPI, Bohrium):
            with self.subTest(machine=machine_class.__name__):
                machine = machine_class.__new__(machine_class)
                self.assertIn(
                    expected,
                    machine._gen_backward_files_list(self.job),
                )

    def test_bohrium_custom_backward_list_keeps_diagnostic(self):
        machine = Bohrium.__new__(Bohrium)
        machine.context = MagicMock()
        machine.context.remote_profile = {"program_id": 1}
        machine.input_data = {
            "job_type": "container",
            "backward_files": ["custom.log"],
        }
        machine.group_id = None
        machine.grouped = False
        machine.api = MagicMock()
        machine.api.job_create.return_value = (123, 456)
        machine.gen_local_script = MagicMock()
        self.job.upload_path = "program/1/cloud-job.zip"
        self.job.script_file_name = "cloud-job.sh"
        self.job.job_id = ""
        self.job.job_task_list = [MagicMock(task_work_path="task0", outlog="task0.out")]

        machine.do_submit(self.job)

        input_data = machine.api.job_create.call_args[1]["input_data"]
        self.assertEqual(
            input_data["backward_files"], ["custom.log", "cloud-job_last_err_file"]
        )

    def test_reads_diagnostic_from_result_archive(self):
        error_path = os.path.join(self.tmpdir.name, "cloud-job_last_err_file")
        for machine_class in (OpenAPI, Bohrium):
            with self.subTest(machine=machine_class.__name__):
                if os.path.exists(error_path):
                    os.remove(error_path)
                machine = machine_class.__new__(machine_class)
                machine.context = MagicMock(local_root=self.tmpdir.name)

                def download(_job):
                    with open(error_path, "w") as fp:
                        fp.write("remote stderr")

                machine._download_job = MagicMock(side_effect=download)
                machine.job = MagicMock()
                machine.api = MagicMock()
                self.assertEqual(
                    machine.get_job_error(self.job),
                    "remote stderr",
                )

    def test_falls_back_to_cloud_job_log(self):
        for machine_class in (OpenAPI, Bohrium):
            with self.subTest(machine=machine_class.__name__):
                machine = machine_class.__new__(machine_class)
                machine.context = MagicMock(local_root=self.tmpdir.name)
                machine._download_job = MagicMock()
                machine.job = MagicMock()
                machine.job.log.return_value = "openapi log"
                machine.api = MagicMock()
                machine.api.get_log.return_value = "bohrium log"
                expected = "openapi log" if machine_class is OpenAPI else "bohrium log"
                self.assertEqual(machine.get_job_error(self.job), expected)
                if machine_class is Bohrium:
                    machine.api.get_log.assert_called_once_with(123)


if __name__ == "__main__":
    unittest.main()
