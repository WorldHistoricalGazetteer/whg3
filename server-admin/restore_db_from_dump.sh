#!/bin/bash

# Check if the BACKUP_NAME parameter is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 BACKUP_NAME"
    exit 1
fi

# Assign parameters to variables
ADMIN_USER=$DB_USER
ADMIN_PASSWORD=$DB_PASSWORD
DB_NAME=$DB_NAME
BACKUP_NAME=$1

# Clean up old log files
rm -f /tmp/restore_schema_errors.log
rm -f /tmp/restore_data_errors.log

# Drop the existing database if it exists
psql -U postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"

# Create a new database
psql -U postgres -c "CREATE DATABASE $DB_NAME;"

# Create the postgis extension
psql -U postgres -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Create the admin user and grant replication bypass
psql -U postgres -c "CREATE USER $ADMIN_USER WITH PASSWORD '$ADMIN_PASSWORD';"
psql -U postgres -c "ALTER USER $ADMIN_USER WITH REPLICATION BYPASSRLS;"

# Grant necessary privileges to $ADMIN_USER on the new database and public schema
psql -U postgres -d $DB_NAME -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $ADMIN_USER;"
psql -U postgres -d $DB_NAME -c "GRANT USAGE ON SCHEMA public TO $ADMIN_USER;"
psql -U postgres -d $DB_NAME -c "GRANT CREATE ON SCHEMA public TO $ADMIN_USER;"
psql -U postgres -d $DB_NAME -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $ADMIN_USER;"
psql -U postgres -d $DB_NAME -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $ADMIN_USER;"
psql -U postgres -d $DB_NAME -c "GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO $ADMIN_USER;"

# Create read-only user
psql -U postgres -c "CREATE USER ro_user;"

# Restore the schema
pg_restore -U $ADMIN_USER -d $DB_NAME -v --jobs=4 --no-owner --schema-only $BACKUP_NAME > /tmp/restore_schema.log 2> /tmp/restore_schema_errors.log

# Restore the data
pg_restore -U $ADMIN_USER -d $DB_NAME -v --jobs=4 --no-owner --data-only $BACKUP_NAME > /tmp/restore_data.log 2> /tmp/restore_data_errors.log
