# Agent Skills Installation and Usage

This page is for users and agent maintainers.
It explains how to install skills from this repository.

For a quick introduction to skills, see:

- https://agentskills.io/what-are-skills

## What is an agent skill?

An agent skill is a directory under `skills/` containing a `SKILL.md` file.
`SKILL.md` provides machine-readable metadata and instructions for agents.

## Repository skills

- `dpdisp-submit`: enables agents to generate HPC scheduler systems jobs input scripts,
  submit them to local/remote HPC systems, and monitor until completion.

## Recommended way: ask your agent to install skills

The easiest way is to ask the agent to install skills for you.
Users usually do not need to perform manual installation.

Tell the agent to:

1. clone `deepmodeling/dpdispatcher`,
2. copy required skill directories from `skills/` into your OpenClaw workspace skills directory,
3. refresh/restart session so skills are reloaded.

## Manual installation (if needed)

OpenClaw skill locations:

- per-workspace: `<workspace>/skills/<skill-name>/SKILL.md`
- shared (multi-agent): `~/.openclaw/skills/<skill-name>/SKILL.md`

If your current directory is this repository root:

```bash
mkdir -p ~/.openclaw/workspace/skills
cp -r ./skills/dpdisp-submit ~/.openclaw/workspace/skills/
```

Then start a new session (or restart gateway) so skills are re-indexed.

## Minimal verification

Ask the agent to run this task:

- "run `echo hello world` on the local machine using dpdisp-submit"

Optional command-level checks:

```bash
uvx --from dpdispatcher dpdisp --help
uvx --with dpdispatcher dargs --help
```
