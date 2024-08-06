#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Source the common functions script
source /app/entrypoints/wait_for_db.sh

# Wait for the database to be ready
wait_for_db

echo "Starting Celery worker..."
exec celery -A whg worker --loglevel=debug

