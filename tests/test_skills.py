"""Tests for offline, version-matched workflow discovery."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dpdispatcher.dpdisp import main_parser, parse_args
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
