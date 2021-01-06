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
from .sample_class import SampleClass

class TestSubmissionInit(unittest.TestCase):
    def setUp(self):
        self.submission = SampleClass.get_sample_empty_submission()
    
    def test_reigister_task(self):
        task = SampleClass.get_sample_task()
        self.submission.register_task(task=task)
        self.assertIn(task, self.submission.belonging_tasks)

    def test_reigister_task_list(self):
        task_list = SampleClass.get_sample_task_list()
        self.submission.register_task_list(task_list=task_list)
        self.assertEqual(task_list, self.submission.belonging_tasks)

    def tesk_generate_jobs(self):
        task_list = SampleClass.get_sample_task_list()
        self.submission.register_task_list(task_list=task_list)
        self.submission.generate_jobs()
        task1, task2, task3, task4 = task_list
        task_ll = [job.job_task_list for job in self.submission.belonging_jobs]
        self.assertEqual([[task3, task2], [task4, task1]], task_ll)

class TestSubmission(unittest.TestCase):
    def setUp(self) :
        pbs = SampleClass.get_sample_pbs_local_context()

        self.submission = SampleClass.get_sample_submission()

        self.submission.bind_batch(batch=pbs)

        self.submission2 = Submission.submission_from_json('jsons/submission.json')
        # self.submission2 = Submission.submission_from_json('jsons/submission.json')
    
    def test_serialize_deserialize(self):
        self.assertEqual(self.submission, Submission.deserialize(submission_dict=self.submission.serialize()))

    def test_get_hash(self):
        pass

    def test_bind_batch(self):
        self.assertIsNotNone(self.submission.batch.context.submission)
        for job in self.submission.belonging_jobs:
            self.assertIsNotNone(job.batch)

    def test_get_submision_state(self):
        pass

    def test_handle_unexpected_submission_state(self):
        pass

    def test_submit_submission(self):
        pass

    def test_upload_jobs(self):
        pass

    def test_download_jobs(self):
        pass

    def test_submission_to_json(self):
        pass

    def test_submission_from_json(self):
        self.assertTrue(self.submission == self.submission2)

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

    def test_try_recover_from_json(self):
        pass
        # self.submission_to_json()
