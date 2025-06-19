#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

AWS_ACCOUNT_ID="${1}"
AWS_REGION="${2}"
CDK_STACK_NAME="${3:-AwsStack}" # Default stack name, ensure it matches your CDK app

if [ -z "${AWS_ACCOUNT_ID}" ] || [ -z "${AWS_REGION}" ]; then
  echo "Usage: $0 <aws_account_id> <aws_region> [cdk_stack_name]"
  echo "Example: $0 123456789012 us-east-1 MyAtomicCDKStack"
  exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
OUTPUT_FILE="${SCRIPT_DIR}/cdk-outputs.json"

# Check for AWS CLI, CDK, jq, Docker
if ! command -v aws &> /dev/null || \
   ! command -v cdk &> /dev/null || \
   ! command -v jq &> /dev/null || \
   ! command -v docker &> /dev/null; then
    echo "Error: Required tools (aws cli, cdk, jq, docker) are not installed or not in PATH." >&2
    exit 1
fi
echo "All prerequisite tools are available."

echo -e "\n=== Section 1: Building and Pushing Docker Images ==="
echo "--- Starting Docker image build and push ---"
if ! "${SCRIPT_DIR}/build_scripts/build_and_push_all.sh" "${AWS_ACCOUNT_ID}" "${AWS_REGION}"; then
    echo "Error: Docker image build and push failed." >&2
    exit 1
fi
echo "--- Finished Docker image build and push successfully ---"

echo -e "\n=== Section 2: Deploying AWS CDK Stack (${CDK_STACK_NAME}) ==="
echo "--- Starting CDK deployment ---"
# Navigate to CDK app directory
cd "${SCRIPT_DIR}"
# Using the specific stack name for deployment is generally better.
if ! cdk deploy "${CDK_STACK_NAME}" --require-approval never --outputs-file "${OUTPUT_FILE}"; then
    echo "Error: CDK deployment failed." >&2
    cd - > /dev/null # Go back to original dir before exiting
    exit 1
fi
echo "--- Finished CDK deployment successfully. Outputs saved to ${OUTPUT_FILE} ---"
cd - > /dev/null # Go back to original dir

echo -e "\n=== Section 3: Extracting Outputs from ${OUTPUT_FILE} ==="
echo "--- Starting output extraction ---"
if [ ! -f "${OUTPUT_FILE}" ]; then
    echo "Error: CDK output file ${OUTPUT_FILE} not found." >&2
    exit 1
fi

# Extract outputs using jq. Output keys must match those defined in aws-stack.ts CfnOutput
ALB_DNS_NAME=$(jq -r ".${CDK_STACK_NAME}.AlbDnsName" "${OUTPUT_FILE}")
RDS_ENDPOINT=$(jq -r ".${CDK_STACK_NAME}.DbInstanceEndpoint" "${OUTPUT_FILE}")
RDS_SECRET_ARN=$(jq -r ".${CDK_STACK_NAME}.DbSecretArn" "${OUTPUT_FILE}")
RDS_DB_NAME="atomicdb" # This is hardcoded in aws-stack.ts for rds.DatabaseInstance
HASURA_ADMIN_SECRET_ARN=$(jq -r ".${CDK_STACK_NAME}.HasuraAdminSecretOutput" "${OUTPUT_FILE}")
MSK_CLUSTER_ARN_OUTPUT_KEY="MskClusterArnOutput"
MSK_CLUSTER_ARN=$(jq -r ".${CDK_STACK_NAME}.${MSK_CLUSTER_ARN_OUTPUT_KEY}" "${OUTPUT_FILE}")

# Validate extracted outputs
if [ -z "${ALB_DNS_NAME}" ] || [ "${ALB_DNS_NAME}" == "null" ] || \
   [ -z "${RDS_ENDPOINT}" ] || [ "${RDS_ENDPOINT}" == "null" ] || \
   [ -z "${RDS_SECRET_ARN}" ] || [ "${RDS_SECRET_ARN}" == "null" ] || \
   [ -z "${HASURA_ADMIN_SECRET_ARN}" ] || [ "${HASURA_ADMIN_SECRET_ARN}" == "null" ] || \
   [ -z "${MSK_CLUSTER_ARN}" ] || [ "${MSK_CLUSTER_ARN}" == "null" ]; then
    echo "Error: Failed to extract one or more required outputs from ${OUTPUT_FILE}." >&2
    echo "ALB_DNS_NAME: ${ALB_DNS_NAME}" >&2
    echo "RDS_ENDPOINT: ${RDS_ENDPOINT}" >&2
    echo "RDS_SECRET_ARN: ${RDS_SECRET_ARN}" >&2
    echo "HASURA_ADMIN_SECRET_ARN: ${HASURA_ADMIN_SECRET_ARN}" >&2
    echo "MSK_CLUSTER_ARN: ${MSK_CLUSTER_ARN}" >&2
    exit 1
