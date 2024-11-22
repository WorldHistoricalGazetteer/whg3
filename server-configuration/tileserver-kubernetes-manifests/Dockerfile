FROM node:16

# Install Tippecanoe
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    cmake \
    wget \
    libboost-all-dev \
    libsqlite3-dev \
    && wget https://github.com/mapbox/tippecanoe/releases/download/v2.16.0/tippecanoe-v2.16.0-x86_64-linux.tar.gz \
    && tar -xvzf tippecanoe-v2.16.0-x86_64-linux.tar.gz \
    && mv tippecanoe /usr/local/bin/ \
    && rm -rf tippecanoe-v2.16.0-x86_64-linux.tar.gz

# Set up the Node application
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .

# Expose the application port
EXPOSE 8080

CMD ["node", "index.js"]
