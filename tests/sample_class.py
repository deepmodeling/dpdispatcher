import os,sys,json,glob,shutil,uuid,time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import LocalSession
# from .context import LocalContext
from dpdispatcher.local_context import LocalContext
from .context import PBS
from .context import JobStatus
from .context import Dispatcher
from .context import setUpModule
from .context import Submission, Job, Task, Resources

# class TestSubmissionInit(unittest.TestCase):
#     def setUp(self):
#         pass
class SampleClass(object):
    @classmethod
    def get_sample_resources(cls):
        resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=1, queue_name="V100_8_32", group_size=2, if_cuda_multi_devices=True) 
        return resources
    
    @classmethod
    def get_sample_task(cls):
        task = Task(command='lmp_serial -i input.lammps', task_work_path='bct-1/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=1)
        return task
        
    @classmethod
    def get_sample_task_list(cls):
        task1 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-1/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=1)
        task2 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-2/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.25)
        task3 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-3/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.25)
        task4 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-4/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.5)
        task_list = [task1, task2, task3, task4]
        return task_list
        
    @classmethod
    def get_sample_empty_submission(cls):
        resources = cls.get_sample_resources()
        submission = Submission(work_base='0_md/', resources=resources,  forward_common_files=['graph.pb'], backward_common_files=[]) #,  batch=PBS)
        return submission 
    
    @classmethod
    def get_sample_submission(cls):
        submission = cls.get_sample_empty_submission()
        task_list = cls.get_sample_task_list()
        submission.register_task_list(task_list)
        submission.generate_jobs()
        return submission 
    
