---
name: dpdisp-submit
description: >
    Run Shell commands as computational jobs, on local machines or HPC clusters, through Shell, Slurm, PBS, LSF, Bohrium, etc. 
    USE WHEN the user needs to submit batch jobs to a cluster, run commands on a remote server, execute tasks via job schedulers (Slurm, PBS, LSF), or safely run long-term/background shell commands that require state tracking and auto-recovery.
compatibility: Requires uv and access to the internet.
license: LGPL-3.0-or-later
metadata:
  author: deepmodeling
  version: '1.0'
---

# dpdisp-submit

This skill uses the DPDispatcher tool to run Shell commands as computational jobs, on local machines or HPC clusters, through Shell, Slurm, PBS, LSF, Bohrium, etc.

## Agent responsibilities

1. Collect enough information from the user in plain language.
2. Generate the submission JSON file based on collected user input. 
3. Validate `submission.json` before submission.
4. Submit with `uvx --from dpdispatcher dpdisp submit submission.json`.
5. Automatically manage job interruptions and retries by relying on built-in state tracking (see the "Resuming Jobs" section for details).
6. **CRITICAL SECURITY CONSTRAINT: DO NOT attempt direct SSH connections.** Never attempt to connect to the remote HPC directly using `ssh`, write custom Paramiko/Fabric Python scripts, or manually execute remote commands. Just generate the `submission.json` and use the `dpdisp submit` tool. DPDispatcher will handle all remote connections, file transfers, and job management safely.

## Autonomous Information Gathering & User Prompts

Before this step, always execute `uvx --with dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args` to learn what information needs to be filled.

If information is missing, ask questions users can understand, for example:

- Where should this run: your local machine or a remote HPC cluster?
- What shell command should be executed?
- How many CPUs/GPUs/nodes do you need?
- Which queue/partition/account should we use (if applicable)?
- Which input files should be uploaded, and which output files should be collected?

## Generate `submission.json` from user input

According the result of `uvx --with dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args`, translate user answers into:

- `machine` (where/how to run),
- `resources` (compute resources),
- `task_list` (which shell commands/files to run).

If the user indicates that a specific value (like a username, token, or remote path) should be read from a local environment variable, format that value in the JSON template as `${ENV_VAR_NAME}`.
*Example:* `"remote_root": "${MY_HPC_WORKSPACE}"`

### Handling Environment Variables
If the user specifies values that must be loaded from local environment variables (e.g., sensitive tokens, dynamic paths), do **not** write them directly into the final JSON. Instead:
1. Generate a `submission.template.json` file using the `${VAR_NAME}` syntax. 
   *Example:* `"remote_root": "${MY_HPC_WORKSPACE}"`
2. Use `envsubst` to inject the variables and create the final file:
   `envsubst < submission.template.json > submission.json`
3. **CRITICAL SECURITY CONSTRAINT: DO NOT read or print the contents of the newly generated `submission.json` file.** Once `envsubst` replaces the variables, the file contains raw sensitive data. Reading it will leak these secrets into your context, which is strictly prohibited.

If no environment variables are needed, simply generate `submission.json` directly.

### Simple local shell tasks

When the user asks for a simple local shell task, prefer these defaults to avoid common failures:

- `machine.context_type = "LazyLocalContext"`
- `machine.batch_type = "Shell"`
- `task_list[0].task_work_path = "."` (avoid non-existing subdirectory failures)
- `resources.group_size = 1`

## Required commands

```bash
# 1) Print full submission schema
uvx --with dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args

# 2) [Optional] Substitute environment variables if a template was generated
envsubst < submission.template.json > submission.json

# 3) Syntax check JSON
uv run -m json.tool submission.json >/dev/null

# 4) Validate generated submission.json
uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json

# 5) Submit
uvx --from dpdispatcher dpdisp submit submission.json
```
### Best Practices for Long-Running Jobs

