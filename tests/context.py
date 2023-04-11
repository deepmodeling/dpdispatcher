import hashlib
import os
import pathlib
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# from dpgen.dispatcher.Dispatcher import FinRecord

# from dpdispatcher.local_context import local_context

# from dpdispatcher.local_context import LocalSession

try:
    pass
except Exception:
    pass


def setUpModule():
    os.chdir(os.path.abspath(os.path.dirname(__file__)))


def get_file_md5(file_path):
    return hashlib.md5(pathlib.Path(file_path).read_bytes()).hexdigest()
