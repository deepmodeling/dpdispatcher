import hashlib
import os
import pathlib
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import dpdispatcher  # noqa: F401
from dpdispatcher.base_context import BaseContext  # noqa: F401
from dpdispatcher.distributed_shell import DistributedShell  # noqa: F401
from dpdispatcher.dp_cloud_server import Lebesgue  # noqa: F401
from dpdispatcher.hdfs_cli import HDFS  # noqa: F401
from dpdispatcher.hdfs_context import HDFSContext  # noqa: F401

# from dpgen.dispatcher.Dispatcher import FinRecord
from dpdispatcher.JobStatus import JobStatus  # noqa: F401

# from dpdispatcher.local_context import local_context
from dpdispatcher.lazy_local_context import LazyLocalContext  # noqa: F401

# from dpdispatcher.local_context import LocalSession
from dpdispatcher.local_context import LocalContext, _identical_files  # noqa: F401
from dpdispatcher.lsf import LSF  # noqa: F401
from dpdispatcher.pbs import PBS  # noqa: F401
from dpdispatcher.shell import Shell  # noqa: F401
from dpdispatcher.slurm import Slurm  # noqa: F401
from dpdispatcher.ssh_context import SSHContext, SSHSession  # noqa: F401

try:
    from dpdispatcher.dp_cloud_server import DpCloudServer  # noqa: F401
    from dpdispatcher.dp_cloud_server_context import DpCloudServerContext  # noqa: F401
except Exception:
    pass
import dargs  # noqa: F401

from dpdispatcher.machine import Machine  # noqa: F401
from dpdispatcher.submission import Job, Resources, Submission, Task  # noqa: F401
from dpdispatcher.utils import RetrySignal, retry  # noqa: F401


def setUpModule():
    os.chdir(os.path.abspath(os.path.dirname(__file__)))


def get_file_md5(file_path):
    return hashlib.md5(pathlib.Path(file_path).read_bytes()).hexdigest()
