import hashlib
import os
import pathlib
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dpdispatcher  # noqa: F401
from dpdispatcher.base_context import BaseContext  # noqa: F401
from dpdispatcher.utils.job_status import JobStatus  # noqa: F401
from dpdispatcher.machine import Machine  # noqa: F401
from dpdispatcher.submission import Job, Resources, Submission, Task  # noqa: F401
from dpdispatcher.utils.utils import RetrySignal, retry  # noqa: F401


def setUpModule():
    os.chdir(os.path.abspath(os.path.dirname(__file__)))


def get_file_md5(file_path):
    return hashlib.md5(pathlib.Path(file_path).read_bytes()).hexdigest()
