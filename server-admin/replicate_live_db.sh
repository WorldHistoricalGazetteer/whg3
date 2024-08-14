#!/bin/bash

# Source and Target
DATABASE_SOURCE="whgazetteer-org"
DATABASE_TARGET="dev-whgazetteer-org"

# Derived Variables
DATABASE_COPY_DIR="/home/whgadmin/databases/${DATABASE_SOURCE}-copy"  # Directory for the database copy
TARGET_DB_DIR="/home/whgadmin/databases/${DATABASE_TARGET}"  # Target database directory
TEMP_DB_DIR="${TARGET_DB_DIR}-temp"  # Temporary directory for the existing database

# Load database connection variables from .env file
ENV_FILE="/home/whgadmin/sites/${DATABASE_SOURCE}/.env/.env"
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
else
    echo "Error: .env file not found at $ENV_FILE"
    exit 1
fi
# Override DB_HOST with localhost
DB_HOST="localhost"

# Ensure script stops on first error
set -e

# Function to handle cleanup on error or interruption
cleanup() {
    echo "An error occurred. Cleaning up..."
    # If the temp directory exists, revert the changes
    if [ -d "$TEMP_DB_DIR" ]; then
        mv "$TEMP_DB_DIR" "$TARGET_DB_DIR"
        echo "Reverted to the original database directory."
    fi
    # Remove any partially copied directories
    sudo rm -rf "$DATABASE_COPY_DIR"
    sudo rm -rf "$TEMP_DB_DIR"
    echo "Cleanup completed."
    exit 1
}

# Trap errors and interruptions (e.g., CTRL+C)
trap cleanup ERR INT

# Remove the existing copy directory if it exists
if [ -d "$DATABASE_COPY_DIR" ]; then
    echo "Warning: $DATABASE_COPY_DIR already exists. Removing it."
    sudo rm -rf "$DATABASE_COPY_DIR"
fi

# Create new copy directory
mkdir -p "$DATABASE_COPY_DIR"

# Perform the PostgreSQL base backup
pg_basebackup -D "$DATABASE_COPY_DIR" -Fp -P -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -X fetch

echo "Database copying completed."

# Change ownership and permissions of the copied directory
sudo chown -R lxd:whgadmin "$DATABASE_COPY_DIR"
sudo chmod -R 0700 "$DATABASE_COPY_DIR"

# Remove the temporary directory if it exists
if [ -d "$TEMP_DB_DIR" ]; then
    echo "Removing existing temporary directory $TEMP_DB_DIR"
    sudo rm -rf "$TEMP_DB_DIR"
fi

# Move the existing database directory to the temporary location
if [ -d "$TARGET_DB_DIR" ]; then
    mv "$TARGET_DB_DIR" "$TEMP_DB_DIR"
fi

# Move the copied database directory to the target location
mv "$DATABASE_COPY_DIR" "$TARGET_DB_DIR"

# Remove the temporary directory
sudo rm -rf "$TEMP_DB_DIR"

echo "Database replacement completed."
