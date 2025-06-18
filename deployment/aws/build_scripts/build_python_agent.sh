#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

LOCAL_IMAGE_NAME="atomic-python-agent" # Standardized local image name
IMAGE_TAG="latest"
# Path to the Dockerfile directory, relative to this script's location (deployment/aws/build_scripts/)
DOCKERFILE_DIR="../../atomic-docker/python_agent_build_docker"

echo "Building local Docker image: $LOCAL_IMAGE_NAME:$IMAGE_TAG"

# The DOCKERFILE_DIR is the build context. The Dockerfile is in DOCKERFILE_DIR.
# Dockerfile COPY ../project assumes context is DOCKERFILE_DIR.
docker build -t "$LOCAL_IMAGE_NAME:$IMAGE_TAG" -f "$DOCKERFILE_DIR/Dockerfile" "$DOCKERFILE_DIR"

echo "Python Agent local image build complete: $LOCAL_IMAGE_NAME:$IMAGE_TAG"
