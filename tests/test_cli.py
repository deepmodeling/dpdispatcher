import subprocess as sp
import unittest


class TestCLI(unittest.TestCase):
    def test_cli(self):
        sp.check_output(["dpdisp", "-h"])
        for subcommand in (
            "submission",
            "gui",
            "run",
            "submit",
        ):
            sp.check_output(["dpdisp", subcommand, "-h"])
