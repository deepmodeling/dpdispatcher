import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"

from .context import (
    Machine,
    Resources,
    setUpModule,  # noqa: F401
)


class TestLoginShellOption(unittest.TestCase):
    def _make_header(self, batch_type: str, login_shell: bool) -> str:
        machine = Machine(
            batch_type=batch_type,
            context_type="LazyLocalContext",
            local_root="./test_context_dir",
        )
        resources = Resources(
            number_node=1,
            cpu_per_node=1,
            gpu_per_node=0,
            queue_name="queue",
            group_size=1,
            kwargs={"login_shell": login_shell},
        )
        return machine.gen_script_header(SimpleNamespace(resources=resources))

    def test_login_shell_enabled_by_default(self):
        resources = Resources(
            number_node=1,
            cpu_per_node=1,
            gpu_per_node=0,
            queue_name="queue",
            group_size=1,
        )

        header = Machine.apply_login_shell_option("#!/bin/bash -l\n", resources)

        self.assertEqual(header, "#!/bin/bash -l\n")

    def test_login_shell_can_be_disabled_for_shell(self):
        header = self._make_header("Shell", login_shell=False)

        self.assertIn("#!/bin/bash\n", header)
        self.assertNotIn("#!/bin/bash -l", header)

    def test_login_shell_can_be_disabled_for_slurm(self):
        header = self._make_header("Slurm", login_shell=False)

        self.assertIn("#!/bin/bash\n", header)
        self.assertNotIn("#!/bin/bash -l", header)

    def test_login_shell_can_be_disabled_for_pbs(self):
        header = self._make_header("PBS", login_shell=False)

        self.assertIn("#!/bin/bash\n", header)
        self.assertNotIn("#!/bin/bash -l", header)

    def test_login_shell_can_be_disabled_for_lsf(self):
        header = self._make_header("LSF", login_shell=False)

        self.assertIn("#!/bin/bash\n", header)
        self.assertNotIn("#!/bin/bash -l", header)
