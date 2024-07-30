#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --no-input

# Wait for the database to be ready
echo "Waiting for the database to be ready..."
until pg_isready -h db_beta -p 5432 -U postgres; do
  echo "Database not ready yet. Sleeping..."
  sleep 2
done

echo "Database is ready. Starting Gunicorn..."

# Start Gunicorn server
exec gunicorn whg.wsgi:application --bind 0.0.0.0:8003 --timeout 1200 -w 4
