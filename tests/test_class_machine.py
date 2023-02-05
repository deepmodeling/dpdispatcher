import glob
import json
import os
import shutil
import sys
import time
import unittest
import uuid
from socket import gaierror
from unittest.mock import MagicMock, PropertyMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
from dargs.dargs import ArgumentKeyError

from .context import (
    LSF,
    PBS,
    BaseContext,
    DistributedShell,
    HDFSContext,
    JobStatus,
    LazyLocalContext,
    LocalContext,
    Machine,
    Shell,
    Slurm,
    SSHContext,
    dargs,
)
from .sample_class import SampleClass


class TestMachineInit(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_machine_serialize_deserialize(self):
        pbs = SampleClass.get_sample_pbs_local_context()
        self.assertEqual(pbs, Machine.deserialize(pbs.serialize()))

    def test_machine_load_from_dict(self):
        pbs = SampleClass.get_sample_pbs_local_context()
        self.assertEqual(pbs, PBS.load_from_dict(pbs.serialize()))
