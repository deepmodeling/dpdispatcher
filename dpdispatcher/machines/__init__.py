"""Machines."""

import importlib
from pathlib import Path

PACKAGE_BASE = "dpdispatcher.machines"
NOT_LOADABLE = ("__init__.py",)

for module_file in Path(__file__).parent.glob("*.py"):
    if module_file.name not in NOT_LOADABLE:
        module_name = f".{module_file.stem}"
        importlib.import_module(module_name, PACKAGE_BASE)
