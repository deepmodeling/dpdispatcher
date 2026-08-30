# from dpdispatcher.batch_object import BatchObject
# from dpdispatcher.batch import Batch
import os
import sys
import tempfile
import textwrap

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
import json
import unittest
from types import SimpleNamespace
from typing import Any

from dpdispatcher.machines.slurm import SlurmJobArray

from .context import (
    Job,
    Machine,
    Resources,
    Task,
    setUpModule,  # noqa: F401
)


class TestSlurmScriptGeneration(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None

    def _make_header(
        self,
        resource_updates: dict[str, Any] | None = None,
        remove_resource_keys: list[str] | None = None,
    ) -> str:
        with open("jsons/machine_lazy_local_slurm.json") as f:
            machine_dict = json.load(f)

        resource_updates = resource_updates or {}
        remove_resource_keys = remove_resource_keys or []
        for key in remove_resource_keys:
            machine_dict["resources"].pop(key, None)
        machine_dict["resources"].update(resource_updates)

        machine = Machine(**machine_dict["machine"])
        resources = Resources(**machine_dict["resources"])
        return machine.gen_script_header(SimpleNamespace(resources=resources))

    def test_shell_trival(self) -> None:
        header = self._make_header()
        benchmark_str = textwrap.dedent(
            """\
            #!/bin/bash -l
            #SBATCH --nodes 1
            #SBATCH --ntasks-per-node 4
            #SBATCH --gres=gpu:2080Ti:2
            #SBATCH --partition GPU_2080Ti"""
        )
        self.assertEqual(header, benchmark_str)

    def test_cpu_header_omits_gpu_request(self) -> None:
        header = self._make_header(
            resource_updates={
                "gpu_per_node": 0,
                "queue_name": "CPU",
                "strategy": {"if_cuda_multi_devices": False},
            },
            remove_resource_keys=["custom_gpu_line"],
        )

        self.assertIn("#!/bin/bash -l", header)
        self.assertNotIn("#SBATCH --parsable", header)
        self.assertNotIn("#SBATCH --gres=gpu:0", header)
        self.assertIn("#SBATCH --nodes 1", header)
        self.assertIn("#SBATCH --ntasks-per-node 4", header)
        self.assertIn("#SBATCH --partition CPU", header)

    def test_gpu_header_uses_default_gres_when_requested(self) -> None:
        header = self._make_header(remove_resource_keys=["custom_gpu_line"])

        self.assertIn("#SBATCH --gres=gpu:2", header)

    def test_repeated_script_command_generation_is_deterministic(self) -> None:
        """Repeated rendering must not carry parallelism state across calls."""
        machine = Machine(
            batch_type="Slurm",
            context_type="LazyLocalContext",
            local_root=".",
            remote_root="/tmp/dpdispatcher",
            remote_profile={},
        )
        resources = Resources(
            number_node=1,
            cpu_per_node=1,
            gpu_per_node=0,
            queue_name="",
            group_size=3,
            para_deg=2,
        )
        tasks = [
            Task(
                command=f"echo {index}",
                task_work_path=".",
                forward_files=[],
                backward_files=[],
                outlog=None,
                errlog=None,
            )
            for index in range(3)
        ]
        job = Job(job_task_list=tasks, resources=resources, machine=machine)

        first = machine.gen_script_command(job)
        second = machine.gen_script_command(job)

        self.assertEqual(first, second)

    def test_repeated_job_array_script_generation_is_deterministic(self) -> None:
        """Slurm job arrays reset the same per-script counters as Slurm."""
        machine = Machine(
            batch_type="Slurm",
            context_type="LazyLocalContext",
            local_root=".",
            remote_root="/tmp/dpdispatcher",
            remote_profile={},
        )
        resources = Resources(
            number_node=1,
            cpu_per_node=1,
            gpu_per_node=2,
            queue_name="",
            group_size=3,
            para_deg=1,
            strategy={"if_cuda_multi_devices": True},
        )
        tasks = [
            Task(
                command=f"echo {index}",
                task_work_path=".",
                forward_files=[],
                backward_files=[],
                outlog=None,
                errlog=None,
            )
            for index in range(3)
        ]
        job = Job(job_task_list=tasks, resources=resources, machine=machine)
        array_machine = SlurmJobArray(
            context=machine.context,
            retry_count=machine.retry_count,
        )

        first = array_machine.gen_script_command(job)
        second = array_machine.gen_script_command(job)

        self.assertEqual(first, second)

    @unittest.skipIf(sys.platform == "win32", "skip for persimission error")
    def test_template(self) -> None:
        with open("jsons/machine_lazy_local_slurm.json") as f:
            machine_dict = json.load(f)

        benchmark_str = textwrap.dedent(
            """\
            #!/bin/bash -l
            #SBATCH --nodes 1
            #SBATCH --ntasks-per-node 4
            #SBATCH --gres=gpu:2080Ti:2
            #SBATCH --partition GPU_2080Ti"""
        )

        with tempfile.NamedTemporaryFile("w") as f:
            f.write(benchmark_str)
            f.flush()

            machine_dict["resources"]["strategy"][
                "customized_script_header_template_file"
            ] = f.name

            machine = Machine(**machine_dict["machine"])
            resources = Resources(**machine_dict["resources"])
            header = machine.gen_script_header(SimpleNamespace(resources=resources))
            self.assertEqual(header, benchmark_str)
