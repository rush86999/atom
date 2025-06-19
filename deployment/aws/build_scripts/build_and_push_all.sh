#!/bin/bash
set -e

AWS_ACCOUNT_ID="${1}" # First argument
AWS_REGION="${2}"    # Second argument
IMAGE_VERSION_TAG="latest" # Or a git commit hash, etc.

if [ -z "${AWS_ACCOUNT_ID}" ] || [ -z "${AWS_REGION}" ]; then
  echo "Usage: $0 <aws_account_id> <aws_region>"
  exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

SERVICES=("functions" "handshake" "oauth" "app" "optaplanner" "python-agent") # Added python-agent

echo "Logging into AWS ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

for SERVICE_NAME in "${SERVICES[@]}"; do
  LOCAL_IMAGE_NAME="atomic-${SERVICE_NAME}"
  ECR_REPO_NAME="atomic-${SERVICE_NAME}" # Matches CDK ECR repositoryName
  ECR_IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${IMAGE_VERSION_TAG}"

  echo "--------------------------------------------------"
  echo "Building ${SERVICE_NAME}..."
  echo "--------------------------------------------------"
  if ! "${SCRIPT_DIR}/build_${SERVICE_NAME}.sh"; then
    echo "ERROR: Failed to build ${SERVICE_NAME}. Aborting."
    exit 1
  fi

  echo "--------------------------------------------------"
  echo "Tagging ${LOCAL_IMAGE_NAME}:latest as ${ECR_IMAGE_URI}..."
  echo "--------------------------------------------------"
  docker tag "${LOCAL_IMAGE_NAME}:latest" "${ECR_IMAGE_URI}"

  echo "--------------------------------------------------"
  echo "Pushing ${ECR_IMAGE_URI} to ECR..."
  echo "--------------------------------------------------"
  docker push "${ECR_IMAGE_URI}"

  echo "${SERVICE_NAME} pushed successfully to ${ECR_IMAGE_URI}"
done

echo "--------------------------------------------------"
echo "All images built and pushed successfully!"
echo "--------------------------------------------------"
