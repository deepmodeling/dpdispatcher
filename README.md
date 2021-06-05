# DPDispatcher

DPDispatcher is a python package used to generate HPC(High Performance Computing) scheduler systems (Slurm/PBS/LSF/dpcloudserver) jobs input scripts and submit these  scripts to HPC systems and poke until they finish.  
​
DPDispatcher will monitor (poke) until these jobs finish and download the results files (if these jobs is running on remote systems connected by SSH).

For more information, check the [documentation](https://dpdispatcher.readthedocs.io/).

## Installation

DPDispatcher can installed by `pip`:

```bash
pip install dpdispatcher
```

## Usage

See [Getting Started](https://dpdispatcher.readthedocs.io/en/latest/getting-started.html) for usage.

## Contributing

DPDispatcher is maintained by Deep Modeling's developers and welcome other people.
See [Contributing Guide](CONTRIBUTING.md) to become a contributor! 🤓
