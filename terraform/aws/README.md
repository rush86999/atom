# Terraform AWS Deployment for Atomic Application Stack

This document outlines the process for deploying the Atomic application stack to Amazon Web Services (AWS) using Terraform.

## Overview

This Terraform setup provisions the necessary AWS infrastructure and deploys the containerized application services, aiming for functional parity with the CDK deployment. Key components include:
- AWS VPC, Subnets (Public and Private), NAT Gateways, Internet Gateway.
- AWS RDS PostgreSQL for the database (credentials managed in AWS Secrets Manager).
- AWS ECS (Elastic Container Service) with AWS Fargate for running application containers.
- AWS ECR (Elastic Container Registry) for storing Docker images.
- AWS Application Load Balancer (ALB) for request distribution.
- AWS Secrets Manager for handling sensitive information (both auto-generated and placeholders for manual input).
- Amazon S3 bucket for application data.
- Amazon OpenSearch Service for search functionalities.
- Amazon MSK Serverless for Kafka messaging.
- AWS CloudWatch Logs for application and service logging.

The core services deployed include: SuperTokens, Hasura, Functions, App (frontend), Handshake, OAuth, and Optaplanner.

## Prerequisites

Ensure the following tools are installed and configured on your local machine:

- **AWS Account:** An active AWS account with sufficient permissions to create the resources defined in this configuration.
- **AWS CLI:** Configured with your credentials and default region (`aws configure`). These credentials will be used by Terraform.
- **Terraform:** Version 1.0 or higher. Install from [terraform.io](https://developer.hashicorp.com/terraform/downloads).
- **Docker:** Installed and running (for building application images locally before pushing to ECR).
- **jq:** Command-line JSON processor (used by some helper scripts).
- **psql:** PostgreSQL client (required to run the database initialization script).
- **Hasura CLI:** Version 2.x (required to run the Hasura metadata application script). Install from [Hasura Docs](https://hasura.io/docs/latest/hasura-cli/install-hasura-cli/).

## Directory Structure (within `terraform/aws`)

- `main.tf`: Defines all AWS resources managed by Terraform.
- `variables.tf`: Contains input variable definitions (e.g., AWS region, stack prefix).
- `outputs.tf`: Defines outputs from the Terraform configuration (e.g., ALB DNS name, RDS endpoint).
- `providers.tf`: Configures Terraform providers (AWS, Random).
- `.gitignore`: Specifies files and directories for Git to ignore.
- `deploy_terraform_aws.sh`: Main orchestration script for deployment.
- `scripts/`: Contains helper scripts for post-deployment tasks.
  - `tf_run_db_init.sh`: Applies SQL schema to the RDS database.
  - `tf_apply_hasura_metadata.sh`: Applies metadata to the Hasura GraphQL engine.
- `db_init_scripts/`: Contains SQL files for database schema initialization.

## Deployment Steps

### 1. Initial Setup (One-time per local environment)

1.  Clone the main application repository (if you haven't already).
2.  Navigate to the Terraform AWS directory: `cd terraform/aws`
3.  Initialize Terraform: This downloads provider plugins and sets up the backend.
    ```bash
    terraform init
    ```

### 2. Docker Image Preparation (Handled by Deployment Script)

The custom application services (`app`, `functions`, `handshake`, `oauth`, `optaplanner`) are containerized. The `deploy_terraform_aws.sh` script will attempt to run the Docker build and push scripts located in `deployment/aws/build_scripts/`. Ensure Docker is running and you are logged into AWS ECR if pushing manually or if the script requires it (though the script typically handles ECR login via AWS CLI).

### 3. Running the Main Deployment Script

This script orchestrates the image building/pushing and Terraform deployment.
```bash
./deploy_terraform_aws.sh <your_aws_account_id> <your_aws_region>
```
-   `<your_aws_account_id>`: Your 12-digit AWS Account ID.
-   `<your_aws_region>`: E.g., `us-east-1`, `eu-west-2`.

The script will:
1.  Call `../../deployment/aws/build_scripts/build_and_push_all.sh` to build Docker images and push them to the ECR repositories created by Terraform in a previous run (or to be created in the current run).
2.  Run `terraform init -upgrade` (to ensure provider plugins are up-to-date).
3.  Run `terraform apply -auto-approve` (passing the AWS region and account ID as variables). This provisions or updates all AWS resources.
4.  Display Terraform outputs.
5.  Provide guidance on crucial manual post-deployment steps.

Monitor the script output carefully for any errors.

### 4. Crucial Manual Post-`terraform apply` Configuration

After `terraform apply` successfully completes (especially on the first deployment), several secrets created by Terraform have **placeholder values** and **MUST be manually updated** in the AWS Secrets Manager console for the application to function correctly. Additionally, the MSK bootstrap broker string needs to be configured.

**A. Update Placeholder Secrets in AWS Secrets Manager:**

Locate the following secrets in the AWS Secrets Manager console (their names will be prefixed with your `stack_name_prefix`, e.g., `atomic-`):

-   **`...-openai-api-key`**: Update with your actual OpenAI API key.
-   **`...-supertokens-db-conn-string`**:
    *   **Required Value:** Full PostgreSQL connection URI for SuperTokens.
    *   **Format:** `postgresql://<username>:<password>@<rds_instance_endpoint>:<port>/<database_name>`
    *   **How to get values:**
        *   `<username>` & `<password>`: From the secret specified in `terraform output -raw db_credentials_secret_arn`.
        *   `<rds_instance_endpoint>`: From `terraform output -raw db_instance_address`.
        *   `<port>`: From `terraform output -raw db_instance_port`.
        *   `<database_name>`: From `terraform output -raw db_instance_name`.
-   **`...-hasura-db-conn-string`**:
    *   **Required Value:** Full PostgreSQL connection URI for Hasura.
    *   **Format:** `postgres://<username>:<password>@<rds_instance_endpoint>:<port>/<database_name>`
    *   **How to get values:** Same as for SuperTokens.
-   **`...-optaplanner-db-conn-string`**:
    *   **Required Value:** Full PostgreSQL JDBC connection URI for Optaplanner.
    *   **Format:** `jdbc:postgresql://<rds_instance_endpoint>:<port>/<database_name>?user=<username>&password=<password>` (or similar, verify Optaplanner/Quarkus JDBC format).
    *   **How to get values:** Same as for SuperTokens.
-   **`...-hasura-jwt-secret`**:
    *   **Required Value:** A JSON object for Hasura JWT configuration.
    *   **Format:** `{"type":"HS256","key":"YOUR_ACTUAL_STRONG_SECRET_KEY","issuer":"supertokens"}`
    *   **`YOUR_ACTUAL_STRONG_SECRET_KEY`**: Must be a cryptographically strong key, at least 32 characters long (e.g., a 64-character hex string).

*Failure to update these placeholder secrets will result in application malfunction.*

**B. Configure MSK Bootstrap Brokers for `functions` Service:**

The `functions` ECS service needs the Kafka bootstrap broker addresses for Amazon MSK.

1.  **Get MSK Cluster ARN:**
    ```bash
    terraform output -raw msk_serverless_cluster_arn
    ```
2.  **Fetch Bootstrap Brokers:** Use the AWS CLI (the command template is also an output):
    ```bash
    aws kafka get-bootstrap-brokers --cluster-arn <YOUR_MSK_CLUSTER_ARN_FROM_ABOVE> --region <YOUR_AWS_REGION>
    ```
    Note the `BootstrapBrokerStringTls` value from the JSON output.
3.  **Update `functions` Service Configuration:** Set the `KAFKA_BOOTSTRAP_SERVERS` environment variable for the `functions` service container to this `BootstrapBrokerStringTls` value. Options:
    *   **Option A (Manual Task Definition Update - for dev/test):**
        1.  Go to AWS ECS Console -> Task Definitions.
        2.  Find the `${stack_name_prefix}-functions` task definition, create a new revision.
        3.  Edit the `${stack_name_prefix}-functions-container` definition.
        4.  Update the `KAFKA_BOOTSTRAP_SERVERS` environment variable.
        5.  Save revision. Update the `${stack_name_prefix}-functions-service` to use this new revision.
    *   **Option B (Store in New Secret & Update Terraform - recommended):**
        1.  Create a new secret in AWS Secrets Manager (e.g., `${stack_name_prefix}-msk-bootstrap-brokers`).
        2.  Store the `BootstrapBrokerStringTls` value there.
        3.  Modify `terraform/aws/main.tf`: In the `functions` task definition, change `KAFKA_BOOTSTRAP_SERVERS` to read from this new secret (e.g., `valueFrom = aws_secretsmanager_secret.msk_bootstrap_brokers.arn`).
        4.  Run `terraform apply` again (via `deploy_terraform_aws.sh`).

### 5. Running Post-Deployment Scripts (After Terraform Apply and Manual Configs)

These scripts use Terraform outputs to target the correct resources. Run them from the `terraform/aws/` directory.

-   **Database Initialization:**
    ```bash
    ./scripts/tf_run_db_init.sh $(terraform output -raw db_instance_address) $(terraform output -raw db_instance_name) $(terraform output -raw db_credentials_secret_arn) $(terraform output -raw aws_region)
    ```
-   **Hasura Metadata Application:**
    ```bash
    ./scripts/tf_apply_hasura_metadata.sh $(terraform output -raw alb_dns_name) $(terraform output -raw hasura_admin_secret_arn) $(terraform output -raw aws_region)
    ```

## Accessing the Application

-   The main application is accessible via the Application Load Balancer DNS name:
    ```bash
    terraform output -raw alb_dns_name
    ```
    Access it via `http://<ALB_DNS_NAME>`.
-   Service Paths:
    -   App (Frontend): `/`
    -   SuperTokens API: `/v1/auth/`
    -   Hasura GraphQL: `/v1/graphql/` (Console also available via these paths)
    -   Functions API: `/v1/functions/`
    -   Handshake Service: `/v1/handshake/`
    -   OAuth Service: `/v1/oauth/`
    -   Optaplanner Service: `/v1/optaplanner/`
-   (Note: OpenSearch Dashboards and MSK are not publicly exposed by this setup.)

## Updating the Deployment

-   **Application Code Changes:**
    1.  Modify application code and rebuild/push Docker images (e.g., by re-running `./deploy_terraform_aws.sh <account_id> <region>`, which handles the image build/push first).
    2.  If only images changed and no infrastructure, `terraform apply` will detect changes to ECR image tags in ECS task definitions (if tags are dynamic) or you might need to force a new deployment on the ECS service.
-   **Infrastructure Changes (Terraform Code):**
    1.  Modify `.tf` files in `terraform/aws/`.
    2.  Run `terraform plan` to review changes.
    3.  Run `terraform apply` (or use `deploy_terraform_aws.sh`).

## Tearing Down the Stack

To remove all AWS resources created by this Terraform configuration:
```bash
cd terraform/aws
terraform destroy -auto-approve \
  -var="aws_region=<your_aws_region>" \
  -var="aws_account_id=<your_aws_account_id>"
  # Pass any other required variables if their defaults aren't suitable for destroy context
```
**Note:**
- S3 buckets require manual emptying before `terraform destroy` can remove them if they contain objects and `force_destroy` is not used on the bucket resource (not currently used).
- ECR repositories, if not empty, might also block deletion unless configured with `force_delete = true` (not currently used).

## Troubleshooting

- **Terraform Errors:** Examine output from `terraform plan` and `terraform apply`. Enable debug logging with `TF_LOG=DEBUG terraform apply`.
- **ECS Task Failures:** Check CloudWatch Logs for groups like `/ecs/${stack_name_prefix}-<service_name>`. Inspect ECS service events and task statuses in the AWS ECS console.
- **ALB Issues:** Review ALB access logs (if enabled) and target group health checks in the EC2 console. Check listener rules.
- **Application Errors:** Use browser developer tools; check application container logs in CloudWatch.
- **Secret/Configuration Issues:** Verify all placeholder secrets were correctly updated in AWS Secrets Manager. Ensure MSK bootstrap brokers are correctly configured for the `functions` service.
- **IAM Permissions:** Use IAM console to check policies attached to `ecs_application_task_role` if services fail to access other AWS resources.
- **Amazon OpenSearch Service:** Check domain status and logs in the AWS OpenSearch console.
- **Amazon MSK Serverless:** Check cluster status in the AWS MSK console. Verify `functions` service IAM permissions and bootstrap server configuration. Security Groups (`ecs_tasks` and `msk_client`) must allow traffic on port 9098.
