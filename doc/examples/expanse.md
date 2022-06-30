# Running the DeePMD-kit on the Expanse cluster

[Expanse](https://www.sdsc.edu/support/user_guides/expanse.html) is a cluster operated by the San Diego Supercomputer Center. Here we provide an example to run jobs on the expanse.

The machine parameters are provided below. Expanse uses the SLURM workload manager for job scheduling. {ref}`remote_root <machine/remote_root>` has been created in advance. It's worth metioned that we do not recommend to use the password, so [SSH keys](https://www.ssh.com/academy/ssh/key) are used instead to improve security.

```{literalinclude} ../../examples/machine/expanse.json
:language: json
:linenos:
```

Expanse's standard compute nodes are each powered by two 64-core AMD EPYC 7742 processors and contain 256 GB of DDR4 memory. Here, we request one node with 32 cores and 16 GB memory from the `shared` partition. Expanse does not support `--gres=gpu:0` command, so we use {ref}`custom_gpu_line <resources[Slurm]/kwargs/custom_gpu_line>` to customize the statement.

```{literalinclude} ../../examples/resources/expanse_cpu.json
:language: json
:linenos:
```

The following task parameter runs a DeePMD-kit task, forwarding an input file and backwarding graph files. Here, the data set will be used among all the tasks, so it is not included in the {ref}`forward_files <task/forward_files>`. Instead, it should be included in the submission's {ref}`forward_common_files <task/forward_common_files>`.

```{literalinclude} ../../examples/task/deepmd-kit.json
:language: json
:linenos:
```
