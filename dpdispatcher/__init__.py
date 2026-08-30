"""Public interface for configuring and running DPDispatcher submissions.

The top-level package exports the core configuration and runtime objects. Batch
systems and execution contexts register themselves when the package is imported,
so :class:`Machine` can construct the requested backend from configuration.
"""

__author__ = "DeepModeling Team"
__copyright__ = "Copyright 2019-2023, DeepModeling"
__status__ = "Production"
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

import dpdispatcher.contexts  # noqa: F401
import dpdispatcher.machines  # noqa: F401
from dpdispatcher.machine import Machine
from dpdispatcher.submission import Job, Resources, Submission, Task

__all__ = [
    "__version__",
    "Machine",
    "Submission",
    "Task",
    "Job",
    "Resources",
]
