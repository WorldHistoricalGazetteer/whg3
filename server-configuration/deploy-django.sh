#!/bin/bash

#TODO: Build yaml from configuration files

# Deploy PostgreSQL components
echo "Deploying PostgreSQL..."
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/postgres-secret.yaml"
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/postgres-pvc.yaml"
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/postgres-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/postgres-service.yaml"

# Deploy Redis
echo "Deploying Redis..."
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/redis-pvc.yaml"
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/redis-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/redis-service.yaml"

echo "Deploying Django app..."
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/django-secret.yaml"
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/django-pvc.yaml"
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/django-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/django-service.yaml"
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/django-ingress.yaml"

# Deploy Celery components
echo "Deploying Celery components..."
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/celery-worker-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/celery-beat-deployment.yaml"

# Deploy Webpack
echo "Deploying Webpack..."
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/webpack-config.yaml"
kubectl apply -f "$SCRIPT_DIR/django-kubernetes-manifests/webpack-deployment.yaml"

echo "Django application deployed successfully!"
