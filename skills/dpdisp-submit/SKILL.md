---
name: dpdisp-submit
description: Use when a user asks the agent to run shell commands on local or remote HPC systems via `dpdisp submit`.
compatibility: Requires uv and access to the internet.
license: LGPL-3.0-or-later
metadata:
  author: deepmodeling
  version: '1.0'
---

# dpdisp-submit

## Agent responsibilities

1. Collect enough information from the user in plain language.
2. Generate `submission.json` yourself (do **not** ask the user to hand-write it).
3. Validate `submission.json` before submission.
4. Submit with `uvx --from dpdispatcher dpdisp submit submission.json`.
5. For long-running work, delegate execution to a sub-agent/worker when available and report progress.

## Ask the user in plain language

If information is missing, ask questions users can understand, for example:

- Where should this run: your local machine or a remote HPC cluster?
- What shell command should be executed?
- How many CPUs/GPUs/nodes do you need?
- Which queue/partition/account should we use (if applicable)?
- Which input files should be uploaded, and which output files should be collected?

## One-shot success defaults (recommended)

When the user asks for a simple local shell task, prefer these defaults to avoid common failures:

- `machine.context_type = "LazyLocalContext"`
- `machine.batch_type = "Shell"`
- `task_list[0].task_work_path = "."` (avoid non-existing subdirectory failures)
- `resources.group_size = 1`

## Generate `submission.json` from user input

Translate user answers into:

- `machine` (where/how to run),
- `resources` (compute resources),
- `task_list` (which shell commands/files to run).

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
  "work_base": "0_md/",
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
    "group_size": 1
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

## What to report back to the user

- A short summary of what the user asked for (where to run, command, resources).
- Submission status (started/running/finished/failed).
- Output locations (for example `log` and `err` when `task_work_path` is `.`).
