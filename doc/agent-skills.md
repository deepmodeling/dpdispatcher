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

## If you are an agent: install skills from this repository

1. Clone `deepmodeling/dpdispatcher`.
2. Copy required skill directories from `skills/` into the target OpenClaw workspace skills directory.
3. Refresh/restart session so skills are reloaded.

## Minimal verification

Ask the agent to run this task:

- "run `echo hello world` on the local machine using dpdisp-submit"
