import logging
import os, sys


ROOT_PATH=__path__[0]
NAME="dpdispatcher"
SHORT_CMD="dpdisp"
dlog = logging.getLogger(__name__)
dlog.setLevel(logging.INFO)
dlogf = logging.FileHandler(os.getcwd()+os.sep+SHORT_CMD+'.log')
# dlogf = logging.FileHandler('./'+os.sep+SHORT_CMD+'.log')
# dlogf = logging.FileHandler(os.path.join(os.environ['HOME'], SHORT_CMD+'.log'))
# dlogf = logging.FileHandler(os.path.join(os.path.expanduser('~'), SHORT_CMD+'.log'))
# dlogf = logging.FileHandler(os.path.join("/tmp/", SHORT_CMD+'.log'))
dlogf_formatter=logging.Formatter('%(asctime)s - %(levelname)s : %(message)s')
# dlogf_formatter=logging.Formatter('%(asctime)s - %(name)s - [%(filename)s:%(funcName)s - %(lineno)d ] - %(levelname)s \n %(message)s')
dlogf.setFormatter(dlogf_formatter)
dlog.addHandler(dlogf)

dlog_stdout=logging.StreamHandler(sys.stdout)
dlog_stdout.setFormatter(dlogf_formatter)
dlog.addHandler(dlog_stdout)

__author__    = "DeepModeling Team"
__copyright__ = "Copyright 2019"
__status__    = "Development"
try:
    from ._version import version as __version__
except ImportError:
    __version__ = 'unkown'
try:
    from ._date import date as __date__
except ImportError:
    __date__ = 'unkown'

try:
    from .submission import Submission
    from .submission import Task
    from .submission import Job
    from .submission import Resources
    from .slurm import Slurm
    from .pbs import PBS
    from .shell import Shell
    from .lsf import LSF
    from .machine import Machine

    from .lazy_local_context import LazyLocalContext
    from .local_context import LocalContext
    from .ssh_context import SSHContext
except:
    print("Dependency not satisfied. Unable to import main classes.")

try:
    from .dp_cloud_server import DpCloudServer
    from .dp_cloud_server_context import DpCloudServerContext
except ImportError:
    pass


def info():
    """
        Show basic information about """+NAME+""", its location and version.
    """

    print('DeepModeling\n------------')
    print('Version: ' + __version__)
    print('Date:    ' + __date__)
    print('Path:    ' + ROOT_PATH)
    print('')
    print('Dependency')
    print('------------')
    for modui in ['psutil', 'paramiko', 'dargs', 'oss2']:
        try:
            mm = __import__(modui)
            print('%10s %10s   %s' % (modui, mm.__version__, mm.__path__[0]))
        except ImportError:
            print('%10s %10s Not Found' % (modui, ''))
    print()

