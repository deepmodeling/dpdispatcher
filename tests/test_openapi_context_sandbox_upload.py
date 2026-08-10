import os
import unittest
from unittest.mock import MagicMock, patch

from dpdispatcher.contexts.openapi_context import OpenAPIContext


class TestOpenAPIContextSandboxUpload(unittest.TestCase):
    @patch("dpdispatcher.contexts.openapi_context.Tiefblue")
    @patch("dpdispatcher.contexts.openapi_context.Job")
    @patch("dpdispatcher.contexts.openapi_context.Bohrium")
    def test_upload_job_uses_store_host_in_sandbox_mode(
        self, mock_bohrium, mock_job_cls, mock_tiefblue_cls
    ):
        mock_job_api = MagicMock()
        mock_job_api.create.return_value = {
            "jobId": 123,
            "jobGroupId": "grp-1",
            "token": "upload-token",
            "storePath": "jobs/13375/123",
            "storeHost": "https://sandbox-store.example.com",
        }
        mock_job_cls.return_value = mock_job_api

        storage_instances = []
        upload_storage = MagicMock()

        def make_storage(*args, **kwargs):
            storage_instances.append(kwargs)
            return upload_storage

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

        with patch.dict(os.environ, {"BOHRIUM_USE_SANDBOX": "1"}, clear=False):
            with patch(
                "dpdispatcher.contexts.openapi_context.zip_file_list",
                return_value="/tmp/work/abc123.zip",
            ):
                context.upload_job(job)

        self.assertEqual(storage_instances[-1], {"base_url": "https://sandbox-store.example.com"})
        upload_storage.upload_From_file_multi_part.assert_called_once_with(
            object_key="jobs/13375/123/abc123.zip",
            file_path="/tmp/work/abc123.zip",
            token="upload-token",
        )
        self.assertEqual(job.upload_path, "jobs/13375/123/abc123.zip")
        self.assertNotIn("?", job.upload_path)

    @patch("dpdispatcher.contexts.openapi_context.Tiefblue")
    @patch("dpdispatcher.contexts.openapi_context.Job")
    @patch("dpdispatcher.contexts.openapi_context.Bohrium")
    def test_upload_job_keeps_default_storage_without_sandbox(
        self, mock_bohrium, mock_job_cls, mock_tiefblue_cls
    ):
        mock_job_api = MagicMock()
        mock_job_api.create.return_value = {
            "jobId": 123,
            "jobGroupId": "grp-1",
            "token": "upload-token",
            "storePath": "jobs/13375/123",
            "storeHost": "https://sandbox-store.example.com",
        }
        mock_job_cls.return_value = mock_job_api
        mock_tiefblue_cls.return_value = MagicMock()

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

        with patch.dict(os.environ, {"BOHRIUM_USE_SANDBOX": "0"}, clear=False):
            with patch(
                "dpdispatcher.contexts.openapi_context.zip_file_list",
                return_value="/tmp/work/abc123.zip",
            ):
                context.upload_job(job)

        self.assertEqual(mock_tiefblue_cls.call_count, 1)
        mock_tiefblue_cls.assert_called_with()
        self.assertEqual(job.upload_path, "jobs/13375/123/abc123.zip")


if __name__ == "__main__":
    unittest.main()
