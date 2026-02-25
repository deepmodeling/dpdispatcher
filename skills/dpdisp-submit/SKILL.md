---
name: dpdisp-submit
description: Submit DPDispatcher jobs from a unified submission schema. Use when you need to print the full submission argument docs, validate submission JSON, and run `dpdisp submit` in agent workflows.
license: LGPL-3.0-or-later
metadata:
  author: deepmodeling
  version: '1.1'
---

# dpdisp submit workflow

Use this skill for a compact, agent-friendly `submission.json` flow.

## 1) Quick checks

```bash
uvx --from dpdispatcher dpdisp --help
uvx --from dpdispatcher dpdisp submit --help
uvx --from dpdispatcher dargs --help
```

## 2) Print full submission argument docs

Use the submission-level arg function to print the entire schema (including nested `machine`, `resources`, and `task_list`):

```bash
uvx --from dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args
```

## 3) Validate a submission JSON with the same schema

```bash
uvx --from dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args examples/submit_example.json
```

## 4) Submit

```bash
uvx --from dpdispatcher dpdisp submit submission.json
```

Useful flags:

- `--dry-run`: upload/prepare only, do not submit.
- `--exit-on-submit`: return immediately after submission.
- `--allow-ref`: allow `$ref` loading from external JSON/YAML snippets.
