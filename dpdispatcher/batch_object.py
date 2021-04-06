import json
from dpdispatcher.batch import Batch
from dpdispatcher.pbs import PBS
from dpdispatcher.lsf import LSF
from dpdispatcher.slurm import Slurm
from dpdispatcher.shell import Shell
from dpdispatcher.lazy_local_context import LazyLocalContext
from dpdispatcher.local_context import LocalContext
from dpdispatcher.ssh_context import SSHContext
from dpdispatcher.submission import Resources


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
        else:
            raise RuntimeError(f"unknown batch_type:{batch_type}")
        return batch

def get_batch_and_resources_from_machine_json(json_path):
    with open(json_path, 'r') as f:
        mdata = json.load(f)
    batch_dict = mdata['batch']
    resources_dict = mdata['resources_dict']
    batch = BatchObject(jdata=batch_dict)
    resources = Resources(**resources_dict)
    return batch, resources

# submission.bind_batch(batch=batch)

