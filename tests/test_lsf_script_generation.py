# from dpdispatcher.batch_object import BatchObject
# from dpdispatcher.batch import Batch
import sys, os, shutil
import textwrap
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import Submission, Job, Task, Resources
from .context import Shell
from .context import LocalContext
from .context import get_file_md5
from .context import Machine

import unittest
import json


class TestLSFScriptGeneration(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_shell_trival(self):
        with open('jsons/machine_lazy_local_lsf.json', 'r') as f:
            machine_dict = json.load(f)

        machine = Machine(**machine_dict['machine'])
        resources = Resources(**machine_dict['resources'])

        task1 = Task(command='cat example.txt', task_work_path='dir1/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        task2 = Task(command='cat example.txt', task_work_path='dir2/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        task3 = Task(command='cat example.txt', task_work_path='dir3/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        task4 = Task(command='cat example.txt', task_work_path='dir4/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
        task_list = [task1, task2, task3, task4]

        submission = Submission(work_base='parent_dir/',
            machine=machine,
            resources=resources,
            forward_common_files=['graph.pb'],
            backward_common_files=[],
            task_list=task_list
        )
        submission.generate_jobs()
        
        task_hash = submission.get_hash()
        test_job = submission.belonging_jobs[0]
        job_hash = test_job.job_hash

        header_str = machine.gen_script_header(test_job)
        benchmark_header = textwrap.dedent("""\
            #!/bin/bash -l
            #BSUB -e %J.err
            #BSUB -o %J.out
            #BSUB -n 4
            #BSUB -R 'span[ptile=4]'
            #BSUB -q gpu
            #BSUB -gpu 'num=1:mode=shared:j_exclusive=no'""")
        self.assertEqual(header_str, benchmark_header)

        custom_flags_str = machine.gen_script_custom_flags_lines(test_job)
        benchmark_custom_flags = textwrap.dedent("""\
            #BSUB -R "select[hname != g005]"
            #BSUB -W 24:00
            """)
        self.assertEqual(custom_flags_str, benchmark_custom_flags)

        env_str = machine.gen_script_env(test_job)
        benchmark_env = textwrap.dedent("""
            REMOTE_ROOT={task_hash}
            echo 0 > $REMOTE_ROOT/{job_hash}_flag_if_job_task_fail
            test $? -ne 0 && exit 1

            module purge

            module load use.own
            module load deepmd/1.3

            {{ source /data/home/ypliu/scripts/avail_gpu.sh; }} 
            {{ source /data/home/ypliu/dprun/tf_envs.sh; }} 

            export DP_DISPATCHER_EXPORT=test_foo_bar_baz

            echo 'The summer you were there.'
            """.format(task_hash=task_hash, job_hash=job_hash))
        self.assertEqual(env_str.split("\n")[2:], benchmark_env.split("\n")[2:])

        footer_str = machine.gen_script_end(test_job)
        benchmark_footer = textwrap.dedent(f"""\

            cd $REMOTE_ROOT
            test $? -ne 0 && exit 1

            wait
            FLAG_IF_JOB_TASK_FAIL=$(cat {job_hash}_flag_if_job_task_fail)
            if test $FLAG_IF_JOB_TASK_FAIL -eq 0; then touch {job_hash}_job_tag_finished; else exit 1;fi

            echo 'shizuku'
            echo 'kaori'
            """)
        self.assertEqual(footer_str, benchmark_footer)
