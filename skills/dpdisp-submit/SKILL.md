---
name: dpdisp-submit
description: Run DPDispatcher submission workflows in agents. Use when you need to confirm user configs, print submission schema docs, validate submission JSON, and submit jobs via `dpdisp submit`.
license: LGPL-3.0-or-later
metadata:
  author: deepmodeling
  version: "1.2"
---

# dpdisp submit workflow (agent-friendly)

This skill is for AI agents (for example OpenClaw) that submit DPDispatcher jobs.

## 0) First communicate required config with user

Before submitting, confirm these are explicitly provided. If any item is missing, ask first.

- **Machine / context**: `context_type`, `batch_type`, local/remote root, remote profile.
- **Resources**: queue/partition/account, nodes/CPU/GPU, scheduler kwargs.
- **Task command**: executable command and expected runtime behavior.
- **Files**: forward/backward files and work paths.

## 1) Quick checks

```bash
uvx --from dpdispatcher dpdisp --help
uvx --from dpdispatcher dpdisp submit --help
uvx --with dpdispatcher dargs --help
```

## 2) Print full submission argument docs

Print the full submission schema (including nested `machine`, `resources`, `task_list`):

```bash
uvx --with dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args
```

## 3) Validate `submission.json` using the same schema

```bash
uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json
```

(Example file)

```bash
uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args examples/submit_example.json
```

## 4) Submit

```bash
uvx --from dpdispatcher dpdisp submit submission.json
```

Useful flags:

- `--dry-run`: upload/prepare only, do not submit.
- `--exit-on-submit`: return immediately after submission.
- `--allow-ref`: allow `$ref` loading from external JSON/YAML snippets.

## 5) Long/slow workflows: use a sub-agent

If your agent framework supports sub-agents (e.g., OpenClaw `sessions_spawn`), prefer running the DPDispatcher execution as a sub-agent task. The main agent should:

1. collect/confirm config from user,
2. delegate long-running execution to a sub-agent,
3. report progress and final results back to user.
