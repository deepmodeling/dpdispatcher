Install the `dpdisp-submit` agent skill
=======================================

This page is for users. It explains how to install the `dpdisp-submit` skill
so your agent can use DPDispatcher submission workflows.

What this skill adds
--------------------

After installation, the agent can:

- validate ``submission.json`` with ``dargs``;
- submit jobs with ``dpdisp submit``;
- handle local or remote DPDispatcher configurations.

Install for OpenClaw (recommended)
----------------------------------

Option A: install into workspace skills

1. Put this folder in your OpenClaw workspace:

   ``<workspace>/skills/dpdisp-submit/SKILL.md``

   Example workspace path:

   ``~/.openclaw/workspace/skills/dpdisp-submit/SKILL.md``

2. Start a new agent session (or restart gateway) so skills are re-indexed.

Option B: install with ClawHub (when published)

.. code-block:: bash

   clawhub install dpdisp-submit

By default, ClawHub installs to ``./skills`` (or your configured workspace),
which OpenClaw loads as ``<workspace>/skills``.

Agent-side install instruction
------------------------------

If you want another agent to install it for you, ask it to do exactly this:

1. create ``<workspace>/skills/dpdisp-submit/``;
2. write ``SKILL.md`` into that folder;
3. refresh/restart session so OpenClaw reloads skills.

Minimal verification
--------------------

In a new session, ask the agent to use ``dpdisp-submit`` and run:

- ``uvx --from dpdispatcher dpdisp --help``
- ``uvx --with dpdispatcher dargs --help``

If both run, the skill and runtime dependencies are ready.
