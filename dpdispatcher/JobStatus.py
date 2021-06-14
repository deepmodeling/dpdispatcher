from enum import IntEnum
class JobStatus(IntEnum) :
    unsubmitted = 1
    waiting = 2
    running = 3
    terminated = 4
    finished = 5
    completing = 6
    unknown = 100
#     def __str__(self):
#         return repr(self)

