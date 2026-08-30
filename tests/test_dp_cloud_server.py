"""Regression tests for the legacy Bohrium batch backend."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import dpdispatcher.machines.dp_cloud_server as dp_cloud_server
from dpdispatcher.machine import Machine


class TestBohrium(unittest.TestCase):
    """Verify legacy Bohrium behavior without contacting the cloud service."""

    def _make_context(self) -> SimpleNamespace:
        """Build a context containing representative legacy API settings."""
        return SimpleNamespace(
            remote_profile={
                "email": "test@example.com",
                "password": "password",
                "project_id": 7,
                "input_data": {
                    "job_type": "indicate",
                    "job_resources": ["https://example/base.zip"],
                },
            },
            local_root="/tmp/dpdispatcher-test",
        )

    @staticmethod
    def _make_job(job_hash: str) -> SimpleNamespace:
        """Build the small job surface used by ``Bohrium.do_submit``."""
        return SimpleNamespace(
            job_hash=job_hash,
            upload_path=f"{job_hash}.zip",
            script_file_name=f"{job_hash}.sh",
            job_task_list=[
                SimpleNamespace(
                    task_work_path=job_hash,
                    outlog="log",
                    backward_files=[],
                )
            ],
        )

    def test_gen_script_does_not_require_legacy_alias(self) -> None:
        """Script generation works when the old module alias is unavailable."""
        with patch.object(dp_cloud_server, "Client"):
            machine = dp_cloud_server.Bohrium(self._make_context())

        with patch.object(Machine, "gen_script", lambda _machine, _job: "script"):
            with patch.dict(dp_cloud_server.__dict__, clear=False):
                del dp_cloud_server.__dict__["DpCloudServer"]
                self.assertEqual(machine.gen_script(object()), "script")

    def test_each_job_gets_independent_oss_resources(self) -> None:
        """Do not accumulate one job's upload URL into later API payloads."""
        context = self._make_context()
        base_resources = context.remote_profile["input_data"]["job_resources"]

        with patch.object(dp_cloud_server, "Client") as client_cls:
            machine = dp_cloud_server.Bohrium(context)
            machine.gen_local_script = MagicMock()
            client = client_cls.return_value
            client.job_create.side_effect = [(101, None), (102, None)]

            first_job = self._make_job("first")
            second_job = self._make_job("second")
            machine.do_submit(first_job)
            machine.do_submit(second_job)

        first_resources = client.job_create.call_args_list[0][1]["oss_path"]
        second_resources = client.job_create.call_args_list[1][1]["oss_path"]
        expected_first = [
            *base_resources,
            dp_cloud_server.ALI_OSS_BUCKET_URL + "first.zip",
        ]
        expected_second = [
            *base_resources,
            dp_cloud_server.ALI_OSS_BUCKET_URL + "second.zip",
        ]
        self.assertEqual(first_resources, expected_first)
        self.assertEqual(second_resources, expected_second)
        self.assertIsNot(first_resources, second_resources)
        self.assertIsNot(
            machine.input_data["job_resources"],
            context.remote_profile["input_data"]["job_resources"],
        )
        self.assertEqual(
            context.remote_profile["input_data"]["job_resources"], base_resources
        )


if __name__ == "__main__":
    unittest.main()
