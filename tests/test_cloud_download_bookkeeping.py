import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

from dpdispatcher.contexts.dp_cloud_server_context import BohriumContext
from dpdispatcher.contexts.openapi_context import OpenAPIContext
from dpdispatcher.contexts.openapi_context import unzip_file as openapi_unzip_file
from dpdispatcher.utils.dpcloudserver import zip_file as legacy_zip_file
from dpdispatcher.utils.dpcloudserver.zip_file import unzip_file as legacy_unzip_file


class TestCloudDownloadBookkeeping(unittest.TestCase):
    """Exercise archive manifest bookkeeping in cloud download contexts."""

    def test_legacy_context_records_extracted_files(self) -> None:
        """Record files extracted by the legacy Bohrium context."""
        context = BohriumContext.__new__(BohriumContext)
        with tempfile.TemporaryDirectory() as local_root:
            context.local_root = local_root
            context.remote_profile = {}
            context.api = MagicMock()
            context.api.get_job_detail.return_value = {
                "id": 123,
                "resultUrl": "https://example.test/result.zip",
                "status": 2,
            }
            job = SimpleNamespace(job_id="123:job_group_id:group", job_hash="job-hash")
            submission = SimpleNamespace(belonging_jobs=[job])

            with (
                patch.object(
                    context,
                    "_check_if_job_has_already_downloaded",
                    return_value=False,
                ),
                patch.object(context, "_backup"),
                patch.object(context, "_clean_backup"),
                patch.object(
                    legacy_zip_file,
                    "unzip_file",
                    return_value={"task/result.txt"},
                ) as unzip,
            ):
                self.assertTrue(context.download(submission))

            unzip.assert_called_once()
            self.assertEqual(context.last_downloaded_files, {"task/result.txt"})

    def test_openapi_context_records_extracted_files(self) -> None:
        """Record files extracted by the OpenAPI Bohrium context."""
        context = OpenAPIContext.__new__(OpenAPIContext)
        with tempfile.TemporaryDirectory() as local_root:
            context.local_root = local_root
            context.remote_profile = {}
            context.job = MagicMock()
            context.storage = MagicMock()
            context.job.detail.return_value = {
                "id": "job-1",
                "resultUrl": "https://example.test/result.zip",
                "status": 2,
            }
            job = SimpleNamespace(job_id="job-1", job_hash="job-hash")
            submission = SimpleNamespace(belonging_jobs=[job])

            with (
                patch.object(
                    context,
                    "_check_if_job_has_already_downloaded",
                    return_value=False,
                ),
                patch.object(context, "_backup"),
                patch.object(context, "_clean_backup"),
                patch(
                    "dpdispatcher.contexts.openapi_context.unzip_file",
                    return_value={"task/result.txt"},
                ) as unzip,
            ):
                self.assertTrue(context.download(submission))

            unzip.assert_called_once()
            self.assertEqual(context.last_downloaded_files, {"task/result.txt"})

    def test_cloud_contexts_share_the_archive_unzip_helper(self) -> None:
        """Both cloud contexts use the same safe ZIP extractor implementation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = f"{temp_dir}/empty.zip"
            with ZipFile(archive_path, "w"):
                pass
            with patch.object(
                legacy_zip_file,
                "safe_extract_zip",
                return_value={"shared.txt"},
            ) as extractor:
                self.assertEqual(openapi_unzip_file(archive_path), {"shared.txt"})
                self.assertEqual(legacy_unzip_file(archive_path), {"shared.txt"})

            self.assertEqual(extractor.call_count, 2)

    def test_cloud_metadata_file_operations_use_safe_local_paths(self) -> None:
        """Both cloud contexts share the same atomic metadata-file contract."""
        for context_class, module_name in (
            (BohriumContext, "dpdispatcher.contexts.dp_cloud_server_context"),
            (OpenAPIContext, "dpdispatcher.contexts.openapi_context"),
        ):
            with (
                self.subTest(context=context_class.__name__),
                tempfile.TemporaryDirectory() as temp_dir,
            ):
                context = context_class.__new__(context_class)
                context.local_root = temp_dir
                context.remote_profile = {}
                context.submission = SimpleNamespace(submission_hash="submission")
                with patch(f"{module_name}.DP_CLOUD_SERVER_HOME_DIR", temp_dir):
                    self.assertTrue(context.write_file("state.txt", "ready"))
                    self.assertEqual(context.read_file("state.txt"), "ready")
                    self.assertTrue(context.check_file_exists("state.txt"))
                    local_file = context.write_local_file("local.txt", "local")
                    with open(local_file, encoding="utf-8") as stream:
                        self.assertEqual(stream.read(), "local")
                    Path(temp_dir, "submission.json").write_text("{}", encoding="utf-8")
                    self.assertTrue(context.clean())
                    self.assertFalse(Path(temp_dir, "submission.json").exists())


if __name__ == "__main__":
    unittest.main()
