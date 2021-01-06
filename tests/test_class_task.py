import os,sys,json,glob,shutil,uuid,time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import LocalSession
# from .context import LocalContext
from dpdispatcher.local_context import LocalContext
from .context import JobStatus
from .context import Dispatcher
from .context import setUpModule
from .context import Submission, Job, Task, Resources

task1 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-1', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])

class TestTask(unittest.TestCase) :
    def setUp(self) :
        self.task = Task(command='lmp_serial -i input.lammps', task_work_path='bct-1', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], outlog = 'log', errlog='err', task_need_resources=1)

        self.task_dict={'command': 'lmp_serial -i input.lammps', 'task_work_path': 'bct-1', 'forward_files': ['conf.lmp', 'input.lammps'] , 'backward_files': ['log.lammps'], 'outlog': 'log', 'errlog':'err', 'task_need_resources':1}

    def test_serialize(self):
        self.assertEqual(self.task.serialize(), self.task_dict)

    def test_deserialize(self):
        task = Task.deserialize(task_dict=self.task_dict)
        self.assertTrue(self.task, task)
    
    def test_serialize_deserialize(self):
        self.assertEqual(self.task, Task.deserialize(task_dict=self.task.serialize()))
            
