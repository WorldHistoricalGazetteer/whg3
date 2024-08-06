#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Source the common functions script
source /app/entrypoints/wait_for_db.sh

# Ensure required environment variables are set
: "${DB_HOST:?Environment variable DB_HOST is not set}"
: "${DB_PORT_INTERNAL:?Environment variable DB_PORT_INTERNAL is not set}"

# Wait for the database to be ready
wait_for_db "${DB_HOST}" "${DB_PORT_INTERNAL}"

# Remove the existing celerybeat.pid file if it exists
echo "Removing existing celerybeat.pid file if it exists..."
rm -f /app/celerybeat.pid

echo "Starting Celery Beat..."
exec celery -A whg beat --loglevel=debug --scheduler django_celery_beat.schedulers:DatabaseScheduler

