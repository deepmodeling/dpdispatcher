#!/bin/bash

docker compose up -d --no-build

# Set up SSH keys on server
docker exec server /bin/bash -c "ssh-keygen -b 2048 -t rsa -f /root/.ssh/id_rsa -q -N \"\" && cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys"
docker exec server /bin/bash -c "mkdir -p /dpdispatcher_working"
docker exec server /bin/bash -c "mkdir -p /tmp/rsync_test"

# Set up SSH keys on jumphost and configure it to access server
docker exec jumphost /bin/bash -c "ssh-keygen -b 2048 -t rsa -f /root/.ssh/id_rsa -q -N \"\" && cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys"

# Copy keys between containers to enable jump host functionality
# Get the public key from jumphost and add it to server's authorized_keys
docker exec jumphost /bin/bash -c "cat /root/.ssh/id_rsa.pub" | docker exec -i server /bin/bash -c "cat >> /root/.ssh/authorized_keys"

# Get the public key from test (which shares volume with server) and add it to jumphost authorized_keys
docker exec test /bin/bash -c "cat /root/.ssh/id_rsa.pub" | docker exec -i jumphost /bin/bash -c "cat >> /root/.ssh/authorized_keys"

# Configure SSH client settings for known hosts to avoid host key verification
docker exec test /bin/bash -c "echo 'StrictHostKeyChecking no' >> /root/.ssh/config && echo 'UserKnownHostsFile /dev/null' >> /root/.ssh/config"
docker exec jumphost /bin/bash -c "echo 'StrictHostKeyChecking no' >> /root/.ssh/config && echo 'UserKnownHostsFile /dev/null' >> /root/.ssh/config"
docker exec server /bin/bash -c "echo 'StrictHostKeyChecking no' >> /root/.ssh/config && echo 'UserKnownHostsFile /dev/null' >> /root/.ssh/config"

# Install rsync on all containers
docker exec test /bin/bash -c "apt-get -y update && apt-get -y install rsync"
docker exec jumphost /bin/bash -c "apt-get -y update && apt-get -y install rsync"
docker exec server /bin/bash -c "apt-get -y update && apt-get -y install rsync"
