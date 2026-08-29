"""Regression tests for shared forward files during retry."""

import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from dpdispatcher.contexts.local_context import LocalContext
from dpdispatcher.submission import Job


class TestRetryCommonFiles(unittest.TestCase):
    """A single-job retry must not replace live shared inputs."""

    def _make_job(self, context):
        job = Job.__new__(Job)
        job.machine = MagicMock()
        job.machine.context = context
        task = MagicMock()
        task.task_work_path = "task0"
        task.forward_files = []
        job.job_task_list = [task]
        return job

    def test_retry_payload_requests_preservation(self):
        context = MagicMock()
        context.submission.forward_common_files = ["shared"]
        job = self._make_job(context)

        job._ensure_forward_files_on_retry()

        payload = context.upload.call_args[0][0]
        self.assertTrue(payload.preserve_existing_forward_common_files)

    def test_existing_common_entries_are_preserved_while_missing_entries_are_added(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            local_root = os.path.join(tmpdir, "local")
            remote_root = os.path.join(tmpdir, "remote")
            local_common = os.path.join(local_root, "shared")
            remote_common = os.path.join(remote_root, "shared")
            os.makedirs(local_common)
            os.makedirs(remote_common)

            with open(os.path.join(local_common, "model.pb"), "w") as fp:
                fp.write("replacement")
            with open(os.path.join(local_common, "config.json"), "w") as fp:
                fp.write("new config")
            with open(os.path.join(remote_common, "model.pb"), "w") as fp:
                fp.write("in use by sibling job")

            context = LocalContext.__new__(LocalContext)
            context.local_root = local_root
            context.remote_root = remote_root
            context.symlink = False
            context.submission = MagicMock()
            context.submission.forward_common_files = ["shared"]
            job = self._make_job(context)

            job._ensure_forward_files_on_retry()

            with open(os.path.join(remote_common, "model.pb")) as fp:
                self.assertEqual(fp.read(), "in use by sibling job")
            with open(os.path.join(remote_common, "config.json")) as fp:
                self.assertEqual(fp.read(), "new config")

    def test_concurrent_retries_publish_shared_directory_atomically(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            local_root = os.path.join(tmpdir, "local")
            remote_root = os.path.join(tmpdir, "remote")
            local_common = os.path.join(local_root, "shared")
            remote_common = os.path.join(remote_root, "shared")
            os.makedirs(local_common)
            os.makedirs(remote_root)
            with open(os.path.join(local_common, "model.pb"), "w") as fp:
                fp.write("complete model")

            context = LocalContext.__new__(LocalContext)
            context.symlink = False
            publish_barrier = threading.Barrier(2)
            rename = os.rename

            def synchronized_rename(source, target):
                publish_barrier.wait(timeout=5)
                return rename(source, target)

            with patch(
                "dpdispatcher.contexts.local_context.os.rename",
                side_effect=synchronized_rename,
            ):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [
                        executor.submit(
                            context._copy_missing_from_local_to_remote,
                            local_common,
                            remote_common,
                        )
                        for _ in range(2)
                    ]
                    for future in futures:
                        future.result()

            with open(os.path.join(remote_common, "model.pb")) as fp:
                self.assertEqual(fp.read(), "complete model")
            self.assertFalse(
                any(
                    name.startswith(".dpdispatcher-")
                    for name in os.listdir(remote_root)
                )
            )


if __name__ == "__main__":
    unittest.main()
