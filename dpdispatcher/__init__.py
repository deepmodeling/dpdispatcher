import logging
import os
import sys
import warnings

ROOT_PATH = tuple(__path__)[0]
dlog = logging.getLogger(__name__)
dlog.propagate = False
dlog.setLevel(logging.INFO)
try:
    dlogf = logging.FileHandler(
        os.getcwd() + os.sep + "dpdispatcher" + ".log", delay=True
    )
except PermissionError:
    warnings.warn(
        "dpdispatcher.log meet permission error. redirect the log to ~/dpdispatcher.log"
    )
    dlogf = logging.FileHandler(
        os.path.join(os.path.expanduser("~"), "dpdispatcher.log")
    )

# dlogf = logging.FileHandler('./'+os.sep+SHORT_CMD+'.log')
# dlogf = logging.FileHandler(os.path.join(os.environ['HOME'], SHORT_CMD+'.log'))
# dlogf = logging.FileHandler(os.path.join(os.path.expanduser('~'), SHORT_CMD+'.log'))
# dlogf = logging.FileHandler(os.path.join("/tmp/", SHORT_CMD+'.log'))
dlogf_formatter = logging.Formatter("%(asctime)s - %(levelname)s : %(message)s")
# dlogf_formatter=logging.Formatter('%(asctime)s - %(name)s - [%(filename)s:%(funcName)s - %(lineno)d ] - %(levelname)s \n %(message)s')
dlogf.setFormatter(dlogf_formatter)
dlog.addHandler(dlogf)

dlog_stdout = logging.StreamHandler(sys.stdout)
dlog_stdout.setFormatter(dlogf_formatter)
dlog.addHandler(dlog_stdout)

__author__ = "DeepModeling Team"
__copyright__ = "Copyright 2019"
__status__ = "Development"
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unkown"

from dpdispatcher.machine import Machine
from dpdispatcher.submission import Job, Resources, Submission, Task
import dpdispatcher.machines as _  # noqa: F401
import dpdispatcher.contexts as _  # noqa: F401

__all__ = [
    "__version__",
    "Machine",
    "Submission",
    "Task",
    "info",
    "Job",
    "Resources",
]
