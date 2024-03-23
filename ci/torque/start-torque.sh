#!/bin/bash

docker-compose up -d --no-build
docker exec -u testuser torque /bin/bash -c "mkdir -p /home/testuser/dpdispatcher_working"
echo "Torque properly configured"
