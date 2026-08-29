import unittest
from types import SimpleNamespace

from dpdispatcher import Resources, Task
from dpdispatcher.entrypoints.submission import _configured_log_files
from dpdispatcher.machine import Machine


class TestNoneErrlogScriptGeneration(unittest.TestCase):
    def _make_job(self, tasks):
        resources = Resources(1, 1, 0, "", len(tasks))
        return SimpleNamespace(
            resources=resources,
            job_task_list=tasks,
            job_hash="job-hash",
            fail_count=0,
        )

    def _make_machine(self, batch_type):
        return Machine(
            batch_type=batch_type,
            context_type="LazyLocalContext",
            local_root=".",
        )

    def test_generic_machine_omits_tail_without_errlog(self):
        machine = self._make_machine("Shell")
        task = Task("false", "task dir", outlog=None, errlog=None)

        script = machine.gen_script_command(self._make_job([task]))

        self.assertNotIn("1>>", script)
        self.assertNotIn("2>>", script)
        self.assertNotIn("tail -v", script)
        self.assertIn("echo 1 > $REMOTE_ROOT/job-hash_flag_if_job_task_fail", script)

    def test_generic_machine_keeps_tail_for_configured_errlog(self):
        machine = self._make_machine("Shell")
        task = Task("false", "task dir", errlog="error log")

        script = machine.gen_script_command(self._make_job([task]))

        self.assertIn("2>>'error log'", script)
        self.assertIn(
            "tail -v -c 1000 $REMOTE_ROOT/'task dir'/'error log'",
            script,
        )
        self.assertIn("> $REMOTE_ROOT/job-hash_last_err_file", script)

    def test_slurm_job_array_handles_mixed_errlogs(self):
        machine = self._make_machine("SlurmJobArray")
        tasks = [
            Task("false", "task-a", errlog=None),
            Task("false", "task-b", errlog="err"),
        ]

        script = machine.gen_script_command(self._make_job(tasks))

        self.assertEqual(script.count("tail -v -c 1000"), 1)
        self.assertNotIn("task-a/''", script)
        self.assertIn("$REMOTE_ROOT/task-b/err", script)

    def test_terminated_log_files_filter_optional_names(self):
        cases = (
            (Task("true", ".", outlog="out", errlog=None), ["out"]),
            (Task("true", ".", outlog=None, errlog="err"), ["err"]),
            (Task("true", ".", outlog=None, errlog=None), []),
        )

        for task, expected in cases:
            with self.subTest(outlog=task.outlog, errlog=task.errlog):
                self.assertEqual(_configured_log_files(task), expected)


if __name__ == "__main__":
    unittest.main()
