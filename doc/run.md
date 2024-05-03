# Run Python scripts

DPDispatcher can be used to run a single Python script directly:

```sh
dpdisp run script.py
```

The script must contain [inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/) in the style of [PEP 723](https://peps.python.org/pep-0723/).
An example of the script is shown below.

```{literalinclude} ../../examples/dpdisp_run.py
:language: py
:linenos:
```

The PEP 723 metadata entries for `tool.dpdispatcher` are defined as below:

```{dargs}
:module: dpdispatcher.run
:func: pep723_args
```
