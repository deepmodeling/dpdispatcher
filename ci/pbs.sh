#!/usr/bin/env bash
set -e

cd ./ci/pbs
docker-compose pull
./start-pbs.sh
cd -

docker exec pbs_master /bin/bash -c "chmod -R 777 /shared_space"
docker exec pbs_master /bin/bash -c "chown -R pbsuser:pbsuser /home/pbsuser"

docker exec pbs_master /bin/bash -c "cd /dpdispatcher && pip install .[test] coverage && chown -R pbsuser ."
docker exec -u pbsuser pbs_master /bin/bash -c "cd /dpdispatcher && coverage run --source=./dpdispatcher -m unittest -v && coverage report"
docker exec -u pbsuser --env-file <(env | grep GITHUB) pbs_master /bin/bash -c "cd /dpdispatcher && curl -Os https://uploader.codecov.io/latest/linux/codecov && chmod +x codecov && ./codecov"
