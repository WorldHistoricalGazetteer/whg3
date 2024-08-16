#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Navigate to the working directory
cd /app

npm install

# Start Webpack Dev Server
echo "Starting Webpack Dev Server..."
npx webpack serve --config webpack.config.js
