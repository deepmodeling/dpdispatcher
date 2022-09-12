#!/usr/bin/env bash

cd ./ci/slurm
docker-compose pull
./start-slurm.sh
cd -

docker exec slurmctld /bin/bash -c "cd dpdispatcher && pip install .[test] coverage && coverage run --source=./dpdispatcher -m unittest -v && coverage report"

