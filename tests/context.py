import hashlib
import os
import pathlib
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dpdispatcher  # noqa: F401
from dpdispatcher.base_context import BaseContext  # noqa: F401
from dpdispatcher.contexts.hdfs_context import HDFSContext  # noqa: F401
from dpdispatcher.contexts.lazy_local_context import LazyLocalContext  # noqa: F401
from dpdispatcher.contexts.local_context import LocalContext  # noqa: F401
from dpdispatcher.contexts.ssh_context import SSHContext, SSHSession  # noqa: F401

# test backward compatibility with dflow
from dpdispatcher.dpcloudserver.client import RequestInfoException as _  # noqa: F401
from dpdispatcher.entrypoints.run import run  # noqa: F401
from dpdispatcher.entrypoints.submission import handle_submission  # noqa: F401
from dpdispatcher.machine import Machine  # noqa: F401
from dpdispatcher.machines.distributed_shell import DistributedShell  # noqa: F401
from dpdispatcher.machines.dp_cloud_server import Lebesgue  # noqa: F401
from dpdispatcher.machines.JH_UniScheduler import JH_UniScheduler  # noqa: F401
from dpdispatcher.machines.lsf import LSF  # noqa: F401
from dpdispatcher.machines.pbs import PBS  # noqa: F401
from dpdispatcher.machines.shell import Shell  # noqa: F401
from dpdispatcher.machines.slurm import Slurm  # noqa: F401
from dpdispatcher.submission import Job, Resources, Submission, Task  # noqa: F401
from dpdispatcher.utils.hdfs_cli import HDFS  # noqa: F401
from dpdispatcher.utils.job_status import JobStatus  # noqa: F401
from dpdispatcher.utils.record import record  # noqa: F401
from dpdispatcher.utils.utils import RetrySignal, retry  # noqa: F401


def setUpModule():
    os.chdir(os.path.abspath(os.path.dirname(__file__)))


def get_file_md5(file_path):
    return hashlib.md5(pathlib.Path(file_path).read_bytes()).hexdigest()
