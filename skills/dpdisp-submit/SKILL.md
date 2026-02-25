---
name: dpdisp-submit
description: Agent workflow for DPDispatcher to generate HPC scheduler job input scripts, submit jobs to local/remote HPC systems, and monitor (poke) them until completion using `dpdisp submit` plus `dargs` validation.
license: LGPL-3.0-or-later
metadata:
  author: deepmodeling
  version: "1.4"
---

# dpdisp-submit (agent instructions)

Use this skill when the user asks the agent to run DPDispatcher submissions on local or remote HPC systems.

## What you must do

1. Confirm required configuration with the user before execution.
2. Validate the provided `submission.json` against the DPDispatcher submission schema.
3. Submit with `dpdisp submit`.
4. For long-running work, use a sub-agent/worker when your framework supports it and report progress.

## Required configuration to confirm with the user

If any item below is missing or ambiguous, ask before submitting.

- `machine`: `context_type`, `batch_type`, `local_root`, and remote fields when needed.
- `resources`: queue/partition/account, node/CPU/GPU sizing, scheduler kwargs.
- `task_list`: commands, `task_work_path`, forward/backward file lists.

## Command sequence

```bash
# 1) sanity
uvx --from dpdispatcher dpdisp --help
uvx --from dpdispatcher dpdisp submit --help
uvx --with dpdispatcher dargs --help

# 2) print full submission schema
uvx --with dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args

# 3) validate user-provided input (must exist)
uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json

# 4) submit
uvx --from dpdispatcher dpdisp submit submission.json
```

Useful flags for submit:

- `--dry-run`
- `--exit-on-submit`
- `--allow-ref`

## Example run (self-contained)

This example does not assume files outside the current workspace.

```bash
cat > submission.json <<'JSON'
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
      "command": "echo hello",
      "task_work_path": "task1/",
      "forward_files": [],
      "backward_files": [],
      "outlog": "log",
      "errlog": "err"
    }
  ]
}
JSON

uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json
uvx --from dpdispatcher dpdisp submit submission.json
```

## Agent output expectations

Report back to user with:

- confirmed config summary,
- submission status,
- output/log locations.
