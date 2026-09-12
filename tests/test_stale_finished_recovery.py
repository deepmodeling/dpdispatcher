import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher import Task
from dpdispatcher.utils.job_status import JobStatus


class TestStaleFinishedRecovery(unittest.TestCase):
    def test_missing_backward_file_reopens_task_and_quarantines_tag(self) -> None:
        task = Task("true", "task", backward_files=["result"])
        task.task_state = JobStatus.finished
        context = MagicMock()
        context.remote_root = "/remote/submission"
        context.check_file_exists.side_effect = lambda path: path.endswith(
            "_task_tag_finished"
        )
        context.sftp = MagicMock()

        task.reconcile_finished_state(context)

        self.assertEqual(task.task_state, JobStatus.unsubmitted)
        context.sftp.rename.assert_called_once()
        self.assertTrue(
            context.sftp.rename.call_args.args[1].endswith(".stale-recovery")
        )

    def test_complete_backward_file_keeps_finished_task(self) -> None:
        task = Task("true", "task", backward_files=["result"])
        task.task_state = JobStatus.finished
        context = MagicMock()
        context.check_file_exists.return_value = True
        context.sftp = MagicMock()

        task.reconcile_finished_state(context)

        self.assertEqual(task.task_state, JobStatus.finished)
        context.sftp.rename.assert_not_called()

    def test_local_glob_output_keeps_finished_task(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "task" / "results" / "frame.out"
            output.parent.mkdir(parents=True)
            output.write_text("ok", encoding="utf-8")
            task = Task("true", "task", backward_files=["results/*.out"])
            task.task_state = JobStatus.finished
            context = SimpleNamespace(
                remote_root=root,
                check_file_exists=lambda path: (Path(root) / path).is_file(),
            )

            task.reconcile_finished_state(context)

            self.assertEqual(task.task_state, JobStatus.finished)

    def test_ssh_glob_output_keeps_finished_task(self) -> None:
        task = Task("true", "task", backward_files=["results/*.out"])
        task.task_state = JobStatus.finished
        context = MagicMock()
        context.remote_root = "/remote/submission"
        context.check_file_exists.return_value = False
        context.list_remote_dir = MagicMock(
            side_effect=lambda sftp, remote, ref, result: result.extend(
                ["task/results/frame.out"]
            )
        )

        task.reconcile_finished_state(context)

        self.assertEqual(task.task_state, JobStatus.finished)

    @patch("dpdispatcher.utils.hdfs_cli._run_hadoop")
    def test_hdfs_glob_output_is_detected(self, run_hadoop: MagicMock) -> None:
        run_hadoop.return_value = (0, b"-rw-r--r-- hdfs frame.out\n", b"")

        from dpdispatcher.utils.hdfs_cli import HDFS

        self.assertTrue(HDFS.glob_exists("hdfs:///work/results/*.out"))
        run_hadoop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
