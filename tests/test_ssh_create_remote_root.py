import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"

from .context import SSHContext, setUpModule  # noqa: F401


class TestSSHCreateRemoteRoot(unittest.TestCase):
    def test_recursive_mkdir_disabled_by_default(self):
        calls = []
        context = SSHContext.__new__(SSHContext)
        context.ssh_session = MagicMock()
        context.ssh_session.sftp = MagicMock()
        context.ssh_session.sftp.mkdir.side_effect = lambda path: calls.append(path)

        context._mkdir("/data/home/user/work", recursive=False)

        self.assertEqual(calls, ["/data/home/user/work"])

    def test_recursive_mkdir_creates_missing_parents(self):
        calls = []
        context = SSHContext.__new__(SSHContext)
        context.ssh_session = MagicMock()
        context.ssh_session.sftp = MagicMock()

        def mkdir(path):
            calls.append(path)
            if path in {"/data", "/data/home/user/work"}:
                raise OSError("already exists")

        context.ssh_session.sftp.mkdir.side_effect = mkdir

        context._mkdir("/data/home/user/work", recursive=True)

        self.assertEqual(
            calls,
            [
                "/data",
                "/data/home",
                "/data/home/user",
                "/data/home/user/work",
            ],
        )

    def test_machine_roundtrip_keeps_create_remote_root(self):
        machine_dict = {
            "batch_type": "Shell",
            "context_type": "SSHContext",
            "local_root": "./",
            "remote_root": "/some/path",
            "clean_asynchronously": False,
            "create_remote_root": True,
            "remote_profile": {
                "hostname": "example.com",
                "username": "alice",
            },
        }

        from .context import Machine

        original_init = SSHContext.__init__

        def fake_init(
            self,
            local_root,
            remote_root,
            remote_profile,
            clean_asynchronously=False,
            create_remote_root=False,
            *args,
            **kwargs,
        ):
            self.init_local_root = local_root
            self.init_remote_root = remote_root
            self.remote_profile = remote_profile
            self.clean_asynchronously = clean_asynchronously
            self.create_remote_root = create_remote_root

        SSHContext.__init__ = fake_init
        try:
            machine = Machine.load_from_dict(machine_dict)
            serialized = machine.serialize()
        finally:
            SSHContext.__init__ = original_init

        self.assertTrue(serialized["create_remote_root"])
        self.assertFalse(serialized["clean_asynchronously"])
        self.assertEqual(serialized["remote_root"], "/some/path")
        self.assertEqual(serialized["remote_profile"]["hostname"], "example.com")
