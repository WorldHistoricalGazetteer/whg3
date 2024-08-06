#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Function to wait for the database to be ready
wait_for_db() {
#  local db_host=$1
#  local db_port=$2
  local db_host="db_beta"
  local db_port=5432

  echo "Waiting for the database at ${db_host}:${db_port} to be ready..."
  until nc -z "${db_host}" "${db_port}"; do
    echo "Database not ready yet. Sleeping..."
    sleep 2
  done
  echo "Database is ready."
}

