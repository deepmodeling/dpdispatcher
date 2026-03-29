# Submit from JSON file

DPDispatcher can submit a submission from a JSON file:

```sh
dpdisp submit submission.json
```

## Quickstart: smallest working local example

For a one-task local shell run, the most stable starter layout is:

- `machine.context_type = "LazyLocalContext"`
- `machine.batch_type = "Shell"`
- `machine.local_root = "./"`
- `work_base = "."`
- `task.task_work_path = "."`
- `resources.group_size = 1`
- `resources.para_deg = 1`

This avoids the common confusion of creating a task subdirectory that does not actually exist yet.

```{literalinclude} ../examples/submit_example.json
---
language: json
linenos:
---
```

## Path layout mental model

In the most common setup, one task lives at:

```text
machine.local_root / work_base / task.task_work_path
```

Practical rules:

- put files shared by all tasks in `forward_common_files` / `backward_common_files`
- put files specific to one task in `forward_files` / `backward_files`
- if you only want to run a command in the current working directory, prefer `task_work_path = "."`

## Grouping vs parallelism

Two fields are commonly confused:

- `resources.group_size`: how many tasks are packed into one generated job
- `resources.para_deg`: how many tasks inside that job run in parallel

For the safest minimal workflow, use both as `1`.

## Validation workflow

Before real submission, the recommended order is:

```bash
# Syntax check JSON
uv run -m json.tool submission.json >/dev/null

# Inspect schema / arginfo
uvx --with dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args

# Validate submission.json against the schema
uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json

# Submit
uvx --from dpdispatcher dpdisp submit submission.json
```

The JSON file must contain the submission configuration.
The JSON entries for submission are defined as follows:

```{eval-rst}
.. dargs::
   :module: dpdispatcher.entrypoints.submit
   :func: submission_args
```

## Options

- `--dry-run`: Only upload files without submitting.
- `--exit-on-submit`: Exit after submitting without waiting for completion.
- `--allow-ref`: Allow loading external JSON/YAML snippets through `$ref` (disabled by default for security).
