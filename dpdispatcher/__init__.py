"""Public interface for configuring and running DPDispatcher submissions.

The top-level package exports the core configuration and runtime objects. Batch
systems and execution contexts register themselves when a runtime object is accessed,
so :class:`Machine` can construct the requested backend from configuration.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dpdispatcher.machine import Machine
    from dpdispatcher.submission import Job, Resources, Submission, Task

__author__ = "DeepModeling Team"
__copyright__ = "Copyright 2019-2023, DeepModeling"
__status__ = "Production"
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"


__all__ = [
    "__version__",
    "Machine",
    "Submission",
    "Task",
    "Job",
    "Resources",
]


def __getattr__(name: str) -> object:
    """Load submission objects only when needed, not while reading CLI guides."""
    if name in {"Machine", "Job", "Resources", "Submission", "Task"}:
        import dpdispatcher.contexts  # noqa: F401
        import dpdispatcher.machines  # noqa: F401

        if name == "Machine":
            from dpdispatcher.machine import Machine

            value = Machine
        else:
            from dpdispatcher import submission

            value = getattr(submission, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
