---
name: dpdisp-submit
description: Use this skill when a user asks the agent to run shell commands on local or remote HPC systems and needs the agent to prepare, submit, and monitor the workflow.
compatibility: Requires uv and access to the internet.
license: LGPL-3.0-or-later
metadata:
  author: deepmodeling
  version: "1.0"
---

# dpdisp-submit

## Agent responsibilities

1. Collect enough information from the user in plain language.
2. Generate `submission.json` yourself (do **not** ask the user to hand-write it).
3. Validate `submission.json` with `dargs`.
4. Submit with `uvx --from dpdispatcher dpdisp submit submission.json`.
5. For long-running work, delegate execution to a sub-agent/worker when available and report progress.

## Ask the user in plain language

If information is missing, ask questions users can understand, for example:

- Where should this run: your local machine or a remote HPC cluster?
- What shell command should be executed?
- How many CPUs/GPUs/nodes do you need?
- Which queue/partition/account should we use (if applicable)?
- Which input files should be uploaded, and which output files should be collected?

## Generate `submission.json` from user input

Translate user answers into:

- `machine` (where/how to run),
- `resources` (compute resources),
- `task_list` (which shell commands/files to run).

## Required commands

```bash
# Print full submission schema
uvx --with dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args

# Validate generated submission.json
uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json

# Submit
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
      "task_work_path": "task1/",
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
uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json
uvx --from dpdispatcher dpdisp submit submission.json
```

## What to report back to the user

- A short summary of what the user asked for (where to run, command, resources).
- Submission status (started/running/finished/failed).
- Output locations (for example `task1/log` and `task1/err`).
