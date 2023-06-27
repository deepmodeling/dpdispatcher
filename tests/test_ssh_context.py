import os
import socket
import sys
import unittest

from paramiko.ssh_exception import SSHException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
from .context import (
    Machine,
    Resources,
    SSHSession,
    Submission,
    Task,
    setUpModule,  # noqa: F401
)
from .sample_class import SampleClass


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "ssh", "outside the ssh testing environment"
)
class TestSSHContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mdata = {
            "batch_type": "Shell",
            "context_type": "SSHContext",
            "local_root": "./test_context_dir",
            "remote_root": "/dpdispatcher_working",
            "remote_profile": {
                "hostname": "server",
                "port": 22,
                "username": "root",
                "key_filename": "/root/.ssh/id_rsa",
            },
        }
        cls.mdata = mdata
        try:
            cls.machine = Machine.load_from_dict(mdata)
        except (SSHException, socket.timeout):
            raise unittest.SkipTest("SSHException ssh cannot connect")
        cls.submission = SampleClass.get_sample_submission()
        cls.submission.bind_machine(cls.machine)
        cls.submission_hash = cls.submission.submission_hash
        file_list = [
            "bct-1/log.lammps",
            "bct-2/log.lammps",
            "bct-3/log.lammps",
            "bct-4/log.lammps",
            "dir with space/file with space",
        ]
        for file in file_list:
            cls.machine.context.sftp.mkdir(
                os.path.join(cls.machine.context.remote_root, os.path.dirname(file))
            )
            cls.machine.context.write_file(file, "# mock log")

    @classmethod
    def tearDownClass(cls):
        cls.machine.context.clean()
        # close the server
        cls.machine.context.close()

    def setUp(self):
        self.context = self.__class__.machine.context

    def test_ssh_session(self):
        self.assertIsInstance(self.__class__.machine.context.ssh_session, SSHSession)

    def test_upload(self):
        self.context.upload(self.__class__.submission)
        check_file_list = [
            "graph.pb",
            "bct-1/conf.lmp",
            "bct-4/input.lammps",
            "dir with space/file with space",
        ]
        for file in check_file_list:
            self.assertTrue(
                self.context.check_file_exists(
                    os.path.join(self.context.remote_root, file)
                )
            )

    def test_empty_transfer(self):
        # Both forward_files and backward_files are empty
        machine = Machine.load_from_dict(self.machine.serialize())
        resources = Resources.load_from_dict(
            {
                "number_node": 1,
                "cpu_per_node": 1,
                "gpu_per_node": 0,
                "queue_name": "?",
                "group_size": 2,
            }
        )
        task = Task(
            command="echo dpdispatcher_unittest",
            task_work_path="./",
            forward_files=[],
            backward_files=[],
            outlog="out.txt",
        )

        submission = Submission(
            work_base="./",
            machine=machine,
            resources=resources,
            forward_common_files=[],
            backward_common_files=[],
            task_list=[task],
        )
        submission.run_submission()

    def test_recover(self):
        """Test recover from a previous submission."""
        machine = Machine.load_from_dict(self.machine.serialize())
        resources = Resources.load_from_dict(
            {
                "number_node": 1,
                "cpu_per_node": 1,
                "gpu_per_node": 0,
                "queue_name": "?",
                "group_size": 1,
            }
        )
        task = Task(
            command="touch times && echo 1 >> times && test $(wc -l < times) -gt 3 && echo done",
            task_work_path="./",
            forward_files=[],
            backward_files=[],
            outlog="out.txt",
        )

        submission = Submission(
            work_base="./",
            machine=machine,
            resources=resources,
            forward_common_files=[],
            backward_common_files=[],
            task_list=[task],
        )
        try:
            submission.run_submission()
        except RuntimeError:
            # expected to fail, try again
            # reinit machine to test machine recover
            machine = Machine.load_from_dict(self.mdata)
            resources = Resources.load_from_dict(resources.serialize())
            task = Task.deserialize(task.serialize())

            submission = Submission(
                work_base="./",
                machine=machine,
                resources=resources,
                forward_common_files=[],
                backward_common_files=[],
                task_list=[task],
            )
            submission.run_submission()

    def test_download(self):
        self.context.download(self.__class__.submission)


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "ssh", "outside the ssh testing environment"
)
class TestSSHContextNoCompress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mdata = {
            "batch_type": "Shell",
            "context_type": "SSHContext",
            "local_root": "./test_context_dir",
            "remote_root": "/dpdispatcher_working",
            "remote_profile": {
                "hostname": "server",
                "port": 22,
                "username": "root",
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
        file_list = [
            "bct-1/log.lammps",
            "bct-2/log.lammps",
            "bct-3/log.lammps",
            "bct-4/log.lammps",
            "dir with space/file with space",
        ]
        for file in file_list:
            cls.machine.context.sftp.mkdir(
                os.path.join(cls.machine.context.remote_root, os.path.dirname(file))
            )
            cls.machine.context.write_file(file, "# mock log")

    @classmethod
    def tearDownClass(cls):
        cls.machine.context.clean()
        # close the server
        cls.machine.context.close()

    def setUp(self):
        self.context = self.__class__.machine.context

    def test_ssh_session(self):
        self.assertIsInstance(self.__class__.machine.context.ssh_session, SSHSession)

    def test_upload(self):
        self.context.upload(self.__class__.submission)
        check_file_list = [
            "graph.pb",
            "bct-1/conf.lmp",
            "bct-4/input.lammps",
            "dir with space/file with space",
        ]
        for file in check_file_list:
            self.assertTrue(
                self.context.check_file_exists(
                    os.path.join(self.context.remote_root, file)
                )
            )

    def test_download(self):
        self.context.download(self.__class__.submission)
