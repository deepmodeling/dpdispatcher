import shlex
import unittest
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

from dpdispatcher.machines.distributed_shell import DistributedShell
from dpdispatcher.machines.lsf import LSF


def _resources(
    source_list: Optional[List[str]] = None,
    envs: Optional[Dict[Any, Any]] = None,
    prepend_script: Optional[List[str]] = None,
) -> SimpleNamespace:
    """Build the resource attributes used by environment script generation."""
    return SimpleNamespace(
        number_node=2,
        cpu_per_node=4,
        gpu_per_node=1,
        queue_name="gpu queue; not-a-command",
        group_size=3,
        module_purge=False,
        module_unload_list=[],
        module_list=[],
        source_list=[] if source_list is None else source_list,
        envs={} if envs is None else envs,
        prepend_script=[] if prepend_script is None else prepend_script,
    )


def _job(
    source_list: Optional[List[str]] = None,
    envs: Optional[Dict[Any, Any]] = None,
    prepend_script: Optional[List[str]] = None,
) -> SimpleNamespace:
    """Build a minimal job accepted by both script environment generators."""
    return SimpleNamespace(
        job_hash="job-hash",
        resources=_resources(
            source_list=source_list,
            envs=envs,
            prepend_script=prepend_script,
        ),
    )


class TestMachineScriptEnvironment(unittest.TestCase):
    """Test source and export generation shared by scheduler machines."""

    def setUp(self) -> None:
        context = Mock()
        context.remote_root = "/remote root"
        self.machine = LSF(context=context)

    def test_quotes_static_source_words_and_environment_values(self) -> None:
        """Paths, arguments, scalar values, and list values are safely quoted."""
        source_list = [
            "",
            "   \t",
            "'/opt/application env/setup.sh' --flag 'argument value'",
            "activate legacy_env",
        ]
        envs = {
            "SAFE_VALUE": "value with spaces; $(touch injected)",
            "EMPTY_VALUE": "",
            "QUOTE_VALUE": "single'quote\nnext line",
            "NUMBER_VALUE": 7,
            "LIST_VALUE": ["first value", "second; value"],
            "EMPTY_LIST": [],
        }

        script = self.machine.gen_script_env(_job(source_list, envs))

        self.assertIn(
            "source '/opt/application env/setup.sh' --flag 'argument value'\n",
            script,
        )
        # A historical source entry with an argument keeps its behavior.
        self.assertIn("source activate legacy_env\n", script)
        self.assertNotIn("source \n", script)
        self.assertIn(f"export SAFE_VALUE={shlex.quote(envs['SAFE_VALUE'])}\n", script)
        self.assertIn("export EMPTY_VALUE=''\n", script)
        self.assertIn(
            f"export QUOTE_VALUE={shlex.quote(envs['QUOTE_VALUE'])}\n", script
        )
        self.assertIn("export NUMBER_VALUE=7\n", script)
        self.assertIn("export LIST_VALUE='first value'\n", script)
        self.assertIn("export LIST_VALUE='second; value'\n", script)
        self.assertNotIn("export EMPTY_LIST=", script)
        self.assertIn(
            "export DPDISPATCHER_QUEUE_NAME='gpu queue; not-a-command'\n", script
        )

    def test_rejects_invalid_environment_names(self) -> None:
        """Generated exports accept only portable POSIX identifiers."""
        invalid_names = (
            "",
            "1INVALID",
            "INVALID-NAME",
            "BAD NAME",
            "BAD;touch",
            "BAD\nNAME",
        )
        for invalid_name in invalid_names:
            with self.subTest(invalid_name=invalid_name):
                with self.assertRaisesRegex(ValueError, "POSIX environment"):
                    self.machine.gen_script_env(_job(envs={invalid_name: "value"}))

        with self.assertRaisesRegex(TypeError, "names must be strings"):
            self.machine.gen_script_env(_job(envs={1: "value"}))

    def test_rejects_nul_in_scalar_and_list_values(self) -> None:
        """NUL cannot be represented in a process environment or shell word."""
        invalid_envs = (
            {"VALUE": "prefix\x00suffix"},
            {"VALUE": ["valid", "prefix\x00suffix"]},
        )
        for invalid_env in invalid_envs:
            with self.subTest(invalid_env=invalid_env):
                with self.assertRaisesRegex(ValueError, "NUL character"):
                    self.machine.gen_script_env(_job(envs=invalid_env))

    def test_rejects_shell_source_fragments_with_guidance(self) -> None:
        """Intentional shell code is rejected rather than silently literalized."""
        unsafe_entries = (
            "setup.sh; touch injected",
            "$(touch injected)",
            "`touch injected`",
            "${HOME}/setup.sh",
            "setup-*.sh",
            "setup.sh | tee output",
            "-p injected",
        )
        for unsafe_entry in unsafe_entries:
            with self.subTest(unsafe_entry=unsafe_entry):
                with self.assertRaisesRegex(ValueError, "prepend_script"):
                    self.machine.gen_script_env(_job(source_list=[unsafe_entry]))

    def test_literal_envs_and_trusted_prepend_script_are_distinct(self) -> None:
        """Only prepend_script retains explicitly requested shell expansion."""
        raw_export = 'export EXPANDED_PATH="${HOME}/bin:${PATH}"'
        script = self.machine.gen_script_env(
            _job(
                envs={"LITERAL_PATH": "${HOME}/bin:${PATH}"},
                prepend_script=[raw_export],
            )
        )

        self.assertIn("export LITERAL_PATH='${HOME}/bin:${PATH}'\n", script)
        self.assertIn(raw_export, script)


class TestDistributedShellEnvironment(unittest.TestCase):
    """Ensure DistributedShell uses the same safe rendering contract."""

    def setUp(self) -> None:
        context = Mock()
        context.remote_root = "/remote root"
        context.submission.submission_hash = "submission-hash"
        self.machine = DistributedShell(context=context)

    def test_quotes_source_and_list_exports(self) -> None:
        """Distributed scripts wrap safely rendered source and export lines."""
        script = self.machine.gen_script_env(
            _job(
                source_list=["", "'/opt/env dir/setup.sh' argument"],
                envs={"VALUE": ["first value", "second; value"]},
            )
        )

        self.assertIn("{ source '/opt/env dir/setup.sh' argument; } \n", script)
        self.assertIn("export VALUE='first value'\n", script)
        self.assertIn("export VALUE='second; value'\n", script)
        self.assertNotIn("{ ; }", script)

    def test_rejects_invalid_names_and_source_fragments(self) -> None:
        """DistributedShell cannot bypass the shared validation helpers."""
        with self.assertRaisesRegex(ValueError, "POSIX environment"):
            self.machine.gen_script_env(_job(envs={"BAD-NAME": "value"}))
        with self.assertRaisesRegex(ValueError, "prepend_script"):
            self.machine.gen_script_env(_job(source_list=["setup.sh && injected"]))


if __name__ == "__main__":
    unittest.main()
