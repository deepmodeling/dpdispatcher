task: 
    | type: ``dict``
    | argument path: ``task``

    command: 
        | type: ``str``
        | argument path: ``task/command``

        A command to be executed of this task. The expected return code is 0.

    task_work_path: 
        | type: ``str``
        | argument path: ``task/task_work_path``

        The dir where the command to be executed.

    forward_files: 
        | type: ``list``
        | argument path: ``task/forward_files``

        The files to be uploaded in task_work_path before the task exectued.

    backward_files: 
        | type: ``list``
        | argument path: ``task/backward_files``

        The files to be download to local_root in task_work_path after the task finished

    outlog: 
        | type: ``NoneType`` | ``str``
        | argument path: ``task/outlog``

        The out log file name. redirect from stdout

    errlog: 
        | type: ``NoneType`` | ``str``
        | argument path: ``task/errlog``

        The err log file name. redirect from stderr
