import io
import unittest
from types import SimpleNamespace
from typing import Type
from unittest.mock import Mock

from dpdispatcher.machine import Machine
from dpdispatcher.machines.JH_UniScheduler import JH_UniScheduler
from dpdispatcher.machines.lsf import LSF
from dpdispatcher.utils.job_status import JobStatus


class TestSchedulerStatusParsing(unittest.TestCase):
    """Exercise scheduler responses that contain no usable job data row."""

    def _check_header_only_status(
        self, machine_class: Type[Machine], finish_tag: bool
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

        expected = JobStatus.finished if finish_tag else JobStatus.unknown
        self.assertEqual(status, expected)

    def test_header_only_output_uses_finish_tag(self) -> None:
        for machine_class in (LSF, JH_UniScheduler):
            with self.subTest(machine=machine_class.__name__):
                self._check_header_only_status(machine_class, finish_tag=True)

    def test_header_only_output_without_finish_tag_is_unknown(self) -> None:
        for machine_class in (LSF, JH_UniScheduler):
            with self.subTest(machine=machine_class.__name__):
                self._check_header_only_status(machine_class, finish_tag=False)

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
