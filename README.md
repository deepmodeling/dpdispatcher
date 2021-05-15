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

## ussage example


```python3

machine = Machine.load_from_json_file(json_path='jsons/machine_local_shell.json')
submission = Submission(work_base='parent_dir/', resources=machine.resources,  forward_common_files=['graph.pb'], backward_common_files=[])

task1 = Task(command='cat example.txt', task_work_path='dir1/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')

task2 = Task(command='cat example.txt', task_work_path='dir2/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')

task3 = Task(command='cat example.txt', task_work_path='dir3/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')

task4 = Task(command='cat example.txt', task_work_path='dir4/', forward_files=['example.txt'], backward_files=['out.txt'], outlog='out.txt')

submission.register_task_list([task1, task2, task3, task4, ])
submission.generate_jobs()
submission.bind_batch(batch=machine.batch)
submission.run_submission(clean=False)
```


the machine_local_shell.json looks like:
(more machine examples, see: tests/jsons/*json)


tests/jsons/machine_local_shell.json


```json
{
    "batch":{
        "batch_type": "shell",
        "context_type": "local",
        "local_root" : "./test_shell_trival_dir",
        "remote_root" : "./tmp_shell_trival_dir"
    },
    "resources":{
        "number_node": 1,
        "cpu_per_node": 4,
        "gpu_per_node": 0,
        "queue_name": "CPU",
        "group_size": 2
    }
}
```
