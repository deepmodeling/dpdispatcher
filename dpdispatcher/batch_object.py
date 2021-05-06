import json
from dpdispatcher.batch import Batch
from dpdispatcher.pbs import PBS
from dpdispatcher.lsf import LSF
from dpdispatcher.slurm import Slurm
from dpdispatcher.shell import Shell
from dpdispatcher.dp_cloud_server import DpCloudServer
from dpdispatcher.lazy_local_context import LazyLocalContext
from dpdispatcher.local_context import LocalContext
from dpdispatcher.ssh_context import SSHContext
from dpdispatcher.dp_cloud_server_context import DpCloudServerContext

from dpdispatcher.submission import Resources

# from typing import TypedDict
from typing_extensions import TypedDict
from os import PathLike

class BatchObject(object):
    def __new__(self, jdata):
        context_type = jdata.get('context_type', 'lazy_local')
        batch_type = jdata['batch_type']
        context = None
        batch = None
        if context_type == 'local':
            context = LocalContext.from_jdata(jdata=jdata)
        elif context_type == 'lazy_local':
            context = LazyLocalContext.from_jdata(jdata=jdata)
        elif context_type == 'ssh':
            context = SSHContext.from_jdata(jdata=jdata)
        elif context_type == 'dp_cloud_server':
            context = DpCloudServerContext.from_jdata(jdata=jdata)
        else:
            raise RuntimeError(f"unknown context_type:{context_type}")

        if batch_type == 'pbs':
            batch = PBS(context=context)
        elif batch_type == 'lsf':
            batch = LSF(context=context)
        elif batch_type == 'slurm':
            batch = Slurm(context=context)
        elif batch_type == 'shell':
            batch = Shell(context=context)
        elif batch_type == 'dp_cloud_server':
            input_data = jdata.get('input_data')
            batch = DpCloudServer(context=context, input_data=input_data)
        else:
            raise RuntimeError(f"unknown batch_type:{batch_type}")
        return batch

class MachineDict(TypedDict):
    batch : dict
    resources : dict

# FilePathStr = PathLike[str]
class MachineConfig(TypedDict):
    machine_config_json : PathLike
    batch_name : str
    resources_name : str

class Machine(object):
    def __init__(
        self,
        batch=None,
        resources=None
    ):
        self.batch = batch
        self.resources = resources

    @classmethod
    def load_from_machine_dict(cls, machine_dict):
        batch_dict = machine_dict['batch']
        resources_dict = machine_dict['resources']
        batch = BatchObject(jdata=batch_dict)
        # if resources_dict is not None: 
        resources = Resources(**resources_dict)
        # else:
        #     resources = None
        machine = cls(batch=batch,resources=resources)
        return machine

    @classmethod
    def load_from_json_file(cls, json_path):
        with open(json_path, 'r') as f:
            machine_dict = json.load(f)
        machine = cls.load_from_machine_dict(
            machine_dict=machine_dict
        )
        return machine
    
    @classmethod
    def load_from_yaml_file(cls, yaml_path):
        pass
        # with open(yaml_path, 'r') as f:
        #     machine_dict = {}
        # machine = cls.load_from_machine_dict(
        #     machine_dict=machine_dict
        # )
        # return machine

    @classmethod
    def load_from_machine_config(cls, machine_config):
        machine_center_json = machine_config['machine_center_json']

        batch_name = machine_config['batch_name']
        resources_name = machine_config['resources_name']
        with open(machine_center_json, 'r') as f:
            machine_config_dict = json.load(f)
        machine_dict = {
            'batch' : machine_config_dict[batch_name],
            'resources' : machine_config_dict[resources_name] 
        }
        machine = cls.load_from_machine_dict(machine_dict=machine_dict)
        return machine


# def get_batch_and_resources_from_machine_jdata():
#     pass

# def get_batch_and_resources_from_machine_json(json_path):
#     with open(json_path, 'r') as f:
#         mdata = json.load(f)
#     batch_dict = mdata['batch']
#     resources_dict = mdata['resources_dict']
#     batch = BatchObject(jdata=batch_dict)
#     resources = Resources(**resources_dict)
#     return batch, resources

# submission.bind_batch(batch=batch)

