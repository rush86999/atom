#!/bin/bash
set -e

RDS_ENDPOINT="${1}"
# RDS_INIT_DB_USERNAME="${2}" # Removed
RDS_DB_NAME="${2}" # Was ${3}
RDS_SECRET_ARN="${3}" # Was ${4}, ARN of the RDS master user secret
AWS_REGION="${4:-us-east-1}" # Was ${5}

if [ -z "${RDS_ENDPOINT}" ] || [ -z "${RDS_DB_NAME}" ] || [ -z "${RDS_SECRET_ARN}" ]; then
  echo "Usage: $0 <rds_endpoint> <rds_db_name> <rds_secret_arn> [aws_region]"
  echo "Example: $0 my-db.cluster-xxxx.us-east-1.rds.amazonaws.com atomicdb arn:aws:secretsmanager:us-east-1:123456789012:secret:PostgresAdminCreds-XXXXXX"
  exit 1
fi

echo "Fetching RDS master credentials from Secrets Manager..."
RDS_CREDENTIALS_JSON=$(aws secretsmanager get-secret-value --secret-id "${RDS_SECRET_ARN}" --region "${AWS_REGION}" --query SecretString --output text)

RDS_INIT_DB_USERNAME=$(echo "${RDS_CREDENTIALS_JSON}" | jq -r .username)
RDS_PASSWORD=$(echo "${RDS_CREDENTIALS_JSON}" | jq -r .password)

if [ -z "${RDS_INIT_DB_USERNAME}" ] || [ -z "${RDS_PASSWORD}" ]; then
    echo "Error: Failed to fetch RDS username or password."
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
DB_SCRIPTS_PATH="${SCRIPT_DIR}/db_init_scripts"

SQL_FILES=(
  "0001-create-schema.sql"
  "atomic-schema-up.sql"
  "optaplanner-create-schema.sql"
)

# Check if psql is installed
if ! command -v psql &> /dev/null; then
    echo "psql command could not be found. Please install PostgreSQL client tools."
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "jq command could not be found. Please install jq."
    exit 1
fi

for SQL_FILE in "${SQL_FILES[@]}"; do
  FILE_PATH="${DB_SCRIPTS_PATH}/${SQL_FILE}"
  if [ -f "${FILE_PATH}" ]; then
    echo "Applying ${SQL_FILE} to database ${RDS_DB_NAME} on ${RDS_ENDPOINT}..."
    PGPASSWORD="${RDS_PASSWORD}" psql -h "${RDS_ENDPOINT}" -U "${RDS_INIT_DB_USERNAME}" -d "${RDS_DB_NAME}" -a -f "${FILE_PATH}"
  else
    echo "Warning: SQL script ${FILE_PATH} not found."
  fi
done

echo "Database initialization scripts applied."
