import os,sys,json,glob,shutil,uuid,getpass
import unittest
from pathlib import Path
from paramiko.ssh_exception import NoValidConnectionsError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import SSHContext, SSHSession

class TestSSHContext(unittest.TestCase):
    def setUp(self):
        self.tmp_local_root = 'test_context_dir/'
        self.tmp_remote_root = 'tmp_ssh_context_dir/'

        self.username = getpass.getuser()
        # try:
        #     self.ssh_session = SSHSession(
        #         hostname='localhost',
        #         username=self.username)
        # except NoValidConnectionsError:
        #     self.skipTest("skip ssh tests due to ssh connection errors")

    def test_ssh_session(self):
        pass
        # with self.


