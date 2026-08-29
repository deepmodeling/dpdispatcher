.. deepmd-kit documentation master file, created by
   sphinx-quickstart on Sat Nov 21 18:36:24 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

DPDispatcher's documentation
======================================

DPDispatcher generates job scripts for HPC schedulers such as Slurm, PBS, LSF,
JH UniScheduler, and cloud backends. It submits those jobs, monitors them until
completion, and transfers declared input and result files.

The same Python API works with local shell execution, SSH-connected clusters,
distributed filesystems, and supported cloud services.

Please cite the following paper if you use this project in your work:

-  Fengbo Yuan, Zhaohan Ding, Yun-Pei Liu, Kai Cao, Jiahao Fan, Cao
   Thang Nguyen, Yuzhi Zhang, Haidi Wang, Yixiao Chen, Jiameng Huang,
   Tongqi Wen, Mingkang Liu, Yifan Li, Yong-Bin Zhuang, Hao Yu, Ping
   Tuo, Yaotang Zhang, Yibo Wang, Linfeng Zhang, Han Wang, Jinzhe Zeng,
   DPDispatcher: Scalable HPC Task Scheduling for AI-Driven Science, *J.
   Chem. Inf. Model.*, 2025.

.. toctree::
   :maxdepth: 2
   :caption: Contents:


   install
   getting-started
   python-api
   context
   batch
   dpdispatcher_on_yarn
   machine
   resources
   task
   env
   run
   submit
   agent-skills
   cli
   api/api

.. toctree::
   :caption: Examples
   :glob:

   examples/expanse
   examples/g16
   examples/shell
   examples/template

.. toctree::
   :caption: Project details
   :glob:

   credits

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
