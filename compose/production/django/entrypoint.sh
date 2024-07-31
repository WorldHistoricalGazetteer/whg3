#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --no-input

# Ensure required environment variables are set
: "${DB_HOST:?Environment variable DB_HOST is not set}"
: "${DB_PORT:?Environment variable DB_PORT is not set}"
: "${APP_PORT:?Environment variable APP_PORT is not set}"

# Wait for the database to be ready
echo "Waiting for the database to be ready..."
until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U postgres; do
  echo "Database not ready yet. Sleeping..."
  sleep 2
done

echo "Database is ready. Starting Gunicorn..."

# Start Gunicorn server
exec gunicorn whg.wsgi:application --bind 0.0.0.0:${APP_PORT} --timeout 1200 -w 4
