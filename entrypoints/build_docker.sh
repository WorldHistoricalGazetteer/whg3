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
PUSH=$2  # Optional second parameter to determine if the image should be pushed

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

# Handle version type and push parameter
if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    echo "Usage: $0 [major|minor|patch] [push]"
    exit 1
fi

# Get the current version from Docker Hub
current_version=$(get_latest_version)
echo "Current version: $current_version"

# If VERSION_TYPE is not provided, default to the latest version
if [ -z "$VERSION_TYPE" ]; then
    VERSION_TYPE="patch"
elif [ "$VERSION_TYPE" == "version" ]; then
	exit 1
elif [ "$VERSION_TYPE" == "push" ]; then
	echo "Cannot push without version type. Usage: $0 [major|minor|patch] [push]."
	exit 1
elif [[ ! "$VERSION_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo "Invalid version type: $VERSION_TYPE. Use 'major', 'minor', or 'patch'."
    exit 1
fi

# Increment the version
new_version=$(increment_version "$current_version" "$VERSION_TYPE")
echo "New version: $new_version"

exit 1

# Build and tag the Docker image
docker build -t "$DOCKER_IMAGE:$new_version" ./build

# Push the new version to Docker Hub if push parameter is passed
if [ "$PUSH" == "push" ]; then
    docker push "$DOCKER_IMAGE:$new_version"
    echo "Docker image pushed to Docker Hub with tag $DOCKER_IMAGE:$new_version"
else
    echo "Docker image built and tagged as $DOCKER_IMAGE:$new_version, but not pushed to Docker Hub."
fi
