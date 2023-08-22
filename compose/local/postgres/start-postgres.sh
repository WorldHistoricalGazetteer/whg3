#!/bin/bash

# `docker-compose.yml` uses this to replace the default startup script at /docker-entrypoint-initdb.d/10_postgis.sh
# It will not be executed if a database already exists in a mounted volume.

set -e

# Create new database
psql -c "CREATE DATABASE $DB_NAME WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'C.UTF-8' OWNER postgres;"
echo "Empty database $DB_NAME created."
