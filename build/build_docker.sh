#!/bin/bash
set -e

# Ensure environment variables are set
if [ -z "$DOCKER_IMAGE" ]; then
    echo "Environment variable DOCKER_IMAGE must be set."
    exit 1
fi

# Configuration
DOCKERHUB_API="https://hub.docker.com/v2/repositories/$DOCKER_IMAGE/tags/"
VERSION_TYPE=$1

# Function to get the latest version from Docker Hub
get_latest_version() {
    local latest_version="0.0.0"
    response=$(curl -s "$DOCKERHUB_API?page_size=1&ordering=created")
    if [ $? -ne 0 ]; then
        echo "Failed to fetch tags from Docker Hub"
        exit 1
    fi

    # Extract the latest tag from the response JSON
    latest_version=$(echo "$response" | jq -r '.results[0].name // empty')

    # If no tags found, default to "0.0.0"
    if [ -z "$latest_version" ]; then
        latest_version="0.0.0"
    fi

    echo "$latest_version"
}

# Function to increment the version
increment_version() {
    local version=$1
    local type=$2
    local IFS=.
    local parts=($version)
    local major=${parts[0]}
    local minor=${parts[1]}
    local patch=${parts[2]}

    case $type in
        major)
            ((major++))
            minor=0
            patch=0
            ;;
        minor)
            ((minor++))
            patch=0
            ;;
        patch)
            ((patch++))
            ;;
        *)
            echo "Unknown version type: $type. Use 'major', 'minor', or 'patch'."
            exit 1
            ;;
    esac

    echo "${major}.${minor}.${patch}"
}

# Parse command-line arguments
if [ $# -ne 1 ]; then
    echo "Usage: $0 [major|minor|patch]"
    exit 1
fi

# Validate version type
if [[ ! "$VERSION_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo "Invalid version type: $VERSION_TYPE. Use 'major', 'minor', or 'patch'."
    exit 1
fi

# Get the current version from Docker Hub
current_version=$(get_latest_version)
echo "Current version: $current_version"

# Increment the version
new_version=$(increment_version "$current_version" "$VERSION_TYPE")
echo "New version: $new_version"

# Build and tag the Docker image
docker build -t "$DOCKER_IMAGE:$new_version" .

# Push the new version to Docker Hub
docker push "$DOCKER_IMAGE:$new_version"

echo "Docker image built and tagged as $DOCKER_IMAGE:$new_version"
