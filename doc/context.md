# Supported contexts

Context is the way to connect to the remote server.
One needs to set {dargs:argument}`context_type <machine/context_type>` to one of the following values:

## LazyLocal

{dargs:argument}`context_type <machine/context_type>`: `LazyLocal`

`LazyLocal` directly runs jobs in the local server and local directory.

## Local

{dargs:argument}`context_type <machine/context_type>`: `Local`

`Local` runs jobs in the local server, but in a different directory.
Files will be copied to the remote directory before jobs start and copied back after jobs finish.

## SSH

{dargs:argument}`context_type <machine/context_type>`: `SSH`

`SSH` runs jobs in a remote server.
Files will be copied to the remote directory via SSH channels before jobs start and copied back after jobs finish.
To use SSH, one needs to provide necessary parameters in {dargs:argument}`remote_profile <machine[SSHContext]/remote_profile>`, such as {dargs:argument}`username <machine[SSHContext]/remote_profile/hostname>` and {dargs:argument}`hostname <username[SSHContext]/remote_profile/hostname>`.

It's suggested to generate [SSH keys](https://help.ubuntu.com/community/SSH/OpenSSH/Keys) and transfer the public key to the remote server in advance, which is more secure than password authentication.

Note that `SSH` context is [non-login](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html), so `bash_profile` files will not be executed.

## Bohrium

{dargs:argument}`context_type <machine/context_type>`: `Bohrium`

Bohrium is the cloud platform for scientific computing.
Read Bohrium documentation for details.
To use Bohrium, one needs to provide necessary parameters in {dargs:argument}`remote_profile <machine[BohriumContext]/remote_profile>`.

## HDFS

{dargs:argument}`context_type <machine/context_type>`: `HDFS`

The Hadoop Distributed File System (HDFS) is a distributed file system.
Read [Support DPDispatcher on Yarn](dpdispatcher_on_yarn.md) for details.
