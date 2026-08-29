import glob
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from zipfile import ZipFile

from dpdispatcher.contexts.lazy_local_context import LazyLocalContext, SPRetObj
from dpdispatcher.contexts.openapi_context import zip_file_list as openapi_zip_file_list
from dpdispatcher.machines.distributed_shell import DistributedShell
from dpdispatcher.machines.fugaku import Fugaku
from dpdispatcher.machines.JH_UniScheduler import JH_UniScheduler
from dpdispatcher.machines.lsf import LSF
from dpdispatcher.machines.pbs import PBS, SGE, Torque
from dpdispatcher.machines.shell import Shell
from dpdispatcher.machines.slurm import Slurm, SlurmJobArray
from dpdispatcher.submission import Job
from dpdispatcher.utils.dpcloudserver.zip_file import (
    zip_file_list as bohrium_zip_file_list,
)

from .context import setUpModule  # noqa: F401
from .sample_class import SampleClass


class TestHiddenJobScripts(unittest.TestCase):
    def setUp(self) -> None:
        self.job = SampleClass.get_sample_job()
        self.expected_script_name = f".{self.job.job_hash}.sub"

    def test_scheduler_scripts_source_hidden_run_file(self) -> None:
        """All scheduler variants should use the hidden name without path changes."""
        context = LazyLocalContext(local_root=".")
        context.remote_root = "/tmp/dpdispatcher"
        context.submission = SimpleNamespace(submission_hash="submission")

        scheduler_classes = (
            Shell,
            Slurm,
            SlurmJobArray,
            PBS,
            Torque,
            SGE,
            LSF,
            Fugaku,
            JH_UniScheduler,
            DistributedShell,
        )
        for scheduler_class in scheduler_classes:
            with self.subTest(scheduler=scheduler_class.__name__):
                machine = scheduler_class(context=context)
                self.job.machine = machine
                script = machine.gen_script(self.job)

                self.assertEqual(self.job.script_file_name, self.expected_script_name)
                self.assertIn(
                    f"source $REMOTE_ROOT/{self.expected_script_name}.run", script
                )

    def test_lazy_local_resubmission_and_recovery_use_hidden_paths(self) -> None:
        """Recovered jobs regenerate hidden scripts while retaining their hash."""
        with tempfile.TemporaryDirectory() as local_root:
            context = LazyLocalContext(local_root=local_root)
            context.bind_submission(SimpleNamespace(work_base="work"))
            machine = Shell(context=context)
            self.job.machine = machine

            context.block_call = MagicMock(
                return_value=(0, None, SPRetObj(b"123\n"), SPRetObj(b""))
            )
            self.job.submit_job()

            script_path = os.path.join(context.remote_root, self.expected_script_name)
            run_path = f"{script_path}.run"
            self.assertTrue(os.path.isfile(script_path))
            self.assertTrue(os.path.isfile(run_path))
            visible_entries = [
                os.path.basename(path)
                for path in glob.glob(os.path.join(context.remote_root, "*"))
            ]
            self.assertNotIn(self.expected_script_name, visible_entries)
            self.assertNotIn(f"{self.expected_script_name}.run", visible_entries)

            recovered_job = Job.deserialize(self.job.serialize(), machine=machine)
            self.assertEqual(recovered_job.job_hash, self.job.job_hash)
            self.assertEqual(recovered_job.script_file_name, self.expected_script_name)

            os.remove(script_path)
            os.remove(run_path)
            recovered_job.submit_job()
            self.assertTrue(os.path.isfile(script_path))
            self.assertTrue(os.path.isfile(run_path))

    def test_cloud_archives_include_explicit_hidden_scripts(self) -> None:
        """Cloud contexts list scripts explicitly, so dot prefixes remain uploadable."""
        with tempfile.TemporaryDirectory() as local_root:
            script_names = (
                self.expected_script_name,
                f"{self.expected_script_name}.run",
            )
            for script_name in script_names:
                with open(os.path.join(local_root, script_name), "w") as script_file:
                    script_file.write("#!/bin/bash\n")

            archive_builders = (openapi_zip_file_list, bohrium_zip_file_list)
            for index, archive_builder in enumerate(archive_builders):
                with self.subTest(archive_builder=archive_builder.__module__):
                    archive_name = f"scripts-{index}.zip"
                    archive_builder(local_root, archive_name, list(script_names))
                    with ZipFile(os.path.join(local_root, archive_name)) as archive:
                        self.assertEqual(set(archive.namelist()), set(script_names))
