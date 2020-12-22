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

class TestResources(unittest.TestCase) :
    def setUp(self) :
        self.resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=1, queue_name="V100_8_32", group_size=2, if_cuda_multi_devices=False) 

        self.resources_dict={'number_node': 1, 'cpu_per_node':4, 'gpu_per_node':1, 'queue_name':'V100_8_32', 'group_size':2, 'if_cuda_multi_devices':False}

    def test_serialize(self):
        self.assertEqual(self.resources.serialize(), self.resources_dict)

    def test_deserialize(self):
        resources = Resources.deserialize(resources_dict=self.resources_dict)
        self.assertEqual(self.resources, resources)
    
    def test_serialize_deserialize(self):
        self.assertEqual(self.resources, Resources.deserialize(resources_dict=self.resources.serialize()))
     
    def test_eq(self):
        self.assertNotEqual(self.resources, Resources(number_node=4, cpu_per_node=2, gpu_per_node=4, queue_name="V100_12_92", group_size=1))
            
