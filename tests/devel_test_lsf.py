import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dpdispatcher.ssh_context import SSHSession, SSHContext
from dpdispatcher.submission import Submission, Task, Resources
from dpdispatcher.lsf import LSF

# edit ssh parameters
ssh_session = SSHSession(
    hostname='127.0.0.1',
    port=22,
    remote_root='/home/dp/dpdispatcher/tests',
    username='debug'
)
# local_root is the relevant path that containing tasks to be submit
ssh_context = SSHContext(local_root='test_lsf_dir', ssh_session=ssh_session)
lsf = LSF(context=ssh_context)

prepend_text = '''
module load cuda/9.2
module load gcc/4.9.4
module load deepmd/1.0
source /home/dp/scripts/avail_gpu.sh
'''

lsf_bsub_dict = {
    'R': "'select[hname != g005]'"
}
resources = Resources(
    number_node=1,
    cpu_per_node=4,
    gpu_per_node=0,
    queue_name="gpu",
    walltime="24:00:00",
    prepend_text=prepend_text,
    append_text="",
    gpu_usage=False,
    gpu_new_syntax=False,
    extra_specification=lsf_bsub_dict,
    group_size=1
)

# task_need_resources has no effect
submission = Submission(
    work_base='0_md',  # the dir containing all of task_work_path
    resources=resources,  # resources above
    forward_common_files=['graph.pb'],  # file to be upload
    backward_common_files=['*.json']  # file to be downloaded
)
task1 = Task(
    command='lmp_mpi_20201029 -i input.lammps',
    task_work_path='bct-1',
    forward_files=['conf.lmp', 'input.lammps'],
    backward_files=['log.lammps'],
)
task2 = Task(
    command='lmp_mpi_20201029 -i input.lammps',
    task_work_path='bct-2',
    forward_files=['conf.lmp', 'input.lammps'],
    backward_files=['log.lammps'],
)
task3 = Task(
    command='lmp_mpi_20201029 -i input.lammps',
    task_work_path='bct-3',
    forward_files=['conf.lmp', 'input.lammps'],
    backward_files=['log.lammps'],
)
task4 = Task(
    command='lmp_mpi_20201029 -i input.lammps',
    task_work_path='bct-4',
    forward_files=['conf.lmp', 'input.lammps'],
    backward_files=['log.lammps'],
)
submission.register_task_list([task1, task2, task3, task4, ])
submission.generate_jobs()
submission.bind_batch(batch=lsf)

submission.run_submission()
