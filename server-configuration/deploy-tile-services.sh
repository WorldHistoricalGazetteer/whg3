#!/bin/bash

echo "Deploying Tile services..."

# Deploy TileServer-GL
kubectl apply -f "$SCRIPT_DIR/tileserver-kubernetes-manifests/tileserver-gl-pvc.yaml"
kubectl apply -f "$SCRIPT_DIR/tileserver-kubernetes-manifests/tileserver-gl-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/tileserver-kubernetes-manifests/tileserver-gl-service.yaml"
kubectl apply -f "$SCRIPT_DIR/tileserver-kubernetes-manifests/tileserver-gl-ingress.yaml"

# Deploy Node server for Tippecanoe
# TODO: Build and push the docker image to DockerHub
kubectl apply -f "$SCRIPT_DIR/tileserver-kubernetes-manifests/tippecanoe-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/tileserver-kubernetes-manifests/tippecanoe-service.yaml"
kubectl apply -f "$SCRIPT_DIR/tileserver-kubernetes-manifests/tippecanoe-ingress.yaml"


echo "Tile services deployed successfully!"
