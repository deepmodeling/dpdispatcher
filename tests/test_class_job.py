import os,sys,json,glob,shutil,uuid,time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
# from .context import LocalSession
# from .context import LocalContext
from .context import LocalContext
from .context import PBS
from .context import JobStatus
from .context import setUpModule
from .context import Submission, Job, Task, Resources
from .sample_class import SampleClass

class TestJob(unittest.TestCase) :
    def setUp(self) :
        self.job = SampleClass.get_sample_job()

        self.submission2 = Submission.submission_from_json('jsons/submission.json')
        self.job2 = self.submission2.belonging_jobs[0]

    def test_eq(self):
        self.assertTrue(self.job == self.job2)

    def test_get_hash(self):
        self.assertEqual(self.job.get_hash(), self.job2.get_hash())
        # self.assertEqual(self.submission, self.submission2)

    def test_serialize_deserialize(self):
        self.assertEqual(self.job, Job.deserialize(job_dict=self.job.serialize()))

    def test_static_serialize(self):
        self.assertNotIn('job_state', list(self.job.serialize(if_static=True).values())[0] )
        self.assertNotIn('job_id', list(self.job.serialize(if_static=True).values())[0] )
        self.assertNotIn('fail_count', list(self.job.serialize(if_static=True).values())[0] )
    
    def test_get_job_state(self):
        pass

    def test_handle_unexpected_job_state(self):
        pass

    def test_register_job_id(self):
        pass

    def test_submit_job(self):
        pass

    def test_job_to_json(self):
        pass
    
   #  def test_content_serialize(self):
   #      self.assertEqual(self.job.content_serialize(), self.job.serialize()[self.job.job_hash])
            
