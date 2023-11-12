import logging
import os
import sys
import warnings

dlog = logging.getLogger("dpdispatcher")
dlog.propagate = False
dlog.setLevel(logging.INFO)
try:
    dlogf = logging.FileHandler(
        os.getcwd() + os.sep + "dpdispatcher" + ".log", delay=True
    )
except PermissionError:
    warnings.warn(
        "dpdispatcher.log meet permission error. redirect the log to ~/dpdispatcher.log"
    )
    dlogf = logging.FileHandler(
        os.path.join(os.path.expanduser("~"), "dpdispatcher.log"), delay=True
    )

dlogf_formatter = logging.Formatter("%(asctime)s - %(levelname)s : %(message)s")
dlogf.setFormatter(dlogf_formatter)
dlog.addHandler(dlogf)

dlog_stdout = logging.StreamHandler(sys.stdout)
dlog_stdout.setFormatter(dlogf_formatter)
dlog.addHandler(dlog_stdout)

__all__ = [
    "dlog",
]
