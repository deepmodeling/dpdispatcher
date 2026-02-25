Agent skill-style workflow for `dpdisp submit`
=============================================

This page provides a copy-paste workflow suitable for agent automation around
`dpdisp submit`.

Quick checks
------------

Run these first to confirm command availability:

.. code-block:: bash

   uvx --from=dpdispatcher dpdisp --help
   uvx --from=dpdispatcher dpdisp submit --help
   uvx --from=dpdispatcher dargs --help

Generate full submission parameter docs
---------------------------------------

To print the full submission schema (including nested ``machine``/``resources``/``task_list``):

.. code-block:: bash

   uvx --from=dpdispatcher dargs doc dpdispatcher.entrypoints.submit.submission_args

Validate a submission JSON against the same schema
--------------------------------------------------

Use ``dargs check`` with the same argument factory:

.. code-block:: bash

   uvx --from=dpdispatcher dargs check -f dpdispatcher.entrypoints.submit.submission_args examples/submit_example.json

Submission flow
---------------

1. Prepare ``submission.json`` (or start from ``examples/submit_example.json``).
2. Optionally validate with ``dargs check`` as shown above.
3. Submit:

.. code-block:: bash

   uvx --from=dpdispatcher dpdisp submit submission.json

Useful flags
------------

- ``--dry-run``: upload/prepare only, do not submit.
- ``--exit-on-submit``: return immediately after submit.
- ``--allow-ref``: allow loading external JSON/YAML snippets via ``$ref``.
