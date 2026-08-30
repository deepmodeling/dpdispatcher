import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from dpdispatcher import Resources, Task
from dpdispatcher.machine import Machine


class TestRemoteRootQuoting(unittest.TestCase):
    def test_shell_generated_script_runs_when_remote_root_contains_spaces(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dpdispatcher remote root ") as remote_root:
            remote_path = Path(remote_root)
            task_dir = remote_path / "task dir"
            task_dir.mkdir()

            task = Task(
                "printf 'ok' > result.txt",
                "task dir",
                outlog=None,
                errlog="error log",
            )
            resources = Resources(1, 1, 0, "", 1)
            job = SimpleNamespace(
                resources=resources,
                job_task_list=[task],
                job_hash="job-hash",
                script_file_name="job.sub",
                fail_count=0,
            )
            machine = Machine(
                batch_type="Shell",
                context_type="LazyLocalContext",
                local_root=".",
            )
            machine.context.remote_root = remote_root

            (remote_path / "job.sub.run").write_text(
                machine.gen_script_command(job), encoding="utf-8"
            )
            completed = subprocess.run(
                ["bash"],
                input=machine.gen_script(job),
                cwd=remote_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual((task_dir / "result.txt").read_text(), "ok")
            self.assertEqual(
                (remote_path / "job-hash_flag_if_job_task_fail").read_text().strip(),
                "0",
            )
            self.assertTrue((remote_path / "job-hash_job_tag_finished").exists())


if __name__ == "__main__":
    unittest.main()
