#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Source the common functions script
source /app/entrypoints/wait_for_db.sh

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --no-input

# Ensure required environment variables are set
: "${DB_HOST:?Environment variable DB_HOST is not set}"
: "${DB_PORT_INTERNAL:?Environment variable DB_PORT_INTERNAL is not set}"
: "${APP_PORT:?Environment variable APP_PORT is not set}"

# Wait for the database to be ready
wait_for_db "${DB_HOST}" "${DB_PORT_INTERNAL}"

echo "Starting Gunicorn server..."
exec gunicorn whg.wsgi:application --bind 0.0.0.0:${APP_PORT} --timeout 1200 -w 4

