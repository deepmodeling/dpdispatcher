"""Tests for offline, version-matched workflow discovery."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from dpdispatcher.dpdisp import main, main_parser, parse_args
from dpdispatcher.skills import read_skill, run, skill_root


class TestSkills(unittest.TestCase):
    def test_list_and_read(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run(parse_args(["skills", "list"]))
        self.assertIn("dpdisp-submit", output.getvalue().splitlines())
        expected = (skill_root() / "dpdisp-submit" / "SKILL.md").read_bytes()
        self.assertEqual(read_skill("dpdisp-submit").encode(), expected)

    def test_help_and_legacy_parser(self) -> None:
        self.assertIn("skills", main_parser().format_help())
        args = parse_args(["submit", "job.json", "--dry-run"])
        self.assertEqual(args.filename, "job.json")
        self.assertTrue(args.dry_run)

    def test_invalid_paths(self) -> None:
        for name, path in [
            ("../dpdisp-submit", "SKILL.md"),
            ("missing", "SKILL.md"),
            ("dpdisp-submit", "../README.md"),
            ("dpdisp-submit", "/etc/passwd"),
            ("dpdisp-submit", "..\\README.md"),
            ("dpdisp-submit", "C:/file"),
            ("dpdisp-submit", "SKILL.md\0"),
        ]:
            with self.subTest(name=name, path=path), self.assertRaises(ValueError):
                read_skill(name, path)

    def test_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / "skills" / "guide"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("guide", encoding="utf-8")
            outside = root / "private.txt"
            outside.write_text("private", encoding="utf-8")
            (skill / "escape.md").symlink_to(outside)
            with patch("dpdispatcher.skills.skill_root", return_value=root / "skills"):
                with self.assertRaises(ValueError):
                    read_skill("guide", "escape.md")

    def test_cli_leaves_home_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            result = subprocess.run(
                [sys.executable, "-m", "dpdispatcher.dpdisp", "skills", "list"],
                env={
                    **os.environ,
                    "HOME": home,
                    "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                },
                cwd=home,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("dpdisp-submit", result.stdout)
            self.assertEqual(list(Path(home).iterdir()), [])

    def test_public_exports_and_registration(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from dpdispatcher import Machine, Submission, Task, Resources, Job, __version__; "
                    "from dpdispatcher.submission import Submission as Direct; "
                    "assert Submission is Direct; "
                    "assert 'Shell' in Machine.subclasses_dict; "
                    "assert isinstance(__version__, str)",
                ],
                env={**os.environ, "HOME": home},
                check=True,
            )

    def test_direct_factory_imports_register_backends(self) -> None:
        for module, symbol, key in [
            ("dpdispatcher.machine", "Machine", "Shell"),
            ("dpdispatcher.base_context", "BaseContext", "LocalContext"),
        ]:
            with tempfile.TemporaryDirectory() as home:
                subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        f"from {module} import {symbol}; "
                        f"assert {key!r} in {symbol}.subclasses_dict",
                    ],
                    env={**os.environ, "HOME": home},
                    check=True,
                )

    def test_resource_locations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "dpdispatcher"
            package.mkdir()
            with patch("dpdispatcher.skills.__file__", str(package / "skills.py")):
                with self.assertRaisesRegex(ValueError, "reinstall"):
                    skill_root()
                (root / "pyproject.toml").touch()
                with self.assertRaisesRegex(ValueError, "reinstall"):
                    skill_root()
                (root / "skills").mkdir()
                self.assertEqual(skill_root(), root / "skills")
                bundled = package / "_skills"
                bundled.mkdir()
                self.assertEqual(skill_root(), bundled)

    def test_invalid_utf8_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guide = root / "guide"
            guide.mkdir()
            (guide / "SKILL.md").write_text("guide", encoding="utf-8")
            (guide / "invalid.txt").write_bytes(b"\xff")
            with patch("dpdispatcher.skills.skill_root", return_value=root):
                with self.assertRaisesRegex(ValueError, "not UTF-8"):
                    read_skill("guide", "invalid.txt")
                with self.assertRaisesRegex(ValueError, "unknown skill reference"):
                    read_skill("guide", "missing.md")

    def test_read_reports_resource_and_io_errors(self) -> None:
        args = parse_args(["skills", "read", "dpdisp-submit"])
        for error in [ValueError("missing resources"), OSError("cannot read guide")]:
            output, errors = io.StringIO(), io.StringIO()
            with (
                self.subTest(error=error),
                patch("dpdispatcher.skills.read_skill", side_effect=error),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(errors),
                self.assertRaises(SystemExit) as raised,
            ):
                run(args)
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(output.getvalue(), "")
            self.assertIn(f"dpdisp skills: {error}", errors.getvalue())
            self.assertNotIn("Traceback", errors.getvalue())

    def test_main_reads_exact_guide(self) -> None:
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["dpdisp", "skills", "read", "dpdisp-submit"]),
            contextlib.redirect_stdout(output),
        ):
            main()
        self.assertEqual(output.getvalue(), read_skill("dpdisp-submit"))

    def test_lazy_workflow_dispatch_preserves_arguments(self) -> None:
        cases = [
            (
                ["run", "script.py", "--allow-ref"],
                "run",
                "run",
                {"filename": "script.py", "allow_ref": True},
            ),
            (
                ["submit", "job.json"],
                "submit",
                "submit",
                {
                    "filename": "job.json",
                    "dry_run": False,
                    "exit_on_submit": False,
                    "allow_ref": False,
                    "clean": True,
                    "continue_on_failure": None,
                },
            ),
            (
                ["submit", "job.json", "--continue-on-failure", "--no-clean"],
                "submit",
                "submit",
                {
                    "filename": "job.json",
                    "dry_run": False,
                    "exit_on_submit": False,
                    "allow_ref": False,
                    "clean": False,
                    "continue_on_failure": True,
                },
            ),
            (
                ["gui", "--port", "7000", "--bind_all"],
                "gui",
                "start_dpgui",
                {"port": 7000, "bind_all": True},
            ),
            (
                ["submission", "hash", "--clean"],
                "submission",
                "handle_submission",
                {
                    "submission_hash": "hash",
                    "download_terminated_log": False,
                    "download_finished_task": False,
                    "clean": True,
                    "reset_fail_count": False,
                },
            ),
        ]
        for argv, module, function, expected in cases:
            name = f"dpdispatcher.entrypoints.{module}"
            fake = ModuleType(name)
            handler = Mock()
            setattr(fake, function, handler)
            with (
                self.subTest(argv=argv),
                patch.dict(sys.modules, {name: fake}),
                patch.object(sys, "argv", ["dpdisp", *argv]),
            ):
                main()
            handler.assert_called_once_with(**expected)

    def test_missing_resources_are_cli_errors(self) -> None:
        for command in [["skills", "list"], ["skills", "read", "dpdisp-submit"]]:
            args = parse_args(command)
            for error in [ValueError("missing guides"), OSError("guides inaccessible")]:
                output, errors = io.StringIO(), io.StringIO()
                with (
                    self.subTest(command=command, error=error),
                    patch("dpdispatcher.skills.skill_root", side_effect=error),
                    contextlib.redirect_stdout(output),
                    contextlib.redirect_stderr(errors),
                    self.assertRaises(SystemExit) as raised,
                ):
                    run(args)
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(output.getvalue(), "")
                self.assertIn(f"dpdisp skills: {error}", errors.getvalue())
                self.assertNotIn("Traceback", errors.getvalue())
