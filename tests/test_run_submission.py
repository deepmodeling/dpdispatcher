import asyncio
import os
import random
import shutil
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
import unittest

from .context import (
    Machine,
    Resources,
    Submission,
    Task,
    handle_submission,
    record,
    setUpModule,  # noqa: F401
)


class RunSubmission:
    def setUp(self):
        self.machine_dict = {
            "batch_type": "Shell",
            "context_type": "LocalContext",
            "local_root": "test_run_submission/",
            # /data is mounted in the docker container
            "remote_root": os.path.join(
                os.environ.get("CI_SHARED_SPACE", "/"), "tmp_run_submission"
            ),
            "remote_profile": {},
        }
        self.resources_dict = {
            "number_node": 1,
            "cpu_per_node": 1,
            "gpu_per_node": 0,
            "queue_name": "?",
            "group_size": 2,
        }
        os.makedirs(
            os.path.join(self.machine_dict["local_root"], "test_dir"), exist_ok=True
        )
        os.makedirs(
            os.path.join(self.machine_dict["local_root"], "test_dir", "test space"),
            exist_ok=True,
        )
        with open(
            os.path.join(
                self.machine_dict["local_root"],
                "test_dir",
                "test space",
                "inp space.txt",
            ),
            "w",
        ) as f:
            f.write("inp space")

    def test_run_submission(self):
        machine = Machine.load_from_dict(self.machine_dict)
        resources = Resources.load_from_dict(self.resources_dict)

        task_list = []
        for ii in range(4):
            task = Task(
                command=f"echo dpdispatcher_unittest_{ii}",
                task_work_path="./",
                forward_files=[],
                backward_files=[f"out{ii}.txt"],
                outlog=f"out{ii}.txt",
            )
            task_list.append(task)

        for ii in range(2):
            task = Task(
                command=f"mkdir -p out_dir{ii} && touch out_dir{ii}/out{ii}",
                task_work_path="./",
                forward_files=[],
                backward_files=[f"out_dir{ii}"],
                outlog=f"out_dir{ii}.txt",
            )
            task_list.append(task)

        # test space in file name
        task_list.append(
            Task(
                command="echo dpdispatcher_unittest_space",
                task_work_path="test space/",
                forward_files=["inp space.txt"],
                backward_files=["out space.txt"],
                outlog="out space.txt",
            )
        )
        submission = Submission(
            work_base="test_dir/",
            machine=machine,
            resources=resources,
            forward_common_files=[],
            backward_common_files=[],
            task_list=task_list,
        )
        # test override directory
        os.makedirs(
            os.path.join(self.machine_dict["local_root"], "test_dir", "out_dir1"),
            exist_ok=True,
        )
        submission.run_submission(check_interval=2)

        for ii in range(4):
            self.assertTrue(
                os.path.isfile(
                    os.path.join(
                        self.machine_dict["local_root"], "test_dir/", f"out{ii}.txt"
                    )
                )
            )

    def test_failed_submission(self):
        machine = Machine.load_from_dict(self.machine_dict)
        resources = Resources.load_from_dict(self.resources_dict)

        task_list = []
        err_msg = "DPDISPATCHER_TEST"
        # prevent err_msg directly in commands; we need to check error message
        err_msg_shell = "".join([f'"{x}"' for x in err_msg])
        for ii in range(1):
            task = Task(
                command=f'echo "Error!" {err_msg_shell} 1>&2 && exit 1',
                task_work_path="./",
                forward_files=[],
                backward_files=[f"out{ii}.txt"],
                outlog=f"out{ii}.txt",
                errlog=f"err{ii}.txt",
            )
            task_list.append(task)

        submission = Submission(
            work_base="test_dir/",
            machine=machine,
            resources=resources,
            forward_common_files=[],
            backward_common_files=[],
            task_list=task_list,
        )
        try:
            submission.run_submission(check_interval=2)
        except RuntimeError:
            # macos shell has some issues
            if sys.platform == "linux":
                self.assertTrue(err_msg in traceback.format_exc())
            self.assertTrue(record.get_submission(submission.submission_hash).is_file())
            # post processing
            handle_submission(
                submission_hash=submission.submission_hash,
                download_finished_task=True,
                download_terminated_log=True,
                clean=True,
            )

    def test_async_run_submission(self):
        machine = Machine.load_from_dict(self.machine_dict)
        resources = Resources.load_from_dict(self.resources_dict)
        ntask = 4

        async def run_jobs(ntask):
            background_tasks = set()
            for ii in range(ntask):
                sleep_time = random.random() * 5 + 2
                task = Task(
                    command=f"echo dpdispatcher_unittest_{ii} && sleep {sleep_time}",
                    task_work_path="./",
                    forward_files=[],
                    backward_files=[f"out{ii}.txt"],
                    outlog=f"out{ii}.txt",
                )
                submission = Submission(
                    work_base="test_dir/",
                    machine=machine,
                    resources=resources,
                    forward_common_files=[],
                    backward_common_files=[],
                    task_list=[task],
                )
                background_task = asyncio.create_task(
                    submission.async_run_submission(check_interval=2, clean=False)
                )
                background_tasks.add(background_task)
                # background_task.add_done_callback(background_tasks.discard)
            res = await asyncio.gather(*background_tasks)
            return res

        res = asyncio.run(run_jobs(ntask=ntask))
        print(res)

        for ii in range(4):
            self.assertTrue(
                os.path.isfile(
                    os.path.join(
                        self.machine_dict["local_root"], "test_dir/", f"out{ii}.txt"
                    )
                )
            )

    def tearDown(self):
        shutil.rmtree(os.path.join(self.machine_dict["local_root"]))


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "slurm",
    "outside the slurm testing environment",
)
class TestSlurmRun(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.machine_dict["batch_type"] = "Slurm"
        self.resources_dict["queue_name"] = "normal"

    @unittest.skip("Manaually skip")  # comment this line to open unittest
    def test_async_run_submission(self):
        return super().test_async_run_submission()


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "slurm",
    "outside the slurm testing environment",
)
class TestSlurmJobArrayRun(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.machine_dict["batch_type"] = "SlurmJobArray"
        self.resources_dict["queue_name"] = "normal"

    @unittest.skip("Manaually skip")  # comment this line to open unittest
    def test_async_run_submission(self):
        return super().test_async_run_submission()


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "slurm",
    "outside the slurm testing environment",
)
class TestSlurmJobArrayRun2(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.machine_dict["batch_type"] = "SlurmJobArray"
        self.resources_dict["queue_name"] = "normal"
        self.resources_dict["kwargs"] = {"slurm_job_size": 2}

    @unittest.skip("Manaually skip")  # comment this line to open unittest
    def test_async_run_submission(self):
        return super().test_async_run_submission()


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "pbs", "outside the pbs testing environment"
)
class TestPBSRun(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.machine_dict["batch_type"] = "PBS"
        self.resources_dict["queue_name"] = "workq"

    @unittest.skip("Manaually skip")  # comment this line to open unittest
    def test_async_run_submission(self):
        return super().test_async_run_submission()


@unittest.skipIf(sys.platform == "win32", "Shell is not supported on Windows")
class TestLocalContext(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.machine_dict["context_type"] = "LocalContext"
        self.machine_dict["remote_root"] = self.temp_dir.name

    def tearDown(self):
        super().tearDown()
        self.temp_dir.cleanup()

    @unittest.skip("It seems the remote file may be deleted")
    def test_async_run_submission(self):
        return super().test_async_run_submission()


@unittest.skipIf(sys.platform == "win32", "Shell is not supported on Windows")
class TestLazyLocalContext(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.machine_dict["context_type"] = "LazyLocalContext"
