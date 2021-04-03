import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))

# from dpdispatcher.local_context import LocalSession
# from dpdispatcher.local_context import LocalContext

from dpdispatcher.submission import Submission, Job, Task, Resources
# from dpdispatcher.batch import Batch
# from dpdispatcher.pbs import PBS
from dpdispatcher.batch_object import BatchObject

with open('ssh_machine.json', 'r') as f:
    jdata = json.load(f)

batch = BatchObject(jdata=jdata)
# local_session = LocalSession({'work_path':'temp2'})
# local_context = LocalContext(local_root='temp1/', work_profile=local_session)
# lazy_local_context = LazyLocalContext(local_root='/home/fengbo/10_dpdispatcher/dpdispatcher/tests/temp3/0_md', work_profile=None)
# pbs = PBS(context=lazy_local_context)
# ssh_session = SSHSession(hostname='39.106.84.25', remote_root='/home/fengbo/dp_remote', username='fengbo')
# ssh_context = SSHContext(local_root='test_slurm_dir', ssh_session=ssh_session)
# jdata = 

# pbs = PBS(context=ssh_context)

resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=1, queue_name="V100_8_32", group_size=4) 
submission = Submission(work_base='test_pbs_dir/0_md', resources=resources,  forward_common_files=['graph.pb'], backward_common_files=[]) #,  batch=PBS)
task1 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-1', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task2 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-2', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task3 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-3', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task4 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-4', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
submission.register_task_list([task1, task2, task3, task4, ])
submission.generate_jobs()
submission.bind_batch(batch=batch)
# for job in submission.belonging_jobs:
#     job.job_to_json()
# print('111', submission)
# submission2 = Submission.recover_jobs_from_json('./jr.json')
# print('222', submission2)
# print(submission==submission2)
submission.run_submission()

# submission1.dump_jobs_fo_json()
# submission2 = Submission.submission_from_json('jsons/submission.json')
# print(677, submission==submission2)
# print(submission1.belonging_jobs)
# print(local_context)
