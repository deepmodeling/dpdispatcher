# %%
import os
import shutil
import sys
import unittest
import uuid
from unittest.mock import MagicMock

# %%
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
# from .context import LocalSession
from .context import (
    LocalContext,
    _identical_files,
    get_file_md5,
    setUpModule,  # noqa: F401
)

# from .context import dpd


class TestIdFile(unittest.TestCase):
    def test_id(self):
        with open("f0", "w") as fp:
            fp.write("foo")
        with open("f1", "w") as fp:
            fp.write("foo")
        self.assertTrue(_identical_files("f0", "f1"))
        os.remove("f0")
        os.remove("f1")

    def test_diff(self):
        with open("f0", "w") as fp:
            fp.write("foo")
        with open("f1", "w") as fp:
            fp.write("bar")
        self.assertFalse(_identical_files("f0", "f1"))
        os.remove("f0")
        os.remove("f1")


class TestLocalContext(unittest.TestCase):
    def setUp(self):
        self.tmp_local_root = "test_context_dir/"
        self.tmp_remote_root = "tmp_local_context_remote_root/"
        self.local_context = LocalContext(
            local_root=self.tmp_local_root, remote_root=self.tmp_remote_root
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree("tmp_local_context_remote_root/")

    def test_upload_non_exist(self):
        submission_hash = "mock_hash_1"
        task1 = MagicMock(task_work_path="bct-1/", forward_files=["foo.py"])
        submission = MagicMock(
            work_base="0_md/", belonging_tasks=[task1], submission_hash=submission_hash
        )

        self.local_context.bind_submission(submission)

        with self.assertRaises(RuntimeError):
            self.local_context.upload(submission)

    def test_upload(self):
        submission_hash = "mock_hash_2"
        task1 = MagicMock(
            task_work_path="bct-1/",
            forward_files=["input.lammps", "conf.lmp", "some_dir/some_file"],
        )
        task2 = MagicMock(
            task_work_path="bct-2/", forward_files=["input.lammps", "conf.lmp"]
        )
        submission = MagicMock(
            work_base="0_md/",
            belonging_tasks=[task1, task2],
            forward_common_files=["graph.pb", "some_dir/some_file"],
            submission_hash=submission_hash,
        )

        self.local_context.bind_submission(submission)
        self.local_context.upload(submission)

        check_file_list = [
            "bct-1/input.lammps",
            "bct-1/conf.lmp",
            "bct-1/some_dir/some_file",
            "bct-2/input.lammps",
            "bct-2/conf.lmp",
            "graph.pb",
            "some_dir/some_file",
        ]
        for file in check_file_list:
            f1 = os.path.join(self.tmp_local_root, "0_md/", file)
            f2 = os.path.join(self.tmp_remote_root, submission_hash, file)
            self.assertEqual(get_file_md5(f1), get_file_md5(f2), msg=(f1, f2))

    # TODO: support other platforms
    @unittest.skipIf(sys.platform != "linux", "not linux")
    def test_block_call(self):
        submission_hash = "mock_hash_3"
        task1 = MagicMock(
            task_work_path="bct-1/", forward_files=["input.lammps", "conf.lmp"]
        )
        task2 = MagicMock(
            task_work_path="bct-2/", forward_files=["input.lammps", "conf.lmp"]
        )
        submission = MagicMock(
            work_base="0_md/",
            belonging_tasks=[task1, task2],
            submission_hash=submission_hash,
        )
        self.local_context.bind_submission(submission)
        self.local_context.upload(submission)
        # time.sleep(0.01)
        code, stdin, stdout, stderr = self.local_context.block_call("ls")
        self.assertEqual(code, 0)
        self.assertEqual(stdout.readlines(), ["bct-1\n", "bct-2\n"])

        code, stdin, stdout, stderr = self.local_context.block_call("ls a")
        self.assertEqual(code, 2)
        err_msg = stderr.read().decode("utf-8")
        self.assertTrue("ls: cannot access" in err_msg)
        self.assertTrue("No such file or directory\n" in err_msg)

    @unittest.skipIf(sys.platform == "win32", "sleep is not supported on Windows")
    def test_call(self):
        submission_hash = "mock_hash_4"
        submission = MagicMock(
            work_base="0_md/", belonging_tasks=[], submission_hash=submission_hash
        )
        self.local_context.bind_submission(submission)
        self.local_context.upload(submission)

        proc = self.local_context.call("sleep 0.12")
        # in some environment it's not easy to determine which is faster..
        # self.assertFalse(self.local_context.check_finish(proc))
        # time.sleep(0.06)
        # self.assertFalse(self.local_context.check_finish(proc))
        # time.sleep(0.10)
        # wait until terminated, as in some test environments, it's slow to execute commands
        proc.wait(timeout=2)
        self.assertTrue(self.local_context.check_finish(proc))
        r, o, e = self.local_context.get_return(proc)
        self.assertEqual(r, 0)
        self.assertEqual(o.read(), b"")
        self.assertEqual(e.read(), b"")
        # not correct on centos7 aliyun ehpc
        # r,o,e=self.local_context.get_return(proc)
        # self.assertEqual(r, 0)
        # self.assertEqual(o, None)
        # self.assertEqual(e, None)

    def test_file(self):
        submission_hash = "mock_hash_5"
        submission = MagicMock(
            work_base="0_md/", belonging_tasks=[], submission_hash=submission_hash
        )
        self.local_context.bind_submission(submission)
        self.local_context.upload(submission)

        self.assertFalse(self.local_context.check_file_exists("aaa"))
        tmp = str(uuid.uuid4())
        self.local_context.write_file("aaa", tmp)
        self.assertTrue(self.local_context.check_file_exists("aaa"))
        tmp1 = self.local_context.read_file("aaa")
        self.assertEqual(tmp, tmp1)


class TestLocalContextDownload(unittest.TestCase):
    # @classmethod
    # def setUpClass(cls):
    def setUp(self):
        shutil.copytree(src="test_context_dir/", dst="tmp_local_context_download_dir/")
        os.makedirs("tmp_local_context_backfill_dir/0_md/bct-1/")
        os.makedirs("tmp_local_context_backfill_dir/0_md/bct-2/")

        self.tmp_local_root = "tmp_local_context_backfill_dir"
        self.tmp_remote_root = "tmp_local_context_download_dir"
        self.local_context = LocalContext(
            local_root=self.tmp_local_root, remote_root=self.tmp_remote_root
        )

    def tearDown(self):
        shutil.rmtree("tmp_local_context_download_dir/")
        shutil.rmtree("tmp_local_context_backfill_dir/")

    def test_download_trival(self):
        # submission_hash = 'mock_hash_2'
        task1 = MagicMock(
            task_work_path="bct-1/", backward_files=["input.lammps", "conf.lmp"]
        )
        task2 = MagicMock(
            task_work_path="bct-2/", backward_files=["input.lammps", "conf.lmp"]
        )
        submission = MagicMock(
            work_base="0_md/",
            belonging_tasks=[task1, task2],
            backward_common_files=["graph.pb"],
            submission_hash="0_md/",
        )

        self.local_context.bind_submission(submission)

        check_file_list = [
            "bct-1/input.lammps",
            "bct-1/conf.lmp",
            "bct-2/input.lammps",
            "bct-2/conf.lmp",
            "graph.pb",
        ]

        self.local_context.download(submission)

        for file in check_file_list:
            f1 = os.path.join(self.tmp_local_root, "0_md/", file)
            self.assertTrue(os.path.isfile(f1))
            self.assertFalse(os.path.islink(f1))

    def test_download_check_exists(self):
        task1 = MagicMock(task_work_path="bct-1/", backward_files=["foo.py"])
        submission = MagicMock(
            work_base="0_md/",
            belonging_tasks=[task1],
            backward_common_files=["graph.pb"],
            submission_hash="0_md/",
        )
        self.local_context.bind_submission(submission)
        with self.assertRaises(RuntimeError):
            self.local_context.download(submission, check_exists=False)

    def test_download_mark_failure_tag(self):
        task1 = MagicMock(task_work_path="bct-1/", backward_files=["foo.py"])
        submission = MagicMock(
            work_base="0_md/",
            belonging_tasks=[task1],
            backward_common_files=["graph.pb"],
            submission_hash="0_md/",
        )
        self.local_context.bind_submission(submission)
        # with self.assertRaises(RuntimeError):
        self.local_context.download(submission, check_exists=True, mark_failure=True)

        tag_file = os.path.join(
            self.tmp_local_root, "0_md/", "bct-1/", "tag_failure_download_foo.py"
        )
        self.assertTrue(os.path.isfile(tag_file))

    def test_download_replace_old_files(self):
        task1 = MagicMock(task_work_path="bct-1/", backward_files=["input.lammps"])
        submission = MagicMock(
            work_base="0_md/",
            belonging_tasks=[task1],
            backward_common_files=["graph.pb"],
            submission_hash="0_md/",
        )
        # with self.assertRaises(RuntimeError):
        target_file = os.path.join(
            self.tmp_local_root, "0_md/", "bct-1/", "input.lammps"
        )
        with open(target_file, "w") as f:
            f.write("\n")
        md5_old = get_file_md5(target_file)
        self.local_context.bind_submission(submission)
        self.local_context.download(submission)
        md5_new = get_file_md5(target_file)
        self.assertNotEqual(md5_old, md5_new)

    def test_download_symlink(self):
        task1 = MagicMock(
            task_work_path="bct-1/", backward_files=["input.lammps.symlink"]
        )
        submission = MagicMock(
            work_base="0_md/",
            belonging_tasks=[task1],
            backward_common_files=["graph.pb.symlink"],
            submission_hash="0_md/",
        )
        os.symlink(
            os.path.abspath(
                os.path.join(self.tmp_remote_root, "0_md", "bct-1", "input.lammps")
            ),
            os.path.join(self.tmp_remote_root, "0_md", "bct-1", "input.lammps.symlink"),
        )
        os.symlink(
            os.path.abspath(os.path.join(self.tmp_remote_root, "0_md", "graph.pb")),
            os.path.join(self.tmp_remote_root, "0_md", "graph.pb.symlink"),
        )

        self.local_context.bind_submission(submission)
        self.local_context.download(submission)
        self.local_context.clean()
        task_file = os.path.join(
            self.tmp_local_root,
            "0_md",
            "bct-1",
            "input.lammps.symlink",
        )
        common_file = os.path.join(
            self.tmp_local_root,
            "0_md",
            "graph.pb.symlink",
        )
        self.assertTrue(os.path.isfile(task_file))
        self.assertTrue(os.path.isfile(common_file))
