# from dpdispatcher.batch_object import BatchObject
# from dpdispatcher.batch import Batch
import sys, os, shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import Submission, Job, Task, Resources
from .context import Shell
from .context import LocalContext
from .context import get_file_md5
from .context import Machine

import unittest
import json


class TestShellTrival(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        # self.local_context_dict = {
        #     'local_root': './test_shell_trival_dir',
        #     'remote_root': './tmp_shell_trival_dir'
        # }
    
    def test_shell_trival(self):
        with open('jsons/machine_local_shell.json', 'r') as f:
            machine_dict = json.load(f)

        machine = Machine.load_from_dict(machine_dict['machine'])
        resources = Resources.load_from_dict(machine_dict['resources'])

        task1 = Task(command='cat example.txt', task_work_path='dir1/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        task2 = Task(command='cat example.txt', task_work_path='dir2/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        task3 = Task(command='cat example.txt', task_work_path='dir3/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        task4 = Task(command='cat example.txt', task_work_path='dir4/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        task_list = [task1, task2, task3, task4]

        submission = Submission(work_base='parent_dir/',
            machine=machine,
            resources=resources,
            forward_common_files=['graph.pb'],
            backward_common_files=[],
            task_list=task_list
        )
        submission.run_submission(clean=False)

        for dir in ['dir1', 'dir2', 'dir3', 'dir4']:
            f1 = os.path.join('test_shell_trival_dir/', 'parent_dir/', dir, 'example.txt')
            f2 = os.path.join('test_shell_trival_dir/', 'parent_dir/', dir, 'out.txt')
            self.assertEqual(get_file_md5(f1), get_file_md5(f2))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree('tmp_shell_trival_dir/')





