#!/bin/bash

docker-compose up -d --no-build
docker exec torque /bin/bash -c "mkdir -p /dpdispatcher_working"
echo "Torque properly configured"
