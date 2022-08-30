import os,sys,json,glob,shutil,uuid,getpass
from typing import Tuple
import unittest
import pathlib
import tempfile
import socket

from paramiko.ssh_exception import NoValidConnectionsError
from paramiko.ssh_exception import SSHException
import mockssh
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import SSHContext, SSHSession
from .context import Machine
from .sample_class import SampleClass


def generate_private_key() -> str:
    """Generate a private key."""
    # https://stackoverflow.com/a/39126754/9567349
    key = rsa.generate_private_key(
        backend=crypto_default_backend(),
        public_exponent=65537,
        key_size=2048,
    )

    private_key = key.private_bytes(
        crypto_serialization.Encoding.PEM,
        crypto_serialization.PrivateFormat.TraditionalOpenSSL,
        crypto_serialization.NoEncryption(),
    )
    return private_key


def mock_server():
    """Generate a mock ssh server."""
    TEST_USER = "test-user"
    with tempfile.TemporaryDirectory() as temp_dir:
        private_key = generate_private_key()
        fn_private_key = os.path.join(temp_dir, "id_rsa")
        with open(fn_private_key, 'wb') as f:
            f.write(private_key)
        os.chmod(fn_private_key, 0o600)
        workdir = os.path.join(temp_dir, 'dpgen_workdir')
        os.makedirs(workdir, exist_ok=True)
        with mockssh.Server({
            TEST_USER: fn_private_key,
        }) as s:
            yield s.host, s.port, TEST_USER, workdir, fn_private_key
    yield # yield the last one


class TestSSHContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = mock_server()
        host, port, username, workdir, key_filename = next(cls.server)
        mdata = {
            "batch_type": "Shell",
            "context_type": "SSHContext",
            "local_root": "./test_context_dir",
            "remote_root": workdir,
            "remote_profile": {
                "hostname": host,
                "port": port,
                "username": username,
                "key_filename": key_filename,
            },
        }
        try:
            cls.machine = Machine.load_from_dict(mdata)
        except (SSHException, socket.timeout):
            raise unittest.SkipTest("SSHException ssh cannot connect")
        cls.submission = SampleClass.get_sample_submission()
        cls.submission.bind_machine(cls.machine)
        cls.submission_hash = cls.submission.submission_hash
        file_list = ['bct-1/log.lammps', 'bct-2/log.lammps', 'bct-3/log.lammps', 'bct-4/log.lammps']
        for file in file_list:
            cls.machine.context.sftp.mkdir(os.path.join(cls.machine.context.remote_root, os.path.dirname(file)))
            cls.machine.context.write_file(file, '# mock log')

    @classmethod
    def tearDownClass(cls):
        cls.machine.context.clean()
        # close the server
        cls.machine.context.close()
        next(cls.server)
    
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

class TestSSHContextNoCompress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = mock_server()
        host, port, username, workdir, key_filename = next(cls.server)
        mdata = {
            "batch_type": "Shell",
            "context_type": "SSHContext",
            "local_root": "./test_context_dir",
            "remote_root": workdir,
            "remote_profile": {
                "hostname": host,
                "port": port,
                "username": username,
                "key_filename": key_filename,
                "tar_compress": False,
            },
        }
        try:
            cls.machine = Machine.load_from_dict(mdata)
        except (SSHException, socket.timeout):
            raise unittest.SkipTest("SSHException ssh cannot connect")
        cls.submission = SampleClass.get_sample_submission()
        cls.submission.bind_machine(cls.machine)
        cls.submission_hash = cls.submission.submission_hash
        file_list = ['bct-1/log.lammps', 'bct-2/log.lammps', 'bct-3/log.lammps', 'bct-4/log.lammps']
        for file in file_list:
            cls.machine.context.sftp.mkdir(os.path.join(cls.machine.context.remote_root, os.path.dirname(file)))
            cls.machine.context.write_file(file, '# mock log')

    @classmethod
    def tearDownClass(cls):
        cls.machine.context.clean()
        # close the server
        cls.machine.context.close()
        next(cls.server)
    
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
        


