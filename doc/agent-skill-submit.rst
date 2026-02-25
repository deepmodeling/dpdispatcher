Agent skill-style workflow for `dpdisp submit`
=============================================

This page explains how an agent (for example OpenClaw) should install/use the
`dpdisp-submit` skill and execute DPDispatcher submission safely.

Scope
-----

Use this workflow when users ask an agent to submit DPDispatcher tasks from JSON.

User communication before execution
-----------------------------------

Before submission, the agent should explicitly confirm required configuration
with the user. If anything is missing, ask first.

Required items:

- machine/context: ``context_type``, ``batch_type``, local/remote roots,
  connection profile;
- resources: queue/partition/account, nodes/CPU/GPU and scheduler kwargs;
- task command and expected runtime behavior;
- forward/backward files and work paths.

Command checks
--------------

.. code-block:: bash

   uvx --from dpdispatcher dpdisp --help
   uvx --from dpdispatcher dpdisp submit --help
   uvx --with dpdispatcher dargs --help

Generate full submission parameter docs
---------------------------------------

Use submission-level args to print the full schema
(including nested ``machine``/``resources``/``task_list``):

.. code-block:: bash

   uvx --with dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args

Validate submission JSON
------------------------

.. code-block:: bash

   uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args submission.json

Example file:

.. code-block:: bash

   uvx --with dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args examples/submit_example.json

Submit
------

.. code-block:: bash

   uvx --from dpdispatcher dpdisp submit submission.json

Useful flags
------------

- ``--dry-run``: upload/prepare only, do not submit.
- ``--exit-on-submit``: return immediately after submit.
- ``--allow-ref``: allow loading external JSON/YAML snippets via ``$ref``.

Sub-agent recommendation for long runs
--------------------------------------

For long-running submissions, the main agent should delegate execution to a
sub-agent when available (for OpenClaw, typically via ``sessions_spawn``),
then report progress and final status back to the user.
