import os,sys,json,glob,shutil,uuid,getpass
import unittest
import pathlib
from paramiko.ssh_exception import NoValidConnectionsError
from paramiko.ssh_exception import SSHException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import SSHContext, SSHSession
from .context import Machine
from .sample_class import SampleClass

class TestSSHContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open('jsons/machine_ali_ehpc.json', 'r') as f:
            mdata = json.load(f)
        try:
            cls.machine = Machine.load_from_dict(mdata['machine'])
        except SSHException:
            raise unittest.SkipTest("SSHException ssh cannot connect")
        cls.submission = SampleClass.get_sample_submission()
        cls.submission.bind_machine(cls.machine)
        cls.submission_hash = cls.submission.submission_hash
        file_list = ['bct-1/log.lammps', 'bct-2/log.lammps', 'bct-3/log.lammps', 'bct-4/log.lammps']
        for file in file_list:
            cls.machine.context.write_file(file, '# mock log')
    
    def setUp(self):
        self.context = self.__class__.machine.context

    def test_ssh_session(self):
        self.assertIsInstance(
            self.__class__.machine.context.ssh_session, SSHSession
        )

    def test_upload(self):
        self.context.upload(self.__class__.submission)
        check_file_list = ['graph.pb', 'bct-1/conf.lmp', 'bct-4/input.lammps']
        for file in check_file_list:
            self.assertTrue(self.context.check_file_exists(os.path.join(self.context.remote_root, file)))

    def test_download(self):
        self.context.download(self.__class__.submission)
        


