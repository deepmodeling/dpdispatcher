.. deepmd-kit documentation master file, created by
   sphinx-quickstart on Sat Nov 21 18:36:24 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

DPDispatcher's documentation
======================================

DPDispatcher is a Python package used to generate HPC (High Performance Computing) scheduler systems (Slurm/PBS/LSF/dpcloudserver) jobs input scripts and submit these scripts to HPC systems and poke until they finish.  

DPDispatcher will monitor (poke) until these jobs finish and download the results files (if these jobs is running on remote systems connected by SSH). 

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   
   install
   getting-started
   context
   batch
   machine
   resources
   task
   api/api

.. toctree::
   :caption: Examples
   :glob:

   examples/*

.. toctree::
   :caption: Project details
   :glob:
   
   credits

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
