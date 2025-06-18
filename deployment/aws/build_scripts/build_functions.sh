#!/bin/bash
set -e
SERVICE_NAME="functions"
# Using a fixed tag for now, will be parameterized later if needed for ECR
IMAGE_NAME="atomic-${SERVICE_NAME}"
CONTEXT_PATH="../../atomic-docker/functions_build_docker"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BUILD_CONTEXT="${SCRIPT_DIR}/${CONTEXT_PATH}"

echo "Building ${SERVICE_NAME} Docker image from context: ${BUILD_CONTEXT}"
docker build -t "${IMAGE_NAME}:latest" "${BUILD_CONTEXT}"
echo "${SERVICE_NAME} Docker image built successfully: ${IMAGE_NAME}:latest"
