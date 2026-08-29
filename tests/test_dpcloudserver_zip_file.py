import inspect
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from dpdispatcher.utils.dpcloudserver.zip_file import zip_file_list


class TestZipFileList(unittest.TestCase):
    def test_file_list_default_is_none(self):
        default = inspect.signature(zip_file_list).parameters["file_list"].default
        self.assertIsNone(default)

    def test_omitted_file_list_creates_empty_archive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = zip_file_list(temp_dir, "empty.zip")

            with ZipFile(archive) as zip_obj:
                self.assertEqual(zip_obj.namelist(), [])

    def test_explicit_patterns_are_not_modified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "input.txt").write_text("input")
            patterns = ["*.txt"]

            archive = zip_file_list(temp_dir, "inputs.zip", patterns)

            self.assertEqual(patterns, ["*.txt"])
            with ZipFile(archive) as zip_obj:
                self.assertEqual(zip_obj.namelist(), ["input.txt"])


if __name__ == "__main__":
    unittest.main()
