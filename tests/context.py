import sys,os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from dpdispatcher.LocalContext import LocalSession
from dpdispatcher.LocalContext import LocalContext
# from dpdispatcher.local_context import local_context
from dpdispatcher.LazyLocalContext import LazyLocalContext
from dpdispatcher.SSHContext import SSHSession
from dpdispatcher.SSHContext import SSHContext
# from dpgen.dispatcher.Dispatcher import FinRecord
from dpdispatcher.Dispatcher import _split_tasks
from dpdispatcher.Dispatcher import Dispatcher
from dpdispatcher.JobStatus import JobStatus
from dpdispatcher.pbs import PBS
from dpdispatcher.LocalContext import _identical_files
from dpdispatcher.submission import Submission, Job, Task, Resources

def setUpModule():
    os.chdir(os.path.abspath(os.path.dirname(__file__)))

