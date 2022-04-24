import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'

from .context import setUpModule
from .context import Task, Resources, Machine

class TestJob(unittest.TestCase):

    def test_machine_argcheck(self):
        norm_dict = Machine.load_from_dict({
            "batch_type": "slurm",
            "context_type": "local",
            "local_root": "./",
            "remote_root": "/some/path",
        }).serialize()
        expected_dict = {
            'batch_type': 'Slurm',
            'context_type': 'LocalContext',
            'local_root': './',
            'remote_root': '/some/path',
            'remote_profile': {},
        }
        self.assertDictEqual(norm_dict, expected_dict)

    def test_resources_argcheck(self):
        norm_dict = Resources.load_from_dict({
            "number_node": 1,
            "cpu_per_node": 2,
            "gpu_per_node": 0,
            "queue_name": "haha",
            "group_size": 1,
            "envs": {
                "aa": "bb",
            },
            "kwargs": {
                "cc": True,
            }
        }).serialize()
        expected_dict = {'cpu_per_node': 2,
                         'custom_flags': [],
                         'envs': {'aa': 'bb'},
                         'gpu_per_node': 0,
                         'group_size': 1,
                         'kwargs': {
                             "cc": True,
                         },
                         'module_list': [],
                         'module_purge': False,
                         'module_unload_list': [],
                         'number_node': 1,
                         'para_deg': 1,
                         'queue_name': 'haha',
                         'source_list': [],
                         'strategy': {'if_cuda_multi_devices': False, 'ratio_unfinished': 0.0},
                         'wait_time': 0,
                         }
        self.assertDictEqual(norm_dict, expected_dict)

    def test_task_argcheck(self):
        norm_dict = Task.load_from_dict({
            "command": "ls",
            "task_work_path": "./",
            "forward_files": [],
            "backward_files": [],
            "outlog": "out",
            "errlog": "err",
        }).serialize()
        expected_dict = {
            "command": "ls",
            "task_work_path": "./",
            "forward_files": [],
            "backward_files": [],
            "outlog": "out",
            "errlog": "err",
        }
        self.assertDictEqual(norm_dict, expected_dict)
