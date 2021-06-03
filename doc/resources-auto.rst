resources_dict: 
    | type: ``dict``
    | argument path: ``resources_dict``

    number_node: 
        | type: ``int``
        | argument path: ``resources_dict/number_node``

        The number of node need for each `job`

    cpu_per_node: 
        | type: ``int``
        | argument path: ``resources_dict/cpu_per_node``

        cpu numbers of each node.

    gpu_per_node: 
        | type: ``int``
        | argument path: ``resources_dict/gpu_per_node``

        gpu numbers of each node.

    queue_name: 
        | type: ``str``
        | argument path: ``resources_dict/queue_name``

        The queue name of batch job scheduler system.

    group_size: 
        | type: ``int``
        | argument path: ``resources_dict/group_size``

        The number of `tasks` in a `job`.

    custom_flags: 
        | type: ``str``, optional
        | argument path: ``resources_dict/custom_flags``

        The extra lines pass to job submitting script header

    strategy: 
        | type: ``dict``, optional
        | argument path: ``resources_dict/strategy``

        strategies we use to generation job submitting scripts.

    para_deg: 
        | type: ``int``, optional
        | argument path: ``resources_dict/para_deg``

        Decide how many tasks will be run in parallel.

    source_list: 
        | type: ``list``, optional
        | argument path: ``resources_dict/source_list``

        The env file to be sourced before the command execution.

    kwargs: 
        | type: ``dict``, optional
        | argument path: ``resources_dict/kwargs``

        extra key-value pair
