import logging
import os
import sys
import warnings

dlog = logging.getLogger("dpdispatcher")
dlog.propagate = False
dlog.setLevel(logging.INFO)
cwd_logfile_path = os.path.join(os.getcwd(), "dpdispatcher.log")
dlogf = logging.FileHandler(cwd_logfile_path, delay=True)
try:
    dlog.addHandler(dlogf)
    dlog.info(f"LOG INIT:dpdispatcher log direct to {cwd_logfile_path}")
except PermissionError:
    dlog.removeHandler(dlogf)
    warnings.warn(
        f"dump logfile dpdispatcher.log to {cwd_logfile_path} meet permission error. redirect the log to ~/dpdispatcher.log"
    )
    dlogf = logging.FileHandler(
        os.path.join(os.path.expanduser("~"), "dpdispatcher.log"), delay=True
    )
    dlog.addHandler(dlogf)
    dlog.info("LOG INIT:dpdispatcher log init at ~/dpdispatcher.log")

dlogf_formatter = logging.Formatter("%(asctime)s - %(levelname)s : %(message)s")
dlogf.setFormatter(dlogf_formatter)
# dlog.addHandler(dlogf)

dlog_stdout = logging.StreamHandler(sys.stdout)
dlog_stdout.setFormatter(dlogf_formatter)
dlog.addHandler(dlog_stdout)

__all__ = [
    "dlog",
]
