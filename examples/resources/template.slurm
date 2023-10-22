#!/bin/bash -l
#SBATCH --parsable
#SBATCH --nodes={number_node}
#SBATCH --ntasks-per-node={cpu_per_node}
#SBATCH --qos={kwargs[qos]}
#SBATCH --time=01:02:00
#SBATCH --mem-per-cpu=4G
