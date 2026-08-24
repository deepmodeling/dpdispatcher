"""Regression tests for shared forward files during retry."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock

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

        payload = context.upload.call_args.args[0]
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


if __name__ == "__main__":
    unittest.main()
