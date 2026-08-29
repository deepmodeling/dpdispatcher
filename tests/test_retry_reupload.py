"""Test _ensure_forward_files_on_retry for PR #629.

Tests verify that:
1. context.upload() is called on retry with the job's tasks
2. forward_common_files from submission are included
3. Restoration exceptions stop resubmission and remain actionable
4. No-machine case is a no-op
5. Binary files are uploaded intact (integration test with real LocalContext)
"""

import os
import shutil
import sys
import tempfile
import unittest
from typing import Any, List, Optional
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher.submission import Job
from dpdispatcher.utils.job_status import JobStatus


class TestEnsureForwardFilesOnRetry(unittest.TestCase):
    """Unit tests for Job._ensure_forward_files_on_retry()."""

    def _make_job(
        self,
        task_list: Optional[List[MagicMock]] = None,
        forward_common_files: Optional[List[str]] = None,
    ) -> Job:
        """Create a Job with mocked machine/context."""
        job = Job.__new__(Job)
        job.machine = MagicMock()
        job.machine.context.upload = MagicMock()

        mock_submission = MagicMock()
        mock_submission.forward_common_files = forward_common_files or []
        job.machine.context.submission = mock_submission

        if task_list is None:
            task = MagicMock()
            task.task_work_path = "task0"
            task.forward_files = ["input.lammps", "frozen_model.pb"]
            task_list = [task]
        job.job_task_list = task_list
        return job

    def test_calls_context_upload(self) -> None:
        """Calls context.upload() exactly once."""
        job = self._make_job()
        job._ensure_forward_files_on_retry()
        job.machine.context.upload.assert_called_once()

    def test_payload_contains_job_tasks(self) -> None:
        """Upload payload contains this job's task list."""
        task = MagicMock()
        task.task_work_path = "task0"
        task.forward_files = ["*.pb"]
        job = self._make_job(task_list=[task])
        job._ensure_forward_files_on_retry()
        payload = job.machine.context.upload.call_args[0][0]
        self.assertEqual(payload.belonging_tasks, [task])

    def test_payload_contains_forward_common_files(self) -> None:
        """Upload payload includes forward_common_files from submission."""
        job = self._make_job(forward_common_files=["shared_model.pb"])
        job._ensure_forward_files_on_retry()
        payload = job.machine.context.upload.call_args[0][0]
        self.assertEqual(payload.forward_common_files, ["shared_model.pb"])

    def test_payload_contains_retry_job(self) -> None:
        """Upload payload includes the job collection required by cloud contexts."""
        job = self._make_job()
        job._ensure_forward_files_on_retry()
        payload = job.machine.context.upload.call_args[0][0]
        self.assertEqual(payload.belonging_jobs, [job])

    def test_cloud_upload_contexts_receive_retry_job(self) -> None:
        """Both cloud upload implementations can consume the retry payload."""
        from dpdispatcher.contexts.dp_cloud_server_context import (
            BohriumContext,
        )
        from dpdispatcher.contexts.openapi_context import (
            OpenAPIContext,
        )
        from dpdispatcher.utils.job_status import (
            JobStatus,
        )

        for upload_method in (OpenAPIContext.upload, BohriumContext.upload):
            with self.subTest(context=upload_method.__qualname__):
                job = self._make_job(forward_common_files=["shared_model.pb"])
                job.job_state = JobStatus.terminated
                context = job.machine.context
                context.upload_job = MagicMock()

                def run_real_upload(
                    payload: Any,  # noqa: ANN401
                    method: Any = upload_method,  # noqa: ANN401
                    ctx: Any = context,  # noqa: ANN401
                ) -> Any:  # noqa: ANN401
                    return method(ctx, payload)

                context.upload.side_effect = run_real_upload
                job._ensure_forward_files_on_retry()

                context.upload_job.assert_called_once_with(job, ["shared_model.pb"])

    def test_no_submission_on_context(self) -> None:
        """If context has no submission attr, method returns early (no-op)."""
        job = self._make_job()
        del job.machine.context.submission
        job._ensure_forward_files_on_retry()
        job.machine.context.upload.assert_not_called()

    def test_no_machine_is_noop(self) -> None:
        """If machine is None, method is a no-op."""
        job = Job.__new__(Job)
        job.machine = None
        job.job_task_list = []
        job._ensure_forward_files_on_retry()

    def test_upload_exception_propagates(self) -> None:
        """Exceptions from upload propagate to the retry caller."""
        job = self._make_job()
        job.machine.context.upload.side_effect = FileNotFoundError("gone")
        with self.assertRaises(FileNotFoundError):
            job._ensure_forward_files_on_retry()

    def test_restore_failure_prevents_resubmission(self) -> None:
        """A terminated job is not resubmitted without its required inputs."""
        job = self._make_job()
        job.job_state = JobStatus.terminated
        job.job_hash = "job-hash"
        job.job_id = "job-id"
        job.fail_count = 0
        job.resources = MagicMock(wait_time=0)
        job.machine.retry_count = 3
        job._ensure_forward_files_on_retry = MagicMock(
            side_effect=FileNotFoundError("missing input")
        )
        job.submit_job = MagicMock()

        with self.assertRaisesRegex(FileNotFoundError, "missing input"):
            job.handle_unexpected_job_state()

        job.submit_job.assert_not_called()


