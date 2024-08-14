#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Ensure required environment variables are set
: "${APP_PORT:?Environment variable APP_PORT is not set}"

# Change user password
/app/entrypoints/user_pwd.sh

# Collect static files
echo "Collecting static files..."
/py/bin/python manage.py collectstatic --no-input

# Wait for the database to be ready
source /app/entrypoints/wait_for_db.sh
wait_for_db

## Run migrations
#echo "Running migrations..."
#sudo /py/bin/python manage.py migrate

echo "Starting Gunicorn server..."
exec gunicorn whg.wsgi:application --bind 0.0.0.0:${APP_PORT} --timeout 1200 -w 4
