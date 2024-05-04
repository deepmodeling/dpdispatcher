# Run Python scripts

DPDispatcher can be used to directly run a single Python script:

```sh
dpdisp run script.py
```

The script must include [inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/) compliant with [PEP 723](https://peps.python.org/pep-0723/).
An example of the script is shown below.

```{literalinclude} ../examples/dpdisp_run.py
:language: py
:linenos:
```

The PEP 723 metadata entries for `tool.dpdispatcher` are defined as follows:

```{eval-rst}
.. include:: pep723.rst
```
