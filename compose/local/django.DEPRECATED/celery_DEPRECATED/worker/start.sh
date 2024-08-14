#!/bin/bash

set -o errexit
set -o nounset

celery -A whg worker -l INFO