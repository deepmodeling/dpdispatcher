# Agent Skills Installation and Usage

This page is for users and agent maintainers.
It describes how to install and use agent skills in this repository.

## What is an agent skill?

An agent skill is a directory under `skills/` that contains a `SKILL.md` file.
The `SKILL.md` file contains machine-readable metadata and instructions for agents.

## Repository skills

- `dpdisp-submit`: help agents generate HPC scheduler job input scripts,
  submit jobs to local/remote HPC systems, and monitor them until completion.

## Installation options

### Option A: workspace skills (recommended for OpenClaw)

Put the skill folder into your OpenClaw workspace:

- `<workspace>/skills/<skill-name>/SKILL.md`

Example:

- `~/.openclaw/workspace/skills/dpdisp-submit/SKILL.md`

Then start a new session (or restart gateway) so skills are re-indexed.

### Option B: shared managed skills

For multi-agent/shared environments, place skills under:

- `~/.openclaw/skills/<skill-name>/SKILL.md`

## Install directly from this repository (no copy-paste)

If your workspace is this repository root:

```bash
mkdir -p ~/.openclaw/workspace/skills
ln -sfn "$(pwd)/skills/dpdisp-submit" ~/.openclaw/workspace/skills/dpdisp-submit
```

This keeps the skill linked to repository updates.

## Agent-side installation instructions

If an agent is asked to install skills, it should:

1. create `<workspace>/skills/<skill-name>/`,
1. write or link `SKILL.md` from this repository,
1. refresh/restart session so skills are reloaded.

## Minimal verification

After installation, ask the agent to run:

```bash
uvx --from dpdispatcher dpdisp --help
uvx --with dpdispatcher dargs --help
```

If both commands work, runtime dependencies are available.
