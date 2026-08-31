# Submit from JSON file

DPDispatcher can submit a submission from a JSON file:

```sh
dpdisp submit submission.json
```

The JSON file must contain the submission configuration. An example of the JSON file is shown below.

```{literalinclude} ../examples/submit_example.json
---
language: json
linenos:
---
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
- `--allow-ref`: Allow loading external JSON/YAML snippets through `$ref` (disabled by default for security).
- `--no-clean`: Keep the remote submission directory after results are downloaded.
- `--continue-on-failure`: Continue monitoring other jobs after one job exhausts
  its retries. By default, retry exhaustion fails the submission immediately.

The JSON submission field `continue_on_failure` provides the same opt-in for
configuration-driven workflows:

```json
{
  "continue_on_failure": true
}
```

By default, `dpdisp submit` removes the submission-specific remote directory after
downloading the declared `backward_files` and `backward_common_files`. Use
`--no-clean` when the complete remote directory must remain available for inspection.
