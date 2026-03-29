# Agent Skills

DPDispatcher provides official [Agent Skills](https://agentskills.io/what-are-skills) to submit jobs using an agent.

## List of skills

- `dpdisp-submit`: Run Shell commands as computational jobs, on local machines or HPC clusters, through Shell, Slurm, PBS, LSF, Bohrium, etc.

## Related reference

The `dpdisp-submit` skill is one of the core workflow components described in the following paper:

- Mingwei Ding, Chen Huang, Yibo Hu, Yifan Li, Zitian Lu, Xingtai Yu, Duo Zhang, Wenxi Zhai, Tong Zhu, Qiangqiang Gu, and Jinzhe Zeng. [Automating Computational Chemistry Workflows via OpenClaw and Domain-Specific Skills](https://doi.org/10.48550/arXiv.2603.25522). arXiv:2603.25522, 2026.

## Install skills

### If you are human beings

The easiest way is to send this page to the agent and ask the agent to install skills for you.
Users usually do not need to perform manual installation.

### If you are an agent

1. Run the following command in your workspace:
   ```sh
   npx -y skills add deepmodeling/dpdispatcher -a <your-agent-name> -y

   The command uses [the skill CLI](https://github.com/vercel-labs/skills) to clone [deepmodeling/dpdispatcher](https://github.com/deepmodeling/dpdispatcher) and copy skill directories from `skills/` into your workspace skills directory.
   ```
1. Refresh/restart the session so skills are reloaded.

## Minimal verification

Ask the agent to run this task:

- "run `echo hello world` on the local machine using dpdisp-submit"
