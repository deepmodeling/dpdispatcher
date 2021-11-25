import os,sys,json,glob,shutil,uuid,time
from socket import gaierror
import unittest
from unittest.mock import MagicMock, patch, PropertyMock


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import LocalContext
from .context import BaseContext
from .context import PBS
from .context import JobStatus
from .context import LazyLocalContext, LocalContext, SSHContext
from .context import LSF, Slurm, PBS, Shell
from .context import Machine
from .context import dargs
from .context import DistributedShell, HDFSContext
from .sample_class import SampleClass
from dargs.dargs import ArgumentKeyError

class TestMachineInit(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
    
    def test_machine_serialize_deserialize(self):
        pbs = SampleClass.get_sample_pbs_local_context()
        self.assertEqual(pbs, Machine.deserialize(pbs.serialize()))

    def test_machine_load_from_dict(self):
        pbs = SampleClass.get_sample_pbs_local_context()
        self.assertEqual(pbs, PBS.load_from_dict(pbs.serialize()))
