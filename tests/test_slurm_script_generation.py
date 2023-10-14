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

from .context import (
    Machine,
    Resources,
    Submission,
    Task,
    setUpModule,  # noqa: F401
)


class TestSlurmScriptGeneration(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_shell_trival(self):
        with open("jsons/machine_lazy_local_slurm.json") as f:
            machine_dict = json.load(f)

        machine = Machine(**machine_dict["machine"])
        resources = Resources(**machine_dict["resources"])

        task1 = Task(
            command="cat example.txt",
            task_work_path="dir1/",
            forward_files=["example.txt"],
            backward_files=["out.txt"],
            outlog="out.txt",
        )
        task2 = Task(
            command="cat example.txt",
            task_work_path="dir2/",
            forward_files=["example.txt"],
            backward_files=["out.txt"],
            outlog="out.txt",
        )
        task3 = Task(
            command="cat example.txt",
            task_work_path="dir3/",
            forward_files=["example.txt"],
            backward_files=["out.txt"],
            outlog="out.txt",
        )
        task4 = Task(
            command="cat example.txt",
            task_work_path="dir4/",
            forward_files=["example.txt"],
            backward_files=["out.txt"],
            outlog="out.txt",
        )
        task_list = [task1, task2, task3, task4]

        submission = Submission(
            work_base="parent_dir/",
            machine=machine,
            resources=resources,
            forward_common_files=["graph.pb"],
            backward_common_files=[],
            task_list=task_list,
        )
        submission.generate_jobs()
        str = machine.gen_script_header(submission.belonging_jobs[0])
        benchmark_str = textwrap.dedent(
            """\
            #!/bin/bash -l
            #SBATCH --parsable
            #SBATCH --nodes 1
            #SBATCH --ntasks-per-node 4
            #SBATCH --gres=gpu:2080Ti:2
            #SBATCH --partition GPU_2080Ti"""
        )
        self.assertEqual(str, benchmark_str)

    @unittest.skipIf(sys.platform == "win32", "skip for persimission error")
    def test_template(self):
        with open("jsons/machine_lazy_local_slurm.json") as f:
            machine_dict = json.load(f)

        benchmark_str = textwrap.dedent(
            """\
            #!/bin/bash -l
            #SBATCH --parsable
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

            task1 = Task(
                command="cat example.txt",
                task_work_path="dir1/",
                forward_files=["example.txt"],
                backward_files=["out.txt"],
                outlog="out.txt",
            )
            task2 = Task(
                command="cat example.txt",
                task_work_path="dir2/",
                forward_files=["example.txt"],
                backward_files=["out.txt"],
                outlog="out.txt",
            )
            task3 = Task(
                command="cat example.txt",
                task_work_path="dir3/",
                forward_files=["example.txt"],
                backward_files=["out.txt"],
                outlog="out.txt",
            )
            task4 = Task(
                command="cat example.txt",
                task_work_path="dir4/",
                forward_files=["example.txt"],
                backward_files=["out.txt"],
                outlog="out.txt",
            )
            task_list = [task1, task2, task3, task4]

            submission = Submission(
                work_base="parent_dir/",
                machine=machine,
                resources=resources,
                forward_common_files=["graph.pb"],
                backward_common_files=[],
                task_list=task_list,
            )
            submission.generate_jobs()
            str = machine.gen_script_header(submission.belonging_jobs[0])
            self.assertEqual(str, benchmark_str)
