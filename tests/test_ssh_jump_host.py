import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
from .context import (
    SSHSession,
    setUpModule,  # noqa: F401
)


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "ssh", "outside the ssh testing environment"
)
class TestSSHJumpHost(unittest.TestCase):
    """Test SSH jump host functionality."""

    def test_proxy_command_direct(self):
        """Test using proxy_command directly."""
        with patch("paramiko.SSHClient"), patch("paramiko.Transport"), patch(
            "paramiko.ProxyCommand"
        ) as mock_proxy:
            # Test with direct proxy command
            ssh_session = SSHSession(
                hostname="server",
                username="root",
                key_filename="/root/.ssh/id_rsa",
                proxy_command="ssh -W server:22 root@server",
            )

            # Verify ProxyCommand was called with the direct command
            mock_proxy.assert_called_with("ssh -W server:22 root@server")

    def test_no_proxy_command(self):
        """Test direct connection without proxy command."""
        with patch("paramiko.SSHClient"), patch("paramiko.Transport"), patch(
            "socket.socket"
        ) as mock_socket:
            mock_sock = Mock()
            mock_socket.return_value = mock_sock

            # Test without any proxy configuration
            ssh_session = SSHSession(
                hostname="server", username="root", key_filename="/root/.ssh/id_rsa"
            )

            # Verify direct socket connection was used
            mock_sock.connect.assert_called_with(("server", 22))

    def test_proxy_command_attribute_direct(self):
        """Test proxy_command attribute with direct proxy command."""
        with patch("paramiko.SSHClient"), patch("paramiko.Transport"), patch(
            "paramiko.ProxyCommand"
        ):
            ssh_session = SSHSession(
                hostname="server",
                username="root",
                key_filename="/root/.ssh/id_rsa",
                proxy_command="custom proxy command",
            )

            self.assertEqual(ssh_session.proxy_command, "custom proxy command")

    def test_proxy_command_attribute_none(self):
        """Test proxy_command attribute with no proxy configuration."""
        with patch("paramiko.SSHClient"), patch("paramiko.Transport"), patch(
            "socket.socket"
        ):
            ssh_session = SSHSession(
                hostname="server", username="root", key_filename="/root/.ssh/id_rsa"
            )

            self.assertIsNone(ssh_session.proxy_command)


if __name__ == "__main__":
    unittest.main()
