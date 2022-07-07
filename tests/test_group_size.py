"""Test `Submission.generate_jobs` with different group size."""

import os
import sys
import json
from unittest import TestCase
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import Machine, Resources, Task, Submission

# 99 tasks in total
# group_size - expected_ntasks
group_ntasks_pairs = [
    (1, 99),
    (3, 33),
    (10, 10),
    (100, 1),
    (0, 1),
]

cwd = Path(__file__).parent
with open(cwd / "jsons" / "machine.json") as f:
    j_machine = json.load(f)['machine']
with open(cwd / "jsons" / "resources.json") as f:
    j_resources = json.load(f)
with open(cwd / "jsons" / "task.json") as f:
    j_task = json.load(f)


class TestGroupSize(TestCase):
    def test_works_as_expected(self):
        for group_size, ntasks in group_ntasks_pairs:
            with self.subTest(group_size):
                machine = Machine.load_from_dict(j_machine)
                j_resources['group_size'] = group_size
                resources = Resources.load_from_dict(j_resources)
                tasks = [Task.load_from_dict(j_task) for _ in range(99)]
                submission = Submission(".", machine, resources, task_list=tasks)
                submission.generate_jobs()
                self.assertEqual(len(submission.belonging_jobs), ntasks)
