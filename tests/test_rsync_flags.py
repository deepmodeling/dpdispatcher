import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"

from dpdispatcher.utils.utils import rsync


class TestRsyncFlags(unittest.TestCase):
    """Test rsync function flags to ensure correct options are used."""

    @patch("dpdispatcher.utils.utils.run_cmd_with_all_output")
    def test_rsync_flags_exclude_owner_group(self, mock_run_cmd):
        """Test that rsync uses flags that exclude owner and group preservation."""
        # Mock successful command execution
        mock_run_cmd.return_value = (0, "", "")

        # Call rsync function
        rsync("source_file", "dest_file", key_filename="test_key")

        # Verify the command was called
        mock_run_cmd.assert_called_once()

        # Get the command that was executed
        called_cmd = mock_run_cmd.call_args[0][0]

        # Verify the command contains the correct flags
        self.assertIn("-rlptDz", called_cmd)
        self.assertNotIn("-az", called_cmd)

        # Verify rsync command structure
        self.assertIn("rsync", called_cmd)
        self.assertIn("source_file", called_cmd)
        self.assertIn("dest_file", called_cmd)
        self.assertIn("-e", called_cmd)
        self.assertIn("-q", called_cmd)

    @patch("dpdispatcher.utils.utils.run_cmd_with_all_output")
    def test_rsync_with_proxy_command_flags(self, mock_run_cmd):
        """Test that rsync uses correct flags even with proxy command."""
        # Mock successful command execution
        mock_run_cmd.return_value = (0, "", "")

        # Call rsync function with proxy command
        rsync(
            "source_file",
            "dest_file",
            key_filename="test_key",
            proxy_command="ssh -W target:22 jump_host",
        )

        # Verify the command was called
        mock_run_cmd.assert_called_once()

        # Get the command that was executed
        called_cmd = mock_run_cmd.call_args[0][0]

        # Verify the command contains the correct flags
        self.assertIn("-rlptDz", called_cmd)
        self.assertNotIn("-az", called_cmd)

    @patch("dpdispatcher.utils.utils.run_cmd_with_all_output")
    def test_rsync_error_handling(self, mock_run_cmd):
        """Test that rsync properly handles errors."""
        # Mock failed command execution
        mock_run_cmd.return_value = (
            23,
            "",
            "rsync: chown failed: Operation not permitted",
        )

        # Call rsync function and expect RuntimeError
        with self.assertRaises(RuntimeError) as context:
            rsync("source_file", "dest_file")

        # Verify error message contains the command and error
        self.assertIn("Failed to run", str(context.exception))
        self.assertIn(
            "rsync: chown failed: Operation not permitted", str(context.exception)
        )


if __name__ == "__main__":
    unittest.main()
