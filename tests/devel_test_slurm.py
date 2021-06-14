import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))
# from .context import dpdispatcher
#from dpdispatcher.local_context import LocalContext
from dpdispatcher.lazy_local_context import LazyLocalContext
# from dpdispatcher.ssh_context import SSHContext

from dpdispatcher.submission import Submission, Job, Task, Resources
from dpdispatcher.machine import Machine
# from dpdispatcher.submission import
# from dpdispatcher.slurm import Slurm

# local_session = LocalSession({'work_path':'temp2'})
# local_context = LocalContext(local_root='test_slurm_dir/', work_profile=local_session)
# lazy_local_context = LazyLocalContext(local_root='test_slurm_dir/')


# machine_dict = dict(hostname='localhost', remote_root='/home/dp/dpdispatcher/tests/temp2', username='dp')
# ssh_session = SSHSession(**machine_dict)
# ssh_session = SSHSession(hostname='8.131.233.55', remote_root='/home/dp/dp_remote', username='dp')
# ssh_context = SSHContext(local_root='test_slurm_dir', ssh_session=ssh_session)
# slurm = Slurm(context=ssh_context)
# slurm = Slurm(context=lazy_local_context)

# resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=2, queue_name="GPU_2080Ti", group_size=4, 
#     custom_flags=['#SBATCH --exclude=2080ti000,2080ti001,2080ti002,2080ti004,2080ti005,2080ti006'],
#     para_deg=2,
#     strategy={"if_cuda_multi_devices":True})
# slurm_sbatch_dict={'mem': '10G', 'cpus_per_task':1, 'time': "120:0:0"} 
# slurm_resources = SlurmResources(resources=resources, slurm_sbatch_dict=slurm_sbatch_dict)

with open("jsons/machine_slurm.json", 'r') as f:
    mdata = json.load(f)

machine = Machine.load_from_dict(mdata['machine'])
resources = Resources.load_from_dict(mdata['resources'])

submission = Submission(work_base='0_md/', machine=machine, resources=resources,  forward_common_files=['graph.pb'], backward_common_files=[]) #,  batch=PBS)
task1 = Task(command='lmp -i input.lammps', task_work_path='bct-1/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps']) 
task2 = Task(command='lmp -i input.lammps', task_work_path='bct-2/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task3 = Task(command='lmp -i input.lammps', task_work_path='bct-3/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task4 = Task(command='lmp -i input.lammps', task_work_path='bct-4/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
submission.register_task_list([task1, task2, task3, task4, ])
submission.run_submission(clean=True)
