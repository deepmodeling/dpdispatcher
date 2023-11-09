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

from .machines.distributed_shell import DistributedShell
from .machines.dp_cloud_server import DpCloudServer, Lebesgue
from .contexts.dp_cloud_server_context import DpCloudServerContext, LebesgueContext
from .machines.fugaku import Fugaku
from .contexts.hdfs_context import HDFSContext
from .contexts.lazy_local_context import LazyLocalContext
from .contexts.local_context import LocalContext
from .machines.lsf import LSF
from .machines import Machine
from .machines.openapi import OpenAPI
from .contexts.openapi_context import OpenAPIContext
from .machines.pbs import PBS, Torque
from .machines.shell import Shell
from .machines.slurm import Slurm
from .contexts.ssh_context import SSHContext
from .submission import Job, Resources, Submission, Task


def info():
    """Show basic information about dpdispatcher, its location and version."""
    print("DeepModeling\n------------")
    print("Version: " + __version__)
    print("Path:    " + ROOT_PATH)
    print("")
    print("Dependency")
    print("------------")
    for modui in ["psutil", "paramiko", "dargs", "oss2"]:
        try:
            mm = __import__(modui)
            print("%10s %10s   %s" % (modui, mm.__version__, mm.__path__[0]))
        except ImportError:
            print("%10s %10s Not Found" % (modui, ""))
    print()


__all__ = [
    "__version__",
    "DistributedShell",
    "DpCloudServer",
    "OpenAPI",
    "OpenAPIContext",
    "DpCloudServerContext",
    "HDFSContext",
    "LazyLocalContext",
    "LocalContext",
    "LSF",
    "Machine",
    "PBS",
    "Shell",
    "Slurm",
    "Fugaku",
    "SSHContext",
    "Submission",
    "Task",
    "Torque",
    "info",
    "Lebesgue",
    "LebesgueContext",
    "Job",
    "Resources",
]
