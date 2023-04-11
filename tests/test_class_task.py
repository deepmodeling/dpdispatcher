import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
# from .context import LocalContext

# from .context import Dispatcher
from .context import (
    Task,
    setUpModule,  # noqa: F401
)
from .sample_class import SampleClass


class TestTask(unittest.TestCase):
    def setUp(self):
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
        with open("jsons/task.json") as f:
            task_json_dict = json.load(f)
        self.assertTrue(task_json_dict, self.task_dict)
        self.assertTrue(task_json_dict, self.task.serialize())

    def test_repr(self):
        task_repr = repr(self.task)
        print("debug:", task_repr, self.task_dict)
        self.assertEqual(task_repr, str(self.task_dict))
