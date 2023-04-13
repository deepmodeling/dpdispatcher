import json
import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
import unittest

from .context import (
    Machine,
    Resources,
    Submission,
    Task,
    get_file_md5,
    setUpModule,  # noqa: F401
)


@unittest.skipIf(sys.platform == "win32", "Shell is not supported on Windows")
class TestShellCudaMultiDevices(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_shell_cuda_multi_devices(self):
        with open("jsons/machine_if_cuda_multi_devices.json") as f:
            machine_dict = json.load(f)
        machine = Machine.load_from_dict(machine_dict["machine"])
        resources = Resources.load_from_dict(machine_dict["resources"])

        task_list = []
        for ii in range(16):
            task = Task(
                command=f"echo dpdispatcher_unittest_{ii}",
                task_work_path="./",
                forward_files=[],
                backward_files=[],
                outlog="out.txt",
            )
            task_list.append(task)

        submission = Submission(
            work_base="test_dir/",
            machine=machine,
            resources=resources,
            forward_common_files=["test.txt"],
            backward_common_files=["out.txt"],
            task_list=task_list,
        )
        submission.run_submission(clean=False)

        for ii in ["test.txt"]:
            f1 = os.path.join("test_if_cuda_multi_devices/", "test_dir/", ii)
            f2 = os.path.join(
                "tmp_if_cuda_multi_devices/", submission.submission_hash, ii
            )
            self.assertEqual(get_file_md5(f1), get_file_md5(f2))

        self.assertTrue(os.path.isfile("test_if_cuda_multi_devices/test_dir/out.txt"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree("tmp_if_cuda_multi_devices/")
        # pass
