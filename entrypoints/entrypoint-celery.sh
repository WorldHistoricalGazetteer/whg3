#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Source the common functions script
source /app/entrypoints/wait_for_db.sh

# Ensure required environment variables are set
: "${DB_HOST_BETA:?Environment variable DB_HOST_BETA is not set}"
: "${DB_PORT_BETA:?Environment variable DB_PORT_BETA is not set}"

# Add user to docker group
if [ -S /var/run/docker.sock ]; then
    DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
    if ! getent group ${DOCKER_GID} &>/dev/null; then
        groupadd -g ${DOCKER_GID} docker
    fi
    usermod -aG docker $(whoami)
    newgrp docker <<EONG
        echo "Waiting for Docker group permissions to apply..."
        sleep 1
EONG
fi

# Wait for the database to be ready
wait_for_db "${DB_HOST_BETA}" "${DB_PORT_BETA}"

echo "Starting Celery worker..."
exec celery -A whg worker --loglevel=debug
