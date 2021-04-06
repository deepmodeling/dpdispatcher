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

class TestResources(unittest.TestCase) :
    def setUp(self) :
        self.maxDiff = None
        self.resources = SampleClass.get_sample_resources()
        self.resources_dict = SampleClass.get_sample_resources_dict()

    def test_eq(self):
        self.assertEqual(self.resources, SampleClass.get_sample_resources())

    def test_serialize(self):
        self.assertEqual(self.resources.serialize(), self.resources_dict)

    def test_deserialize(self):
        resources = Resources.deserialize(resources_dict=self.resources_dict)
        self.assertEqual(self.resources, resources)
    
    def test_serialize_deserialize(self):
        self.assertEqual(self.resources, Resources.deserialize(resources_dict=self.resources.serialize()))
        
    def test_resources_json(self):
        with open('jsons/resources.json', 'r') as f:
            resources_json_dict = json.load(f)
        self.assertTrue(resources_json_dict, self.resources_dict)
        self.assertTrue(resources_json_dict, self.resources.serialize())
