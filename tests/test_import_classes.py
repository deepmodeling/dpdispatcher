import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
from .context import (
    dpdispatcher,
    setUpModule,  # noqa: F401
)


class TestImportClasses(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None

    def test_import_class_Machine(self) -> None:
        from dpdispatcher import Machine

        self.assertEqual(dpdispatcher.machine.Machine, Machine)

    def test_import_class_Resources(self) -> None:
        from dpdispatcher import Resources

        self.assertEqual(dpdispatcher.submission.Resources, Resources)

    def test_import_class_Submission(self) -> None:
        from dpdispatcher import Submission

        self.assertEqual(dpdispatcher.submission.Submission, Submission)

    def test_import_class_Task(self) -> None:
        from dpdispatcher import Task

        self.assertEqual(dpdispatcher.submission.Task, Task)
