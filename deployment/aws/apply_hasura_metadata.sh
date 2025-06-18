#!/bin/bash
set -e

ALB_DNS_NAME="${1}"
HASURA_ADMIN_SECRET_ARN="${2}"
AWS_REGION="${3:-us-east-1}" # Default region if not provided

if [ -z "${ALB_DNS_NAME}" ] || [ -z "${HASURA_ADMIN_SECRET_ARN}" ]; then
  echo "Usage: $0 <alb_dns_name> <hasura_admin_secret_arn> [aws_region]"
  echo "Example: $0 my-alb-dns.amazonaws.com arn:aws:secretsmanager:us-east-1:123456789012:secret:HasuraAdminSecret-XXXXXX us-east-1"
  exit 1
fi

echo "Fetching Hasura admin secret..."
# Assuming the secret stores a JSON where the key is HASURA_GRAPHQL_ADMIN_SECRET_VALUE and the value is the actual secret
# This was based on 'generateStringKey: "HASURA_GRAPHQL_ADMIN_SECRET_VALUE"' in the Secret construct.
# If the secret directly stores the string, the jq query would be simpler (e.g. | jq -r .)
# If the secret JSON key is 'HASURA_GRAPHQL_ADMIN_SECRET' (from secretStringTemplate), then use that.
# The current Hasura Admin Secret is: secretStringTemplate: JSON.stringify({ HASURA_GRAPHQL_ADMIN_SECRET: 'dummyPasswordPlaceholder' }), generateStringKey: 'HASURA_GRAPHQL_ADMIN_SECRET_VALUE'
# So the value is under HASURA_GRAPHQL_ADMIN_SECRET_VALUE if generateStringKey was used for the *value*.
# Or, if secretStringTemplate defines the whole JSON, then the key inside that JSON.
# The secret definition is: generateSecretString: { secretStringTemplate: JSON.stringify({ HASURA_GRAPHQL_ADMIN_SECRET: 'dummyPasswordPlaceholder' }), generateStringKey: 'HASURA_GRAPHQL_ADMIN_SECRET_VALUE', ... }
# This means the secret string IS the template, and then another key 'HASURA_GRAPHQL_ADMIN_SECRET_VALUE' is added with a generated value. This is likely not what was intended.
# The intention was probably: secretValue: cdk.SecretValue.unsafePlainText(JSON.stringify({ HASURA_GRAPHQL_ADMIN_SECRET: "YOUR_INITIAL_PW_HERE" })) OR auto-generated with a specific key.
# Given: generateSecretString: { secretStringTemplate: JSON.stringify({ HASURA_GRAPHQL_ADMIN_SECRET: 'dummyPasswordPlaceholder' }), generateStringKey: 'HASURA_GRAPHQL_ADMIN_SECRET_VALUE', ...}
# The actual secret string will be '{"HASURA_GRAPHQL_ADMIN_SECRET":"dummyPasswordPlaceholder","HASURA_GRAPHQL_ADMIN_SECRET_VALUE":"generated_value"}'.
# We need the "generated_value" if that's the one Hasura uses, or "dummyPasswordPlaceholder" if the template key is the one.
# The Hasura container uses ecs.Secret.fromSecretsManager(this.hasuraAdminSecret) which defaults to the full secret JSON or a specific JSON field if specified.
# The Hasura container's HASURA_GRAPHQL_ADMIN_SECRET is mapped from this.hasuraAdminSecret. This secret has generateStringKey: 'HASURA_GRAPHQL_ADMIN_SECRET_VALUE'.
# So, the container will receive the *value* of HASURA_GRAPHQL_ADMIN_SECRET_VALUE as its env var.
HASURA_ADMIN_SECRET_VALUE=$(aws secretsmanager get-secret-value --secret-id "${HASURA_ADMIN_SECRET_ARN}" --region "${AWS_REGION}" --query SecretString --output text | jq -r .HASURA_GRAPHQL_ADMIN_SECRET_VALUE)


if [ -z "${HASURA_ADMIN_SECRET_VALUE}" ]; then
    echo "Error: Failed to fetch Hasura admin secret (jq query '.HASURA_GRAPHQL_ADMIN_SECRET_VALUE'). Check secret structure and ARN."
    # Attempt fetching the other possible key for debugging:
    ALT_SECRET_VALUE=$(aws secretsmanager get-secret-value --secret-id "${HASURA_ADMIN_SECRET_ARN}" --region "${AWS_REGION}" --query SecretString --output text | jq -r .HASURA_GRAPHQL_ADMIN_SECRET)
    echo "Alternative fetch attempt (jq query '.HASURA_GRAPHQL_ADMIN_SECRET') yielded: '${ALT_SECRET_VALUE}'"
    exit 1
fi

HASURA_ENDPOINT="http://${ALB_DNS_NAME}/v1/graphql"
METADATA_PROJECT_DIR="atomic-docker/project"

echo "Applying Hasura metadata to endpoint: ${HASURA_ENDPOINT}"
echo "Using metadata from: ${METADATA_PROJECT_DIR}/metadata"

if ! command -v hasura &> /dev/null; then
    echo "Hasura CLI could not be found. Please install it first."
    echo "See: https://hasura.io/docs/latest/hasura-cli/install-hasura-cli/"
    exit 1
fi

if [ ! -d "${METADATA_PROJECT_DIR}/metadata" ]; then
    echo "Error: Hasura metadata directory not found at ${METADATA_PROJECT_DIR}/metadata"
    echo "Please ensure you are running this script from the repository root or adjust METADATA_PROJECT_DIR."
    exit 1
fi

# Ensure jq is installed for secret parsing
if ! command -v jq &> /dev/null; then
    echo "jq command could not be found. Please install jq."
    exit 1
fi

CURRENT_DIR=$(pwd)
echo "Current directory: ${CURRENT_DIR}. Changing to ${METADATA_PROJECT_DIR} for Hasura CLI commands."
cd "${METADATA_PROJECT_DIR}"

echo "Applying metadata..."
hasura metadata apply --endpoint "${HASURA_ENDPOINT}" --admin-secret "${HASURA_ADMIN_SECRET_VALUE}"

# Optional: Apply migrations if they exist and are managed this way
if [ -d "migrations" ]; then
  MIGRATIONS_EXIST=$(find migrations -mindepth 2 -name '*.up.sql' -print -quit) # Check if any up migration files exist
  if [ -n "$MIGRATIONS_EXIST" ]; then
    echo "Applying migrations..."
    hasura migrate apply --endpoint "${HASURA_ENDPOINT}" --admin-secret "${HASURA_ADMIN_SECRET_VALUE}" --all-databases
  else
    echo "No migration files found in migrations directory. Skipping migrations."
  fi
else
  echo "Migrations directory not found. Skipping migrations."
fi

cd "${CURRENT_DIR}" # Return to original directory
echo "Hasura metadata applied successfully."
