import os
import pathlib
import posixpath
import shlex
import sys
import tempfile
import unittest
from typing import cast
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher.contexts.ssh_context import SSHContext, SSHSession


class TestSSHArchiveChunking(unittest.TestCase):
    """Test split archive downloads without requiring an SSH server."""

    def setUp(self) -> None:
        self.context = cast(SSHContext, SSHContext.__new__(SSHContext))
        self.session = MagicMock()
        self.sftp = MagicMock()
        self.session.sftp = self.sftp
        self.context.ssh_session = cast(SSHSession, self.session)
        self.block_checkcall = MagicMock()
        self.context.block_checkcall = self.block_checkcall  # type: ignore[method-assign]

    def test_zero_chunk_size_uses_single_transfer(self) -> None:
        """The default keeps the existing one-file transfer behavior."""
        self.session.archive_chunk_size = 0

        self.context._get_archive("/remote/result.tar.gz", "/local/result.tar.gz")

        self.session.get.assert_called_once_with(
            "/remote/result.tar.gz", "/local/result.tar.gz"
        )
        self.block_checkcall.assert_not_called()

    def test_positive_chunk_size_reassembles_and_cleans_parts(self) -> None:
        """Remote parts are downloaded in suffix order and reconstructed exactly."""
        archive_content = b"0123456789"
        remote_archive = "/remote/result.tar.gz"
        self.session.archive_chunk_size = 6
        self.sftp.stat.return_value.st_size = len(archive_content)
        split_state: dict[str, str] = {}

        def remember_split(command: str) -> None:
            split_state["prefix"] = shlex.split(command)[-1]

        def list_remote_parts(directory: str) -> list[str]:
            self.assertEqual(directory, "/remote")
            prefix = posixpath.basename(split_state["prefix"])
            # Return the parts out of order to verify deterministic assembly.
            return [prefix + "aaaaab", "unrelated", prefix + "aaaaaa"]

        def download_part(remote_path: str, local_path: str) -> None:
            content = (
                archive_content[:6]
                if remote_path.endswith("aaaaaa")
                else archive_content[6:]
            )
            pathlib.Path(local_path).write_bytes(content)

        self.block_checkcall.side_effect = remember_split
        self.sftp.listdir.side_effect = list_remote_parts
        self.session.get.side_effect = download_part

        with tempfile.TemporaryDirectory() as directory:
            local_archive = os.path.join(directory, "result.tar.gz")
            self.context._get_archive(remote_archive, local_archive)

            self.assertEqual(pathlib.Path(local_archive).read_bytes(), archive_content)
            self.assertEqual(list(pathlib.Path(directory).glob("*.part-*")), [])

        self.block_checkcall.assert_called_once()
        split_command = self.block_checkcall.call_args.args[0]
        self.assertIn("split -b 6 -a 6", split_command)
        removed_parts = [call.args[0] for call in self.sftp.remove.call_args_list]
        self.assertEqual(
            removed_parts,
            [split_state["prefix"] + "aaaaaa", split_state["prefix"] + "aaaaab"],
        )

    def test_negative_chunk_size_is_rejected_before_connecting(self) -> None:
        """Invalid configuration fails before any SSH network activity."""
        with patch.object(SSHSession, "_setup_ssh") as setup_ssh:
            with self.assertRaisesRegex(ValueError, "archive_chunk_size"):
                SSHSession("example.com", "user", archive_chunk_size=-1)

        setup_ssh.assert_not_called()

    def test_reconstructed_size_mismatch_is_reported(self) -> None:
        """A missing or truncated part cannot silently produce a corrupt archive."""
        self.session.archive_chunk_size = 4
        self.sftp.stat.return_value.st_size = 5
        split_state: dict[str, str] = {}

        def remember_split(command: str) -> None:
            split_state["prefix"] = shlex.split(command)[-1]

        def list_remote_parts(directory: str) -> list[str]:
            prefix = posixpath.basename(split_state["prefix"])
            return [prefix + "aaaaaa"]

        def download_truncated_part(remote_path: str, local_path: str) -> None:
            pathlib.Path(local_path).write_bytes(b"1234")

        self.block_checkcall.side_effect = remember_split
        self.sftp.listdir.side_effect = list_remote_parts
        self.session.get.side_effect = download_truncated_part

        with tempfile.TemporaryDirectory() as directory:
            local_archive = os.path.join(directory, "result.tar.gz")
            with self.assertRaisesRegex(OSError, "expected 5 bytes, got 4 bytes"):
                self.context._get_archive("/remote/result.tar.gz", local_archive)

        self.sftp.remove.assert_called_once_with(split_state["prefix"] + "aaaaaa")


if __name__ == "__main__":
    unittest.main()
