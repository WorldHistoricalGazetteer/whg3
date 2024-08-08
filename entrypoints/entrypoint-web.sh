#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Change user password
/app/entrypoints/permitted/user_pwd.sh

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --no-input

# Wait for the database to be ready
source /app/entrypoints/wait_for_db.sh
wait_for_db

echo "Starting Gunicorn server..."
exec gunicorn whg.wsgi:application --bind 0.0.0.0:8004 --timeout 1200 -w 4
