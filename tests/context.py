import hashlib
import os
import pathlib
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import dpdispatcher
from dpdispatcher.base_context import BaseContext
from dpdispatcher.distributed_shell import DistributedShell
from dpdispatcher.dp_cloud_server import Lebesgue
from dpdispatcher.hdfs_cli import HDFS
from dpdispatcher.hdfs_context import HDFSContext

# from dpgen.dispatcher.Dispatcher import FinRecord
from dpdispatcher.JobStatus import JobStatus

# from dpdispatcher.local_context import local_context
from dpdispatcher.lazy_local_context import LazyLocalContext

# from dpdispatcher.local_context import LocalSession
from dpdispatcher.local_context import LocalContext, _identical_files
from dpdispatcher.lsf import LSF
from dpdispatcher.pbs import PBS
from dpdispatcher.shell import Shell
from dpdispatcher.slurm import Slurm
from dpdispatcher.ssh_context import SSHContext, SSHSession

try:
    from dpdispatcher.dp_cloud_server import DpCloudServer
    from dpdispatcher.dp_cloud_server_context import DpCloudServerContext
except Exception:
    pass
import dargs

from dpdispatcher.machine import Machine
from dpdispatcher.submission import Job, Resources, Submission, Task
from dpdispatcher.utils import RetrySignal, retry


def setUpModule():
    os.chdir(os.path.abspath(os.path.dirname(__file__)))


def get_file_md5(file_path):
    return hashlib.md5(pathlib.Path(file_path).read_bytes()).hexdigest()
