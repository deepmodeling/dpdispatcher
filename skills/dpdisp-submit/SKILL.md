---
name: dpdisp-submit
description: Agent workflow for submitting DPDispatcher jobs on local or remote servers. It validates `submission.json` with dargs, runs `dpdisp submit`, and reports progress/results back to the user.
license: LGPL-3.0-or-later
metadata:
  author: deepmodeling
  version: '1.3'
---

# dpdisp submit (for agents)

Use this skill when an agent needs to execute DPDispatcher tasks (local or remote) from a `submission.json` file.

## Agent responsibilities

1. Confirm required config with the user before execution.
1. Validate `submission.json` against submission schema.
1. Submit with `dpdisp submit`.
1. For long runs, prefer a sub-agent/worker and report progress + final status.

## Required config checklist (ask user if missing)

- **Machine/context**: `context_type`, `batch_type`, `local_root`, `remote_root` (if needed), auth profile.
- **Resources**: queue/partition/account, node/CPU/GPU, scheduler kwargs.
- **Tasks**: commands, `task_work_path`, input/output file lists.

## Commands

```bash
# sanity checks
uvx --from dpdispatcher dpdisp --help
uvx --from dpdispatcher dpdisp submit --help
uvx --with dpdispatcher dargs --help

# print full submission schema
uvx --with dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args

# validate input
uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json

# submit
uvx --from dpdispatcher dpdisp submit submission.json
```

Useful flags:

- `--dry-run`
- `--exit-on-submit`
- `--allow-ref`

## Example (agent execution)

### Input (from user)

- Run `echo hello` on local shell backend.
- Use one task in `task1/`.

### Agent actions

```bash
cp examples/submit_example.json submission.json
uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json
uvx --from dpdispatcher dpdisp submit submission.json
```

### Agent output to user

- Confirmed config (machine/resources/task).
- Submission started/completed.
- Where logs/results are written (e.g., `task1/log`, `task1/err`).
