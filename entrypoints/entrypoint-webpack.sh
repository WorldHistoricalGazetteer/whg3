#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Navigate to the working directory
cd /app

npm install

# Start Webpack
echo "Starting Webpack..."
npx webpack --watch --config webpack.config.js
