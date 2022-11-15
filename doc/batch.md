# Supported batch job systems

Batch job system is a system to process batch jobs.
One needs to set {dargs:argument}`batch_type <machine/batch_type>` to one of the following values:

## Bash

{dargs:argument}`batch_type <resources/batch_type>`: `Shell`

When {dargs:argument}`batch_type <resources/batch_type>` is set to `Shell`, dpdispatcher will generate a bash script to process jobs.
No extra packages are required for `Shell`.

Due to lack of scheduling system, `Shell` runs all jobs at the same time.
To avoid running multiple jobs at the same time, one could set {dargs:argument}`group_size <resources/group_size>` to `0` (means infinity) to generate only one job with multiple tasks.

## Slurm

{dargs:argument}`batch_type <resources/batch_type>`: `Slurm`, `SlurmJobArray`

[Slurm](https://slurm.schedmd.com/) is a job scheduling system used by lots of HPCs.
One needs to make sure slurm has been setup in the remote server and the related environment is activated.

When `SlurmJobArray` is used, dpdispatcher submits Slurm jobs with [job arrays](https://slurm.schedmd.com/job_array.html).
In this way, a dpdispatcher {class}`task <dpdispatcher.submission.Task>` maps to a Slurm job and a dpdispatcher {class}`job <dpdispatcher.submission.Job>` maps to a Slurm job array.
Millions of Slurm jobs can be submitted quickly and Slurm can execute all Slurm jobs at the same time.
One can use {dargs:argument}`group_size <resources/group_size>` to control how many Slurm jobs are contained in a Slurm job array.

## OpenPBS or PBSPro

{dargs:argument}`batch_type <resources/batch_type>`: `PBS`

[OpenPBS](https://www.openpbs.org/) is an open-source job scheduling of the Linux Foundation and [PBS Profession](https://www.altair.com/pbs-professional/) is its commercial solution.
One needs to make sure OpenPBS has been setup in the remote server and the related environment is activated.

Note that do not use `PBS` for Torque.

## TORQUE

{dargs:argument}`batch_type <resources/batch_type>`: `Torque`

The [Terascale Open-source Resource and QUEue Manager (TORQUE)](https://adaptivecomputing.com/cherry-services/torque-resource-manager/) is a distributed resource manager based on standard OpenPBS.
However, not all OpenPBS flags are still supported in TORQUE.
One needs to make sure TORQUE has been setup in the remote server and the related environment is activated.

## LSF

{dargs:argument}`batch_type <resources/batch_type>`: `LSF`

[IBM Spectrum LSF Suites](https://www.ibm.com/products/hpc-workload-management) is a comprehensive workload management solution used by HPCs.
One needs to make sure LSF has been setup in the remote server and the related environment is activated.

## Bohrium

{dargs:argument}`batch_type <resources/batch_type>`: `Bohrium`

Bohrium is the cloud platform for scientific computing.
Read Bohrium documentation for details.

## DistributedShell

{dargs:argument}`batch_type <resources/batch_type>`: `DistributedShell`

`DistributedShell` is used to submit yarn jobs.
Read [Support DPDispatcher on Yarn](dpdispatcher_on_yarn.md) for details.
