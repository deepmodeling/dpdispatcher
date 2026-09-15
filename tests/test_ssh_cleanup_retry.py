import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher.contexts.ssh_context import SSHContext


class TestSSHCleanupRetry(unittest.TestCase):
    """Verify bounded retries for transient SSH cleanup failures."""

    def setUp(self) -> None:
        self.context = cast(SSHContext, SSHContext.__new__(SSHContext))
        self.context.clean_asynchronously = False
        self.context.block_checkcall = MagicMock()

    @patch("dpdispatcher.contexts.ssh_context.time.sleep")
    def test_rmtree_retries_transient_failure(self, sleep: MagicMock) -> None:
        """Retry a transient directory metadata race."""
        self.context.block_checkcall.side_effect = [
            RuntimeError("Directory not empty"),
            None,
        ]

        self.context._rmtree("/remote/root")

        self.assertEqual(
            self.context.block_checkcall.call_args_list,
            [
                call("env LC_ALL=C rm -rf /remote/root", asynchronously=False),
                call("env LC_ALL=C rm -rf /remote/root", asynchronously=False),
            ],
        )
        sleep.assert_called_once_with(1)

    @unittest.skipIf(os.name == "nt", "Requires a POSIX shell and env")
    @patch("dpdispatcher.contexts.ssh_context.time.sleep")
    def test_rmtree_retries_with_localized_remote_environment(
        self, sleep: MagicMock
    ) -> None:
        """Fix the command locale before classifying transient remote errors."""
        for english, localized in (
            ("Directory not empty", "目录非空"),
            (".nfs0001: Device or resource busy", ".nfs0001: 设备或资源忙"),
        ):
            with self.subTest(error=english), tempfile.TemporaryDirectory() as tmpdir:
                # Execute a real shell/env with fake rm diagnostics so this test
                # does not require installed translations or an NFS server.
                fake_rm = Path(tmpdir) / "rm"
                fake_rm.write_text(
                    r"""#!/bin/sh
if [ -f "$0.called" ]; then
    exit 0
fi
: > "$0.called"
if [ "$LC_ALL" = C ]; then
    printf '%s\n' "$TEST_CLEANUP_ENGLISH_ERROR" >&2
else
    printf '%s\n' "$TEST_CLEANUP_LOCALIZED_ERROR" >&2
fi
exit 1
""",
                    encoding="utf-8",
                )
                fake_rm.chmod(0o755)
                environment = dict(
                    os.environ,
                    PATH=tmpdir + os.pathsep + os.defpath,
                    LC_ALL="zh_CN.UTF-8",
                    TEST_CLEANUP_ENGLISH_ERROR=english,
                    TEST_CLEANUP_LOCALIZED_ERROR=localized,
                )

                def run_remote_command(
                    command: str, asynchronously: bool = False
                ) -> None:
                    self.assertFalse(asynchronously)
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        env=environment,
                        timeout=10,
                        check=False,
                    )
                    if result.returncode:
                        raise RuntimeError(result.stderr)

                block_checkcall = MagicMock(side_effect=run_remote_command)
                self.context.block_checkcall = block_checkcall
                sleep.reset_mock()

                self.context._rmtree("/remote/root")

                self.assertEqual(block_checkcall.call_count, 2)
                sleep.assert_called_once_with(1)

    @patch("dpdispatcher.contexts.ssh_context.time.sleep")
    def test_rmtree_propagates_non_transient_failure(self, sleep: MagicMock) -> None:
        """Propagate unrelated cleanup failures without retrying."""
        self.context.block_checkcall.side_effect = RuntimeError("permission denied")

        with self.assertRaisesRegex(RuntimeError, "permission denied"):
            self.context._rmtree("/remote/root")

        self.context.block_checkcall.assert_called_once_with(
            "env LC_ALL=C rm -rf /remote/root", asynchronously=False
        )
        sleep.assert_not_called()

    @patch("dpdispatcher.contexts.ssh_context.time.sleep")
    def test_rmtree_retries_nfs_busy_failure(self, sleep: MagicMock) -> None:
        """Retry a busy NFS temporary file left by an open handle."""
        self.context.block_checkcall.side_effect = [
            RuntimeError(
                "Get error code 1 in calling env LC_ALL=C rm -rf /remote/root "
                "with job: test . message: .nfs0001: Device or resource busy"
            ),
            None,
        ]

        self.context._rmtree("/remote/root")

        self.assertEqual(self.context.block_checkcall.call_count, 2)
        sleep.assert_called_once_with(1)

    @patch("dpdispatcher.contexts.ssh_context.time.sleep")
    def test_rmtree_propagates_non_nfs_busy_failure(self, sleep: MagicMock) -> None:
        """Do not retry a busy error unrelated to an NFS temporary file."""
        self.context.block_checkcall.side_effect = RuntimeError(
            "Get error code 1 in calling env LC_ALL=C rm -rf /remote/.nfs0001 "
            "with job: test . message: /mnt/active: Device or resource busy"
        )

        with self.assertRaisesRegex(RuntimeError, "Device or resource busy"):
            self.context._rmtree("/remote/root")

        self.context.block_checkcall.assert_called_once_with(
            "env LC_ALL=C rm -rf /remote/root", asynchronously=False
        )
        sleep.assert_not_called()

    @patch("dpdispatcher.contexts.ssh_context.time.sleep")
    def test_rmtree_raises_after_retry_exhaustion(self, sleep: MagicMock) -> None:
        """Raise the original transient error after bounded retries."""
        self.context.block_checkcall.side_effect = RuntimeError("Directory not empty")

        with self.assertRaisesRegex(RuntimeError, "Directory not empty"):
            self.context._rmtree("/remote/root")

        self.assertEqual(self.context.block_checkcall.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(1), call(2)])

    def test_async_cleanup_does_not_retry(self) -> None:
        """Keep asynchronous cleanup as a single nonblocking call."""
        self.context.clean_asynchronously = True

        self.context._rmtree("/remote/root")

        self.context.block_checkcall.assert_called_once_with(
            "rm -rf /remote/root", asynchronously=True
        )


if __name__ == "__main__":
    unittest.main()
