import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))

from dpdispatcher.local_context import LocalSession, LocalContext
from dpdispatcher.lazy_local_context import LazyLocalContext
from dpdispatcher.ssh_context import SSHSession, SSHContext

from dpdispatcher.submission import Submission, Job, Task, Resources
from dpdispatcher.batch import Batch
from dpdispatcher.slurm import SlurmResources, Slurm

# local_session = LocalSession({'work_path':'temp2'})
# local_context = LocalContext(local_root='test_slurm_dir/', work_profile=local_session)
# lazy_local_context = LazyLocalContext(local_root='/home/fengbo/10_dpdispatcher/dpdispatcher/tests/temp3/0_md', work_profile=None)


# machine_dict = dict(hostname='localhost', remote_root='/home/dp/dpdispatcher/tests/temp2', username='dp')
# ssh_session = SSHSession(**machine_dict)
ssh_session = SSHSession(hostname='8.131.233.55', remote_root='/home/dp/dp_remote', username='dp')
ssh_context = SSHContext(local_root='test_slurm_dir', ssh_session=ssh_session)
slurm = Slurm(context=ssh_context)

resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=0, queue_name="debug", group_size=4, if_cuda_multi_devices=False)
slurm_sbatch_dict={'mem': '10G', 'cpus_per_task':1, 'time': "120:0:0"} 
slurm_resources = SlurmResources(resources=resources, slurm_sbatch_dict=slurm_sbatch_dict)
submission = Submission(work_base='0_md', resources=slurm_resources,  forward_common_files=['graph.pb'], backward_common_files=['submission.json']) #,  batch=PBS)
task1 = Task(command='/home/dp/deepmd-kit/bin/lmp -i input.lammps', task_work_path='bct-1', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=1)
task2 = Task(command='/home/dp/deepmd-kit/bin/lmp -i input.lammps', task_work_path='bct-2', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.25)
task3 = Task(command='/home/dp/deepmd-kit/bin/lmp -i input.lammps', task_work_path='bct-3', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.25)
task4 = Task(command='/home/dp/deepmd-kit/bin/lmp -i input.lammps', task_work_path='bct-4', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.5)
submission.register_task_list([task1, task2, task3, task4, ])
submission.generate_jobs()
submission.bind_batch(batch=slurm)


submission.run_submission()
