---
name: dpdisp-submit
description: Generate DPDispatcher `submission.json` from user intent, validate it, choose stable defaults for local or SSH+Slurm workflows, submit with `dpdisp submit`, and report status plus log/output paths.
compatibility: Requires uv and access to the internet.
license: LGPL-3.0-or-later
metadata:
  author: deepmodeling
  version: '1.1'
---

# dpdisp-submit

Use this skill for DPDispatcher submit workflows.

## Trigger hints

Use this skill when the request implies any of the following:

- run a shell command on a local machine or HPC cluster;
- generate, validate, or repair `submission.json`;
- submit jobs with `dpdisp submit`;
- explain which DPDispatcher submit parameters to use in practice;
- monitor and report job status, logs, or output paths.

## Core idea

Do not just list parameter names back to the user.
Translate plain-language intent into a **working submission recipe**:

- `machine` = where/how to run
- `resources` = how much resource each generated job requests
- `task_list` = what each task runs and which files move in/out

When there is a simple, safer default, prefer it.

## Agent responsibilities

1. Collect enough information from the user in plain language.
2. Generate `submission.json` yourself (**do not** ask the user to hand-write it).
3. Validate `submission.json` before submission.
4. Submit with `uvx --from dpdispatcher dpdisp submit submission.json`.
5. For long-running work, delegate execution to a sub-agent/worker when available and report progress.
6. When a run fails, help the user reason about whether the problem is JSON validation, path layout, SSH, scheduler state, or the scientific command itself.

## Ask the user in plain language

If information is missing, ask questions users can understand, for example:

- Where should this run: your local machine or a remote HPC cluster?
- What shell command should be executed?
- How many CPUs/GPUs/nodes do you need?
- Which queue/partition/account should we use (if applicable)?
- Which input files should be uploaded, and which output files should be collected?
- For SSH/HPC: what host should we connect to, and what remote working directory should we use?

## Recommended defaults

### Smallest local shell task

When the user asks for a simple local shell task, prefer these defaults to avoid common failures:

- `machine.context_type = "LazyLocalContext"`
- `machine.batch_type = "Shell"`
- `machine.local_root = "./"`
- `work_base = "."`
- `task_list[0].task_work_path = "."` (**preferred**; avoids missing-subdirectory problems)
- `resources.group_size = 1`
- `resources.para_deg = 1`
- `queue_name = ""`

### Common SSH + Slurm pattern

For a standard remote cluster submission, the usual pattern is:

- `machine.context_type = "SSHContext"`
- `machine.batch_type = "Slurm"`
- `machine.local_root = <local project root>`
- `machine.remote_root = <remote working root>`
- `resources.queue_name = <Slurm partition>`
- `resources.group_size = 1` unless the user explicitly wants task packing
- `resources.para_deg = 1` unless the user explicitly wants parallel tasks inside one job

## Parameter guidance that often matters

### Path semantics

Treat the most common local task path as:

`machine.local_root / work_base / task.task_work_path`

Practical rule of thumb:

- shared inputs for all tasks → `forward_common_files`
- shared outputs for all tasks → `backward_common_files`
- per-task inputs → `task.forward_files`
- per-task outputs → `task.backward_files`

### `group_size` vs `para_deg`

Do not confuse these two:

- `group_size`: how many tasks are packed into one generated scheduler job
- `para_deg`: how many tasks inside that job are run in parallel

Safest default:

- `group_size = 1`
- `para_deg = 1`

### `remote_root`

For non-local contexts (for example SSH), `remote_root` is not just “some directory”.
It is the remote working root of the submission, and reusing it may interact with recovery/resume behavior.
If the user materially changes commands, inputs, or task layout, prefer a fresh `remote_root`.

## Required commands

```bash
# 1) Syntax check JSON
uv run -m json.tool submission.json >/dev/null

# 2) Print full submission schema
uvx --with dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args

# 3) Validate generated submission.json
uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json

# 4) Submit
uvx --from dpdispatcher dpdisp submit submission.json
```

Useful flags:

- `--dry-run`
- `--exit-on-submit`
- `--allow-ref`

## Example (agent-generated input)

User request (natural language):

- "Please run `echo hello world` on my local machine."

Agent-generated `submission.json`:

```json
{
  "work_base": ".",
  "machine": {
    "batch_type": "Shell",
    "local_root": "./",
    "context_type": "LazyLocalContext"
  },
  "resources": {
    "number_node": 1,
    "cpu_per_node": 1,
    "gpu_per_node": 0,
    "queue_name": "",
    "group_size": 1,
    "para_deg": 1
  },
  "forward_common_files": [],
  "backward_common_files": [],
  "task_list": [
    {
      "command": "echo hello world",
      "task_work_path": ".",
      "forward_files": [],
      "backward_files": [],
      "outlog": "log",
      "errlog": "err"
    }
  ]
}
```

Then run:

```bash
uv run -m json.tool submission.json >/dev/null
uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json
uvx --from dpdispatcher dpdisp submit submission.json
```

## Failure triage

When submission fails, classify the problem before asking the user to change parameters:

1. **JSON syntax / dargs validation**
   - malformed JSON
   - wrong field type/value
2. **Path/layout problem**
   - `task_work_path` does not exist
   - file paths resolved from the wrong base
3. **Connection problem**
   - SSH/auth/proxy/host key failure
4. **Scheduler problem**
   - queued/pending job, unavailable partition, site throttling
5. **Application problem**
   - the scientific command itself failed after submission succeeded

If useful diagnostics may disappear on failure, recommend writing stdout/stderr/return code to files and listing them in `backward_files`.

## What to report back to the user

- A short summary of what the user asked for (where to run, command, resources).
- Submission status (started/running/finished/failed).
- Output locations (for example `log` and `err` when `task_work_path` is `.`).
- If it failed, whether the likely cause is parameterization, environment, scheduler, or the scientific command itself.
