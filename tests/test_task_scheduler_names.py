import unittest

from dpdispatcher import Job, Machine, Resources, Submission, Task


class TestTaskSchedulerNames(unittest.TestCase):
    def _job(
        self, batch_type: str, tasks: list[Task], group_size: int = 1
    ) -> tuple[Machine, Job]:
        machine = Machine(
            batch_type=batch_type,
            context_type="LazyLocalContext",
            local_root=".",
        )
        submission = Submission(
            work_base=".",
            machine=machine,
            resources=Resources(1, 1, 0, "", group_size),
            task_list=tasks,
        )
        submission.generate_jobs()
        return machine, submission.belonging_jobs[0]

    def test_one_task_name_is_emitted_by_supported_schedulers(self) -> None:
        expected = {
            "Slurm": "#SBATCH --job-name water-001",
            "PBS": "#PBS -N water-001",
            "Torque": "#PBS -N water-001",
            "LSF": "#BSUB -J water-001",
            "SGE": "#$ -N water-001",
        }
        for batch_type, directive in expected.items():
            with self.subTest(batch_type=batch_type):
                machine, job = self._job(
                    batch_type, [Task("true", ".", task_name="water 001")]
                )
                self.assertIn(directive, machine.gen_script_header(job))

    def test_grouped_tasks_keep_backend_fallback(self) -> None:
        machine, job = self._job(
            "Slurm",
            [
                Task("true", "task-a", task_name="alpha"),
                Task("true", "task-b", task_name="beta"),
            ],
            group_size=2,
        )
        self.assertIsNone(job.get_scheduler_name(128))
        self.assertNotIn("--job-name", machine.gen_script_header(job))

    def test_pbs_name_is_portable_and_collision_resistant(self) -> None:
        _, first = self._job(
            "PBS", [Task("true", ".", task_name="123 very long calculation alpha")]
        )
        _, second = self._job(
            "PBS", [Task("true", ".", task_name="123 very long calculation beta")]
        )

        first_name = first.get_scheduler_name(15, require_alpha_prefix=True)
        second_name = second.get_scheduler_name(15, require_alpha_prefix=True)
        self.assertIsNotNone(first_name)
        self.assertIsNotNone(second_name)
        assert first_name is not None and second_name is not None
        self.assertLessEqual(len(first_name), 15)
        self.assertTrue(first_name[0].isalpha())
        self.assertNotEqual(first_name, second_name)


if __name__ == "__main__":
    unittest.main()
