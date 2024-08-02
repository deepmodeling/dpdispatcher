# Environment variables

When launching a job, dpdispatcher sets the following environment variables according to the resources, in addition to user-defined environment variables:

:::{envvar} DPDISPATCHER_NUMBER_NODE

The number of nodes required for each job.

:::

:::{envvar} DPDISPATCHER_CPU_PER_NODE

CPU numbers of each node assigned to each job.

:::

:::{envvar} DPDISPATCHER_GPU_PER_NODE

GPU numbers of each node assigned to each job.

:::

:::{envvar} DPDISPATCHER_QUEUE_NAME

The queue name of batch job scheduler system.

:::

:::{envvar} DPDISPATCHER_GROUP_SIZE

The number of tasks in a job. 0 means infinity.

:::

These environment variables can be used in the {dargs:argument}`command <task/command>`, for example, `mpirun -n ${DPDISPATCHER_CPU_PER_NODE} xx.run`.
