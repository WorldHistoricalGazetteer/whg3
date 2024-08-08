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
sudo usermod "$USER_NAME" --password "$(openssl passwd -1 "$WHGADMIN_PASSWORD")"
echo "Password changed for $USER_NAME"

sudo cat /etc/sudoers

# Remove the user from passwordless sudoers
echo "$WHGADMIN_PASSWORD" | sudo -S sed -i "/$USER_NAME ALL=(ALL) NOPASSWD: ALL/d" /etc/sudoers

echo "$WHGADMIN_PASSWORD" | sudo -S cat /etc/sudoers
