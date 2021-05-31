origin files:
[https://www.yuque.com/xingyeyongtantiao/dpdispatcher/rdydgb](https://www.yuque.com/xingyeyongtantiao/dpdispatcher/rdydgb)
​

developers' discussion (temporarily in Chinese):
[https://www.yuque.com/docs/share/08ab09f3-f84d-4ed3-b777-9e0c791963b6?#](https://www.yuque.com/docs/share/08ab09f3-f84d-4ed3-b777-9e0c791963b6?#)


## introduction:
### short introduction
dpdispatcher is a python package used to generate HPC(High Performance Computing) scheduler systems (Slurm/PBS/LSF/dpcloudserver) jobs input scripts and submit these  scripts to HPC systems and poke until they finish.  
​

dpdispatcher will monitor (poke) until these jobs finish and download the results files (if these jobs is running on remote systems connected by SSH). 


### the set of abstraction provided by dpdispatcher.
It defines `Task` class, which represents a command to be run on HPC and essential files need by the command.
It defines `Job` class, which represents a job on the HPC system. dpdispatcher will generate `job`s' submitting scripts used by HPC systems automatically with the `Task` and `Submission`
It define a `Submission` class, which represents a collection of jobs defined by the HPC system and there may be common used files between them. dpdispatcher will actually submit the jobs in them when a `submission` execute `run_submission` method and poke until the jobs in them finish and return.  
​

## How to contribute 
dpdispatcher welcomes every people (or organization) to use under the LGPL-3.0 License.


And Contributions are welcome and are greatly appreciated! Every little bit helps, and credit will always be given.
​

If you want to contribute to dpdispatcher, just open a issue, submiit a pull request , leave a comment on github discussion, or contact deepmodeling team. 
​

Any forms of improvement are welcome.

- use, star or fork dpdispatcher
- improve the documents
- report or fix bugs
- request, discuss or implement features



dpdispatcher is maintained by deepmodeling's developers now and welcome other people.


​

## example


```python3
machine = Machine.load_from_json('machine.json')
resources = Resources.load_from_json('resources.json')

## with open('compute.json', 'r') as f:
##     compute_dict = json.load(f)

## machine = Machine.load_from_dict(compute_dict['machine'])
## resources = Resources.load_from_dict(compute_dict['resources'])

task0 = Task.load_from_json('task.json')

task1 = Task(command='cat example.txt', task_work_path='dir1/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
task2 = Task(command='cat example.txt', task_work_path='dir2/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
task3 = Task(command='cat example.txt', task_work_path='dir3/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')
task4 = Task(command='cat example.txt', task_work_path='dir4/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')

task_list = [task0, task1, task2, task3, task4]

submission = Submission(work_base='lammps_md_300K_5GPa/',
    machine=machine, 
    resources=reasources,
    task_list=task_list,
    forward_common_files=['graph.pb'], 
    backward_common_files=[]
)

## submission.register_task_list(task_list=task_list)

submission.run_submission(clean=False)
```

machine.json
```json
{
    "machine_type": "Slurm",
    "context_type": "SSHContext",
    "local_root" : "/home/user123/workplace/22_new_project/",
    "remote_root": "~/dpdispatcher_work_dir/",
    "remote_profile":{
        "hostname": "39.106.xx.xxx",
        "username": "user1",
        "port": 22,
        "timeout": 10
    }
}
```

resources.json
```json
{
    "number_node": 1,
    "cpu_per_node": 4,
    "gpu_per_node": 1,
    "queue_name": "GPUV100",
    "group_size": 5
}
```

task.json
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
