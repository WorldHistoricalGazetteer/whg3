#!/bin/bash
set -e

echo "Running local_load_database.sh ..."

database_exists() {
  psql -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$1"
}

# Ensure the role exists
psql -U "$POSTGRES_USER" -c "DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
      CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASSWORD' SUPERUSER CREATEDB;
   ELSE
      RAISE NOTICE 'Role $DB_USER already exists';
   END IF;
END
\$\$;"
echo "Default superuser $DB_USER ensured."

# Check if the database exists
if database_exists $DB_NAME; then
 dropdb -U "$POSTGRES_USER" "$DB_NAME"
fi

# Create the database
createdb -U "$POSTGRES_USER" "$DB_NAME"
echo "Database $DB_NAME created."

# Load data from the dump file
echo "Loading data from dump file..."
gunzip -c /app/data/base_data.sql.gz | psql -U "$POSTGRES_USER" -d "$DB_NAME"
echo "Data loaded successfully."
