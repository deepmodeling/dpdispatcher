import os
import sys
import textwrap
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from test_run_submission import RunSubmission

from dpdispatcher.contexts import openapi_context

if openapi_context.found_bohriumsdk:
    from dpdispatcher.contexts.openapi_context import OpenAPIContext


@unittest.skipUnless(openapi_context.found_bohriumsdk, "requires bohrium-sdk")
class TestOpenAPIContextUpload(unittest.TestCase):
    @patch("dpdispatcher.contexts.openapi_context.Tiefblue")
    @patch("dpdispatcher.contexts.openapi_context.Job")
    @patch("dpdispatcher.contexts.openapi_context.Bohrium")
    def test_upload_job_uses_store_host_when_create_returns_it(
        self,
        mock_bohrium: MagicMock,
        mock_job_cls: MagicMock,
        mock_tiefblue_cls: MagicMock,
    ) -> None:
        mock_job_api = MagicMock()
        mock_job_api.create.return_value = {
            "jobId": 123,
            "jobGroupId": "grp-1",
            "token": "upload-token",
            "storePath": "jobs/13375/123",
            "storeHost": "https://sandbox-store.example.com",
        }
        mock_job_cls.return_value = mock_job_api

        default_storage = MagicMock()
        upload_storage = MagicMock()
        storage_instances = []

        def make_storage(*args: Any, **kwargs: Any) -> MagicMock:  # noqa: ANN401
            storage_instances.append(kwargs)
            if kwargs:
                return upload_storage
            return default_storage

        mock_tiefblue_cls.side_effect = make_storage

        context = OpenAPIContext(
            local_root="/tmp/work",
            remote_profile={"project_id": 1, "access_key": "ak", "app_key": "app"},
        )
        context.local_root = "/tmp/work"
        context.machine = MagicMock()
        context.machine.gen_local_script = MagicMock()

        job = MagicMock()
        job.job_hash = "abc123"
        job.script_file_name = "run.sh"
        job.job_task_list = []

        with patch(
            "dpdispatcher.contexts.openapi_context.zip_file_list",
            return_value="/tmp/work/abc123.zip",
        ):
            context.upload_job(job)

        self.assertEqual(
            storage_instances[-1], {"base_url": "https://sandbox-store.example.com"}
        )
        upload_storage.upload_From_file_multi_part.assert_called_once_with(
            object_key="jobs/13375/123/abc123.zip",
            file_path="/tmp/work/abc123.zip",
            token="upload-token",
        )
        self.assertEqual(job.upload_path, "jobs/13375/123/abc123.zip")
        self.assertNotIn("?", job.upload_path)
        self.assertIs(context.storage, default_storage)

    @patch("dpdispatcher.contexts.openapi_context.Tiefblue")
    @patch("dpdispatcher.contexts.openapi_context.Job")
    @patch("dpdispatcher.contexts.openapi_context.Bohrium")
    def test_upload_job_keeps_default_storage_without_store_host(
        self,
        mock_bohrium: MagicMock,
        mock_job_cls: MagicMock,
        mock_tiefblue_cls: MagicMock,
    ) -> None:
        mock_job_api = MagicMock()
        mock_job_api.create.return_value = {
            "jobId": 123,
            "jobGroupId": "grp-1",
            "token": "upload-token",
            "storePath": "jobs/13375/123",
        }
        mock_job_cls.return_value = mock_job_api

        default_storage = MagicMock()
        mock_tiefblue_cls.return_value = default_storage

        context = OpenAPIContext(
            local_root="/tmp/work",
            remote_profile={"project_id": 1, "access_key": "ak", "app_key": "app"},
        )
        context.local_root = "/tmp/work"
        context.machine = MagicMock()
        context.machine.gen_local_script = MagicMock()

        job = MagicMock()
        job.job_hash = "abc123"
        job.script_file_name = "run.sh"
        job.job_task_list = []

        with patch(
            "dpdispatcher.contexts.openapi_context.zip_file_list",
            return_value="/tmp/work/abc123.zip",
        ):
            context.upload_job(job)

        mock_tiefblue_cls.assert_called_once_with()
        default_storage.upload_From_file_multi_part.assert_called_once_with(
            object_key="jobs/13375/123/abc123.zip",
            file_path="/tmp/work/abc123.zip",
            token="upload-token",
        )
        self.assertEqual(job.upload_path, "jobs/13375/123/abc123.zip")


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "bohrium",
    "outside the Bohrium testing environment",
)
class TestBohriumRun(RunSubmission, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.machine_dict.update(
            batch_type="Bohrium",
            context_type="Bohrium",
            remote_profile={
                "email": os.environ["BOHRIUM_EMAIL"],
                "password": os.environ["BOHRIUM_PASSWORD"],
                "project_id": int(os.environ["BOHRIUM_PROJECT_ID"]),
                "input_data": {
                    "job_type": "indicate",
                    "log_file": "log",
                    "job_name": "dpdispather_test",
                    "disk_size": 20,
                    "scass_type": "c2_m4_cpu",
                    "platform": "ali",
                    "image_name": "registry.dp.tech/dptech/ubuntu:22.04-py3.10",
                    "on_demand": 0,
                },
            },
        )

    @unittest.skip("Manaually skip")  # comment this line to open unittest
    def test_async_run_submission(self) -> Any:  # noqa: ANN401
        return super().test_async_run_submission()


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "bohrium",
    "outside the Bohrium testing environment",
)
class TestOpenAPIRun(RunSubmission, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        bohrium_config = textwrap.dedent(
            """\
            [Credentials]
            accessKey={accesskey}
            """
        ).format(accesskey=os.environ["BOHRIUM_ACCESS_KEY"])
        Path.home().joinpath(".brmconfig").write_text(bohrium_config)
        self.machine_dict.update(
            batch_type="OpenAPI",
            context_type="OpenAPI",
            remote_profile={
                "project_id": int(os.environ["BOHRIUM_PROJECT_ID"]),
                "machine_type": "c2_m4_cpu",
                "platform": "ali",
                "image_address": "registry.dp.tech/dptech/ubuntu:22.04-py3.10",
                "job_name": "dpdispather_test",
            },
        )

    @unittest.skip("Manaually skip")  # comment this line to open unittest
    def test_async_run_submission(self) -> Any:  # noqa: ANN401
        return super().test_async_run_submission()
