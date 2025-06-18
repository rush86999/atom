#!/bin/bash
set -e
SERVICE_NAME="oauth"
IMAGE_NAME="atomic-${SERVICE_NAME}"
CONTEXT_PATH="../../atomic-docker/oauth_build_docker"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BUILD_CONTEXT="${SCRIPT_DIR}/${CONTEXT_PATH}"

echo "Building ${SERVICE_NAME} Docker image from context: ${BUILD_CONTEXT}"
# Placeholder for required build ARGs
docker build \
  --build-arg HASURA_GRAPHQL_GRAPHQL_URL="http://dummy/v1/graphql" \
  --build-arg HASURA_GRAPHQL_ADMIN_SECRET="dummy_secret" \
  --build-arg NEXT_PUBLIC_APP_URL="http://dummyapp" \
  --build-arg GOOGLE_CLIENT_ID_WEB="dummy_google_id" \
  --build-arg GOOGLE_CLIENT_SECRET_WEB="dummy_google_secret" \
  --build-arg GOOGLE_REDIRECT_URL="http://dummy/redirect" \
  --build-arg HANDSHAKE_URL="http://dummy_handshake" \
  --build-arg ZOOM_IV_FOR_PASS="dummy_iv" \
  --build-arg ZOOM_SALT_FOR_PASS="dummy_salt" \
  --build-arg ZOOM_PASS_KEY="dummy_key" \
  --build-arg ZOOM_CLIENT_SECRET="dummy_zoom_secret" \
  --build-arg ZOOM_WEBHOOK_SECRET_TOKEN="dummy_webhook_secret" \
  --build-arg NEXT_PUBLIC_ZOOM_REDIRECT_URL="http://dummy/zoom_redirect" \
  --build-arg NEXT_PUBLIC_ZOOM_CLIENT_ID="dummy_zoom_client_id" \
  --build-arg ZOOM_CLIENT_ID="dummy_zoom_client_id_2" \
  -t "${IMAGE_NAME}:latest" "${BUILD_CONTEXT}"
echo "${SERVICE_NAME} Docker image built successfully: ${IMAGE_NAME}:latest"
