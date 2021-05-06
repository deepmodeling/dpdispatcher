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