---
name: dpdisp-submit
description: Submit DPDispatcher jobs from JSON safely using uvx. Use when preparing machine/resources/task configs, checking argument docs with dargs, and running `dpdisp submit` in automation/agent workflows.
license: LGPL-3.0-or-later
metadata:
  author: deepmodeling
  version: "1.0"
---

# dpdisp submit workflow

Use this skill when you want a repeatable, agent-friendly job submission flow for DPDispatcher.

## 1) Quick command sanity checks

```bash
uvx --from=dpdispatcher dpdisp --help
uvx --from=dpdispatcher dpdisp submit --help
uvx --from=dargs dargs --help
```

## 2) Pre-submit checklist

Before submitting `submission.json`, confirm these three parts are correct:

1. **machine**
   - `batch_type`, `context_type`, local/remote paths, remote profile.
   - Start from `examples/machine/*.json` when possible.
2. **resources**
   - Queue/partition, node/cpu/gpu settings, scheduler kwargs, env/source settings.
   - Start from `examples/resources/*.json`.
3. **task** (inside `job_list`)
   - `command`, `task_work_path`, `forward_files`, `backward_files`, logging behavior.
   - Start from `examples/task/*.json`.

## 3) Read full parameter docs with dargs

`dargs` is a separate package. To inspect DPDispatcher arg schemas, include DPDispatcher in the same uvx environment with `--with=dpdispatcher`:

```bash
uvx --from=dargs --with=dpdispatcher dargs doc dpdispatcher.arginfo.machine_dargs
uvx --from=dargs --with=dpdispatcher dargs doc dpdispatcher.arginfo.resources_dargs
uvx --from=dargs --with=dpdispatcher dargs doc dpdispatcher.arginfo.task_dargs
```

> Tip: these are the practical “full parameter docs” commands for machine/resources/task.

## 4) Optional strict JSON checks

```bash
uvx --from=dargs --with=dpdispatcher dargs check -f dpdispatcher.arginfo.machine_dargs examples/machine/lazy_local.json
uvx --from=dargs --with=dpdispatcher dargs check -f dpdispatcher.arginfo.resources_dargs examples/resources/expanse_cpu.json
uvx --from=dargs --with=dpdispatcher dargs check -f dpdispatcher.arginfo.task_dargs examples/task/g16.json
```

## 5) Submit

```bash
uvx --from=dpdispatcher dpdisp submit submission.json
```

Useful flags:

- `--dry-run`: upload/prepare only, do not submit.
- `--exit-on-submit`: return immediately after submission.
- `--allow-ref`: allow `$ref` loading from external JSON/YAML snippets.
