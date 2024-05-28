#!/usr/bin/env bash
set -e

cd ./ci/ssh
docker-compose pull
./start-ssh.sh
cd -

docker exec test /bin/bash -c "cd /dpdispatcher && pip install uv && uv pip install --system .[test] coverage && coverage run --source=./dpdispatcher -m unittest -v && coverage report"
docker exec --env-file <(env | grep -e GITHUB -e CODECOV) test /bin/bash -c "cd /dpdispatcher && curl -Os https://uploader.codecov.io/latest/linux/codecov && chmod +x codecov && ./codecov"
