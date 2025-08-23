# Supported contexts

Context is the way to connect to the remote server.
One needs to set {dargs:argument}`context_type <machine/context_type>` to one of the following values:

## LazyLocal

{dargs:argument}`context_type <machine/context_type>`: `LazyLocal`

`LazyLocal` directly runs jobs in the local server and local directory.

Since [`bash -l`](https://www.gnu.org/software/bash/manual/bash.html#Invoking-Bash) is used in the shebang line of the submission scripts, the [login shell startup files](https://www.gnu.org/software/bash/manual/bash.html#Invoking-Bash) will be executed, potentially overriding the current environment variables. Therefore, it's advisable to explicitly set the environment variables using {dargs:argument}`envs <resources/envs>` or {dargs:argument}`source_list <resources/source_list>`.

## Local

{dargs:argument}`context_type <machine/context_type>`: `Local`

`Local` runs jobs in the local server, but in a different directory.
Files will be symlinked to the remote directory before jobs start and copied back after jobs finish.
If the local directory is not accessible with the [batch system](./batch.md), turn off {dargs:argument}`symlink <machine[LocalContext]/remote_profile/symlink>`, and then files on the local directory will be copied to the remote directory.

Since [`bash -l`](https://www.gnu.org/software/bash/manual/bash.html#Invoking-Bash) is used in the shebang line of the submission scripts, the [login shell startup files](https://www.gnu.org/software/bash/manual/bash.html#Invoking-Bash) will be executed, potentially overriding the current environment variables. Therefore, it's advisable to explicitly set the environment variables using {dargs:argument}`envs <resources/envs>` or {dargs:argument}`source_list <resources/source_list>`.

## SSH

{dargs:argument}`context_type <machine/context_type>`: `SSH`

`SSH` runs jobs in a remote server.
Files will be copied to the remote directory via SSH channels before jobs start and copied back after jobs finish.
To use SSH, one needs to provide necessary parameters in {dargs:argument}`remote_profile <machine[SSHContext]/remote_profile>`, such as {dargs:argument}`username <machine[SSHContext]/remote_profile/hostname>` and {dargs:argument}`hostname <username[SSHContext]/remote_profile/hostname>`.

It's suggested to generate [SSH keys](https://help.ubuntu.com/community/SSH/OpenSSH/Keys) and transfer the public key to the remote server in advance, which is more secure than password authentication.

### SSH Jump Host (Bastion Server)

For connecting to internal servers through a jump host (bastion server), SSH context supports jump host configuration. This allows connecting to internal servers that are not directly accessible from the internet.

#### Method 1: Using proxy_command (Recommended)

For maximum flexibility, specify the ProxyCommand directly using {dargs:argument}`proxy_command <machine[SSHContext]/remote_profile/proxy_command>`:

```json
{
  "context_type": "SSHContext",
  "remote_profile": {
    "hostname": "internal-server.company.com",
    "username": "user",
    "key_filename": "/path/to/internal_key",
    "proxy_command": "ssh -W %h:%p -i /path/to/jump_key jumpuser@bastion.company.com"
  }
}
```

The proxy command uses OpenSSH ProxyCommand syntax. `%h` and `%p` are replaced with the target hostname and port.

#### Method 2: Using individual jump host parameters (Legacy)

Alternatively, use individual jump host parameters (maintained for backward compatibility):

- {dargs:argument}`jump_hostname <machine[SSHContext]/remote_profile/jump_hostname>`: hostname or IP of the jump host
- {dargs:argument}`jump_username <machine[SSHContext]/remote_profile/jump_username>`: username for the jump host
- {dargs:argument}`jump_port <machine[SSHContext]/remote_profile/jump_port>`: port for the jump host (default: 22)
- {dargs:argument}`jump_key_filename <machine[SSHContext]/remote_profile/jump_key_filename>`: SSH key file for the jump host

```json
{
  "context_type": "SSHContext",
  "remote_profile": {
    "hostname": "internal-server.company.com",
    "username": "user",
    "key_filename": "/path/to/internal_key",
    "jump_hostname": "bastion.company.com",
    "jump_username": "jumpuser",
    "jump_key_filename": "/path/to/jump_key"
  }
}
```

**Note**: Cannot specify both `proxy_command` and individual jump host parameters in the same configuration.

This configuration establishes the connection path: Local → Jump Host → Target Server.

Note that `SSH` context is [non-login](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html), so `bash_profile` files will not be executed outside the submission script.

## Bohrium

{dargs:argument}`context_type <machine/context_type>`: `Bohrium`

Bohrium is the cloud platform for scientific computing.
Read Bohrium documentation for details.
To use Bohrium, one needs to provide necessary parameters in {dargs:argument}`remote_profile <machine[BohriumContext]/remote_profile>`.

## HDFS

{dargs:argument}`context_type <machine/context_type>`: `HDFS`

The Hadoop Distributed File System (HDFS) is a distributed file system.
Read [Support DPDispatcher on Yarn](dpdispatcher_on_yarn.md) for details.

## OpenAPI

{dargs:argument}`context_type <machine/context_type>`: `OpenAPI`

OpenAPI is a new way to submit jobs to Bohrium. It using [AccessKey](https://bohrium.dp.tech/personal/setting) instead of username and password. Read Bohrium documentation for details.
To use OpenAPI, one needs to provide necessary parameters in {dargs:argument}`remote_profile <machine[OpenAPIContext]/remote_profile>`.
