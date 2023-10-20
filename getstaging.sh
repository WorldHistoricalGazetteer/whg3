#!/bin/bash

# Step 1: Fetch the latest changes and check out the staging branch
git fetch origin
git checkout staging
git pull origin staging

# Step 2: Build inside the Docker container
WEBPACK_CONTAINER=$(docker ps -qf "name=whg3-webpack")
docker exec -it $WEBPACK_CONTAINER npm run build

echo "Updated to latest staging and built the bundles."
