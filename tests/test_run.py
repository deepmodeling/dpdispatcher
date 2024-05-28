import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"

from .context import run


class TestRun(unittest.TestCase):
    def test_run(self):
        this_dir = Path(__file__).parent
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)
                run(filename=str(this_dir / "hello_world.py"))
                self.assertEqual(
                    (Path(temp_dir) / "log").read_text().strip(), "hello world!"
                )
            finally:
                os.chdir(cwd)
