import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))

from dpdispatcher.local_context import LocalSession
from dpdispatcher.local_context import LocalContext

from dpdispatcher.submission import Submission, Job, Task, Resources
from dpdispatcher.batch import Batch
from dpdispatcher.pbs import PBS

local_session = LocalSession({'work_path':'temp2'})
local_context = LocalContext(local_root='temp1/0_md', work_profile=local_session)
print(local_context)
print('local_context.local_root', local_context.local_root)
print('local_context.work_profile', local_context.work_profile)


pbs = PBS(context=local_context)

resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=1, queue_name="V100_8_32", group_size=2) 
submission = Submission(work_base='temp1/0_md', resources=resources,  forward_common_files=['graph.pb'], backward_common_files=['submission.json']) #,  batch=PBS)
task1 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-1', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task2 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-2', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task3 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-3', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task4 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-4', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
submission.register_task_list([task1, task2, task3, task4, ])
submission.generate_jobs()
submission.bind_batch(batch=pbs)
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
