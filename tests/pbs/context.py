import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from dpgen.dispatcher.Dispatcher import Dispatcher  # noqa: F401
from dpgen.dispatcher.JobStatus import JobStatus  # noqa: F401
from dpgen.dispatcher.LocalContext import LocalContext, LocalSession  # noqa: F401
from dpgen.dispatcher.PBS import PBS  # noqa: F401
from dpgen.dispatcher.SSHContext import SSHContext, SSHSession  # noqa: F401


def my_file_cmp(test, f0, f1):
    with open(f0) as fp0:
        with open(f1) as fp1:
            test.assertTrue(fp0.read() == fp1.read())


def setUpModule():
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
