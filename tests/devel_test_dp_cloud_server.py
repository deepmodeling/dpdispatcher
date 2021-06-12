import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))
from dpdispatcher.submission import Submission, Job, Task, Resources
# from dpdispatcher.batch_object import BatchObject
from dpdispatcher.machine import Machine
from dpdispatcher.dp_cloud_server import DpCloudServer
from dpdispatcher.dp_cloud_server_context import DpCloudServerContext
# from dpdispatcher.slurm import SlurmResources, Slurm

# local_session = LocalSession({'work_path':'temp2'})
# local_context = LocalContext(local_root='test_slurm_dir/', work_profile=local_session)
# lazy_local_context = LazyLocalContext(local_root='./')


# machine_dict = dict(hostname='localhost', remote_root='/home/dp/dpdispatcher/tests/temp2', username='dp')
# ssh_session = SSHSession(**machine_dict)
# ssh_session = SSHSession(hostname='8.131.233.55', remote_root='/home/dp/dp_remote', username='dp')
# ssh_context = SSHContext(local_root='test_slurm_dir', ssh_session=ssh_session)
# slurm = Slurm(context=ssh_context)
# slurm = Slurm(context=lazy_local_context)

# resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=0, queue_name="1 * NVIDIA P100", group_size=4)
# slurm_sbatch_dict={'mem': '10G', 'cpus_per_task':1, 'time': "120:0:0"} 
# slurm_resources = SlurmResources(resources=resources, slurm_sbatch_dict=slurm_sbatch_dict)


# dp_cloud_server_context = DpCloudServerContext(
#     local_root='test_context_dir/', 
#     username='yfb222333',
#     password='yfb222333')
# dp_cloud_server = DpCloudServer(context=dp_cloud_server_context)
# with open('test_dp_cloud_server.json', 'r') as f:
#     jdata = json.load(f)
with open('jsons/machine_dp_cloud_server.json', 'r') as f:
    compute_dict = json.load(f)

machine = Machine.load_from_dict(compute_dict['machine'])
resources = Resources.load_from_dict(compute_dict['resources'])

task1 = Task(command='lmp    -i input.lammps', task_work_path='bct-1/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task2 = Task(command='lmp -i input.lammps', task_work_path='bct-2/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task3 = Task(command='lmp   -i input.lammps', task_work_path='bct-3/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task4 = Task(command='lmp -i input.lammps', task_work_path='bct-4/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task_list = [task1, task2, task3, task4, ]

submission = Submission(work_base='0_md/', 
    machine=machine,
    resources=resources,
    forward_common_files=['graph.pb'],
    backward_common_files=[],
    task_list=task_list
)

submission.run_submission()
