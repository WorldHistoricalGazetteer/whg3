#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Print current user and group memberships
echo "Current user: $(whoami)"
echo "Groups: $(groups)"

# Ensure environment variables are set
: "${USER_NAME:?Environment variable USER_NAME is not set}"
: "${WHGADMIN_PASSWORD:?Environment variable WHGADMIN_PASSWORD is not set}"

# Set the user's password using the hashed password
echo "change_me" | sudo -S usermod "$USER_NAME" --password "$(openssl passwd -1 "$WHGADMIN_PASSWORD")"

# Optionally, verify that the password has been set
echo "Password changed for $USER_NAME"
