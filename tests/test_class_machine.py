import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"

from .context import (
    PBS,
    Machine,
    setUpModule,  # noqa: F401
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
