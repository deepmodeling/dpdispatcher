import os
import sys
import unittest

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

    def test_proxy_command_connection(self):
        """Test SSH connection using proxy_command via jump host."""
        # Test connection from test -> server via jumphost
        ssh_session = SSHSession(
            hostname="server",
            username="root",
            key_filename="/root/.ssh/id_rsa",
            proxy_command="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i /root/.ssh/id_rsa -W server:22 root@jumphost",
        )

        # Verify the connection was established
        self.assertIsNotNone(ssh_session.ssh)
        self.assertTrue(ssh_session._check_alive())

        # Test running a simple command through the proxy
        assert ssh_session.ssh is not None  # for type checker
        stdin, stdout, stderr = ssh_session.ssh.exec_command("echo 'test via proxy'")
        output = stdout.read().decode().strip()
        self.assertEqual(output, "test via proxy")

        # Verify proxy_command attribute is set correctly
        self.assertEqual(
            ssh_session.proxy_command,
            "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i /root/.ssh/id_rsa -W server:22 root@jumphost",
        )

        ssh_session.close()

    def test_direct_connection_no_proxy(self):
        """Test direct SSH connection without proxy command."""
        # Test direct connection from test -> server (no proxy)
        ssh_session = SSHSession(
            hostname="server", username="root", key_filename="/root/.ssh/id_rsa"
        )

        # Verify the connection was established
        self.assertIsNotNone(ssh_session.ssh)
        self.assertTrue(ssh_session._check_alive())

        # Test running a simple command
        assert ssh_session.ssh is not None  # for type checker
        stdin, stdout, stderr = ssh_session.ssh.exec_command("echo 'test direct'")
        output = stdout.read().decode().strip()
        self.assertEqual(output, "test direct")

        # Verify no proxy_command is set
        self.assertIsNone(ssh_session.proxy_command)

        ssh_session.close()

    def test_jump_host_direct_connection(self):
        """Test direct connection to jump host itself."""
        # Test direct connection from test -> jumphost
        ssh_session = SSHSession(
            hostname="jumphost", username="root", key_filename="/root/.ssh/id_rsa"
        )

        # Verify the connection was established
        self.assertIsNotNone(ssh_session.ssh)
        self.assertTrue(ssh_session._check_alive())

        # Test running a command on jumphost
        assert ssh_session.ssh is not None  # for type checker
        stdin, stdout, stderr = ssh_session.ssh.exec_command("hostname")
        output = stdout.read().decode().strip()
        self.assertEqual(output, "jumphost")

        ssh_session.close()


if __name__ == "__main__":
    unittest.main()
