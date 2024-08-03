#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Source the common functions script
source /app/entrypoints/wait_for_db.sh

# Ensure required environment variables are set
: "${DB_HOST_BETA:?Environment variable DB_HOST_BETA is not set}"
: "${DB_PORT_BETA:?Environment variable DB_PORT_BETA is not set}"

# Wait for the database to be ready
wait_for_db "${DB_HOST_BETA}" "${DB_PORT_BETA}"

echo "Starting Celery worker..."
exec celery -A whg worker --loglevel=debug
