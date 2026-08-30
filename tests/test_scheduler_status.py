import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from dpdispatcher.machine import Machine
from dpdispatcher.machines.fugaku import Fugaku
from dpdispatcher.machines.JH_UniScheduler import JH_UniScheduler
from dpdispatcher.machines.lsf import LSF
from dpdispatcher.machines.pbs import PBS, Torque
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

    def test_empty_pbs_family_output_uses_finish_tag(self) -> None:
        """PBS-family backends must not index an absent status row."""
        for machine_class in (PBS, Torque, Fugaku):
            for finish_tag, expected in (
                (True, JobStatus.finished),
                (False, JobStatus.terminated),
            ):
                with self.subTest(
                    machine=machine_class.__name__, finish_tag=finish_tag
                ):
                    machine = machine_class.__new__(machine_class)
                    machine.context = SimpleNamespace(
                        block_call=Mock(
                            return_value=(
                                0,
                                None,
                                io.BytesIO(b""),
                                io.BytesIO(),
                            )
                        ),
                        check_file_exists=Mock(return_value=finish_tag),
                    )
                    job = SimpleNamespace(job_id="123", job_hash="job-hash")

                    self.assertEqual(machine.check_status(job), expected)

    def test_pbs_status_rows_map_to_dispatcher_states(self) -> None:
        """PBS and Torque share the same state-column interpretation."""
        job = SimpleNamespace(job_id="123", job_hash="job-hash")
        for machine_class in (PBS, Torque):
            for status_word, expected, finish_tag in (
                ("Q", JobStatus.waiting, False),
                ("H", JobStatus.waiting, False),
                ("R", JobStatus.running, False),
                ("C", JobStatus.finished, True),
                ("E", JobStatus.terminated, False),
                ("K", JobStatus.finished, True),
                ("F", JobStatus.terminated, False),
                ("OTHER", JobStatus.unknown, False),
            ):
                with self.subTest(
                    machine=machine_class.__name__, status_word=status_word
                ):
                    machine = machine_class.__new__(machine_class)
                    machine.context = SimpleNamespace(
                        check_file_exists=Mock(return_value=finish_tag)
                    )
                    output = (
                        f"header\n123.server name user 00:00:00 {status_word} queue\n"
                    )
                    self.assertEqual(
                        machine._parse_status_output(output, job), expected
                    )

    def test_pbs_short_status_row_uses_finish_tag(self) -> None:
        """Malformed rows follow the same finished-versus-terminated rule."""
        job = SimpleNamespace(job_id="123", job_hash="job-hash")
        for finish_tag, expected in (
            (True, JobStatus.finished),
            (False, JobStatus.terminated),
        ):
            with self.subTest(finish_tag=finish_tag):
                machine = PBS.__new__(PBS)
                machine.context = SimpleNamespace(
                    check_file_exists=Mock(return_value=finish_tag)
                )
                self.assertEqual(
                    machine._parse_status_output("header\n", job), expected
                )


if __name__ == "__main__":
    unittest.main()
