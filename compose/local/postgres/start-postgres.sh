#!/bin/bash

# `docker-compose.yml` uses this to replace the default startup script at /docker-entrypoint-initdb.d/10_postgis.sh
# It will not be executed if a database already exists in a mounted volume.

set -e

# Create new database
psql -c "CREATE DATABASE $DB_NAME WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'C.UTF-8' OWNER postgres;"
echo "Empty database $DB_NAME created."

# Create default user
psql -d ${DB_NAME} -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD' SUPERUSER CREATEDB;"
psql -d ${DB_NAME} -c "GRANT $DB_USER TO postgres;"
echo "Default superuser $DB_USER created."
