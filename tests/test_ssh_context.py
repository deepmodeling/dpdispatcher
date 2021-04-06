import os,sys,json,glob,shutil,uuid,getpass
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import SSHContext, SSHSession
from .context import setUpModule

class TestSSHContext(unittest.TestCase):
    def setUp(self):
        self.tmp_local_root = 'test_context_dir/'
        self.tmp_remote_root = 'tmp_ssh_context_dir/'


