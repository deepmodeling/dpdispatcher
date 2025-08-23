import os
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"

from dpdispatcher.utils.utils import rsync


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "ssh", "outside the ssh testing environment"
)
class TestRsyncProxyCommand(unittest.TestCase):
    """Test rsync function with proxy command support."""

    @patch('dpdispatcher.utils.utils.run_cmd_with_all_output')
    def test_rsync_with_proxy_command(self, mock_run_cmd):
        """Test rsync with direct proxy command."""
        mock_run_cmd.return_value = (0, "", "")
        
        rsync(
            "/local/file",
            "root@server:/remote/file",
            proxy_command="ssh -W %h:%p root@server"
        )
        
        # Verify the command was called with ProxyCommand
        mock_run_cmd.assert_called_once()
        args, kwargs = mock_run_cmd.call_args
        cmd = args[0]
        
        # Check that the command contains our proxy command
        cmd_str = " ".join(cmd)
        self.assertIn("ProxyCommand=ssh -W %h:%p root@server", cmd_str)

    @patch('dpdispatcher.utils.utils.run_cmd_with_all_output')
    def test_rsync_with_legacy_jump_host(self, mock_run_cmd):
        """Test rsync with legacy jump host parameters."""
        mock_run_cmd.return_value = (0, "", "")
        
        rsync(
            "/local/file",
            "root@server:/remote/file",
            jump_hostname="server",
            jump_username="root",
            jump_port=2222,
            jump_key_filename="/root/.ssh/id_rsa"
        )
        
        # Verify the command was called with built ProxyCommand
        mock_run_cmd.assert_called_once()
        args, kwargs = mock_run_cmd.call_args
        cmd = args[0]
        
        # Check that the command contains the built proxy command
        cmd_str = " ".join(cmd)
        self.assertIn("ProxyCommand=ssh -W %h:%p -o StrictHostKeyChecking=no", cmd_str)
        self.assertIn("-p 2222", cmd_str)
        self.assertIn("-i /root/.ssh/id_rsa", cmd_str)
        self.assertIn("root@server", cmd_str)

    @patch('dpdispatcher.utils.utils.run_cmd_with_all_output')
    def test_rsync_without_proxy(self, mock_run_cmd):
        """Test rsync without any proxy configuration."""
        mock_run_cmd.return_value = (0, "", "")
        
        rsync(
            "/local/file",
            "root@server:/remote/file"
        )
        
        # Verify the command was called without ProxyCommand
        mock_run_cmd.assert_called_once()
        args, kwargs = mock_run_cmd.call_args
        cmd = args[0]
        
        # Check that no ProxyCommand is present
        cmd_str = " ".join(cmd)
        self.assertNotIn("ProxyCommand", cmd_str)

    def test_rsync_conflict_error(self):
        """Test error when both proxy_command and jump host parameters are specified."""
        with self.assertRaises(ValueError) as cm:
            rsync(
                "/local/file",
                "root@server:/remote/file",
                proxy_command="ssh -W %h:%p root@server",
                jump_hostname="server"
            )
        
        self.assertIn("Cannot specify both 'proxy_command' and individual jump host parameters", str(cm.exception))

    @patch('dpdispatcher.utils.utils.run_cmd_with_all_output')
    def test_rsync_failed_command(self, mock_run_cmd):
        """Test rsync with failed command."""
        mock_run_cmd.return_value = (1, "", "Connection failed")
        
        with self.assertRaises(RuntimeError) as cm:
            rsync(
                "/local/file",
                "root@server:/remote/file"
            )
        
        self.assertIn("Failed to run", str(cm.exception))
        self.assertIn("Connection failed", str(cm.exception))

    @patch('dpdispatcher.utils.utils.run_cmd_with_all_output')
    def test_rsync_basic_options(self, mock_run_cmd):
        """Test rsync with basic options like port, key, timeout."""
        mock_run_cmd.return_value = (0, "", "")
        
        rsync(
            "/local/file",
            "root@server:/remote/file",
            port=2222,
            key_filename="/root/.ssh/id_rsa",
            timeout=30
        )
        
        # Verify the command contains the expected options
        mock_run_cmd.assert_called_once()
        args, kwargs = mock_run_cmd.call_args
        cmd = args[0]
        cmd_str = " ".join(cmd)
        
        self.assertIn("-p 2222", cmd_str)
        self.assertIn("-i /root/.ssh/id_rsa", cmd_str)
        self.assertIn("ConnectTimeout=30", cmd_str)


if __name__ == "__main__":
    unittest.main()