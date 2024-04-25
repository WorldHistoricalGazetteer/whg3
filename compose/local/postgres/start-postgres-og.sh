#!/bin/bash
set -e

database_exists() {
  psql -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"
}

if [ "$DB_LOAD_DATA" = "True" ]; then
  # Ensure the role exists
  psql -U "$POSTGRES_USER" -c "DO \$\$ BEGIN CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASSWORD' SUPERUSER CREATEDB; EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'Role $DB_USER already exists'; END \$\$;"
  echo "Default superuser $DB_USER ensured."

  # Check if the database exists
  if database_exists; then
    echo "Database $DB_NAME already exists."
    echo "Dropping and recreating the database..."
    dropdb -U "$POSTGRES_USER" "$DB_NAME"
  else
    echo "Database $DB_NAME does not exist."
  fi

  # Create the database
  createdb -U "$POSTGRES_USER" "$DB_NAME"
  echo "Database $DB_NAME created."

  # Load data from the dump file
  echo "Loading data from dump file..."
  gunzip -c /app/data/base_data.sql.gz | psql -U "$POSTGRES_USER" -d "$DB_NAME"
  echo "Data loaded successfully."
else
  echo "DB_LOAD_DATA is not set to True. Skipping database replacement."
fi
