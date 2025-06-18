#!/bin/bash
set -e
SERVICE_NAME="handshake"
IMAGE_NAME="atomic-${SERVICE_NAME}"
CONTEXT_PATH="../../atomic-docker/handshake_build_docker"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BUILD_CONTEXT="${SCRIPT_DIR}/${CONTEXT_PATH}"

echo "Building ${SERVICE_NAME} Docker image from context: ${BUILD_CONTEXT}"
# Placeholder for required build ARGs from docker-compose.yaml
# Example: --build-arg API_TOKEN=\$API_TOKEN
# These will need to be sourced from somewhere in a real deployment script
docker build \
  --build-arg API_TOKEN="dummy_token" \
  --build-arg HASURA_GRAPHQL_ADMIN_SECRET="dummy_secret" \
  --build-arg NEXT_PUBLIC_ATOMIC_HANDSHAKE_API="http://dummy/api" \
  --build-arg HASURA_GRAPHQL_GRAPHQL_URL="http://dummy/v1/graphql" \
  --build-arg MEETING_ASSIST_ADMIN_URL="http://dummy/admin" \
  -t "${IMAGE_NAME}:latest" "${BUILD_CONTEXT}"
echo "${SERVICE_NAME} Docker image built successfully: ${IMAGE_NAME}:latest"
