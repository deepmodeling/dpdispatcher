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
        # self.local_context_dict = {
        #     'local_root': './test_shell_trival_dir',
        #     'remote_root': './tmp_shell_trival_dir'
        # }
    
    def test_shell_trival(self):
        # local_context = LocalContext.from_jdata(self.local_context_dict)
        # shell = Shell(local_context)
        machine = Machine.load_from_json_file(json_path='jsons/machine_local_shell.json')
        # resources = machine.resources
        # resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=0, queue_name="CPU", group_size=2) 
        submission = Submission(work_base='parent_dir/', resources=machine.resources,  forward_common_files=['graph.pb'], backward_common_files=[])
        task1 = Task(command='cat example.txt', task_work_path='dir1/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        task2 = Task(command='cat example.txt', task_work_path='dir2/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        task3 = Task(command='cat example.txt', task_work_path='dir3/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        task4 = Task(command='cat example.txt', task_work_path='dir4/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        submission.register_task_list([task1, task2, task3, task4, ])
        submission.generate_jobs()
        submission.bind_batch(batch=machine.batch)
        submission.run_submission(clean=False)

        for dir in ['dir1', 'dir2', 'dir3', 'dir4']:
            f1 = os.path.join('test_shell_trival_dir/', 'parent_dir/', dir, 'example.txt')
            f2 = os.path.join('test_shell_trival_dir/', 'parent_dir/', dir, 'out.txt')
            self.assertEqual(get_file_md5(f1), get_file_md5(f2))

    @classmethod
    def tearDownClass(self):
        shutil.rmtree('tmp_shell_trival_dir/')





