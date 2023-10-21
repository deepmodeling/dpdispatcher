#!/bin/bash

docker-compose up -d --no-build
while [ `docker exec torque /bin/bash -c ls | wc -l` -ne 1 ]
do
    echo "Waiting for nodes to become available";
    sleep 2
done
echo "Torque properly configured"
