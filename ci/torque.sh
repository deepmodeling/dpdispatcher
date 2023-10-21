#!/usr/bin/env bash
set -e

cd ./ci/torque
docker-compose pull
./start-torque.sh
cd -

docker exec torque /bin/bash -c "cd /dpdispatcher && pip install .[test] coverage && chown -R testuser ."
docker exec -u testuser torque /bin/bash -c "cd /dpdispatcher && coverage run --source=./dpdispatcher -m unittest -v && coverage report"
docker exec -u testuser --env-file <(env | grep GITHUB) torque /bin/bash -c "cd /dpdispatcher && curl -Os https://uploader.codecov.io/latest/linux/codecov && chmod +x codecov && ./codecov"
