import sys, os, shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import (
    Submission,
    Task,
    Resources,
    Machine,
)

import unittest

class RunSubmission:
    def setUp(self):
        self.machine_dict = {
            "batch_type": "Shell",
            "context_type": "LocalContext",
            "local_root" : "test_run_submission/",
            # /data is mounted in the docker container
            "remote_root" : os.path.join(os.environ.get("CI_SHARED_SPACE", "/"), "tmp_run_submission"),
            "remote_profile": {}
        }
        self.resources_dict = {
            "number_node": 1,
            "cpu_per_node": 1,
            "gpu_per_node": 0,
            "queue_name": "?",
            "group_size": 2,
        }
        os.makedirs(os.path.join(self.machine_dict['local_root'], 'test_dir'), exist_ok=True)
        os.makedirs(os.path.join(self.machine_dict['local_root'], 'test_dir', 'test space'), exist_ok=True)
        with open(os.path.join(self.machine_dict['local_root'], 'test_dir', 'test space', 'inp space.txt'), 'w') as f:
            f.write('inp space')

    def test_run_submission(self):
        machine = Machine.load_from_dict(self.machine_dict)
        resources = Resources.load_from_dict(self.resources_dict)

        task_list = []
        for ii in range(4):
            task = Task(
                command=f"echo dpdispatcher_unittest_{ii}",
                task_work_path='./',
                forward_files=[],
                backward_files=[f'out{ii}.txt'],
                outlog=f'out{ii}.txt'
            )
            task_list.append(task)

        # test space in file name
        task_list.append(Task(
            command=f"echo dpdispatcher_unittest_space",
            task_work_path='test space/',
            forward_files=['inp space.txt'],
            backward_files=['out space.txt'],
            outlog='out space.txt',
        ))
        submission = Submission(work_base='test_dir/',
            machine=machine,
            resources=resources,
            forward_common_files=[],
            backward_common_files=[],
            task_list=task_list
        )
        submission.run_submission()

        for ii in range(4):
            self.assertTrue(os.path.isfile(os.path.join(self.machine_dict['local_root'], 'test_dir/', f'out{ii}.txt')))

    def tearDown(self):
        shutil.rmtree(os.path.join(self.machine_dict['local_root']))


@unittest.skipIf(os.environ.get('DPDISPATCHER_TEST') != 'slurm', "outside the slurm testing environment")
class TestSlurmRun(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.machine_dict["batch_type"] = "Slurm"
        self.resources_dict["queue_name"] = "normal"


@unittest.skipIf(os.environ.get('DPDISPATCHER_TEST') != 'slurm', "outside the slurm testing environment")
class TestSlurmJobArrayRun(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.machine_dict["batch_type"] = "SlurmJobArray"
        self.resources_dict["queue_name"] = "normal"


@unittest.skipIf(os.environ.get('DPDISPATCHER_TEST') != 'pbs', "outside the pbs testing environment")
class TestPBSRun(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.machine_dict["batch_type"] = "PBS"
        self.resources_dict["queue_name"] = "workq"


@unittest.skipIf(sys.platform == 'win32', 'Shell is not supported on Windows')
class TestLazyLocalContext(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.machine_dict["context_type"] = "LazyLocalContext"
