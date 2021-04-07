import os,sys,json,glob,shutil,uuid,time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import LocalContext
from .context import PBS
from .context import JobStatus
from .context import LazyLocalContext, LocalContext, SSHContext
from .context import Submission, Job, Task, Resources
from .context import BatchObject, Machine
from .context import PBS, LSF, Slurm, Shell
from .context import Machine
from .sample_class import SampleClass


# print('in', SampleClass.get_sample_empty_submission())

class TestMachine(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        with open('jsons/machine.json', 'r') as f:
            self.machine_dict = json.load(f)
        # self.machine = Machine.load_from_json_file('jsons/machine.json')
    
    def test_load_from_machine_dict(self):
        machine = Machine.load_from_machine_dict(self.machine_dict)

    def test_load_from_json_file(self):
        machine = Machine.load_from_json_file('jsons/machine.json')

    def test_load_from_yaml_file(self):
        pass

    def test_load_from_machine_config(self):
        machine_config = {
            "machine_center_json":"jsons/machine_center.json",
            "batch_name": "batch_lazy_pbs",
            "resources_name": "resources_gpu"
        }
        machine = Machine.load_from_machine_config(
            machine_config=machine_config
        )

