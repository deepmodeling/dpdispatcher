"""Regression tests for generated scripts with whitespace in remote paths."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from dpdispatcher import Machine, Resources, Submission, Task
from dpdispatcher.utils.job_status import JobStatus


@unittest.skipIf(sys.platform == "win32", "Shell is not supported on Windows")
class TestRemoteRootWithSpaces(unittest.TestCase):
    """Ensure Shell and LocalContext preserve whitespace in remote roots."""

    def test_shell_submission_runs_in_remote_root_with_spaces(self) -> None:
        """A generated script must not split REMOTE_ROOT at whitespace."""
        with patch("time.sleep", return_value=None):
            self._run_submission()

    def _run_submission(self) -> None:
        """Run a tiny local job using roots whose names contain spaces."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local_root = root / "local root"
            remote_root = root / "remote root"
            task_dir = local_root / "work" / "task dir"
            task_dir.mkdir(parents=True)

            task = Task(
                command="printf 'hello\\n' > result.txt",
                task_work_path="task dir",
                backward_files=["result.txt"],
                outlog=None,
                errlog=None,
            )
            machine = Machine(
                batch_type="Shell",
                context_type="LocalContext",
                local_root=str(local_root),
                remote_root=str(remote_root),
            )
            submission = Submission(
                work_base="work",
                machine=machine,
                resources=Resources(1, 1, 0, "", 1),
                task_list=[task],
            )
            submission.generate_jobs()
            # ``run_submission`` is intentionally exercised after generation;
            # initialize the generated job as the lifecycle expects it to be.
            submission.belonging_jobs[0].job_state = JobStatus.unsubmitted
            submission.run_submission(clean=False, check_interval=0)

            self.assertEqual((task_dir / "result.txt").read_text(), "hello\n")


if __name__ == "__main__":
    unittest.main()
