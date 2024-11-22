#!/bin/bash

# Check if a role (master or worker) was passed as an argument
ROLE=$1

# Ensure role is provided
if [ -z "$ROLE" ]; then
    echo "Error: Role (master or worker) must be specified."
    exit 1
fi

# Update and install dependencies
echo "Updating package list..."
sudo apt-get update
if [ $? -ne 0 ]; then
    echo "Error occurred during package list update."
    exit 1
fi

sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common jq
if [ $? -ne 0 ]; then
    echo "Error occurred during the installation of dependencies."
    exit 1
fi

sudo wget -O /usr/local/bin/yq https://github.com/mikefarah/yq/releases/download/v4.13.0/yq_linux_amd64
if [ $? -ne 0 ]; then
    echo "Error occurred while downloading yq."
    exit 1
fi

sudo chmod +x /usr/local/bin/yq

# Define script directory
SCRIPT_DIR=$(dirname "$0")

# Load configuration from YAML files
DOCKER_VERSION=$(yq eval '.docker.version' "$SCRIPT_DIR/system/docker-config.yaml")
DOCKER_REPO_URL=$(yq eval '.docker.repo_url' "$SCRIPT_DIR/system/docker-config.yaml")
DOCKER_REPO_KEY=$(yq eval '.docker.repo_key' "$SCRIPT_DIR/system/docker-config.yaml")
KUBE_VERSION=$(yq eval '.kubernetes.version' "$SCRIPT_DIR/system/kubernetes-config.yaml")
POD_NETWORK_CIDR=$(yq eval '.kubernetes.pod_network_cidr' "$SCRIPT_DIR/system/kubernetes-config.yaml")
HELM_VERSION=$(yq eval '.helm.version' "$SCRIPT_DIR/system/helm-config.yaml")
HELM_REPO_URL=$(yq eval '.helm.repo_url' "$SCRIPT_DIR/system/helm-config.yaml")
VESPA_VERSION=$(yq eval '.vespa.version' "$SCRIPT_DIR/system/vespa-config.yaml")
VESPA_DOWNLOAD_URL=$(yq eval '.vespa.download_url' "$SCRIPT_DIR/system/vespa-config.yaml")

# Install Docker
echo "Installing Docker version $DOCKER_VERSION..."
curl -fsSL "$DOCKER_REPO_KEY" | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] $DOCKER_REPO_URL $(lsb_release -cs) stable"
sudo apt-get update
sudo apt-get install -y docker-ce=$DOCKER_VERSION
if [ $? -ne 0 ]; then
    echo "Error occurred while adding Docker repository key."
    exit 1
fi

sudo systemctl enable docker
sudo systemctl start docker
sudo docker --version
sudo usermod -aG docker $USER

# Install Kubernetes
echo "Installing Kubernetes version $KUBE_VERSION..."
sudo apt-get install -y kubeadm=$KUBE_VERSION kubelet=$KUBE_VERSION kubectl=$KUBE_VERSION
if [ $? -ne 0 ]; then
    echo "Error occurred during Kubernetes installation."
    exit 1
fi

sudo apt-mark hold kubeadm kubelet kubectl
kubectl version --client
if [ $? -ne 0 ]; then
    echo "Error occurred while checking Kubernetes version."
    exit 1
fi

# Disable swap (required for Kubernetes)
echo "Disabling swap..."
sudo swapoff -a
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

if [ "$ROLE" == "master" ]; then
  # Initialize Kubernetes cluster
  echo "Initializing Kubernetes cluster with pod network CIDR $POD_NETWORK_CIDR..."
  sudo kubeadm init --pod-network-cidr=$POD_NETWORK_CIDR
  if [ $? -ne 0 ]; then
      echo "Error occurred during Kubernetes cluster initialization."
      exit 1
  fi
