import os
import sys
import unittest
from unittest.mock import Mock, patch, call

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
        with patch('paramiko.SSHClient'), \
             patch('paramiko.Transport'), \
             patch('paramiko.ProxyCommand') as mock_proxy:
            
            # Test with direct proxy command
            ssh_session = SSHSession(
                hostname="server",
                username="root",
                key_filename="/root/.ssh/id_rsa",
                proxy_command="ssh -W server:22 root@server"
            )
            
            # Verify ProxyCommand was called with the direct command
            mock_proxy.assert_called_with("ssh -W server:22 root@server")

    def test_proxy_command_backward_compatibility(self):
        """Test backward compatibility with individual jump host parameters."""
        with patch('paramiko.SSHClient'), \
             patch('paramiko.Transport'), \
             patch('paramiko.ProxyCommand') as mock_proxy:
            
            # Test with legacy jump host parameters
            ssh_session = SSHSession(
                hostname="server",
                username="root",
                key_filename="/root/.ssh/id_rsa",
                jump_hostname="server",
                jump_username="root",
                jump_port=2222,
                jump_key_filename="/root/.ssh/id_rsa"
            )
            
            # Verify ProxyCommand was called with built command
            expected_cmd = "ssh -W server:22 -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p 2222 -i /root/.ssh/id_rsa root@server"
            mock_proxy.assert_called_with(expected_cmd)

    def test_proxy_command_conflict_error(self):
        """Test error when both proxy_command and jump host parameters are specified."""
        with self.assertRaises(ValueError) as cm:
            SSHSession(
                hostname="server",
                username="root",
                key_filename="/root/.ssh/id_rsa",
                proxy_command="ssh -W server:22 root@server",
                jump_hostname="server"
            )
        
        self.assertIn("Cannot specify both 'proxy_command' and individual jump host parameters", str(cm.exception))

    def test_no_proxy_command(self):
        """Test direct connection without proxy command."""
        with patch('paramiko.SSHClient'), \
             patch('paramiko.Transport'), \
             patch('socket.socket') as mock_socket:
            
            mock_sock = Mock()
            mock_socket.return_value = mock_sock
            
            # Test without any proxy configuration
            ssh_session = SSHSession(
                hostname="server",
                username="root",
                key_filename="/root/.ssh/id_rsa"
            )
            
            # Verify direct socket connection was used
            mock_sock.connect.assert_called_with(("server", 22))

    def test_get_proxy_command_direct(self):
        """Test _get_proxy_command method with direct proxy command."""
        with patch('paramiko.SSHClient'), \
             patch('paramiko.Transport'), \
             patch('paramiko.ProxyCommand'):
            
            ssh_session = SSHSession(
                hostname="server",
                username="root",
                key_filename="/root/.ssh/id_rsa",
                proxy_command="custom proxy command"
            )
            
            self.assertEqual(ssh_session._get_proxy_command(), "custom proxy command")

    def test_get_proxy_command_legacy(self):
        """Test _get_proxy_command method with legacy jump host parameters."""
        with patch('paramiko.SSHClient'), \
             patch('paramiko.Transport'), \
             patch('paramiko.ProxyCommand'):
            
            ssh_session = SSHSession(
                hostname="server",
                username="root",
                key_filename="/root/.ssh/id_rsa",
                jump_hostname="server",
                jump_username="root"
            )
            
            expected_cmd = "ssh -W server:22 -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p 22 root@server"
            self.assertEqual(ssh_session._get_proxy_command(), expected_cmd)

    def test_get_proxy_command_none(self):
        """Test _get_proxy_command method with no proxy configuration."""
        with patch('paramiko.SSHClient'), \
             patch('paramiko.Transport'), \
             patch('socket.socket'):
            
            ssh_session = SSHSession(
                hostname="server",
                username="root",
                key_filename="/root/.ssh/id_rsa"
            )
            
            self.assertIsNone(ssh_session._get_proxy_command())

    # @patch('dpdispatcher.utils.utils.rsync')
    # @patch('shutil.which')
    # def test_rsync_with_proxy_command(self, mock_which, mock_rsync):
    #     """Test rsync with proxy command."""
    #     # This test is complex due to the rsync_available property dependencies
    #     # The core functionality is tested in test_rsync_proxy.py
    #     pass

    # @patch('dpdispatcher.utils.utils.rsync')  
    # @patch('shutil.which')
    # def test_rsync_with_legacy_jump_host(self, mock_which, mock_rsync):
    #     """Test rsync with legacy jump host parameters."""
    #     # This test is complex due to the rsync_available property dependencies
    #     # The core functionality is tested in test_rsync_proxy.py
    #     pass


if __name__ == "__main__":
    unittest.main()