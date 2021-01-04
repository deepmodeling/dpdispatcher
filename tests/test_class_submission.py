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


class TestSubmission(unittest.TestCase) :
    def setUp(self) :
        local_session = LocalSession({'work_path':'test_work_path/'})
        local_context = LocalContext(local_root='test_pbs_dir/', work_profile=local_session)
        pbs = PBS(context=local_context)

        resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=1, queue_name="V100_8_32", group_size=2, if_cuda_multi_devices=True) 
        self.submission = Submission(work_base='0_md/', resources=resources,  forward_common_files=['graph.pb'], backward_common_files=['submission.json']) #,  batch=PBS)
        self.task1 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-1/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=1)
        self.task2 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-2/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.25)
        self.task3 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-3/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.25)
        self.task4 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-4/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.5)
    
        self.submission.register_task_list([self.task1, self.task2, self.task3, ])
        self.submission.register_task(self.task4)

        self.submission.generate_jobs()
        self.submission.bind_batch(batch=pbs)

        self.submission2 = Submission.submission_from_json('jsons/submission.json')
        for job in self.submission2.belonging_jobs:
            job.job_state = JobStatus.unsubmitted
            job.fail_count = 0
            job.job_id =  ""
        # self.submission2 = Submission.submission_from_json('jsons/submission.json')
        
    def test_submision_to_json(self):
        self.submission.submission_to_json()

    def test_submission_from_json(self):
        self.assertTrue(self.submission == self.submission2)

    def test_generate_jobs(self):
        task_ll = [job.job_task_list for job in self.submission.belonging_jobs]
        self.assertEqual([[self.task3, self.task2], [self.task4, self.task1]], task_ll)

    def test_serialize_deserialize(self):
        # self.submission.register_task_list([self.task1, self.task2, self.task3, self.task4, ])
        # self.submission.generate_jobs()
        self.assertEqual(self.submission, Submission.deserialize(submission_dict=self.submission.serialize()))
        # self.submission.generate_jobs()


    @patch('dpdispatcher.Submission.submission_to_json')
    @patch('dpdispatcher.Submission.get_submission_state')
    def test_check_all_finished(self, patch_get_submission_state, patch_submission_to_json):
        patch_get_submission_state = MagicMock(return_value=None)
        patch_submission_to_json = MagicMock(return_value=None)

        self.submission.belonging_jobs[0].job_state = JobStatus.running
        self.submission.belonging_jobs[1].job_state = JobStatus.waiting
        self.assertFalse(self.submission.check_all_finished())

        self.submission.belonging_jobs[0].job_state = JobStatus.finished
        self.submission.belonging_jobs[1].job_state = JobStatus.unsubmitted
        self.assertFalse(self.submission.check_all_finished())
        
        self.submission.belonging_jobs[0].job_state = JobStatus.completing
        self.submission.belonging_jobs[1].job_state = JobStatus.finished
        self.assertFalse(self.submission.check_all_finished())

        self.submission.belonging_jobs[0].job_state = JobStatus.finished
        self.submission.belonging_jobs[1].job_state = JobStatus.unknown
        self.assertFalse(self.submission.check_all_finished())

        self.submission.belonging_jobs[0].job_state = JobStatus.finished
        self.submission.belonging_jobs[1].job_state = JobStatus.finished
        self.assertTrue(self.submission.check_all_finished())

    def test_check_bind_batch(self):
        pass  
 
    def test_try_recover_from_json(self):
        pass
        # self.submission_to_json()
      
