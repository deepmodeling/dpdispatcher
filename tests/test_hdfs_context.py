import json
import os
import shutil
import sys
import tarfile
import tempfile
import unittest
from glob import glob
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"

from .context import (
    HDFS,
    HDFSContext,
    Machine,
    setUpModule,  # noqa: F401
)
from .sample_class import SampleClass


class TestHDFSContextDownload(unittest.TestCase):
    """Test download bookkeeping without requiring a Hadoop installation."""

    def test_back_error_uses_relative_copies_without_mutating_submission(self) -> None:
        with tempfile.TemporaryDirectory() as local_root:
            context = HDFSContext.__new__(HDFSContext)
            context.local_root = local_root
            context.remote_root = "/remote/submission"

            task = SimpleNamespace(
                task_work_path="task",
                backward_files=["result.out"],
            )
            submission = SimpleNamespace(
                submission_hash="submission-hash",
                belonging_tasks=[task],
                backward_common_files=["common.out"],
            )
            os.mkdir(os.path.join(local_root, "task"))

            def create_download_archive(_remote: str, destination: str) -> None:
                archive_path = os.path.join(
                    destination, "submission-hash_1_download.tar.gz"
                )
                source_root = os.path.join(local_root, "archive-source")
                os.makedirs(os.path.join(source_root, "task"))
                archive_files = {
                    "task/result.out": "task result",
                    "task/error-task.log": "task error",
                    "common.out": "common result",
                    "error-common.log": "common error",
                }
                for relative_path, content in archive_files.items():
                    source = os.path.join(source_root, relative_path)
                    os.makedirs(os.path.dirname(source), exist_ok=True)
                    with open(source, "w") as stream:
                        stream.write(content)
                with tarfile.open(archive_path, "w:gz") as archive:
                    for relative_path in archive_files:
                        archive.add(
                            os.path.join(source_root, relative_path),
                            arcname=relative_path,
                        )

            with patch.object(
                HDFS, "copy_to_local", side_effect=create_download_archive
            ):
                context.download(submission, back_error=True)

            self.assertEqual(task.backward_files, ["result.out"])
            self.assertEqual(submission.backward_common_files, ["common.out"])
            self.assertTrue(os.path.isfile(os.path.join(local_root, "task/result.out")))
            self.assertTrue(
                os.path.isfile(os.path.join(local_root, "task/error-task.log"))
            )
            self.assertTrue(os.path.isfile(os.path.join(local_root, "common.out")))
            self.assertTrue(
                os.path.isfile(os.path.join(local_root, "error-common.log"))
            )


@unittest.skipIf(not shutil.which("hadoop"), "requires hadoop")
class TestHDFSContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with open("jsons/machine_yarn.json") as f:
            mdata = json.load(f)
        cls.machine = Machine.load_from_dict(mdata["machine"])
        cls.submission = SampleClass.get_sample_submission()
        cls.submission.bind_machine(cls.machine)
        cls.submission_hash = cls.submission.submission_hash

    def setUp(self) -> None:
        self.context = self.__class__.machine.context

    def test_0_hdfs_context(self) -> None:
        self.assertIsInstance(self.context, HDFSContext)

    def test_1_upload(self) -> None:
        self.context.upload(self.__class__.submission)

    def test_2_fake_run(self) -> None:
        rfile_tgz = (
            self.context.remote_root
            + "/"
            + self.context.submission.submission_hash
            + "_upload.tgz"
        )
        tmp_dir = "./tmp_fake_run"
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.mkdir(tmp_dir)
        self.assertTrue(HDFS.copy_to_local(rfile_tgz, tmp_dir))

        cwd = os.getcwd()
        os.chdir(tmp_dir)
        tgz_file_list = glob("*_upload.tgz")
        for tgz in tgz_file_list:
            with tarfile.open(tgz, "r:gz") as tar:
                tar.extractall()
            os.remove(tgz)

        file_list = [
            "bct-1/log.lammps",
            "bct-2/log.lammps",
            "bct-3/log.lammps",
            "bct-4/log.lammps",
        ]
        for fname in file_list:
            with open(fname, "w") as fp:
                fp.write("# mock log")

        file_list = glob("./*")
        download_tgz = self.context.submission.submission_hash + "_1_download.tar.gz"
        with tarfile.open(download_tgz, "w:gz", dereference=True) as tar:
            for ii in file_list:
                tar.add(ii)
        ret, _ = HDFS.copy_from_local(download_tgz, self.context.remote_root)
        self.assertTrue(ret)
        os.chdir(cwd)
        shutil.rmtree(tmp_dir)

    def test_3_download(self) -> None:
        self.context.download(self.__class__.submission)
        file_list = [
            "bct-1/log.lammps",
            "bct-2/log.lammps",
            "bct-3/log.lammps",
            "bct-4/log.lammps",
        ]
        for fname in file_list:
            self.assertTrue(
                os.path.isfile(os.path.join(self.context.local_root, fname))
            )
            os.remove(os.path.join(self.context.local_root, fname))
