import os,sys,json,glob,shutil,uuid,time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
# from .context import LocalContext
from dpdispatcher.local_context import LocalContext
from .context import JobStatus
# from .context import Dispatcher
from .context import setUpModule
from .context import Submission, Job, Task, Resources
from .sample_class import SampleClass


class TestTask(unittest.TestCase) :
    def setUp(self) :
        self.task = SampleClass.get_sample_task()
        self.task_dict = SampleClass.get_sample_task_dict()

    def test_serialize(self):
        self.assertEqual(self.task.serialize(), self.task_dict)

    def test_deserialize(self):
        task = Task.deserialize(task_dict=self.task_dict)
        self.assertTrue(task, self.task)
    
    def test_serialize_deserialize(self):
        self.assertEqual(Task.deserialize(task_dict=self.task.serialize()), self.task)

    def test_task_json(self):
        with open('jsons/task.json', 'r') as f:
            task_json_dict = json.load(f)
        self.assertTrue(task_json_dict, self.task_dict)
        self.assertTrue(task_json_dict, self.task.serialize())
            
