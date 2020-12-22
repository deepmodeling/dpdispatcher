import os,sys,json,glob,shutil,uuid,time
import unittest

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

class TestJob(unittest.TestCase) :
    def setUp(self) :
        resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=1, queue_name="V100_8_32", group_size=2) 
        self.submission = Submission(work_base='0_md/', resources=resources,  forward_common_files=['graph.pb'], backward_common_files=[]) #,  batch=PBS)
        self.task1 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-1', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
        self.task2 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-2', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
        self.task3 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-3', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
        self.task4 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-4', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
        self.submission.register_task_list([self.task1, self.task2, self.task3, self.task4])

        self.submission.generate_jobs()
        self.job = self.submission.belonging_jobs[0]
    
        self.submission2 = Submission.submission_from_json('jsons/submission.json')
        for job in self.submission2.belonging_jobs:
            job.job_state = JobStatus.unsubmitted
            job.fail_count = 0
            job.job_id =  ""

        self.job2 = self.submission2.belonging_jobs[0]

    def test_eq(self):
        self.assertTrue(self.job == self.job2)

    def test_job_hash(self):
        self.assertEqual(self.job.get_hash(), self.job2.get_hash())
        # self.assertEqual(self.submission, self.submission2)

    def test_serialize_deserialize(self):
        self.assertEqual(self.job, Job.deserialize(job_dict=self.job.serialize()))
     
   #  def test_content_serialize(self):
   #      self.assertEqual(self.job.content_serialize(), self.job.serialize()[self.job.job_hash])
            
