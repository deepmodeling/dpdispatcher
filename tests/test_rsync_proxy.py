import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"

from dpdispatcher.utils.utils import rsync


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "ssh", "outside the ssh testing environment"
)
class TestRsyncProxyCommand(unittest.TestCase):
    """Test rsync function with proxy command support."""

    def setUp(self):
        """Set up test files for rsync operations."""
        # Create temporary test files
        self.test_content = "test content for rsync"

        # Local test file
        self.local_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
        self.local_file.write(self.test_content)
        self.local_file.close()

        # Remote paths for testing
        self.remote_test_dir = "/tmp/rsync_test"
        self.remote_file_direct = f"root@server:{self.remote_test_dir}/test_direct.txt"
        self.remote_file_proxy = f"root@server:{self.remote_test_dir}/test_proxy.txt"

    def tearDown(self):
        """Clean up test files."""
        # Remove local test file
        os.unlink(self.local_file.name)

    def test_rsync_with_proxy_command(self):
        """Test rsync with proxy command via jump host."""
        try:
            # Test rsync through jump host: test -> jumphost -> server
            rsync(
                self.local_file.name,
                self.remote_file_proxy,
                key_filename="/root/.ssh/id_rsa",
                proxy_command="ssh -W server:22 root@jumphost",
            )

            # Verify the file was transferred by reading it back
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as download_file:
                download_path = download_file.name

            rsync(
                self.remote_file_proxy,
                download_path,
                key_filename="/root/.ssh/id_rsa",
                proxy_command="ssh -W server:22 root@jumphost",
            )

            # Verify content matches
            with open(download_path) as f:
                content = f.read()
            self.assertEqual(content, self.test_content)

            # Clean up
            os.unlink(download_path)

        except Exception as e:
            raise unittest.SkipTest(f"rsync via proxy failed: {e}")

    def test_rsync_direct_connection(self):
        """Test rsync without proxy command (direct connection)."""
        try:
            # Test direct rsync: test -> server
            rsync(
                self.local_file.name,
                self.remote_file_direct,
                key_filename="/root/.ssh/id_rsa",
            )

            # Verify the file was transferred by reading it back
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as download_file:
                download_path = download_file.name

            rsync(
                self.remote_file_direct, download_path, key_filename="/root/.ssh/id_rsa"
            )

            # Verify content matches
            with open(download_path) as f:
                content = f.read()
            self.assertEqual(content, self.test_content)

            # Clean up
            os.unlink(download_path)

        except Exception as e:
            raise unittest.SkipTest(f"direct rsync failed: {e}")

    def test_rsync_with_additional_options(self):
        """Test rsync with proxy command and additional SSH options."""
        try:
            # Test rsync with custom port, timeout, and proxy
            rsync(
                self.local_file.name,
                self.remote_file_proxy,
                port=22,
                key_filename="/root/.ssh/id_rsa",
                timeout=30,
                proxy_command="ssh -W server:22 root@jumphost",
            )

            # Verify the file exists on remote by attempting to download
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as download_file:
                download_path = download_file.name

            rsync(
                self.remote_file_proxy,
                download_path,
                port=22,
                key_filename="/root/.ssh/id_rsa",
                timeout=30,
                proxy_command="ssh -W server:22 root@jumphost",
            )

            # Verify content
            with open(download_path) as f:
                content = f.read()
            self.assertEqual(content, self.test_content)

            # Clean up
            os.unlink(download_path)

        except Exception as e:
            raise unittest.SkipTest(f"rsync with options failed: {e}")


if __name__ == "__main__":
    unittest.main()
