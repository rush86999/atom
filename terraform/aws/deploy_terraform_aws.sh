#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

AWS_ACCOUNT_ID="${1}"
AWS_REGION="${2}"
# Optional: Terraform workspace if used, e.g., dev/staging/prod
# TF_WORKSPACE="${3:-default}"

if [ -z "${AWS_ACCOUNT_ID}" ] || [ -z "${AWS_REGION}" ]; then
  echo "Usage: $0 <aws_account_id> <aws_region>"
  echo "Example: $0 123456789012 us-east-1"
  exit 1
fi

# Assuming this script is in terraform/aws/
# Path to the CDK-phase build scripts directory
BUILD_SCRIPTS_DIR="../../deployment/aws/build_scripts"
TERRAFORM_DIR="." # Current directory

# Check for AWS CLI, CDK, jq, Terraform
if ! command -v aws &> /dev/null || ! command -v docker &> /dev/null || ! command -v terraform &> /dev/null; then
    echo "Error: Required tools (aws cli, docker, terraform) are not installed or not in PATH."
    exit 1
fi

echo "=== Section 1: Building and Pushing Docker Images ==="
if [ -f "${BUILD_SCRIPTS_DIR}/build_and_push_all.sh" ]; then
  if ! "${BUILD_SCRIPTS_DIR}/build_and_push_all.sh" "${AWS_ACCOUNT_ID}" "${AWS_REGION}"; then
      echo "Error: Docker image build and push failed."
      exit 1
  fi
  echo "Docker images built and pushed successfully."
else
  echo "Warning: Build and push script not found at ${BUILD_SCRIPTS_DIR}/build_and_push_all.sh. Skipping image build."
fi


echo -e "
=== Section 2: Running Terraform Deployment ==="
# Ensure we are in the terraform directory
# cd "${TERRAFORM_DIR}" || { echo "Error: Failed to cd into ${TERRAFORM_DIR}"; exit 1; }

echo "Initializing Terraform..."
if ! terraform init -upgrade; then
    echo "Error: terraform init failed."
    exit 1
fi

# Optional: Select workspace if using them
# echo "Selecting Terraform workspace: ${TF_WORKSPACE}..."
# if ! terraform workspace select "${TF_WORKSPACE}"; then
#   if ! terraform workspace new "${TF_WORKSPACE}"; then
#     echo "Error: Failed to select or create Terraform workspace ${TF_WORKSPACE}."
#     exit 1
#   fi
# fi

echo "Applying Terraform configuration..."
# Pass variables via -var or a .tfvars file if not using defaults or environment variables
# For simplicity, assuming variables.tf defaults are used or AWS creds handle region.
if ! terraform apply -auto-approve \
             -var="aws_region=${AWS_REGION}" \
             -var="aws_account_id=${AWS_ACCOUNT_ID}" ; then # aws_account_id added as var for potential use in naming/arns
    echo "Error: terraform apply failed."
    exit 1
fi
echo "Terraform apply completed successfully."

echo -e "
=== Section 3: Displaying Terraform Outputs ==="
terraform output

# To get JSON output for scripting:
# terraform output -json > terraform_outputs.json
# echo "Full JSON outputs saved to terraform_outputs.json"


echo -e "
=== Terraform Deployment Script Completed ===
"
echo "Next steps typically involve:"
echo "1. Manually updating placeholder secrets in AWS Secrets Manager (DB connection strings, API keys, Hasura JWT key)."
echo "2. Fetching MSK Bootstrap Brokers (see 'msk_serverless_cluster_bootstrap_brokers_instruction' output) and configuring the 'functions' ECS service."
echo "3. Running database initialization scripts. Example:"
echo "   ./scripts/tf_run_db_init.sh \$(terraform output -raw db_instance_address) \$(terraform output -raw db_instance_name) \$(terraform output -raw db_credentials_secret_arn) ${AWS_REGION}"
echo "4. Applying Hasura metadata. Example:"
echo "   ./scripts/tf_apply_hasura_metadata.sh \$(terraform output -raw alb_dns_name) \$(terraform output -raw hasura_admin_secret_arn) ${AWS_REGION}"
ALB_DNS_NAME_RAW=$(terraform output -raw alb_dns_name 2>/dev/null)
if [ -n "$ALB_DNS_NAME_RAW" ]; then
    echo "Application might be accessible at: http://${ALB_DNS_NAME_RAW}"
else
    echo "ALB DNS Name not found in outputs or could not be retrieved."
fi
