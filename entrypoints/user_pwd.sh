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
echo "$(openssl passwd -1 "$WHGADMIN_PASSWORD")" | sudo -S sed -i "/$USER_NAME ALL=(ALL) NOPASSWD: ALL/d" /etc/sudoers

sudo cat /etc/sudoers

# Verify that the user was removed from sudoers
if ! sudo grep -q "$USER_NAME ALL=(ALL) NOPASSWD: ALL" /etc/sudoers; then
    echo "$USER_NAME has been removed from passwordless sudoers"
else
    echo "Failed to remove $USER_NAME from passwordless sudoers"
fi