fi
echo "Extracted outputs successfully:"
echo "  ALB DNS Name: ${ALB_DNS_NAME}"
echo "  RDS Endpoint: ${RDS_ENDPOINT}"
echo "  RDS Secret ARN: ${RDS_SECRET_ARN}"
echo "  Hasura Admin Secret ARN: ${HASURA_ADMIN_SECRET_ARN}"
echo "  MSK Cluster ARN: ${MSK_CLUSTER_ARN}"
echo "--- Finished output extraction ---"

echo -e "\n=== Section 3a: Updating MSK Bootstrap Brokers Secret ==="
echo "--- Starting MSK bootstrap brokers secret update ---"
# MSK_CLUSTER_ARN is already validated by the block above.
# If it was "null" or empty, the script would have exited.

echo "Fetching MSK Bootstrap Brokers for Cluster ARN: ${MSK_CLUSTER_ARN}..."
MSK_BROKERS=$(aws kafka get-bootstrap-brokers --cluster-arn "${MSK_CLUSTER_ARN}" --region "${AWS_REGION}" --query 'BootstrapBrokerStringTls' --output text)

if [ $? -ne 0 ] || [ -z "${MSK_BROKERS}" ] || [ "${MSK_BROKERS}" == "null" ]; then
    echo "Error: Failed to fetch MSK Bootstrap Brokers." >&2
    echo "MSK_BROKERS: ${MSK_BROKERS}" >&2
    echo "Please check the MSK cluster status and AWS CLI configuration." >&2
    exit 1
fi
echo "Successfully fetched MSK Bootstrap Brokers."
# echo "MSK_BROKERS: ${MSK_BROKERS}" # Potentially sensitive, uncomment for debugging only

MSK_SECRET_ARN_OUTPUT_KEY="MskBootstrapBrokersSecretArn"
MSK_SECRET_ARN=$(jq -r ".${CDK_STACK_NAME}.${MSK_SECRET_ARN_OUTPUT_KEY}" "${OUTPUT_FILE}")

if [ -z "${MSK_SECRET_ARN}" ] || [ "${MSK_SECRET_ARN}" == "null" ]; then
    echo "Error: Failed to extract MskBootstrapBrokersSecretArn from ${OUTPUT_FILE}." >&2
    echo "MSK_SECRET_ARN: ${MSK_SECRET_ARN}" >&2
    exit 1
fi
echo "Successfully extracted MSK Bootstrap Brokers Secret ARN: ${MSK_SECRET_ARN}"

echo "Updating AWS Secrets Manager secret (${MSK_SECRET_ARN}) with MSK Bootstrap Brokers..."
if ! aws secretsmanager update-secret --secret-id "${MSK_SECRET_ARN}" --secret-string "${MSK_BROKERS}" --region "${AWS_REGION}"; then
    echo "Error: Failed to update MSK Bootstrap Brokers secret in AWS Secrets Manager." >&2
    exit 1
fi
echo "Successfully updated MSK Bootstrap Brokers secret."
echo "--- Finished MSK bootstrap brokers secret update ---"

echo -e "\n=== Section 4: Running Post-Deployment Scripts ==="
echo "--- Starting post-deployment scripts ---"

echo "Running Database Initialization Script..."
# run_db_init_scripts.sh expects: <rds_endpoint> <rds_db_name> <rds_secret_arn> [aws_region]
if ! "${SCRIPT_DIR}/run_db_init_scripts.sh" "${RDS_ENDPOINT}" "${RDS_DB_NAME}" "${RDS_SECRET_ARN}" "${AWS_REGION}"; then
    echo "Error: Database initialization script failed. This is a critical error." >&2
    exit 1
else
    echo "Database initialization script completed successfully."
fi

echo "Running Hasura Metadata Apply Script..."
# apply_hasura_metadata.sh expects: <alb_dns_name> <hasura_admin_secret_arn> [aws_region]
if ! "${SCRIPT_DIR}/apply_hasura_metadata.sh" "${ALB_DNS_NAME}" "${HASURA_ADMIN_SECRET_ARN}" "${AWS_REGION}"; then
    echo "Error: Hasura metadata apply script failed. This is a critical error." >&2
    exit 1
fi
echo "Hasura metadata apply script completed successfully."
echo "--- Finished post-deployment scripts ---"

echo -e "\n=== Deployment Script Completed ===\n"
echo "Application should be accessible at: http://${ALB_DNS_NAME}"
echo "Important: Review script output for any warnings or errors."
echo "NOTE: Manual population of placeholder secrets (DB connection strings, JWT key, API keys) in AWS Secrets Manager is required for full functionality if not automated."
