#!/bin/bash
set -e
SERVICE_NAME="optaplanner"
IMAGE_NAME="atomic-${SERVICE_NAME}"
# This context path is an assumption. User needs to ensure Dockerfile is here.
CONTEXT_PATH="../../atomic-docker/optaplanner_build_docker"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BUILD_CONTEXT="${SCRIPT_DIR}/${CONTEXT_PATH}"

echo "Building ${SERVICE_NAME} Docker image from context: ${BUILD_CONTEXT}"
if [ ! -f "${BUILD_CONTEXT}/Dockerfile" ]; then
    echo "ERROR: Dockerfile not found at ${BUILD_CONTEXT}/Dockerfile"
    echo "Please place the Optaplanner Dockerfile there or update the CONTEXT_PATH in this script."
    exit 1
fi

docker build -t "${IMAGE_NAME}:latest" "${BUILD_CONTEXT}"
echo "${SERVICE_NAME} Docker image built successfully: ${IMAGE_NAME}:latest"
