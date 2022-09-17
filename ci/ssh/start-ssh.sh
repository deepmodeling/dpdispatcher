#!/bin/bash

docker-compose up -d --no-build

docker exec server /bin/bash -c "ssh-keygen -b 2048 -t rsa -f /root/.ssh/id_rsa -q -N \"\" && cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys"
docker exec server /bin/bash -c "mkdir -p /dpdispatcher_working"
