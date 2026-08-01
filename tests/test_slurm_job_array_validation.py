import unittest
from types import SimpleNamespace

from dargs.dargs import ArgumentValueError

from dpdispatcher.machines.slurm import SlurmJobArray


class TestSlurmJobArrayValidation(unittest.TestCase):
    """Reject invalid array grouping before script arithmetic begins."""

    def test_invalid_slurm_job_size_is_rejected_by_script_generators(self) -> None:
        machine = SlurmJobArray.__new__(SlurmJobArray)

        for value in (0, -1, 1.5, "2", True):
            with self.subTest(value=value):
                job = SimpleNamespace(
                    resources=SimpleNamespace(kwargs={"slurm_job_size": value})
                )
                for generator in (
                    machine.gen_script_header,
                    machine.gen_script_command,
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "slurm_job_size must be an integer greater than or equal to 1",
                    ):
                        generator(job)

    def test_default_slurm_job_size_is_one(self) -> None:
        job = SimpleNamespace(resources=SimpleNamespace(kwargs={}))

        self.assertEqual(SlurmJobArray._get_slurm_job_size(job), 1)

    def test_resource_schema_rejects_non_positive_slurm_job_size(self) -> None:
        kwargs_argument = SlurmJobArray.resources_subfields()[0]

        for value in (0, -1):
            with self.subTest(value=value):
                normalized = kwargs_argument.normalize_value({"slurm_job_size": value})
                with self.assertRaisesRegex(
                    ArgumentValueError,
                    "slurm_job_size must be greater than or equal to 1",
                ):
                    kwargs_argument.check_value(normalized)


if __name__ == "__main__":
    unittest.main()
