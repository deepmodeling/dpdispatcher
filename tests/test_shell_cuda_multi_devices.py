import sys, os, shutil, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import Submission, Job, Task, Resources
from .context import Shell
from .context import LocalContext
from .context import get_file_md5
from .context import Machine

import unittest

class TestShellCudaMultiDevices(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_shell_cuda_multi_devices(self):
        with open('jsons/machine_if_cuda_multi_devices.json', 'r') as f:
            machine_dict = json.load(f)
        machine = Machine.load_from_dict(machine_dict['machine'])
        resources = Resources.load_from_dict(machine_dict['resources'])

        task_list = []
        for ii in range(16):
            task = Task(command=f"echo dpdispatcher_unittest_{ii}", task_work_path='./', forward_files=[], backward_files=[], outlog='out.txt')
            task_list.append(task)

        submission = Submission(work_base='test_dir/',
            machine=machine,
            resources=resources,
            forward_common_files=['test.txt'],
            backward_common_files=['out.txt'],
            task_list=task_list
        )
        submission.run_submission(clean=False)

        for ii in ['test.txt']:
            f1 = os.path.join('test_if_cuda_multi_devices/', 'test_dir/', ii)
            f2 = os.path.join('tmp_if_cuda_multi_devices/', submission.submission_hash, ii)
            self.assertEqual(get_file_md5(f1), get_file_md5(f2))

        self.assertTrue(os.path.isfile('test_if_cuda_multi_devices/test_dir/out.txt'))

    @classmethod
    def tearDownClass(cls):
        # pass
        shutil.rmtree('tmp_if_cuda_multi_devices/')





