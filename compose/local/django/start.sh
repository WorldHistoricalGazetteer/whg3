#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

export PGUSER="postgres"
export POSTGRES_HOST_AUTH_METHOD="trust"

psql -h ${DB_HOST} -p ${DB_PORT} -d ${DB_NAME} -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD' SUPERUSER CREATEDB;"
psql -h ${DB_HOST} -p ${DB_PORT} -d ${DB_NAME} -c "GRANT $DB_USER TO postgres;"

# Check if DB_LOAD_DATA session variable is set to "True"
if [[ "${DB_LOAD_DATA}" == "True" ]]; then
	# Apply schema to empty database
	psql -h ${DB_HOST} -p ${DB_PORT} -d ${DB_NAME} < docs/cloning/whg3_data_dump_schema.sql
	
    # Import data from whg3_data.dump
    export PGPASSWORD=${DB_PASSWORD}
	pg_restore -h ${DB_HOST} -p ${DB_PORT} -d ${DB_NAME} -v --no-owner --no-acl docs/cloning/whg3_data.dump
	
	# Reset Django migration control with --fake option
	PGUSER=${DB_USER} python manage.py migrate --fake # Uses DB_USER
else
	# Build database tables from Django models
	PGUSER=${DB_USER} python manage.py makemigrations
	PGUSER=${DB_USER} python manage.py migrate
	
    # Populate database tables for basic operation
    psql -h ${DB_HOST} -p ${DB_PORT} -d ${DB_NAME} < docs/cloning/types.sql
    psql -h ${DB_HOST} -p ${DB_PORT} -d ${DB_NAME} < docs/cloning/combined.sql
fi

# Run Django management command to create the superuser
python manage.py createsuperuser --noinput --name=${DB_USER} --email=${DB_USER}@whgazetteer.org

# Gather static files into the 'static/' directory
python manage.py collectstatic --no-input

# Start the development server
python manage.py runserver 0.0.0.0:8000