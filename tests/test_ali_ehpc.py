import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))

from dpdispatcher.local_context import LocalSession
from dpdispatcher.local_context import LocalContext

from dpdispatcher.submission import Submission, Job, Task, Resources
from dpdispatcher.batch import Batch, PBS

local_session = LocalSession({'work_path':'temp2'})
local_context = LocalContext(local_root='temp1/0_md', work_profile=local_session)
print(local_context)
print(local_context.local_root)
print(local_context.remote_root)


pbs = PBS(context=local_context)

resources1 = Resources(number_node=1, cpu_per_node=4, gpu_per_node=1, queue_name="G_32_128", group_size=2) 
submission1 = Submission(work_base='temp1/0_md', resources=resources1,  forward_common_files=['graph.pb'], backward_common_files=[]) #,  batch=PBS)
task1 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-1', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task2 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-2', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task3 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-3', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
task4 = Task(command='lmp_serial -i input.lammps', task_work_path='bct-4', forward_files=['conf.lmp', 'input.lammps'], backward_files=['log.lammps'])
submission1.register_task_list([task1, task2, task3, task4, ])
submission1.band_batch(batch=pbs)
submission1.generate_jobs()
submission1.run_submission()


print(submission1.belonging_jobs)
print(local_context)
