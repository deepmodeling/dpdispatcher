import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))
# from .sample_class import SampleClass
# from .context import Machine
# from .context import Resources
# from dpdispatcher.local_context import LocalSession
# from dpdispatcher.local_context import LocalContext
# from dpdispatcher.lazy_local_context import LazyLocalContext

from dpdispatcher.submission import Submission, Job, Task, Resources
from dpdispatcher.machine import Machine
from tests.sample_class import SampleClass
# from dpdispatcher.pbs import PBS

# local_session = LocalSession({'work_path':'test_work_path/'})
# local_context = LocalContext(local_root='test_pbs_dir/', work_profile=local_session)

# lazy_local_context = LazyLocalContext(local_root='/home/fengbo/10_dpdispatcher/dpdispatcher/tests/test_pbs_dir', work_profile=None)

# ssh_session = SSHSession(hostname='39.106.84.25', remote_root='/home/fengbo/dp_remote', username='fengbo')
# ssh_context = SSHContext(local_root='test_slurm_dir', ssh_session=ssh_session)

# pbs = PBS(context=ssh_context)
# pbs = PBS(context=local_context)
# pbs = PBS(context=lazy_local_context)

submission = SampleClass.get_sample_submission()
# pbs = SampleClass.get_sample_pbs_local_context()
# slurm = SampleClass.get_sample_slurm_local_context()

with open('jsons/compute_ali_ehpc.json', 'r') as f:
    compute_dict = json.load(f)

machine = Machine.load_from_dict(compute_dict['machine'])
resources = Resources.load_from_dict(compute_dict['resources'])

submission.resouces = resources
submission.bind_machine(machine=machine)
# submission.run_submission()
# submission.run_submission(exit_on_submit=True)
submission.run_submission()


# resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=1, queue_name="V100_8_32", group_size=2, if_cuda_multi_devices=True) 
# submission = Submission(work_base='0_md/', resources=resources,  forward_common_files=['graph.pb'], backward_common_files=[]) #,  batch=PBS)
# task1 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-1/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=1)
# task2 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-2/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.25)
# task3 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-3/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.25)
# task4 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-4/', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'], task_need_resources=0.5)
# submission.register_task_list([task1, task2, task3, task4, ])
# submission.generate_jobs()
# submission.bind_batch(batch=pbs)
# for job in submission.belonging_jobs:
#     job.job_to_json()
# print('111', submission)
# submission2 = Submission.recover_jobs_from_json('./jr.json')
# print('222', submission2)
# print(submission==submission2)

# submission1.dump_jobs_fo_json()
# submission2 = Submission.submission_from_json('jsons/submission.json')
# print(677, submission==submission2)
# print(submission1.belonging_jobs)
# print(local_context)