elif [ "$ROLE" == "worker" ]; then
  # Ensure JOIN_COMMAND is passed as an argument
  if [ -z "$JOIN_COMMAND" ]; then
      echo "Error: JOIN_COMMAND must be provided to join the worker node."
      exit 1
  fi

  # Join the worker node to the Kubernetes cluster
  echo "Joining the worker node to the Kubernetes cluster using the provided join command..."
  sudo $JOIN_COMMAND
  if [ $? -ne 0 ]; then
      echo "Error occurred while joining the worker node to the Kubernetes cluster."
      exit 1
  fi
fi

# Configure kubectl
echo "Configuring kubectl..."
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
kubectl get nodes
kubectl get pods -n kube-system
if [ $? -ne 0 ]; then
    echo "Error occurred while configuring kubectl."
    exit 1
fi

# Install Helm
echo "Installing Helm version $HELM_VERSION..."
curl -fsSL "$HELM_REPO_URL/helm-v$HELM_VERSION-linux-amd64.tar.gz" -o helm.tar.gz
if [ $? -ne 0 ]; then
    echo "Error occurred while downloading Helm."
    exit 1
fi

tar -zxvf helm.tar.gz
sudo mv linux-amd64/helm /usr/local/bin/helm
sudo rm -rf linux-amd64 helm.tar.gz
helm version
if [ $? -ne 0 ]; then
    echo "Error occurred while checking Helm version."
    exit 1
fi

# Install Flannel
echo "Installing Flannel for Kubernetes..."
kubectl apply -f "$SCRIPT_DIR/system/flannel-config.yaml"
kubectl get pods -n kube-system -l app=flannel
if [ $? -ne 0 ]; then
    echo "Error occurred during Flannel installation."
    exit 1
fi

if [ "$ROLE" == "master" ]; then
  # Install Contour
  echo "Installing Contour Ingress controller..."
  kubectl apply -f "$SCRIPT_DIR/system/contour-config.yaml"
  kubectl get pods -n projectcontour
  if [ $? -ne 0 ]; then
      echo "Error occurred during Contour installation."
      exit 1
  fi
fi

# Install Vespa CLI
echo "Installing Vespa CLI version $VESPA_VERSION..."
curl -LO $VESPA_DOWNLOAD_URL
if [ $? -ne 0 ]; then
    echo "Error occurred while downloading Vespa CLI."
    exit 1
fi

tar -xvf vespa-cli_${VESPA_VERSION}_linux_amd64.tar.gz
sudo mv vespa-cli_${VESPA_VERSION}_linux_amd64/bin/vespa /usr/local/bin/
sudo rm -rf vespa-cli_${VESPA_VERSION}_linux_amd64 vespa-cli_${VESPA_VERSION}_linux_amd64.tar.gz
vespa version || { echo "Vespa CLI installation failed"; exit 1; }

echo "Deployment complete!"

# Deploy Vespa manifests
echo "Deploying Vespa components..."
kubectl apply -f "$SCRIPT_DIR/vespa/content-node-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/vespa/search-node-deployment.yaml"
if [ "$ROLE" == "master" ]; then
  kubectl apply -f "$SCRIPT_DIR/vespa/config-server-deployment.yaml"
  kubectl apply -f "$SCRIPT_DIR/vespa/vespa-ingress.yaml"
fi

# Deploy Django and Tile services
if [ "$ROLE" == "master" ]; then
  bash "$SCRIPT_DIR/deploy-django.sh"
  bash "$SCRIPT_DIR/deploy-tile-services.sh"
fi

# Print instructions for deployment of worker nodes
if [ "$ROLE" == "master" ]; then
  # Print the join command for workers
  JOIN_COMMAND=$(kubeadm token create --print-join-command)
  echo "-------------------------------------------------------------"
  echo "To join worker nodes to the cluster, run this deployment script with the following parameters:"
  echo "sudo ./server-configuration/deploy.sh ROLE=worker JOIN_COMMAND=\"$JOIN_COMMAND\""
fi
