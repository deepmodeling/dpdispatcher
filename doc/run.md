# Run Python scripts

DPDispatcher can be used to directly run a single Python script:

```sh
dpdisp run script.py
```

The script must include [inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/) compliant with [PEP 723](https://peps.python.org/pep-0723/).
An example of the script is shown below.

```{literalinclude} ../examples/dpdisp_run.py
---
language: py
linenos:
---
```

The PEP 723 metadata entries for `tool.dpdispatcher` are defined as follows:

```{eval-rst}
.. include:: pep723.rst
```

## `$ref` support secure by default

`dpdisp run` supports loading external JSON/YAML snippets via `$ref` in `tool.dpdispatcher` metadata.
For security reasons, this feature is disabled by default.

Enable explicitly with:

```sh
dpdisp run script.py --allow-ref
```
