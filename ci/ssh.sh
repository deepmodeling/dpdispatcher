#!/usr/bin/env bash
set -e

cd ./ci/pbs
docker-compose pull
./start-pbs.sh
cd -

docker exec local /bin/bash -c "cd /dpdispatcher && pip install .[test] coverage && coverage run --source=./dpdispatcher -m unittest -v && coverage report"
docker exec --env-file <(env | grep GITHUB) local /bin/bash -c "cd /dpdispatcher && pip install codecov && codecov"
