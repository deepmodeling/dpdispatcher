import unittest
from types import SimpleNamespace
from typing import Any

from dpdispatcher.machines.fugaku import Fugaku
from dpdispatcher.machines.JH_UniScheduler import JH_UniScheduler
from dpdispatcher.machines.lsf import LSF
from dpdispatcher.machines.pbs import PBS, Torque
from dpdispatcher.submission import Resources


class TestOptionalSchedulerDirectives(unittest.TestCase):
    """Ensure optional resources do not produce empty scheduler directives."""

    def _job(self, *, kwargs: dict[str, Any] | None = None) -> SimpleNamespace:
        resources = Resources(
            number_node=1,
            cpu_per_node=4,
            gpu_per_node=0,
            queue_name="",
            group_size=1,
            kwargs=kwargs or {},
        )
        return SimpleNamespace(resources=resources)

    def test_empty_queue_directive_is_omitted(self) -> None:
        queue_prefixes = {
            PBS: "#PBS -q",
            Torque: "#PBS -q",
            LSF: "#BSUB -q",
            JH_UniScheduler: "#JSUB -q",
            Fugaku: '#PJM -L "rscgrp=',
        }

        for machine_class, queue_prefix in queue_prefixes.items():
            with self.subTest(machine=machine_class.__name__):
                machine = machine_class.__new__(machine_class)
                header = machine.gen_script_header(self._job())
                self.assertNotIn(queue_prefix, header)

    def test_zero_gpu_directive_is_omitted(self) -> None:
        scheduler_settings = {
            LSF: ({"gpu_usage": True}, "#BSUB -gpu"),
            JH_UniScheduler: ({}, "#JSUB -gpgpu"),
        }

        for machine_class, (kwargs, gpu_prefix) in scheduler_settings.items():
            with self.subTest(machine=machine_class.__name__):
                machine = machine_class.__new__(machine_class)
                header = machine.gen_script_header(self._job(kwargs=kwargs))
                self.assertNotIn(gpu_prefix, header)

    def test_custom_gpu_line_is_preserved_for_zero_gpu_count(self) -> None:
        scheduler_settings = {
            LSF: "#BSUB -R custom-gpu-resource",
            JH_UniScheduler: "#JSUB --custom-gpu",
        }

        for machine_class, custom_line in scheduler_settings.items():
            with self.subTest(machine=machine_class.__name__):
                machine = machine_class.__new__(machine_class)
                header = machine.gen_script_header(
                    self._job(kwargs={"custom_gpu_line": custom_line})
                )
                self.assertIn(custom_line, header)


if __name__ == "__main__":
    unittest.main()
