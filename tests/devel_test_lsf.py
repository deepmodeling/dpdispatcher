import os
import sys
import json
from dpdispatcher.submission import Submission, Job, Task, Resources
from dpdispatcher.machine import Machine

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# task_need_resources has no effect
with open("jsons/machine_lsf.json", 'r') as f:
    mdata = json.load(f)

machine = Machine.load_from_dict(mdata['machine'])
resources = Resources.load_from_dict(mdata['resources'])

submission = Submission(
    work_base='0_md/',
    machine=machine,
    resources=resources,
    forward_common_files=['graph.pb'],
    backward_common_files=[]
)

task1 = Task(
    command='lmp -i input.lammps',
    task_work_path='bct-1/',
    forward_files=['conf.lmp', 'input.lammps'],
    backward_files=['log.lammps']
)
task2 = Task(
    command='lmp -i input.lammps',
    task_work_path='bct-2/',
    forward_files=['conf.lmp', 'input.lammps'],
    backward_files=['log.lammps']
)
task3 = Task(
    command='lmp -i input.lammps',
    task_work_path='bct-3/',
    forward_files=['conf.lmp', 'input.lammps'],
    backward_files=['log.lammps']
)
task4 = Task(
    command='lmp -i input.lammps',
    task_work_path='bct-4/',
    forward_files=['conf.lmp', 'input.lammps'],
    backward_files=['log.lammps']
)
submission.register_task_list([task1, task2, task3, task4, ])
submission.run_submission(clean=True)
