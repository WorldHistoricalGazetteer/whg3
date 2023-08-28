#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

export POSTGRES_HOST_AUTH_METHOD="trust"

# Update pre-existing database tables using Django migrations
PGUSER=${DB_USER} python manage.py makemigrations
PGUSER=${DB_USER} python manage.py migrate

FIXTURES=("fixtures/users.json" "fixtures/datasets.json" "fixtures/places.json" "fixtures/collection.json" "fixtures/areas.json")
for fixture in "${FIXTURES[@]}"; do
    PGUSER=${DB_USER} python manage.py loaddata "$fixture"
done

# Run Django management command to create the superuser
python manage.py createsuperuser --noinput --name=${DB_USER} --email=${DB_USER}@whgazetteer.org

# Gather static files into the 'static/' directory
python manage.py collectstatic --no-input

# Start the development server
python manage.py runserver 0.0.0.0:8000