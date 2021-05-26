import sys, os, shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import Submission, Job, Task, Resources
from .context import Shell
from .context import LocalContext
from .context import get_file_md5
from .context import Machine

import unittest

class TestShellTrival(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_shell_trival(self):
        machine = Machine.load_from_json_file(json_path='jsons/machine.if_cuda_multi_devices.json')
        submission = Submission(work_base='test_dir/', resources=machine.resources,  forward_common_files=['test.log'], backward_common_files=['out.txt'])
        task_list = []
        for ii in range(16):
            task = Task(command=f"echo dpdispatcher_unittest_{ii}", task_work_path='./', forward_files=[], backward_files=[], outlog='out.txt')
            task_list.append(task)
        submission.register_task_list(task_list=task_list)
        submission.bind_batch(batch=machine.batch)
        submission.run_submission(clean=False)

        # for dir in ['dir1', 'dir2', 'dir3', 'dir4']:
        #     f1 = os.path.join('test_shell_trival_dir/', 'parent_dir/', dir, 'example.txt')
        #     f2 = os.path.join('test_shell_trival_dir/', 'parent_dir/', dir, 'out.txt')
        #     self.assertEqual(get_file_md5(f1), get_file_md5(f2))

    @classmethod
    def tearDownClass(self):
        pass
        # shutil.rmtree('tmp_if_cuda_multi_devices/')





