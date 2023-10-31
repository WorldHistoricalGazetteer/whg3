#!/bin/bash
set -e

# may require removing existing volume; see start-postgres-prod.sh

# Check if database exists
database_exists() {
    psql -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"
}

# Create default user
psql -U "$POSTGRES_USER" -c "DO \$\$ BEGIN CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASSWORD' SUPERUSER CREATEDB; EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'Role $DB_USER already exists'; END \$\$;"
echo "Default superuser $DB_USER ensured."

if database_exists; then
    echo "Database $DB_NAME already exists."
    echo "DB_LOAD_DATA is set to $DB_LOAD_DATA"
    if [[ "$DB_LOAD_DATA" == "True" ]]; then
        # Restore data if DB_LOAD_DATA is set to True
        echo "Restoring data from dump..."
        # Wait for Postgres to become available
        until pg_isready -U "$DB_USER" -d "$DB_NAME"; do
            echo "Waiting for PostgreSQL to become available..."
            sleep 2
        done

        gunzip -c /app/data/base_data.sql.gz | psql -U "$DB_USER" -d "$DB_NAME"
        echo "Data restored."
    fi
else
    # Create the database
    psql -U "$POSTGRES_USER" -c "CREATE DATABASE $DB_NAME WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'C.UTF-8' OWNER $DB_USER;"
    echo "Database $DB_NAME created."

    # Restore data, assuming the default behavior is to restore when a new DB is created
    echo "Restoring data from dump..."
    # Wait for Postgres to become available
    until pg_isready -U "$DB_USER" -d "$DB_NAME"; do
        echo "Waiting for PostgreSQL to become available..."
        sleep 2
    done

    gunzip -c /app/data/base_data.sql.gz | psql -U "$DB_USER" -d "$DB_NAME"
    echo "Data restored."
fi



## OLD STUFF, TRASH AFTER TESTING
##!/bin/bash
#set -e
#
## Check if database exists
#database_exists() {
#    psql -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"
#}
#
## Create default user
#psql -U "$POSTGRES_USER" -c "DO \$\$ BEGIN CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASSWORD' SUPERUSER CREATEDB; EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'Role $DB_USER already exists'; END \$\$;"
#echo "Default superuser $DB_USER ensured."
#
#if ! database_exists; then
#    # Create the database
#    psql -U "$POSTGRES_USER" -c "CREATE DATABASE $DB_NAME WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'C.UTF-8' OWNER $DB_USER;"
#    echo "Database $DB_NAME created."
#
#    # Restore data if DB_LOAD_DATA is set to True
#    if [[ "$DB_LOAD_DATA" == "True" ]]; then
#        echo "Restoring data from dump..."
#
#        # Wait for Postgres to become available
#        until pg_isready -U "$DB_USER" -d "$DB_NAME"; do
#            echo "Waiting for PostgreSQL to become available..."
#            sleep 2
#        done
#
#        gunzip -c /app/data/base_data.sql.gz | psql -U "$DB_USER" -d "$DB_NAME"
#        echo "Data restored."
#    fi
#else
#    echo "Database $DB_NAME already exists. Skipping creation."
#fi



#set -e
#
## Create new database
#psql -c "CREATE DATABASE $DB_NAME WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'C.UTF-8' OWNER postgres;"
#echo "Database $DB_NAME created from postgis image"
#
## Create default user
#psql -d ${DB_NAME} -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD' SUPERUSER CREATEDB;"
#psql -d ${DB_NAME} -c "GRANT $DB_USER TO postgres;"
#echo "Default superuser $DB_USER created."
#
## Restore data if DB_LOAD_DATA is set to True
#if [[ "$DB_LOAD_DATA" == "True" ]]; then
#    echo "Restoring data from dump..."
#    gunzip -c data/base_data.sql.gz | psql -h localhost -U $DB_USER -d $DB_NAME
##    psql -U $DB_USER -d $DB_NAME < /app/data/base_data.sql
#    echo "Data restored."
#fi


# `docker-compose.yml` uses this to replace the default startup script at /docker-entrypoint-initdb.d/10_postgis.sh
# It will not be executed if a database already exists in a mounted volume.

#set -e
#
## Create new database
#psql -c "CREATE DATABASE $DB_NAME WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'C.UTF-8' OWNER postgres;"
#echo "Empty database $DB_NAME created."
#
## Create default user
#psql -d ${DB_NAME} -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD' SUPERUSER CREATEDB;"
#psql -d ${DB_NAME} -c "GRANT $DB_USER TO postgres;"
#echo "Default superuser $DB_USER created."
