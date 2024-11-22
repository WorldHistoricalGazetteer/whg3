#!/bin/bash

# Define script directory
SCRIPT_DIR=$(dirname "$0")

# Set environment to production or development
ENVIRONMENT=$1

if [ "$ENVIRONMENT" != "production" ] && [ "$ENVIRONMENT" != "development" ]; then
  echo "Please specify 'production' or 'development' as the environment."
  exit 1
fi

# Load base configuration variables
eval "$(jq -r ".base | to_entries | .[] | \"export \(.key)=\(.value)\"" < "$SCRIPT_DIR/django/config.json")"
# Load environment variables
eval "$(jq -r ".${ENVIRONMENT} | to_entries | .[] | \"export \(.key)=\(.value)\"" < "$SCRIPT_DIR/django/config.json")"

# Deploy PostgreSQL components
echo "Deploying PostgreSQL..."
envsubst < "$SCRIPT_DIR/django/postgres-pvc.yaml" | kubectl apply -f -
envsubst < "$SCRIPT_DIR/django/postgres-deployment.yaml" | kubectl apply -f -
envsubst < "$SCRIPT_DIR/django/postgres-service.yaml" | kubectl apply -f -

# Deploy Redis
echo "Deploying Redis..."
envsubst < "$SCRIPT_DIR/django/redis-pvc.yaml" | kubectl apply -f -
envsubst < "$SCRIPT_DIR/django/redis-deployment.yaml" | kubectl apply -f -
envsubst < "$SCRIPT_DIR/django/redis-service.yaml" | kubectl apply -f -

# Deploy Django app
echo "Deploying Django app..."
envsubst < "$SCRIPT_DIR/django/django-pvc.yaml" | kubectl apply -f -
envsubst < "$SCRIPT_DIR/django/django-deployment.yaml" | kubectl apply -f -
envsubst < "$SCRIPT_DIR/django/django-service.yaml" | kubectl apply -f -
envsubst < "$SCRIPT_DIR/django/django-ingress.yaml" | kubectl apply -f -

# Deploy Celery components
echo "Deploying Celery components..."
envsubst < "$SCRIPT_DIR/django/celery-worker-deployment.yaml" | kubectl apply -f -
envsubst < "$SCRIPT_DIR/django/celery-beat-deployment.yaml" | kubectl apply -f -

# Deploy Webpack
echo "Deploying Webpack..."
envsubst < "$SCRIPT_DIR/django/webpack-config.yaml" | kubectl apply -f -
envsubst < "$SCRIPT_DIR/django/webpack-deployment.yaml" | kubectl apply -f -

echo "Django application deployed successfully!"
