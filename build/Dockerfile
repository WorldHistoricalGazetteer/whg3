FROM --platform=linux/amd64 python:3.10.7-slim-bullseye

LABEL maintainer="WHC @ Pitt"

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV MAX_MAP_COUNT 262144

EXPOSE 8000

COPY ./requirements.txt /tmp/requirements.txt
    
RUN set -eux; \
    # Update package lists
    apt-get update && \
    # Install necessary packages
    apt-get install -y --no-install-recommends \
        lsb-release \
        curl \
        gnupg2 \
        build-essential \
        python3-gdal \
        libpq-dev \
        sudo \
        nano \
        locate \
        netcat \
        docker.io && \
    # Set up Python virtual environment
    python -m venv /py && \
    /py/bin/pip install --upgrade pip && \
    /py/bin/pip install -r /tmp/requirements.txt && \
    # Clean up unused packages, lists, and temporary files to reduce image size
    apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false && \
    rm -rf /var/lib/apt/lists/* /tmp && \
    # Create directories and set ownership
    mkdir -p /app/static && \
    chown -R 1000:1000 /app/static && \
    chown -R 1000:0 /py/lib/python3.10/site-packages/captcha/migrations/ /py/lib/python3.10/site-packages/guardian/migrations/    

WORKDIR /app

ENV PATH="/py/bin:$PATH"

# Each service has a different `entrypoint.sh`, mounted in the compose file
ENTRYPOINT ["/entrypoint.sh"]
