machine_dict: 
    | type: ``dict``
    | argument path: ``machine_dict``

    batch_type: 
        | type: ``str``
        | argument path: ``machine_dict/batch_type``

        The batch job system type. Option: Slurm, PBS, LSF, Shell, DpCloudServer

    context_type: 
        | type: ``str``
        | argument path: ``machine_dict/context_type``

        The connection used to remote machine. Option: LocalContext, LazyLocalContext, SSHContext， DpCloudServerContext

    local_root: 
        | type: ``str``
        | argument path: ``machine_dict/local_root``

        The dir where the tasks and relating files locate. Typically the project dir.

    remote_root: 
        | type: ``str``, optional
        | argument path: ``machine_dict/remote_root``

        The dir where the tasks are executed on the remote machine.

    remote_profile: 
        | type: ``dict``, optional
        | argument path: ``machine_dict/remote_profile``

        The information used to maintain the connection with remote machine.
