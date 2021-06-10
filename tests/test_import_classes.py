import os,sys,json,glob,shutil,uuid,time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import dpdispatcher

class TestImportClasses(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_import_class_Machine(self):
        from dpdispatcher import Machine
        self.assertEqual(dpdispatcher.machine.Machine, Machine)
    
    def test_import_class_Resources(self):
        from dpdispatcher import Resources
        self.assertEqual(dpdispatcher.submission.Resources, Resources)
    
    def test_import_class_Submission(self):
        from dpdispatcher import Submission
        self.assertEqual(dpdispatcher.submission.Submission, Submission)

    def test_import_class_Task(self):
        from dpdispatcher import Task
        self.assertEqual(dpdispatcher.submission.Task, Task)
