import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from dpdispatcher.machine import Machine
from dpdispatcher.machines.JH_UniScheduler import JH_UniScheduler
from dpdispatcher.machines.lsf import LSF
from dpdispatcher.machines.slurm import Slurm
from dpdispatcher.utils.job_status import JobStatus


class TestSchedulerStatusParsing(unittest.TestCase):
    """Exercise scheduler responses that contain no usable job data row."""

    def _check_header_only_status(
        self, machine_class: type[Machine], finish_tag: bool
    ) -> None:
        machine = machine_class.__new__(machine_class)
        machine.context = SimpleNamespace(
            block_call=Mock(
                return_value=(
                    0,
                    None,
                    io.BytesIO(b"JOBID USER STAT QUEUE\n\n"),
                    io.BytesIO(),
                )
            ),
            check_file_exists=Mock(return_value=finish_tag),
        )
        job = SimpleNamespace(job_id="123", job_hash="job-hash")

        status = machine.check_status(job)

        if finish_tag:
            expected = JobStatus.finished
        elif machine_class is Slurm:
            # A disappeared Slurm job without its success marker has failed;
            # report it as terminated so Submission can retry it.
            expected = JobStatus.terminated
        else:
            expected = JobStatus.unknown
        self.assertEqual(status, expected)

    def test_header_only_output_uses_finish_tag(self) -> None:
        for machine_class in (LSF, JH_UniScheduler, Slurm):
            with self.subTest(machine=machine_class.__name__):
                self._check_header_only_status(machine_class, finish_tag=True)

    def test_header_only_output_without_finish_tag_is_not_finished(self) -> None:
        for machine_class in (LSF, JH_UniScheduler, Slurm):
            with self.subTest(machine=machine_class.__name__):
                self._check_header_only_status(machine_class, finish_tag=False)

    def test_empty_slurm_output_uses_finish_tag(self) -> None:
        """An entirely empty squeue response follows the same fallback."""
        machine = Slurm.__new__(Slurm)
        machine.context = SimpleNamespace(
            block_call=Mock(
                return_value=(0, None, io.BytesIO(b""), io.BytesIO())
            ),
            check_file_exists=Mock(return_value=False),
        )
        job = SimpleNamespace(job_id="123", job_hash="job-hash")

        self.assertEqual(machine.check_status(job), JobStatus.terminated)

    def test_short_data_row_is_unknown(self) -> None:
        for machine_class in (LSF, JH_UniScheduler):
            with self.subTest(machine=machine_class.__name__):
                machine = machine_class.__new__(machine_class)
                machine.context = SimpleNamespace(
                    block_call=Mock(
                        return_value=(
                            0,
                            None,
                            io.BytesIO(b"JOBID USER STAT\n123 user\n"),
                            io.BytesIO(),
                        )
                    ),
                    check_file_exists=Mock(return_value=False),
                )
                job = SimpleNamespace(job_id="123", job_hash="job-hash")

                self.assertEqual(machine.check_status(job), JobStatus.unknown)


if __name__ == "__main__":
    unittest.main()
