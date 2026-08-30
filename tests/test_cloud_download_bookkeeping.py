import tempfile
import unittest
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

    def test_archive_unzip_wrappers_delegate_to_safe_extractors(self) -> None:
        """Delegate both cloud ZIP wrappers to the shared safe extractor."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = f"{temp_dir}/empty.zip"
            with ZipFile(archive_path, "w"):
                pass
            with (
                patch(
                    "dpdispatcher.contexts.openapi_context.safe_extract_zip",
                    return_value={"openapi.txt"},
                ) as openapi_extract,
                patch.object(
                    legacy_zip_file,
                    "safe_extract_zip",
                    return_value={"legacy.txt"},
                ) as legacy_extract,
            ):
                self.assertEqual(openapi_unzip_file(archive_path), {"openapi.txt"})
                self.assertEqual(legacy_unzip_file(archive_path), {"legacy.txt"})

            openapi_extract.assert_called_once()
            legacy_extract.assert_called_once()


if __name__ == "__main__":
    unittest.main()