class TestEnsureForwardFilesIntegration(unittest.TestCase):
    """Integration test with real LocalContext."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.local_root = os.path.join(self.tmpdir, "local")
        self.remote_root = os.path.join(self.tmpdir, "remote")
        os.makedirs(self.local_root)
        os.makedirs(self.remote_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir)

    def test_binary_file_integrity(self) -> None:
        """Binary .pb file is uploaded without corruption."""
        from dpdispatcher.contexts.local_context import LocalContext

        ctx = LocalContext.__new__(LocalContext)
        ctx.local_root = self.local_root
        ctx.remote_root = self.remote_root
        ctx.symlink = False
        ctx.submission = MagicMock()
        ctx.submission.forward_common_files = []

        local_task = os.path.join(self.local_root, "task0")
        os.makedirs(local_task)
        binary_content = bytes(range(256)) * 100
        with open(os.path.join(local_task, "frozen_model.pb"), "wb") as f:
            f.write(binary_content)

        job = Job.__new__(Job)
        job.machine = MagicMock()
        job.machine.context = ctx
        task = MagicMock()
        task.task_work_path = "task0"
        task.forward_files = ["frozen_model.pb"]
        job.job_task_list = [task]

        job._ensure_forward_files_on_retry()

        remote_file = os.path.join(self.remote_root, "task0", "frozen_model.pb")
        self.assertTrue(os.path.exists(remote_file))
        with open(remote_file, "rb") as f:
            self.assertEqual(f.read(), binary_content)

    def test_glob_expansion(self) -> None:
        """Glob patterns in forward_files are expanded correctly."""
        from dpdispatcher.contexts.local_context import LocalContext

        ctx = LocalContext.__new__(LocalContext)
        ctx.local_root = self.local_root
        ctx.remote_root = self.remote_root
        ctx.symlink = False
        ctx.submission = MagicMock()
        ctx.submission.forward_common_files = []

        local_task = os.path.join(self.local_root, "task0")
        os.makedirs(local_task)
        for name in ["graph.000.pb", "graph.001.pb"]:
            with open(os.path.join(local_task, name), "wb") as f:
                f.write(b"model")

        job = Job.__new__(Job)
        job.machine = MagicMock()
        job.machine.context = ctx
        task = MagicMock()
        task.task_work_path = "task0"
        task.forward_files = ["*.pb"]
        job.job_task_list = [task]

        job._ensure_forward_files_on_retry()

        for name in ["graph.000.pb", "graph.001.pb"]:
            self.assertTrue(
                os.path.exists(os.path.join(self.remote_root, "task0", name)),
                f"{name} not uploaded",
            )


if __name__ == "__main__":
    unittest.main()
