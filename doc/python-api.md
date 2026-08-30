# Python API guide

Most Python integrations use four objects imported directly from
`dpdispatcher`:

| Object                            | Responsibility                                                                            |
| --------------------------------- | ----------------------------------------------------------------------------------------- |
| {class}`~dpdispatcher.Machine`    | Selects a batch backend and an execution context.                                         |
| {class}`~dpdispatcher.Resources`  | Describes the resources and grouping strategy for each generated job.                     |
| {class}`~dpdispatcher.Task`       | Describes one command, its working directory, and the files to transfer.                  |
| {class}`~dpdispatcher.Submission` | Groups tasks, generates jobs, transfers files, monitors execution, and downloads results. |

{class}`~dpdispatcher.Job` is also public because it is useful for inspection and
recovery, but applications normally let
{meth}`Submission.generate_jobs <dpdispatcher.Submission.generate_jobs>` create
jobs from tasks.

## Minimal local submission

The following example runs a shell task in the current directory without an HPC
scheduler or file transfer:

```python
from pathlib import Path

from dpdispatcher import Machine, Resources, Submission, Task

work_root = Path.cwd()
machine = Machine.load_from_dict(
    {
        "batch_type": "Shell",
        "context_type": "LazyLocalContext",
        "local_root": str(work_root),
    }
)
resources = Resources(
    number_node=1,
    cpu_per_node=1,
    gpu_per_node=0,
    queue_name="",
    group_size=1,
)
task = Task(
    command="printf 'done\\n' > result.txt",
    task_work_path=".",
    backward_files=["result.txt"],
    outlog="task.out",
    errlog="task.err",
)

submission = Submission(
    work_base=".",
    machine=machine,
    resources=resources,
    task_list=[task],
)
submission.run_submission(check_interval=1, clean=False)
```

Use `clean=False` while debugging so the execution directory and generated
scripts remain available for inspection. For remote contexts, the default
`clean=True` removes the submission-specific remote directory after declared
outputs have been downloaded.

## Paths and file staging

DPDispatcher resolves paths in layers:

1. `machine.local_root` identifies the local project root.
1. `submission.work_base` identifies the submission directory below that root.
1. `task.task_work_path` identifies a task directory below `work_base`.
1. `forward_files` and `backward_files` are resolved below the task directory.

Files shared by every task belong in `forward_common_files` or
`backward_common_files` on the submission. Keep task working paths relative;
absolute task paths bypass the staging model and are not supported.

{class}`~dpdispatcher.contexts.lazy_local_context.LazyLocalContext` runs in the
existing local directory. {class}`~dpdispatcher.contexts.local_context.LocalContext`
stages work into another directory on the same host. Remote contexts such as
{class}`~dpdispatcher.contexts.ssh_context.SSHContext` stage files to a
submission-specific directory below `machine.remote_root`.

## Task grouping and parallelism

`Resources.group_size` and `Resources.para_deg` control different layers:

- `group_size` is the maximum number of tasks packed into one scheduler job.
  A value of `0` places all tasks in one generated job.
- `para_deg` controls how many tasks inside that generated job run concurrently.

Start with both values set to `1`. Increase `group_size` to reduce scheduler
overhead, and increase `para_deg` only when the allocated CPUs or GPUs can run
multiple task commands safely.

## Loading configuration

The core objects accept dictionaries directly and provide JSON/YAML loaders:

```python
machine = Machine.load_from_json("machine.json")
resources = Resources.load_from_yaml("resources.yaml")
task = Task.load_from_dict(task_config)
```

All loaders normalize and validate configuration with `dargs`. External `$ref`
resolution is disabled by default because it reads additional local files. Pass
`allow_ref=True` only for trusted configuration:

```python
task = Task.load_from_json("task.json", allow_ref=True)
machine = Machine.load_from_dict(machine_config, allow_ref=True)
resources = Resources.load_from_dict(resources_config, allow_ref=True)
```

:::{note}
The `Machine` and `Resources` JSON/YAML convenience loaders currently load one
file directly and do not expose `allow_ref`. Read trusted files into a mapping
and use {meth}`Machine.load_from_dict <dpdispatcher.Machine.load_from_dict>` or
{meth}`Resources.load_from_dict <dpdispatcher.Resources.load_from_dict>` when
`$ref` resolution is required.
:::

## Submission lifecycle

{meth}`Submission.run_submission <dpdispatcher.Submission.run_submission>`
performs the complete lifecycle:

1. Generate deterministic groups of jobs from the registered tasks.
1. Recover compatible scheduler state from a previous run when available.
1. Upload task files and generated scripts.
1. Submit or resubmit jobs and poll their normalized status.
1. Download declared results.
1. Save recovery state and, by default, clean the execution directory.

Important keyword arguments are:

- `dry_run=True`: stage inputs and scripts without submitting jobs.
- `exit_on_submit=True`: submit jobs and return without polling for completion.
- `clean=False`: retain the execution directory after downloading results.
- `check_interval=N`: poll scheduler status every `N` seconds.

For concurrent submissions, use
{meth}`Submission.async_run_submission <dpdispatcher.Submission.async_run_submission>`.
The asynchronous wrapper runs the blocking lifecycle in an executor and defaults
to `clean=False`, which avoids one submission removing files another operation
may still need.

## Extending DPDispatcher

A new scheduler subclasses {class}`~dpdispatcher.Machine` and implements the
scheduler-specific submission, status, script-header, and finish-tag methods. A
new execution environment subclasses
{class}`~dpdispatcher.base_context.BaseContext` and implements transfer,
cleanup, file access, and command execution. Subclasses register automatically
under their class name and aliases when imported.

The generated {doc}`api/api` pages contain the complete module and method
reference.
