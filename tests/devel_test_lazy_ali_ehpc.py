import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))

from dpdispatcher.local_context import LocalSession
from dpdispatcher.local_context import LocalContext
from dpdispatcher.lazy_local_context import LazyLocalContext

from dpdispatcher.submission import Submission, Job, Task, Resources
from dpdispatcher.batch import Batch
from dpdispatcher.pbs import PBS

# local_session = LocalSession({'work_path':'temp2'})
# local_context = LocalContext(local_root='temp1/0_md', work_profile=local_session)
lazy_local_context = LazyLocalContext(local_root='/home/fengbo/10_dpdispatcher/dpdispatcher/tests/temp3', work_profile=None)

# pbs = PBS(context=local_context)
pbs = PBS(context=lazy_local_context)

resources = Resources(number_node=1, cpu_per_node=4, gpu_per_node=1, queue_name="V100_8_32", group_size=4, if_cuda_multi_devices=True) 
submission = Submission(work_base='0_md', resources=resources)
task1 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-1') 
task2 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-2')
task3 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-3')
task4 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-4')
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
