# Customizing the submission script header

When submitting jobs to some clusters, such as the [Tiger Cluster](https://researchcomputing.princeton.edu/systems/tiger) at Princeton University, the Slurm header is quite different from the standard one. In this case, DPDispatcher allows users to customize the templates by setting {dargs:argument}`strategy/customized_script_header_template_file <resources/strategy/customized_script_header_template_file>` to a template file:

```{literalinclude} ../../examples/resources/tiger.json
:language: json
:linenos:
```

`template.slurm` is the template file, where {meth}`str.format` is used to format the template with [Resources Parameters](resources):

```{literalinclude} ../../examples/resources/template.slurm
:linenos:
```

See [Python Format String Syntax](https://docs.python.org/3/library/string.html#formatstrings) for how to insert parameters inside the template.
