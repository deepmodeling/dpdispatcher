#!/bin/bash

docker-compose up -d --no-build
docker exec remote /bin/bash -c "mkdir -p /dpdispatcher_working“