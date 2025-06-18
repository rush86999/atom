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

# Check for AWS CLI, CDK, jq
if ! command -v aws &> /dev/null || ! command -v cdk &> /dev/null || ! command -v jq &> /dev/null; then
    echo "Error: Required tools (aws cli, cdk, jq) are not installed or not in PATH."
    exit 1
fi

echo "=== Section 1: Building and Pushing Docker Images ==="
if ! "${SCRIPT_DIR}/build_scripts/build_and_push_all.sh" "${AWS_ACCOUNT_ID}" "${AWS_REGION}"; then
    echo "Error: Docker image build and push failed."
    exit 1
fi
echo "Docker images built and pushed successfully."

echo -e "
=== Section 2: Deploying AWS CDK Stack (${CDK_STACK_NAME}) ==="
# Navigate to CDK app directory
cd "${SCRIPT_DIR}"
# Using the specific stack name for deployment is generally better.
if ! cdk deploy "${CDK_STACK_NAME}" --require-approval never --outputs-file "${OUTPUT_FILE}"; then
    echo "Error: CDK deployment failed."
    cd - > /dev/null # Go back to original dir before exiting
    exit 1
fi
echo "CDK stack deployed successfully. Outputs saved to ${OUTPUT_FILE}"
cd - > /dev/null # Go back to original dir

echo -e "
=== Section 3: Extracting Outputs from ${OUTPUT_FILE} ==="
if [ ! -f "${OUTPUT_FILE}" ]; then
    echo "Error: CDK output file ${OUTPUT_FILE} not found."
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
    echo "Error: Failed to extract one or more required outputs from ${OUTPUT_FILE}."
    echo "ALB_DNS_NAME: ${ALB_DNS_NAME}"
    echo "RDS_ENDPOINT: ${RDS_ENDPOINT}"
    echo "RDS_SECRET_ARN: ${RDS_SECRET_ARN}"
    echo "HASURA_ADMIN_SECRET_ARN: ${HASURA_ADMIN_SECRET_ARN}"
    echo "MSK_CLUSTER_ARN: ${MSK_CLUSTER_ARN}"
    exit 1
fi
echo "Extracted outputs successfully."
echo "  ALB DNS Name: ${ALB_DNS_NAME}"
echo "  RDS Endpoint: ${RDS_ENDPOINT}"
echo "  RDS Secret ARN: ${RDS_SECRET_ARN}"
echo "  Hasura Admin Secret ARN: ${HASURA_ADMIN_SECRET_ARN}"
echo "  MSK Cluster ARN: ${MSK_CLUSTER_ARN}"

echo -e "
=== IMPORTANT: Manual Configuration for MSK ==="
        if [ -n "${MSK_CLUSTER_ARN}" ] && [ "${MSK_CLUSTER_ARN}" != "null" ]; then
          echo "The MSK Serverless cluster ARN is: ${MSK_CLUSTER_ARN}"
          echo "You MUST manually fetch the MSK Bootstrap Brokers using the AWS CLI (copy the full command below):"
          echo "  aws kafka get-bootstrap-brokers --cluster-arn ${MSK_CLUSTER_ARN} --region ${AWS_REGION}"
          echo "Then, you need to update the 'KAFKA_BOOTSTRAP_SERVERS' environment variable for the 'functions' ECS service."
          echo "This can be done by:"
          echo "  1. Creating a new version of the ECS Task Definition for the 'functions' service with the correct KAFKA_BOOTSTRAP_SERVERS string."
          echo "  2. Updating the 'functions' ECS service to use this new task definition version."
          echo "Alternatively, store this bootstrap string in AWS Secrets Manager and configure the 'functions' service to read it from there at startup (recommended for robustness)."
          echo "The 'functions' service (and dependent features) may not function correctly until KAFKA_BOOTSTRAP_SERVERS is properly set."
        else
          echo "Warning: MSK Cluster ARN not found in CDK outputs. Manual configuration for MSK Bootstrap brokers will require finding the ARN from the AWS Console."
        fi
echo "==============================================="

echo -e "
=== Section 4: Running Post-Deployment Scripts ==="

echo "Running Database Initialization Script..."
# run_db_init_scripts.sh expects: <rds_endpoint> <rds_db_name> <rds_secret_arn> [aws_region]
if ! "${SCRIPT_DIR}/run_db_init_scripts.sh" "${RDS_ENDPOINT}" "${RDS_DB_NAME}" "${RDS_SECRET_ARN}" "${AWS_REGION}"; then
    echo "Error: Database initialization script failed."
    # Allowing script to continue to attempt Hasura metadata apply, as DB might be partially initialized.
else
    echo "Database initialization script completed."
fi

echo "Running Hasura Metadata Apply Script..."
# apply_hasura_metadata.sh expects: <alb_dns_name> <hasura_admin_secret_arn> [aws_region]
if ! "${SCRIPT_DIR}/apply_hasura_metadata.sh" "${ALB_DNS_NAME}" "${HASURA_ADMIN_SECRET_ARN}" "${AWS_REGION}"; then
    echo "Error: Hasura metadata apply script failed."
    exit 1
fi
echo "Hasura metadata apply script completed successfully."

echo -e "
=== Deployment Attempt Completed ===
"
echo "Application should be accessible at: http://${ALB_DNS_NAME}"
echo "NOTE: Manual population of placeholder secrets (DB connection strings, JWT key, API keys) in AWS Secrets Manager is required for full functionality."
