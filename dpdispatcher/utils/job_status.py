"""Define scheduler-independent states for jobs and tasks."""

from enum import IntEnum


class JobStatus(IntEnum):
    """Represent normalized lifecycle states returned by machine backends."""

    unsubmitted = 1
    waiting = 2
    running = 3
    terminated = 4
    finished = 5
    completing = 6
    failed = 7
    unknown = 100


#     def __str__(self):
#         return repr(self)
