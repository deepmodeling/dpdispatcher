#!/usr/bin/env bash
set -e

cd ./ci/slurm
docker-compose pull
./start-slurm.sh
cd -

docker exec slurmctld /bin/bash -c "cd dpdispatcher && pip install uv && uv pip install --system .[test] coverage && coverage run --source=./dpdispatcher -m unittest -v && coverage report"
docker exec --env-file <(env | grep -e GITHUB -e CODECOV) slurmctld /bin/bash -c "cd dpdispatcher && curl -Os https://uploader.codecov.io/latest/linux/codecov && chmod +x codecov && ./codecov"
