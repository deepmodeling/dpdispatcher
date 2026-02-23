# Submit from JSON file

DPDispatcher can submit a submission from a JSON file:

```sh
dpdisp submit submission.json
```

The JSON file must contain the submission configuration. An example of the JSON file is shown below.

```{literalinclude} ../examples/submit_example.json
:language: json
:linenos:
```

The JSON entries for submission are defined as follows:

```{eval-rst}
.. dargs::
   :module: dpdispatcher.entrypoints.submit
   :func: submission_args
```

## Options

- `--dry-run`: Only upload files without submitting.
- `--exit-on-submit`: Exit after submitting without waiting for completion.
