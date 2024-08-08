#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Ensure environment variables are set
: "${USER_NAME:?Environment variable USER_NAME is not set}"
: "${WHGADMIN_PASSWORD:?Environment variable WHGADMIN_PASSWORD is not set}"

# Check if the group exists; if not, create it with same name as user
if ! getent group $USER_NAME >/dev/null 2>&1; then
    groupadd -g 1000 $USER_NAME
fi

# Check if the user exists; if not, create it
if ! id -u $USER_NAME >/dev/null 2>&1; then
    useradd -m -d "/home/$USER_NAME" -s "/bin/bash" -u 1000 -g 1000 $USER_NAME
fi

# Set the user's password
echo "$USER_NAME:$WHGADMIN_PASSWORD" | chpasswd

# Grant sudo privileges to the user
if command -v sudo >/dev/null 2>&1; then
    usermod -aG sudo $USER_NAME
fi
