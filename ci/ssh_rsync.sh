#!/usr/bin/env bash
set -e

cd ./ci/ssh
docker-compose pull
./start-ssh.sh
cd -

# install rsync
docker exec server /bin/bash -c "apt-get -y update && apt-get -y install rsync"
docker exec test /bin/bash -c "apt-get -y update && apt-get -y install rsync"

docker exec test /bin/bash -c "cd /dpdispatcher && pip install .[test] coverage && coverage run --source=./dpdispatcher -m unittest -v && coverage report"
docker exec --env-file <(env | grep GITHUB) test /bin/bash -c "cd /dpdispatcher && curl -Os https://uploader.codecov.io/latest/linux/codecov && chmod +x codecov && ./codecov"
