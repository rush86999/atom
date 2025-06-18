#!/bin/bash
set -e

ALB_DNS_NAME="${1}"
HASURA_ADMIN_SECRET_ARN="${2}"
AWS_REGION="${3:-us-east-1}"

if [ -z "${ALB_DNS_NAME}" ] || [ -z "${HASURA_ADMIN_SECRET_ARN}" ]; then
  echo "Usage: $0 <alb_dns_name> <hasura_admin_secret_arn> [aws_region]"
  echo "Obtain values from 'terraform output' (e.g., alb_dns_name, hasura_admin_secret_arn)."
  exit 1
fi

echo "Fetching Hasura admin secret..."
# Assuming the secret stores the raw admin secret string, not a JSON object
# If it's JSON like {"HASURA_GRAPHQL_ADMIN_SECRET":"value"}, then jq is needed as in CDK script
# The Terraform 'hasura_admin_secret' was created with a random password string directly.
HASURA_ADMIN_SECRET_VALUE=$(aws secretsmanager get-secret-value --secret-id "${HASURA_ADMIN_SECRET_ARN}" --region "${AWS_REGION}" --query SecretString --output text)

if [ -z "${HASURA_ADMIN_SECRET_VALUE}" ]; then
    echo "Error: Failed to fetch Hasura admin secret: ${HASURA_ADMIN_SECRET_ARN}"
    exit 1
fi

HASURA_ENDPOINT="http://${ALB_DNS_NAME}/v1/graphql"
# This script is in terraform/aws/scripts. Project root is ../../
# Hasura metadata project dir is ../../atomic-docker/project
METADATA_PROJECT_DIR_RELATIVE_TO_SCRIPT="../../atomic-docker/project"

echo "Applying Hasura metadata to endpoint: ${HASURA_ENDPOINT}"
echo "Using metadata from: $(cd "$(dirname "$0")" && cd "${METADATA_PROJECT_DIR_RELATIVE_TO_SCRIPT}" && pwd)/metadata"


if ! command -v hasura &> /dev/null; then
    echo "Hasura CLI could not be found. Please install it first."
    echo "See: https://hasura.io/docs/latest/hasura-cli/install-hasura-cli/"
    exit 1
fi

CURRENT_DIR=$(pwd)
# Navigate to the correct directory for Hasura CLI
TARGET_HASURA_DIR_FOR_CLI="$(dirname "$0")/${METADATA_PROJECT_DIR_RELATIVE_TO_SCRIPT}"

if [ ! -d "${TARGET_HASURA_DIR_FOR_CLI}/metadata" ]; then
    echo "Error: Hasura metadata directory not found at ${TARGET_HASURA_DIR_FOR_CLI}/metadata"
    exit 1
fi

cd "${TARGET_HASURA_DIR_FOR_CLI}"

hasura metadata apply --endpoint "${HASURA_ENDPOINT}" --admin-secret "${HASURA_ADMIN_SECRET_VALUE}"

cd "${CURRENT_DIR}" # Return to original directory
echo "Hasura metadata applied successfully."
