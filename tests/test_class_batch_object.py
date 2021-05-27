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
from .context import Machine
from .context import Batch
from .context import PBS, LSF, Slurm, Shell
from .sample_class import SampleClass


# print('in', SampleClass.get_sample_empty_submission())

class TestBatchObject(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
    
    def test_lazy_local(self):
        batch_dict = {
            'batch_type': 'pbs',
            'context_type': 'lazy_local',
            'local_root':'./'
        }
        batch = Batch.load_from_batch_dict(
            batch_dict=batch_dict
        )
        # pylint: disable=maybe-no-member
        self.assertIsInstance(batch.context, LazyLocalContext)

    def test_local(self):
        batch_dict = {
            'batch_type': 'pbs',
            'context_type': 'local',
            'local_root': './',
            'remote_root': './'
        }
        batch = Batch.load_from_batch_dict(
            batch_dict=batch_dict
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
        # pass
        batch_dict = {}
        with self.assertRaises(KeyError):
            Batch.load_from_batch_dict(batch_dict=batch_dict)

    def test_context_err(self):
        batch_dict = {
            'context_type' : 'foo',
            'batch_type' : 'pbs'
        }
        with self.assertRaises(RuntimeError):
            Batch.load_from_batch_dict(batch_dict=batch_dict)

    def test_pbs(self):
        batch_dict = {
            'batch_type': 'pbs',
            'context_type': 'lazy_local',
            'local_root':'./'
        }
        batch = Batch.load_from_batch_dict(
            batch_dict=batch_dict
        )
        self.assertIsInstance(batch, PBS)

    def test_lsf(self):
        batch_dict = {
            'batch_type': 'lsf',
            'context_type': 'lazy_local',
            'local_root':'./'
        }
        batch = Batch.load_from_batch_dict(
            batch_dict=batch_dict
        )
        self.assertIsInstance(batch, LSF)

    def test_slurm(self):
        batch_dict = {
            'batch_type': 'slurm',
            'context_type': 'lazy_local',
            'local_root':'./'
        }
        batch = Batch.load_from_batch_dict(
            batch_dict=batch_dict
        )
        self.assertIsInstance(batch, Slurm)

    def test_shell(self):
        batch_dict = {
            'batch_type': 'shell',
            'context_type': 'lazy_local',
            'local_root':'./'
        }
        batch = Batch.load_from_batch_dict(
            batch_dict=batch_dict
        )
        self.assertIsInstance(batch, Shell)