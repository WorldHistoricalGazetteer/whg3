#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

export POSTGRES_HOST_AUTH_METHOD="trust"

# Update pre-existing database tables using Django migrations

# NB: there should be no need for makemigrations here; it generates migration files from changes to models
# if anyone changes a model they would have to run makemigrations in their local environment in order
# to make use of the change, and when they submit a pull request for that branch, migration files would be part of it
PGUSER=${DB_USER} python manage.py makemigrations
PGUSER=${DB_USER} python manage.py migrate

# NB: file names are prefixed with fixture_
FIXTURES=("fixtures/fixture_users.json" "fixtures/fixture_datasets.json" "fixtures/fixture_places.json" "fixtures/fixture_collection.json" "fixtures/fixture_areas.json")
for fixture in "${FIXTURES[@]}"; do
    PGUSER=${DB_USER} python manage.py loaddata "$fixture"
done

# NB: the superuser account 'whgadmin' is provided by the fixture_users.json file now
# Run Django management command to create the superuser
#python manage.py createsuperuser --noinput --name=${DB_USER} --email=${DB_USER}@whgazetteer.org

# Gather static files into the 'static/' directory
python manage.py collectstatic --no-input

# Start the development server
python manage.py runserver 0.0.0.0:8000