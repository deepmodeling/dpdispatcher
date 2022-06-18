# Running multiple MD tasks on a GPU workstation

In this example, we are going to show how to run multiple MD tasks on a GPU workstation. This workstation does not install any job scheduling packages installed, so we will use `Shell` as {ref}`batch_type <machine/batch_type>`.

```{literalinclude} ../../examples/machine/mandu.json
:language: json
:linenos:
```

The workstation has 48 cores of CPUs and 8 RTX3090 cards. Here we hope each card runs 6 tasks at the same time, as each task does not consume too many GPU resources. Thus, {ref}`strategy/if_cuda_multi_devices <resources/strategy/if_cuda_multi_devices>` is set to `true` and {ref}`para_deg <resources/para_deg>` is set to 6.

```{literalinclude} ../../examples/resources/mandu.json
:language: json
:linenos:
```

Note that {ref}`group_size <resources/group_size>` should be set to `0` (means infinity) to ensure there is only one job and avoid running multiple jobs at the same time.
