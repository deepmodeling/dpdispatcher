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
from .sample_class import SampleClass


# print('in', SampleClass.get_sample_empty_submission())

class TestBatchObject(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
    
    def test_lazy_local(self):
        jdata = {
            'batch_type': 'pbs',
            'context_type': 'lazy_local',
            'local_root':'./'
        }
        batch = BatchObject(
            jdata=jdata
        )
        # pylint: disable=maybe-no-member
        self.assertIsInstance(batch.context, LazyLocalContext)

    def test_local(self):
        jdata = {
            'batch_type': 'pbs',
            'context_type': 'local',
            'local_root': './',
            'remote_root': './'
        }
        batch = BatchObject(
            jdata=jdata
        )
        # pylint: disable=maybe-no-member
        self.assertIsInstance(batch.context, LocalContext)

    def test_ssh(self):
        pass
        # jdata = {
        #     'batch_type': 'pbs',
        #     'context_type': 'ssh',
        #     'hostname': 'localhost',
        #     'local_root': './',
        #     "remote_root" : "/home/fengbo/work_path_dpdispatcher_test/",
        #     "username" : "fengbo"
        # }
        # batch = BatchObject(
        #     jdata=jdata
        # )
        # self.assertIsInstance(batch.context, SSHContext)
    def test_key_err(self):
        jdata = {}
        with self.assertRaises(KeyError):
            BatchObject(jdata=jdata)
        
    def test_context_err(self):
        jdata = {
            'context_type' : 'foo',
            'batch_type' : 'pbs'
        }
        with self.assertRaises(RuntimeError):
            BatchObject(jdata=jdata)
        

    def test_pbs(self):
        jdata = {
            'batch_type': 'pbs',
            'context_type': 'lazy_local',
            'local_root':'./'
        }
        batch = BatchObject(
            jdata=jdata
        )
        self.assertIsInstance(batch, PBS)

    def test_lsf(self):
        jdata = {
            'batch_type': 'lsf',
            'context_type': 'lazy_local',
            'local_root':'./'
        }
        batch = BatchObject(
            jdata=jdata
        )
        self.assertIsInstance(batch, LSF)

    def test_slurm(self):
        jdata = {
            'batch_type': 'slurm',
            'context_type': 'lazy_local',
            'local_root':'./'
        }
        batch = BatchObject(
            jdata=jdata
        )
        self.assertIsInstance(batch, Slurm)

    def test_shell(self):
        jdata = {
            'batch_type': 'shell',
            'context_type': 'lazy_local',
            'local_root':'./'
        }
        batch = BatchObject(
            jdata=jdata
        )
        self.assertIsInstance(batch, Shell)