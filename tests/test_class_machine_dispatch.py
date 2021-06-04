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
from .context import LSF, Slurm, PBS, Shell
from .context import Machine
from .context import dargs
from dargs.dargs import ArgumentKeyError

# print('in', SampleClass.get_sample_empty_submission())

class TestMachineDispatch(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_lazy_local(self):
        machine_dict = {
            'batch_type': 'PBS',
            'context_type': 'LazyLocalContext',
            'local_root':'./'
        }
        machine = Machine.load_from_dict(
            machine_dict=machine_dict
        )
        # pylint: disable=maybe-no-member
        self.assertIsInstance(machine.context, LazyLocalContext)

    def test_local(self):
        machine_dict = {
            'batch_type': 'PBS',
            'context_type': 'LocalContext',
            'local_root': './',
            'remote_root': './'
        }
        machine = Machine.load_from_dict(
            machine_dict=machine_dict
        )
        # pylint: disable=maybe-no-member
        self.assertIsInstance(machine.context, LocalContext)

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
        machine_dict = {}
        with self.assertRaises(KeyError):
            Machine.load_from_dict(machine_dict=machine_dict)

    def test_context_err(self):
        machine_dict = {
            'batch_type': 'PBS',
            'context_type': 'foo'
        }
        # with self.assertRaises(KeyError):
        with self.assertRaises(KeyError):
            Machine.load_from_dict(machine_dict=machine_dict)

    def test_pbs(self):
        machine_dict = {
            'batch_type': 'PBS',
            'context_type': 'LazyLocalContext',
            'local_root':'./'
        }
        machine = Machine.load_from_dict(
            machine_dict=machine_dict
        )
        self.assertIsInstance(machine, PBS)

    def test_lsf(self):
        machine_dict = {
            'batch_type': 'LSF',
            'context_type': 'LazyLocalContext',
            'local_root':'./'
        }
        machine = Machine.load_from_dict(
            machine_dict=machine_dict
        )
        self.assertIsInstance(machine, LSF)

    def test_slurm(self):
        machine_dict = {
            'batch_type': 'Slurm',
            'context_type': 'LazyLocalContext',
            'local_root':'./'
        }
        machine = Machine.load_from_dict(
            machine_dict=machine_dict
        )
        self.assertIsInstance(machine, Slurm)

    def test_shell(self):
        machine_dict = {
            'batch_type': 'Shell',
            'context_type': 'LazyLocalContext',
            'local_root':'./'
        }
        machine = Machine.load_from_dict(
            machine_dict=machine_dict
        )
        self.assertIsInstance(machine, Shell)