import errno
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from paramiko.ssh_exception import SSHException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
from .context import (
    Machine,
    Resources,
    SSHContext,
    SSHSession,
    Submission,
    Task,
    setUpModule,  # noqa: F401
)
from .sample_class import SampleClass


class TestSSHContextRemoteRootRecovery(unittest.TestCase):
    """Test submission rebinding without requiring an SSH server."""

    old_remote_root = "/remote/old-hash"
    new_remote_root = "/remote/new-hash"

    def setUp(self) -> None:
        self.context = SSHContext.__new__(SSHContext)
        self.context.temp_local_root = "/local"
        self.context.temp_remote_root = "/remote"
        self.context.remote_root = self.old_remote_root
        self.context.create_remote_root = False
        self.context.ssh_session = MagicMock()
        self.sftp = self.context.ssh_session.sftp
        self.context.ssh_session.ssh.open_sftp.return_value = self.sftp
        self.submission = SimpleNamespace(work_base="work", submission_hash="new-hash")

    def test_empty_old_root_is_removed_instead_of_moved(self) -> None:
        """An empty old hash is a disposable placeholder, not recovery data."""
        self.sftp.listdir.return_value = []

        self.context.bind_submission(self.submission)

        self.sftp.rmdir.assert_called_once_with(self.old_remote_root)
        self.sftp.rename.assert_not_called()
        self.sftp.mkdir.assert_called_once_with(self.new_remote_root)

    def test_initial_bind_skips_recovery_without_an_old_root(self) -> None:
        """The ANN-compatible empty sentinel is not an SFTP recovery path."""
        self.context.remote_root = ""

        self.context.bind_submission(self.submission)

        self.sftp.listdir.assert_not_called()
        self.sftp.mkdir.assert_called_once_with(self.new_remote_root)

    def test_bind_resets_stale_recovery_destination_marker(self) -> None:
        """Each bind attempt must start with fresh recovery bookkeeping."""
        self.context.remote_root = self.new_remote_root
        self.context._last_recovery_already_at_destination = True

        self.context.bind_submission(self.submission)

        self.assertFalse(self.context._last_recovery_already_at_destination)

    def test_non_empty_old_root_is_moved_when_destination_is_absent(self) -> None:
        """Files from an interrupted submission remain available for recovery."""
        self.sftp.listdir.return_value = ["task-state.json"]
        self.sftp.stat.side_effect = FileNotFoundError(errno.ENOENT, "not found")

        self.context.bind_submission(self.submission)

        self.sftp.rename.assert_called_once_with(
            self.old_remote_root, self.new_remote_root
        )
        self.sftp.rmdir.assert_not_called()

    def test_source_disappearance_during_move_is_tolerated(self) -> None:
        """Concurrent recovery can consume the old directory first."""
        self.sftp.listdir.return_value = ["task-state.json"]
        self.sftp.stat.side_effect = FileNotFoundError(errno.ENOENT, "not found")
        self.sftp.rename.side_effect = FileNotFoundError(errno.ENOENT, "not found")

        self.context.bind_submission(self.submission)

        self.sftp.mkdir.assert_called_once_with(self.new_remote_root)

    def test_unrelated_move_error_is_not_masked(self) -> None:
        """Permission and transport-related move failures remain actionable."""
        self.sftp.listdir.return_value = ["task-state.json"]
        self.sftp.stat.side_effect = FileNotFoundError(errno.ENOENT, "not found")
        move_error = PermissionError(errno.EACCES, "permission denied")
        self.sftp.rename.side_effect = move_error

        with self.assertRaises(PermissionError) as raised:
            self.context.bind_submission(self.submission)

        self.assertIs(raised.exception, move_error)

    def test_existing_destination_rejects_conflicting_recovery(self) -> None:
        """Conflicting roots fail instead of silently dropping recovery state."""
        self.sftp.listdir.return_value = ["task-state.json"]
        self.sftp.stat.return_value = MagicMock()

        with self.assertRaisesRegex(FileExistsError, "both old and new"):
            self.context.bind_submission(self.submission)

        self.sftp.rename.assert_not_called()
        self.sftp.rmdir.assert_not_called()

    def test_remote_metadata_paths_use_posix_and_stay_in_root(self) -> None:
        """Remote SFTP paths must not depend on the controller's OS separator."""
        self.context.remote_root = "/remote/hash"

        self.assertEqual(
            self.context._resolve_remote_path("task\\state.json"),
            "/remote/hash/task/state.json",
        )
        self.assertEqual(
            self.context._resolve_remote_path("/remote/hash/task/state.json"),
            "/remote/hash/task/state.json",
        )
        with self.assertRaises(ValueError):
            self.context._resolve_remote_path("/remote/other/state.json")

    def test_remote_file_operations_use_resolved_posix_paths(self) -> None:
        """Metadata I/O keeps POSIX names even when the controller is Windows."""
        self.context.remote_root = "/remote/hash"
        self.context.block_checkcall = MagicMock()
        handle = MagicMock()
        self.context.sftp.open.return_value.__enter__.return_value = handle

        self.context.write_file("state\\status.txt", "ready")
        self.context.sftp.open.assert_called_with(
            "/remote/hash/state/status.txt_tmp", "w"
        )
        self.context.block_checkcall.assert_called_once()

        handle.read.return_value = b"ready"
        self.assertEqual(self.context.read_file("state/status.txt"), "ready")
        self.context.sftp.open.assert_called_with("/remote/hash/state/status.txt", "r")

        self.context.sftp.stat.return_value = MagicMock()
        self.assertTrue(self.context.check_file_exists("state/status.txt"))
        self.context.sftp.stat.side_effect = OSError("missing")
        self.assertFalse(self.context.check_file_exists("state/status.txt"))

        with self.assertRaises(ValueError):
            self.context._resolve_remote_path("bad\x00name")


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "ssh", "outside the ssh testing environment"
)
class TestSSHContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
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
        except (TimeoutError, SSHException):
            raise unittest.SkipTest("SSHException ssh cannot connect")
        cls.submission = SampleClass.get_sample_submission(backward_wildcard=True)
        cls.submission.bind_machine(cls.machine)
        cls.submission_hash = cls.submission.submission_hash
        file_list = [
            "bct-1/log.lammps",
            "bct-2/log.lammps",
            "bct-3/log.lammps",
            "bct-4/log.lammps",
            "dir with space/file with space",
            "bct-backward_wildcard/test456",
            "bct-backward_wildcard/test123/test123",
        ]
        for file in file_list:
            cls.machine.context.sftp.mkdir(
                os.path.join(cls.machine.context.remote_root, os.path.dirname(file))
            )
            cls.machine.context.write_file(file, "# mock log")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.machine.context.clean()
        # close the server
        cls.machine.context.close()

    def setUp(self) -> None:
        self.context = self.__class__.machine.context

    def test_ssh_session(self) -> None:
        self.assertIsInstance(self.__class__.machine.context.ssh_session, SSHSession)

    def test_upload(self) -> None:
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

    def test_empty_transfer(self) -> None:
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

    def test_recover(self) -> None:
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

    def test_download(self) -> None:
        self.context.download(self.__class__.submission)


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "ssh", "outside the ssh testing environment"
)
class TestSSHContextNoCompress(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
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
        except (TimeoutError, SSHException):
            raise unittest.SkipTest("SSHException ssh cannot connect")
        cls.submission = SampleClass.get_sample_submission(backward_wildcard=True)
        cls.submission.bind_machine(cls.machine)
        cls.submission_hash = cls.submission.submission_hash
        file_list = [
            "bct-1/log.lammps",
            "bct-2/log.lammps",
            "bct-3/log.lammps",
            "bct-4/log.lammps",
            "dir with space/file with space",
            "bct-backward_wildcard/test456",
            "bct-backward_wildcard/test123/test123",
        ]
        for file in file_list:
            cls.machine.context.sftp.mkdir(
                os.path.join(cls.machine.context.remote_root, os.path.dirname(file))
            )
            cls.machine.context.write_file(file, "# mock log")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.machine.context.clean()
        # close the server
        cls.machine.context.close()

    def setUp(self) -> None:
        self.context = self.__class__.machine.context

    def test_ssh_session(self) -> None:
        self.assertIsInstance(self.__class__.machine.context.ssh_session, SSHSession)

    def test_upload(self) -> None:
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

    def test_download(self) -> None:
        self.context.download(self.__class__.submission)
