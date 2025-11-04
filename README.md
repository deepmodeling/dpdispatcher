# DPDispatcher

[![conda-forge](https://img.shields.io/conda/dn/conda-forge/dpdispatcher?color=red&label=conda-forge&logo=conda-forge)](https://anaconda.org/conda-forge/dpdispatcher)
[![pip install](https://img.shields.io/pypi/dm/dpdispatcher?label=pip%20install&logo=pypi)](https://pypi.org/project/dpdispatcher)
[![docker pull](https://img.shields.io/docker/pulls/dptechnology/dpdispatcher?logo=docker)](https://hub.docker.com/r/dptechnology/dpdispatcher)
[![Documentation Status](https://readthedocs.org/projects/dpdispatcher/badge/)](https://dpdispatcher.readthedocs.io/)

DPDispatcher is a Python package used to generate HPC (High-Performance Computing) scheduler systems (Slurm/PBS/LSF/Bohrium) jobs input scripts, submit them to HPC systems, and poke until they finish.

DPDispatcher will monitor (poke) until these jobs finish and download the results files (if these jobs are running on remote systems connected by SSH).

For more information, check the [documentation](https://dpdispatcher.readthedocs.io/).

## Credits

Please cite the following paper if you use this project in your work:

- Fengbo Yuan, Zhaohan Ding, Yun-Pei Liu, Kai Cao, Jiahao Fan, Cao Thang Nguyen, Yuzhi Zhang, Haidi Wang, Yixiao Chen, Jiameng Huang, Tongqi Wen, Mingkang Liu, Yifan Li, Yong-Bin Zhuang, Hao Yu, Ping Tuo, Yaotang Zhang, Yibo Wang, Linfeng Zhang, Han Wang, Jinzhe Zeng, DPDispatcher: Scalable HPC Task Scheduling for AI-Driven Science, _J. Chem. Inf. Model._, 2025, DOI: [10.1021/acs.jcim.5c02081](https://doi.org/10.1021/acs.jcim.5c02081). [![Citations](https://citations.njzjz.win/10.1021/acs.jcim.5c02081)](https://badge.dimensions.ai/details/doi/10.1021/acs.jcim.5c02081)

This project was separated out from the [DP-GEN](https://github.com/deepmodeling/dpgen) project (Section 3.3 in [its paper](https://doi.org/10.1016/j.cpc.2020.107206)) to be used by more workflow software.

## Installation

DPDispatcher can be installed by `pip`:

```bash
pip install dpdispatcher
```

To add [Bohrium](https://bohrium.dp.tech/) support, execute

```bash
pip install dpdispatcher[bohrium]
```

## Usage

See [Getting Started](https://dpdispatcher.readthedocs.io/en/latest/getting-started.html) for usage.

## Contributing

DPDispatcher is maintained by Deep Modeling's developers and welcomes other people.
See [Contributing Guide](CONTRIBUTING.md) to become a contributor! 🤓
