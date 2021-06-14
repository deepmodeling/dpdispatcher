resources: 
    | type: ``dict``
    | argument path: ``resources``

    number_node: 
        | type: ``int``
        | argument path: ``resources/number_node``

        The number of node need for each `job`

    cpu_per_node: 
        | type: ``int``
        | argument path: ``resources/cpu_per_node``

        cpu numbers of each node assigned to each job.

    gpu_per_node: 
        | type: ``int``
        | argument path: ``resources/gpu_per_node``

        gpu numbers of each node assigned to each job.

    queue_name: 
        | type: ``str``
        | argument path: ``resources/queue_name``

        The queue name of batch job scheduler system.

    group_size: 
        | type: ``int``
        | argument path: ``resources/group_size``

        The number of `tasks` in a `job`.

    custom_flags: 
        | type: ``list``, optional
        | argument path: ``resources/custom_flags``

        The extra lines pass to job submitting script header

    strategy: 
        | type: ``dict``, optional
        | argument path: ``resources/strategy``

        strategies we use to generation job submitting scripts.

        if_cuda_multi_devices: 
            | type: ``bool``, optional, default: ``True``
            | argument path: ``resources/strategy/if_cuda_multi_devices``

    para_deg: 
        | type: ``int``, optional, default: ``1``
        | argument path: ``resources/para_deg``

        Decide how many tasks will be run in parallel.

    source_list: 
        | type: ``list``, optional, default: ``[]``
        | argument path: ``resources/source_list``

        The env file to be sourced before the command execution.

    module_unload_list: 
        | type: ``list``, optional, default: ``[]``
        | argument path: ``resources/module_unload_list``

        The modules to be unloaded on HPC system before submitting jobs

    module_list: 
        | type: ``list``, optional, default: ``[]``
        | argument path: ``resources/module_list``

        The modules to be loaded on HPC system before submitting jobs

    envs: 
        | type: ``dict``, optional, default: ``{}``
        | argument path: ``resources/envs``

        The environment variables to be exported on before submitting jobs
