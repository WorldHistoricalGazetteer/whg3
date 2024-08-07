#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Function to add user to group
add_user_to_group() {
    USER=$1
    GROUP=$2
    if ! id -nG "$USER" | grep -qw "$GROUP"; then
        usermod -aG "$GROUP" "$USER"
        echo "Added user $USER to group $GROUP"
    else
        echo "User $USER is already in group $GROUP"
    fi
}

# Get the group name of /var/run/docker.sock
DOCKER_SOCK_GROUP=$(stat -c '%G' /var/run/docker.sock)

# Add whgadmin to the group owning /var/run/docker.sock
if [ "$DOCKER_SOCK_GROUP" != "UNKNOWN" ]; then
    add_user_to_group whgadmin "$DOCKER_SOCK_GROUP"
else
    echo "Could not determine group of /var/run/docker.sock"
fi

# Source the common functions script
source /app/entrypoints/wait_for_db.sh

# Wait for the database to be ready
wait_for_db

echo "Starting Celery worker..."
exec celery -A whg worker --loglevel=debug

