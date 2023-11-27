#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

export POSTGRES_HOST_AUTH_METHOD="trust"

python manage.py collectstatic --no-input

# start the nginx server
#gunicorn whg.wsgi:application --bind 0.0.0.0:8003
gunicorn whg.wsgi:application --bind 0.0.0.0:8003 --timeout 1200 -w 4