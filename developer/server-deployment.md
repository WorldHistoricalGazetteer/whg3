# Installation Instructions for Kubernetes and Vespa

## Architecture

- **Docker**: A containerization platform that allows for the deployment of applications in containers.
- `kubeadm`: A tool used to bootstrap Kubernetes clusters.
- `kubelet`: The primary node agent that runs on each node.
- `kubectl`: A command-line tool for interacting with clusters.
- **Helm**: A package manager for Kubernetes.
- **Flannel**: A virtual network that gives a subnet to each host for use with container runtimes.
- **Contour**: An Ingress controller for Kubernetes that works by deploying Envoy Proxy as a reverse proxy and load
  balancer.
- **Vespa**: A platform for scalable serving of data and content.
- **Django**: A high-level Python web framework on which WHG is built.
- **PostgreSQL**: A powerful, open-source object-relational database system.
- **Redis**: An open-source, in-memory data structure store used as a database, cache, and message broker.
- **Celery**: A distributed task queue that is used to handle asynchronous tasks in WHG.
- **Celery Beat**: A scheduler that is used to schedule periodic tasks in WHG.
- **Tileserver-GL**: A server for serving map tiles.
- **Tippecanoe**: A tool for building vector tilesets from large collections of GeoJSON features (runs in Node.js).

## After pulling the repository from GitHub, run `deploy.sh` from the project root

```bash
SCRIPT_DIR="./server-configuration"
chmod +x $SCRIPT_DIR/*.sh
sudo $SCRIPT_DIR/deploy.sh
```
