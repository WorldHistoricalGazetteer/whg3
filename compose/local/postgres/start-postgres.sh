#!/bin/bash
set -e

echo "USE_BETA_DB: $USE_BETA_DB"
echo "DB_NAME_BETA: $DB_NAME_BETA"

database_exists() {
  psql -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$1"
}

create_database() {
  local db_name=$1
  local db_user=$2
  local db_password=$3

  # Ensure the role exists
  psql -U "$POSTGRES_USER" -c "DO \$\$
  BEGIN CREATE ROLE $db_user WITH LOGIN PASSWORD '$db_password' SUPERUSER CREATEDB; EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'Role $db_user already exists'; END \$\$;"
  echo "Default superuser $db_user ensured."

  # Check if the database exists
  if database_exists $db_name; then
    echo "Database $db_name already exists."
    if [ "$DB_LOAD_DATA" = "True" ] && [ "$USE_BETA_DB" = "False" ]; then
      echo "Dropping and recreating the database..."
      dropdb -U "$POSTGRES_USER" "$db_name"
      echo "Database $db_name does not exist."
    else
      echo "Skipping database replacement."
      return
    fi
  else
    echo "Database $db_name does not exist."
  fi

  # Create the database
  createdb -U "$POSTGRES_USER" "$db_name"
  echo "Database $db_name created."

  # Load data from the dump file
  echo "Loading data from dump file..."
  gunzip -c /app/data/base_data.sql.gz | psql -U "$POSTGRES_USER" -d "$db_name"
  echo "Data loaded successfully."
}

# Append custom settings to postgresql.conf
echo "USE_WAL_SETTINGS: $USE_WAL_SETTINGS"
if [ "$USE_WAL_SETTINGS" = "True" ]; then
  CONFIG_FILE="/var/lib/postgresql/data/postgresql.conf"
  CUSTOM_CONFIG_FILE="/etc/postgresql/postgresql.wal-settings.conf"
  if [ -f "$CONFIG_FILE" ] && [ -f "$CUSTOM_CONFIG_FILE" ]; then
    echo "Adding custom configuration file..."
    echo "include = '/etc/postgresql/postgresql.wal-settings.conf'" >> $CONFIG_FILE
  else
    echo "Failed to locate necessary WAL configuration files"
  fi
else
  echo "Skipping WAL archiving configuration."
fi

if [ "$USE_BETA_DB" = "True" ]; then
  create_database "$DB_NAME_BETA" "$DB_USER_BETA" "$DB_PASSWORD_BETA"
#  create_database "$DB_NAME_BETA" "$DB_USER" "$DB_PASSWORD"
else
  create_database "$DB_NAME" "$DB_USER" "$DB_PASSWORD"
fi
