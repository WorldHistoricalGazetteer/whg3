FROM python:3.10.7-slim-bullseye

LABEL maintainer="WHC @ Pitt"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MAX_MAP_COUNT=262144

ARG USER_NAME

# Combine system package installation, Vespa tool installation, and cleanup into a single layer
RUN set -eux; \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3-gdal \
        libpq-dev \
        curl \
        rsync \
        file \
        gpgv \
        lsb-release \
        sudo \
        nano \
        locate \
        netcat \
        procps \
        psmisc \
        git \
        unzip \
        tar \
        default-jre \
        openjdk-11-jdk && \
    # Install Vespa tools
    mkdir -p /usr/local/vespa && \
    # Download and extract vespa-feed-client-cli
    curl -o /usr/local/vespa/vespa-feed-client-cli.zip https://repo1.maven.org/maven2/com/yahoo/vespa/vespa-feed-client-cli/8.458.13/vespa-feed-client-cli-8.458.13-zip.zip && \
    unzip -o /usr/local/vespa/vespa-feed-client-cli.zip -d /usr/local/vespa && \
    rm /usr/local/vespa/vespa-feed-client-cli.zip && \
    chmod +x /usr/local/vespa/vespa-feed-client-cli/vespa-feed-client && \
    ln -s /usr/local/vespa/vespa-feed-client-cli/vespa-feed-client /usr/local/bin/vespa-feed-client-cli && \
    # Download and extract vespa-cli
    curl -L -o /usr/local/vespa/vespa-cli.tar.gz https://github.com/vespa-engine/vespa/releases/download/v8.453.24/vespa-cli_8.453.24_linux_amd64.tar.gz && \
    tar -xzf /usr/local/vespa/vespa-cli.tar.gz -C /usr/local/vespa && \
    mv /usr/local/vespa/vespa-cli_* /usr/local/vespa/vespa-cli && \
    rm /usr/local/vespa/vespa-cli.tar.gz && \
    chmod +x /usr/local/vespa/vespa-cli && \
    ln -s /usr/local/vespa/vespa-cli /usr/local/bin/vespa-cli && \
    # Cleanup
    apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false && \
    rm -rf /var/lib/apt/lists/*

# Set up Python virtual environment and install Python dependencies
COPY ./requirements.txt /tmp/requirements.txt
RUN python -m venv /py && \
    /py/bin/pip install --upgrade pip && \
    /py/bin/pip install -r /tmp/requirements.txt && \
    apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false && \
    rm -rf /var/lib/apt/lists/* /tmp

# Add group and user
RUN groupadd -g 1000 "$USER_NAME" && \
    useradd -rm -d "/home/$USER_NAME" -g "$USER_NAME" -s "/bin/bash" -G sudo -u 1000 "$USER_NAME" -p "$(openssl passwd -1 change_me)" && \
    # Create a new sudoers file for the user
    echo "$USER_NAME ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/"$USER_NAME" && \
    # Set ownership
    chown -R 1000:0 /py/lib/python3.10/site-packages/captcha/migrations/ /py/lib/python3.10/site-packages/guardian/migrations/

# Set working directory
WORKDIR /app

# Set environment variable for the virtual environment path
ENV PATH="/py/bin:$PATH"

USER "$USER_NAME"

# Each service has a different `entrypoint.sh`, mounted in the compose file
ENTRYPOINT ["/entrypoint.sh"]
