### README ###
developers' discussion (in Chinese):
https://www.yuque.com/docs/share/08ab09f3-f84d-4ed3-b777-9e0c791963b6?# 《dpdispatcher 讨论纪要》


ussage example
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
