# Agent Skills

DPDispatcher provides official [Agent Skills](https://agentskills.io/what-are-skills) to submit jobs using an agent.

## List of skills

- `dpdisp-submit`: Run Shell commands as computational jobs, on local machines or HPC clusters, through Shell, Slurm, PBS, LSF, Bohrium, etc.

## Install skills

### If you are human beings

The easiest way is to send this page to the agent and ask the agent to install skills for you.
Users usually do not need to perform manual installation.

### If you are an agent

1. Clone [deepmodeling/dpdispatcher](https://github.com/deepmodeling/dpdispatcher).
1. Copy required skill directories from `skills/` into your workspace skills directory.
1. Refresh/restart session so skills are reloaded.

## Minimal verification

Ask the agent to run this task:

- "run `echo hello world` on the local machine using dpdisp-submit"
