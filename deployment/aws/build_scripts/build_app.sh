#!/bin/bash
set -e
SERVICE_NAME="app"
IMAGE_NAME="atomic-${SERVICE_NAME}"
CONTEXT_PATH="../../atomic-docker/app_build_docker"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BUILD_CONTEXT="${SCRIPT_DIR}/${CONTEXT_PATH}"

echo "Building ${SERVICE_NAME} Docker image from context: ${BUILD_CONTEXT}"
# Placeholder for required build ARGs
docker build \
  --build-arg HASURA_GRAPHQL_ADMIN_SECRET="dummy_secret" \
  --build-arg NEXT_PUBLIC_ATOMIC_HANDSHAKE_API="http://dummy/api" \
  --build-arg HASURA_GRAPHQL_GRAPHQL_URL="http://dummy/v1/graphql" \
  --build-arg NEXT_PUBLIC_HASURA_GRAPHQL_GRAPHQL_URL="http://dummy/v1/graphql_public" \
  --build-arg NEXT_PUBLIC_HASURA_GRAPHQL_GRAPHQL_WS_URL="ws://dummy/v1/graphql_ws" \
  --build-arg NEXT_PUBLIC_EVENT_TO_QUEUE_AUTH_URL="http://dummy/eventq" \
  --build-arg NEXT_PUBLIC_EVENT_TO_QUEUE_SHORT_AUTH_URL="http://dummy/eventqshort" \
  --build-arg NEXT_PUBLIC_CALENDAR_TO_QUEUE_AUTH_URL="http://dummy/calq" \
  --build-arg NEXT_PUBLIC_FEATURES_APPLY_TO_EVENTS_AUTH_URL="http://dummy/featuresapply" \
  --build-arg NEXT_PUBLIC_METHOD_TO_SEARCH_INDEX_AUTH_URL="http://dummy/searchindex" \
  --build-arg NEXT_PUBLIC_GOOGLE_CALENDAR_ANDROID_AUTH_URL="http://dummy/gcandroid" \
  --build-arg NEXT_PUBLIC_GOOGLE_CALENDAR_ANDROID_AUTH_REFRESH_URL="http://dummy/gcandroidrefresh" \
  --build-arg NEXT_PUBLIC_GOOGLE_ATOMIC_WEB_AUTH_REFRESH_URL="http://dummy/gcwebrefresh" \
  --build-arg NEXT_PUBLIC_GOOGLE_CALENDAR_IOS_AUTH_REFRESH_URL="http://dummy/gciosrefresh" \
  --build-arg NEXT_PUBLIC_GOOGLE_OAUTH_ATOMIC_WEB_API_START_URL="http://dummy/googlewebapistart" \
  --build-arg NEXT_PUBLIC_GOOGLE_OAUTH_ATOMIC_WEB_REDIRECT_URL="http://dummy/googlewebredirect" \
  --build-arg GOOGLE_CLIENT_ID_ATOMIC_WEB="dummy_google_client_id_web" \
  --build-arg GOOGLE_CLIENT_SECRET_ATOMIC_WEB="dummy_google_client_secret_web" \
  --build-arg ZOOM_IV_FOR_PASS="dummy_zoom_iv" \
  --build-arg ZOOM_SALT_FOR_PASS="dummy_zoom_salt" \
  --build-arg ZOOM_PASS_KEY="dummy_zoom_key" \
  --build-arg NEXT_PUBLIC_EMAIL_MEETING_INFO_TO_HOST_URL="http://dummy/emailhost" \
  --build-arg NEXT_PUBLIC_EMAIL_MEETING_INVITE_URL="http://dummy/emailinvite" \
  --build-arg NEXT_PUBLIC_EMAIL_MEETING_CANCEL_URL="http://dummy/emailcancel" \
  --build-arg NEXT_PUBLIC_HANDSHAKE_URL="http://dummy/handshakeurl" \
  --build-arg NEXT_PUBLIC_DELETE_ZOOM_CONFERENCE_URL="http://dummy/deletezoom" \
  --build-arg NEXT_PUBLIC_GOOGLE_CALENDAR_SYNC_URL="http://dummy/gcsync" \
  --build-arg NEXT_PUBLIC_SELF_GOOGLE_CALENDAR_WATCH_URL="http://dummy/gcwatch" \
  --build-arg NEXT_PUBLIC_GOOGLE_OAUTH_START_URL="http://dummy/gcauthstart" \
  --build-arg NEXT_PUBLIC_CHAT_WS_API_URL="ws://dummy/chatws" \
  --build-arg NEXT_PUBLIC_GOOGLE_PEOPLE_SYNC_URL="http://dummy/peoplesync" \
  --build-arg NEXT_PUBLIC_ADD_DAILY_FEATURES_AUTOPILOT_URL="http://dummy/autopilotfeatures" \
  --build-arg NEXT_PUBLIC_DELETE_SCHEDULED_EVENT_URL="http://dummy/autopilotdelete" \
  --build-arg NEXT_PUBLIC_ZOOM_CREATE_MEETING_URL="http://dummy/zoomcreate" \
  --build-arg NEXT_PUBLIC_ZOOM_UPDATE_MEETING_URL="http://dummy/zoomupdate" \
  --build-arg NEXT_PUBLIC_ZOOM_DELETE_MEETING_URL="http://dummy/zoomdelete" \
  --build-arg NEXT_PUBLIC_ZOOM_OAUTH_START_URL="http://dummy/zoomauthstart" \
  -t "${IMAGE_NAME}:latest" "${BUILD_CONTEXT}"
echo "${SERVICE_NAME} Docker image built successfully: ${IMAGE_NAME}:latest"
