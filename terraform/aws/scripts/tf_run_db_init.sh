#!/bin/bash
set -e

RDS_ENDPOINT="${1}"
RDS_DB_NAME="${2}"
RDS_SECRET_ARN="${3}" # ARN of the RDS master user secret
AWS_REGION="${4:-us-east-1}" # Default if not provided

if [ -z "${RDS_ENDPOINT}" ] || [ -z "${RDS_DB_NAME}" ] || [ -z "${RDS_SECRET_ARN}" ]; then
  echo "Usage: $0 <rds_endpoint> <rds_db_name> <rds_secret_arn> [aws_region]"
  echo "Obtain values from 'terraform output' (e.g., db_instance_address, db_instance_name, db_credentials_secret_arn)."
  exit 1
fi

echo "Fetching RDS master credentials from Secrets Manager..."
RDS_CREDENTIALS_JSON=$(aws secretsmanager get-secret-value --secret-id "${RDS_SECRET_ARN}" --region "${AWS_REGION}" --query SecretString --output text)

RDS_INIT_DB_USERNAME=$(echo "${RDS_CREDENTIALS_JSON}" | jq -r .username)
RDS_PASSWORD=$(echo "${RDS_CREDENTIALS_JSON}" | jq -r .password)

if [ -z "${RDS_INIT_DB_USERNAME}" ] || [ -z "${RDS_PASSWORD}" ]; then
    echo "Error: Failed to fetch RDS username or password from secret: ${RDS_SECRET_ARN}"
    exit 1
fi

SCRIPT_DIR_RELATIVE_TO_TF_AWS_ROOT="scripts" # This script is in terraform/aws/scripts
DB_SCRIPTS_PATH_FROM_TF_AWS_ROOT="db_init_scripts" # SQL files are in terraform/aws/db_init_scripts
# Correct path from where the script is run (terraform/aws/scripts) to SQL files
DB_SCRIPTS_ACTUAL_PATH="../${DB_SCRIPTS_PATH_FROM_TF_AWS_ROOT}"


SQL_FILES=(
  "0001-create-schema.sql"
  "atomic-schema-up.sql"
  "optaplanner-create-schema.sql"
)

if ! command -v psql &> /dev/null; then
    echo "psql command could not be found. Please install PostgreSQL client tools."
    exit 1
fi
if ! command -v jq &> /dev/null; then
    echo "jq command could not be found. Please install jq."
    exit 1
fi

for SQL_FILE in "${SQL_FILES[@]}"; do
  FILE_PATH="${DB_SCRIPTS_ACTUAL_PATH}/${SQL_FILE}"
  if [ -f "${FILE_PATH}" ]; then
    echo "Applying ${SQL_FILE} to database ${RDS_DB_NAME} on ${RDS_ENDPOINT}..."
    PGPASSWORD="${RDS_PASSWORD}" psql -h "${RDS_ENDPOINT}" -U "${RDS_INIT_DB_USERNAME}" -d "${RDS_DB_NAME}" -a -f "${FILE_PATH}"
  else
    echo "Warning: SQL script ${FILE_PATH} not found."
  fi
done

echo "Database initialization scripts applied."