When executing tasks that are expected to take a long time, it is crucial to prevent the monitoring process from dying due to SSH timeouts or closed terminals. Ensure the DPDispatcher daemon safely runs in the background using one of the following methods:

- **Wrap in `tmux`:** Run the `dpdisp submit` command inside a `tmux` session. This keeps the execution alive and allows you to detach/reattach safely even if your network connection drops.
- **Use the `--exit-on-submit` flag:** Add this flag to your submit command. It exits immediately after successfully pushing the job to the scheduling system (e.g., Slurm) without holding the terminal to wait for job completion. 

### Some Useful Flags
- `--dry-run`: Parses the configuration, generates local directories, and validates the schema, but does **not** actually submit the job to the machine or cluster. Useful for a final safety check before real execution.
- `--allow-ref`: Allows nesting and referencing other JSON files using `{"$ref": "other.json"}` for reusable config snippets. The contents of the referenced file are loaded first, and then the current file's fields override or append to those loaded values.

## Definition of Job Completion
A job is considered **fully completed** ONLY when both of the following are true:
1. **Command Success:** The `dpdisp submit` command naturally finishes executing with a success exit code (`0`).
2. **Files Retrieved:** The tasks have finished computing on the backend, **AND** all corresponding output files (e.g., `log`, `err`, and result files) have been successfully downloaded back to the local `task_work_path`. *(Note: Just finishing on the cluster queue is not enough).*

## Resuming Jobs (Failure Handling & Recovery)

DPDispatcher is inherently idempotent and features built-in state tracking. It will automatically resume unfinished tasks without duplicating completed ones.

**When to trigger recovery:**
- A job fails, times out, or gets unexpectedly interrupted.
- The user explicitly asks to "resume", "retry", or "recover" a previously interrupted or failed job.
- The Agent's SSH or network connection drops during job monitoring.

**Action:** Do **NOT** modify `submission.json` or attempt to clean up the remote directories. Simply re-execute the exact same submission command (`uvx --from dpdispatcher dpdisp submit submission.json`) in the same directory. The tool will safely skip successful tasks and only resubmit or resume the pending/failed ones.

## Example 

User request:
- "Please run `run_simulation.sh` on my Slurm cluster. Load my username from `$HPC_USER` and the workspace path from `$HPC_WORKDIR`. We already have a `resource_defaults.json` for the base compute settings, please use it and just add the debug queue."

Assume `resource_defaults.json` already exists in the directory.
Agent-generated `submission.template.json`:
```json
{
  "work_base": ".",
  "machine": {
    "batch_type": "Slurm",
    "context_type": "SSHContext",
    "remote_profile": {
      "hostname": "login.cluster.edu",
      "username": "${HPC_USER}",
      "port": 22
    },
    "remote_root": "${HPC_WORKDIR}/dpdisp_run"
  },
  "resources": {
    "$ref": "resource_defaults.json",
    "queue_name": "debug",
    "group_size": 1
  },
  "task_list": [
    {
      "command": "bash run_simulation.sh",
      "task_work_path": "task_000",
      "forward_files": [
        "run_simulation.sh",
        "input.dat"
      ],
      "backward_files": [
        "result.out"
      ]
    }
  ]
}
```

Then run:

```bash
envsubst < submission.template.json > submission.json
uv run -m json.tool submission.json >/dev/null
uvx --with dpdispatcher dargs check --allow-ref -f dpdispatcher.entrypoints.submit.submission_args submission.json
tmux new-session -d -s dpdisp_job "uvx --from dpdispatcher dpdisp submit --allow-ref submission.json"
tmux ls
```

## What to report back to the user

- A short summary of what the user asked for (where to run, command, resources).
- Submission status (started/running/finished/failed).
- Output locations (for example `log` and `err` when `task_work_path` is `.`).
- If the job encounters an interruption or partial failure, provide the user with detailed information about this issue and offer to simply re-run the command to resume the unfinished tasks.
