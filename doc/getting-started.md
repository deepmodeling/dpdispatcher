# Getting Started

DPDispatcher provides the following classes:

- {class}`Task <dpdispatcher.submission.Task>` class, which represents a command to be run on batch job system, as well as the essential files need by the command.
- {class}`Submission <dpdispatcher.submission.Submission>` class, which represents a collection of jobs defined by the HPC system.
And there may be common files to be uploaded by them.
DPDispatcher will create and submit these jobs when a `submission` instance execute {meth}`run_submission <dpdispatcher.submission.Submission.run_submission>` method.
This method will poke until the jobs finish and return.  
- {class}`Job <dpdispatcher.submission.Job>` class, a class used by {class}`Submission <dpdispatcher.submission.Submission>` class, which represents a job on the HPC system. 
{class}`Submission <dpdispatcher.submission.Submission>` will generate `job`s' submitting scripts used by HPC systems automatically with the {class}`Task <dpdispatcher.submission.Task>` and {class}`Resources <dpdispatcher.submission.Resources>`
- {class}`Resources <dpdispatcher.submission.Resources>` class, which represents the computing resources for each job  within a `submission`.

You can use DPDispatcher in a Python script to submit five tasks:

```python
from dpdispatcher import Machine, Resources, Task, Submission

machine = Machine.load_from_json('machine.json')
resources = Resources.load_from_json('resources.json')

task0 = Task.load_from_json('task.json')

task1 = Task(command='cat example.txt', task_work_path='dir1/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
task2 = Task(command='cat example.txt', task_work_path='dir2/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
task3 = Task(command='cat example.txt', task_work_path='dir3/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
task4 = Task(command='cat example.txt', task_work_path='dir4/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')

task_list = [task0, task1, task2, task3, task4]

submission = Submission(work_base='lammps_md_300K_5GPa/',
    machine=machine, 
    resources=resources,
    task_list=task_list,
    forward_common_files=['graph.pb'], 
    backward_common_files=[]
)

submission.run_submission()
```

where `machine.json` is
```json
{
    "batch_type": "Slurm",
    "context_type": "SSHContext",
    "local_root" : "/home/user123/workplace/22_new_project/",
    "remote_root": "/home/user123/dpdispatcher_work_dir/",
    "remote_profile":{
        "hostname": "39.106.xx.xxx",
        "username": "user123",
        "port": 22,
        "timeout": 10
    }
}
```

`resources.json` is
```json
{
    "number_node": 1,
    "cpu_per_node": 4,
    "gpu_per_node": 1,
    "queue_name": "GPUV100",
    "group_size": 5
}
```

and `task.json` is
```json
{
    "command": "lmp -i input.lammps",
    "task_work_path": "bct-0/",
    "forward_files": [
        "conf.lmp",
        "input.lammps"
    ],
    "backward_files": [
        "log.lammps"
    ],
    "outlog": "log",
    "errlog": "err",
}
```
You may also submit mutiple GPU jobs:
complex resources example
```python3
resources = Resources(
    number_node=1,
    cpu_per_node=4,
    gpu_per_node=2,
    queue_name="GPU_2080Ti",
    group_size=4,
    custom_flags=[
        "#SBATCH --nice=100", 
        "#SBATCH --time=24:00:00"
    ],
    strategy={
        # used when you want to add CUDA_VISIBLE_DIVECES automatically
        "if_cuda_multi_devices": True 
    },
    para_deg=1,
    # will unload these modules before running tasks
    module_unload_list=["singularity"],
    # will load these modules before running tasks
    module_list=["singularity/3.0.0"],
    # will source the environment files before running tasks
    source_list=["./slurm_test.env"],
    # the envs option is used to export environment variables
    # And it will generate a line like below.
    # export DP_DISPATCHER_EXPORT=test_foo_bar_baz
    envs={"DP_DISPATCHER_EXPORT": "test_foo_bar_baz"},
)
```

The details of parameters can be found in [Machine Parameters](machine), [Resources Parameters](resources), and [Task Parameters](task).
