#!/bin/bash

# Define script directory
SCRIPT_DIR=$(dirname "$0")

echo "Deploying Tile services..."

# Deploy TileServer-GL
kubectl apply -f "$SCRIPT_DIR/tileserver/tileserver-gl-pvc.yaml"
kubectl apply -f "$SCRIPT_DIR/tileserver/tileserver-gl-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/tileserver/tileserver-gl-service.yaml"
kubectl apply -f "$SCRIPT_DIR/tileserver/tileserver-gl-ingress.yaml"

# Deploy Node server for Tippecanoe
# TODO: Build and push the docker image to DockerHub
kubectl apply -f "$SCRIPT_DIR/tileserver/tippecanoe-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/tileserver/tippecanoe-service.yaml"
kubectl apply -f "$SCRIPT_DIR/tileserver/tippecanoe-ingress.yaml"

echo "Tile services deployed successfully!"
