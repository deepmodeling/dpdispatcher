"""This module ensures input in the examples directory
could pass the argument checking.
"""

import json
import unittest
from pathlib import Path
from typing import Sequence, Tuple

from dargs import Argument

from dpdispatcher.arginfo import machine_dargs, resources_dargs, task_dargs

# directory of examples
p_examples = Path(__file__).parent.parent / "examples"

machine_args = machine_dargs()
resources_args = resources_dargs(detail_kwargs=False)
task_args = task_dargs()

# input_files : tuple[tuple[Argument, Path]]
#   tuple of example list
input_files: Sequence[Tuple[Argument, Path]] = (
    (machine_args, p_examples / "machine" / "expanse.json"),
    (machine_args, p_examples / "machine" / "lazy_local.json"),
    (machine_args, p_examples / "machine" / "mandu.json"),
    (resources_args, p_examples / "resources" / "expanse_cpu.json"),
    (resources_args, p_examples / "resources" / "mandu.json"),
    (resources_args, p_examples / "resources" / "tiger.json"),
    (task_args, p_examples / "task" / "deepmd-kit.json"),
    (task_args, p_examples / "task" / "g16.json"),
)


class TestExamples(unittest.TestCase):
    def test_arguments(self):
        for arginfo, fn in input_files:
            fn = str(fn)
            with self.subTest(fn=fn):
                with open(fn) as f:
                    data = json.load(f)
                arginfo.check_value(data, strict=True)
