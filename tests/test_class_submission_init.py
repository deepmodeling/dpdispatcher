import os,sys,json,glob,shutil,uuid,time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import LocalContext
from .context import PBS
from .context import JobStatus
from .context import Submission, Job, Task, Resources
from .sample_class import SampleClass


# print('in', SampleClass.get_sample_empty_submission())

class TestSubmissionInit(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        # self.empty_submission = SampleClass.get_sample_empty_submission()
        # print('TestSubmissionInit.setUp:self.empty_submission.belonging_tasks', self.empty_submission.belonging_tasks)
    
    def test_reigister_task(self):
        empty_submission = SampleClass.get_sample_empty_submission()
        task = SampleClass.get_sample_task()
        # print('TestSubmissionInit.test_reigister_task:self.empty_submission.belonging_tasks', empty_submission.belonging_tasks)
        empty_submission.register_task(task=task)
        # print('7890809', SampleClass.get_sample_empty_submission().belonging_tasks)
        self.assertEqual([task], empty_submission.belonging_tasks)
    
    def test_reigister_task_whether_copy(self):
        empty_submission = SampleClass.get_sample_empty_submission()
        task = SampleClass.get_sample_task()
        empty_submission.register_task(task=task)
        empty_submission2 = SampleClass.get_sample_empty_submission()
        self.assertEqual(empty_submission2.belonging_tasks, [])

          
        # empty_submission = 
        

    # def test_reigister_task_list(self):
    #     pass
# print('out', SampleClass.get_sample_empty_submission())
        # print('TestSubmissionInit.test_register_task_list:task_list', task_list)
        # empty_submission = SampleClass.get_sample_empty_submission()
        # task_list = SampleClass.get_sample_task_list()
        # empty_submission.register_task_list(task_list=task_list)
        # self.empty_submission.register_task_list(task_list=task_list)
        # self.assertEqual(task_list, empty_submission.belonging_tasks)

    # def tesk_generate_jobs(self):
    #     task_list = SampleClass.get_sample_task_list()
    #     self.submission.register_task_list(task_list=task_list)
    #     self.submission.generate_jobs()
    #     task1, task2, task3, task4 = task_list
    #     task_ll = [job.job_task_list for job in self.submission.belonging_jobs]
    #     self.assertEqual([[task3, task2], [task4, task1]], task_ll)

