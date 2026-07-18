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

    def test_default_file_lists_are_independent(self):
        first = Task(command="true", task_work_path=".")
        second = Task(command="true", task_work_path=".")

        first.forward_files.append("input.txt")
        first.backward_files.append("output.txt")

        self.assertEqual(second.forward_files, [])
        self.assertEqual(second.backward_files, [])

    def test_input_file_lists_are_copied(self):
        forward_files = ["input.txt"]
        backward_files = ["output.txt"]
        task = Task(
            command="true",
            task_work_path=".",
            forward_files=forward_files,
            backward_files=backward_files,
        )

        forward_files.append("later-input.txt")
        backward_files.append("later-output.txt")

        self.assertEqual(task.forward_files, ["input.txt"])
        self.assertEqual(task.backward_files, ["output.txt"])
        self.assertEqual(task.task_hash, task.get_hash())

        task.forward_files.append("internal-input.txt")
        task.backward_files.append("internal-output.txt")
        self.assertEqual(forward_files, ["input.txt", "later-input.txt"])
        self.assertEqual(backward_files, ["output.txt", "later-output.txt"])
