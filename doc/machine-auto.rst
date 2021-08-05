machine: 
    | type: ``dict``
    | argument path: ``machine``

    batch_type: 
        | type: ``str``
        | argument path: ``machine/batch_type``

        The batch job system type. Option: Slurm, PBS, LSF, Shell, DpCloudServer

    context_type: 
        | type: ``str``
        | argument path: ``machine/context_type``

        The connection used to remote machine. Option: LocalContext, LazyLocalContext, SSHContext， DpCloudServerContext

    local_root: 
        | type: ``str``
        | argument path: ``machine/local_root``

        The dir where the tasks and relating files locate. Typically the project dir.

    remote_root: 
        | type: ``str``, optional
        | argument path: ``machine/remote_root``

        The dir where the tasks are executed on the remote machine. Only needed when context is not lazy-local.

    remote_profile: 
        | type: ``dict``
        | argument path: ``machine/remote_profile``

        The information used to maintain the connection with remote machine. Only needed when context is ssh.

        hostname: 
            | type: ``str``
            | argument path: ``machine/remote_profile/hostname``

            hostname or ip of ssh connection.

        username: 
            | type: ``str``
            | argument path: ``machine/remote_profile/username``

            username of target linux system

        password: 
            | type: ``str``, optional
            | argument path: ``machine/remote_profile/password``

            password of linux system

        port: 
            | type: ``int``, optional, default: ``22``
            | argument path: ``machine/remote_profile/port``

            ssh connection port.

        key_filename: 
            | type: ``str`` | ``NoneType``, optional, default: ``None``
            | argument path: ``machine/remote_profile/key_filename``

            key filename used by ssh connection. If left None, find key in ~/.ssh or use password for login

        passphrase: 
            | type: ``str`` | ``NoneType``, optional, default: ``None``
            | argument path: ``machine/remote_profile/passphrase``

            passphrase of key used by ssh connection

        timeout: 
            | type: ``int``, optional, default: ``10``
            | argument path: ``machine/remote_profile/timeout``

            timeout of ssh connection

        totp_secret: 
            | type: ``str`` | ``NoneType``, optional, default: ``None``
            | argument path: ``machine/remote_profile/totp_secret``

            Time-based one time password secret. It should be a base32-encoded string extracted from the 2D code.

    clean_asynchronously: 
        | type: ``bool``, optional, default: ``False``
        | argument path: ``machine/clean_asynchronously``

        Clean the remote directory asynchronously after the job finishes.
