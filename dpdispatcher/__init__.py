__author__ = "DeepModeling Team"
__copyright__ = "Copyright 2019-2023, DeepModeling"
__status__ = "Production"
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

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
