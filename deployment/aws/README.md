# AWS Deployment for Atomic Application Stack

This document outlines the process for deploying the Atomic application stack to Amazon Web Services (AWS) using the AWS Cloud Development Kit (CDK).

## Overview

This setup provisions the necessary AWS infrastructure and deploys the containerized application services. Key components include:
- AWS VPC, Subnets (Public and Private)
- AWS RDS PostgreSQL for the database
- AWS ECS (Elastic Container Service) with AWS Fargate for running application containers
- AWS ECR (Elastic Container Registry) for storing Docker images
- AWS Application Load Balancer (ALB) for request distribution
- AWS Secrets Manager for handling sensitive information
- AWS CloudWatch Logs for application and service logging
- **Amazon EFS (Elastic File System):** Used by the `python-agent` service for persistent storage, particularly for LanceDB vector databases.
- **Amazon MSK Serverless:** Offers a managed Apache Kafka service for asynchronous messaging.
- *(Amazon OpenSearch Service is no longer used by default, replaced by LanceDB on EFS for relevant Python agent functionalities).*

The core services deployed include: SuperTokens (auth), Hasura (GraphQL), Functions (Node.js backend logic), App (frontend), Handshake, OAuth, Optaplanner, and the new `python-agent` service. Backend services include Amazon MSK and EFS.

## Prerequisites

Ensure the following tools are installed and configured:

- **AWS Account:** An active AWS account with sufficient permissions.
- **AWS CLI:** Configured with your credentials and default region (`aws configure`).
- **Node.js & npm/yarn:** Node.js (LTS version recommended) and a package manager.
- **AWS CDK CLI:** Installed globally (`npm install -g aws-cdk`).
- **Docker:** Installed and running (for building application images).
- **jq:** Command-line JSON processor (used by deployment scripts).
- **Hasura CLI:** (Optional, for manual metadata operations or if `apply_hasura_metadata.sh` is run locally). Install from [Hasura Docs](https://hasura.io/docs/latest/hasura-cli/install-hasura-cli/).
- **psql:** PostgreSQL client (Optional, for manual database interaction or if `run_db_init_scripts.sh` is run locally).

## Directory Structure (within `deployment/aws`)

- `lib/aws-stack.ts`: The core CDK stack definition.
- `bin/aws.ts`: CDK application entry point.
- `build_scripts/`: Contains scripts to build individual Docker images (`build_<service>.sh`) and a master script to build/push all (`build_and_push_all.sh`).
- `db_init_scripts/`: Contains SQL scripts for database schema initialization.
- `apply_hasura_metadata.sh`: Script to apply Hasura metadata.
- `run_db_init_scripts.sh`: Script to run database initialization SQL.
- `deploy_atomic_aws.sh`: The main deployment orchestration script.
- `cdk.json`, `package.json`, `tsconfig.json`: CDK project files.

## Deployment Steps

### 1. Initial Setup (One-time)

1.  Clone this repository.
2.  Navigate to the CDK app directory: `cd deployment/aws`
3.  Install CDK dependencies: `npm install` (or `yarn install`).

### 2. Environment Configuration: Placeholder Secrets (Crucial First-Time Setup)

The CDK stack creates several secrets in AWS Secrets Manager with **placeholder values**. After the very first successful run of `deploy_atomic_aws.sh` (which deploys the CDK stack and creates these secrets), you **MUST** manually update these secrets in the AWS Secrets Manager console with their real, operational values for the application to function correctly.

The placeholder secrets to update are (names might have a suffix like `-XXXXXX` added by Secrets Manager):

-   **`AwsStack/SupertokensDbConnString`** (or similar, check `cdk-outputs.json` for exact name after deployment if needed):
    *   **Required Value:** The full PostgreSQL connection URI for SuperTokens.
    *   **Format:** `postgresql://<username>:<password>@<rds_instance_endpoint>:<port>/<database_name>`
    *   **How to get values:**
        *   `<username>`, `<password>`, `<rds_instance_endpoint>`, `<port>`, `<database_name>`: These are available from the RDS instance secret (whose ARN is outputted as `DbSecretArn` in `cdk-outputs.json`) and the RDS instance itself (endpoint, port, dbname `atomicdb`).
-   **`AwsStack/HasuraDbConnString`**:
    *   **Required Value:** The full PostgreSQL connection URI for Hasura.
    *   **Format:** `postgres://<username>:<password>@<rds_instance_endpoint>:<port>/<database_name>` (Note: `postgres://` not `postgresql://` for Hasura).
    *   **How to get values:** Same as for SuperTokens.
-   **`AwsStack/PlaceholderHasuraJwtSecret`**:
    *   **Required Value:** A JSON object for Hasura JWT configuration.
    *   **Format:** `{"type":"HS256","key":"YOUR_ACTUAL_STRONG_SECRET_KEY","issuer":"supertokens"}`
    *   **`YOUR_ACTUAL_STRONG_SECRET_KEY`**: Must be a cryptographically strong key, at least 32 characters long (e.g., a 64-character hex string).
-   **`AwsStack/OpenAiApiKeySecret`**:
    *   **Required Value:** Your actual OpenAI API key.
-   **`AwsStack/OptaplannerDbConnString`**:
    *   **Required Value:** The full PostgreSQL JDBC connection URI for Optaplanner.
    *   **Format:** `jdbc:postgresql://<rds_instance_endpoint>:<port>/<database_name>`
    *   **How to get values:** Similar to SuperTokens/Hasura, using details from the RDS instance and its secret.
-   **`AwsStack/NotionApiTokenSecret`**:
    *   **Required Value:** Your actual Notion API Token.
-   **`AwsStack/DeepgramApiKeySecret`**:
    *   **Required Value:** Your actual Deepgram API Key.
-   **`AwsStack/NotionNotesDbIdSecret`**:
    *   **Required Value:** The Database ID of your Notion database for general notes.
-   **`AwsStack/NotionResearchProjectsDbIdSecret`**:
    *   **Required Value:** The Database ID of your Notion database for research projects.
-   **`AwsStack_NotionResearchTasksDbIdSecret`** (or similar generated name):
    *   **Required Value:** The Database ID of your Notion database for research sub-agent tasks.


**Other Secrets:**
-   `AwsStack/HasuraAdminSecret`: Auto-generated by CDK. Used by the system.
-   `AwsStack/ApiTokenSecret`: Auto-generated by CDK. Used by some internal services.
-   `AwsStack/PostgresAdminCredentials...`: Auto-generated by RDS for the master database user.

**Failure to update these placeholder secrets will result in application malfunction.**

**Important Note on Initial Secret Population:** While the MSK bootstrap broker configuration (see next section) is now automated, the *other* placeholder secrets listed above (e.g., `AwsStack/SupertokensDbConnString`, `AwsStack/HasuraDbConnString`, `AwsStack/PlaceholderHasuraJwtSecret`, `AwsStack/OpenAiApiKeySecret`, Notion keys, Deepgram key, etc.) **still require manual updating** in the AWS Secrets Manager console after the very first successful run of `deploy_atomic_aws.sh`.

### MSK Bootstrap Brokers Configuration (Automated)

The configuration of Kafka bootstrap brokers for the `functions` ECS service to connect to Amazon MSK is now **automated** by the `deploy_atomic_aws.sh` script.

**How it works:**
1.  After the CDK stack deployment, if an MSK Cluster ARN (`MskClusterArnOutput`) is found in the `cdk-outputs.json` file, the script attempts to fetch the MSK bootstrap broker string using the AWS CLI.
2.  It then updates an AWS Secrets Manager secret, typically named `AwsStack/MskBootstrapBrokers` (the exact name can be found in `cdk-outputs.json` as `MskBootstrapBrokersSecretArn`), with this broker string.
3.  The `functions` ECS service is already configured in `aws-stack.ts` to read its `KAFKA_BOOTSTRAP_SERVERS` environment variable directly from this secret.

This automated process replaces the previous manual steps involving manual Task Definition updates or secret creation.

**Troubleshooting Note:**
-   If the MSK Serverless cluster is not provisioned as part of your CDK deployment (e.g., if it's commented out or not included), or if the `deploy_atomic_aws.sh` script fails to retrieve the MSK Cluster ARN or bootstrap brokers for any reason, this automation step might fail.
-   In such cases, the `AwsStack/MskBootstrapBrokers` secret might not be updated with the correct broker string.
-   Consequently, the `functions` service may not be able to connect to Kafka, and Kafka-dependent features will not operate correctly. Check the script output and the `functions` service logs for any related errors.

### 3. Running the Deployment Script

Execute the main deployment script:
```bash
./deployment/aws/deploy_atomic_aws.sh <your_aws_account_id> <your_aws_region> [cdk_stack_name]
```
-   `<your_aws_account_id>`: Your 12-digit AWS Account ID.
-   `<your_aws_region>`: E.g., `us-east-1`, `eu-west-2`.
-   `[cdk_stack_name]`: (Optional) The name of the CDK stack. Defaults to `AwsStack` if not provided.

This script will:
1.  Build all necessary Docker images (including the one for `python-agent` via `build_python_agent.sh`) and push them to AWS ECR.
2.  Deploy or update the AWS infrastructure using AWS CDK.
3.  Run database initialization scripts against the RDS instance.
4.  Apply Hasura metadata.

Monitor the script output for any errors.

## Accessing the Application

-   Once the `deploy_atomic_aws.sh` script completes successfully, the main application will be accessible via the Application Load Balancer.
-   The ALB DNS Name is outputted by the script (e.g., `http://<ALB_DNS_NAME>`).
-   Various services are path-routed:
    -   App (Frontend): `http://<ALB_DNS_NAME>/`
    -   SuperTokens API: `http://<ALB_DNS_NAME>/v1/auth/`
    -   Hasura GraphQL: `http://<ALB_DNS_NAME>/v1/graphql/`
    -   Functions API: `http://<ALB_DNS_NAME>/v1/functions/`
    -   Handshake Service: `http://<ALB_DNS_NAME>/v1/handshake/`
    -   OAuth Service: `http://<ALB_DNS_NAME>/v1/oauth/`
    -   Optaplanner Service: `http://<ALB_DNS_NAME>/v1/optaplanner/`
    *(Amazon OpenSearch Service and its dashboards are no longer used by default in this setup, having been replaced by LanceDB with EFS for the python-agent's vector search capabilities.)*

## Updating the Deployment

-   **Application Code Changes (Docker Images):**
    1.  Make your code changes in the respective service directories (e.g., `atomic-docker/app_build_docker/`).
    2.  Re-run the deployment script: `./deployment/aws/deploy_atomic_aws.sh <your_aws_account_id> <your_aws_region>`
    The script will rebuild and push the updated images, and CDK will trigger an update for the relevant ECS services.
-   **Infrastructure Changes (CDK Code):**
    1.  Modify the CDK code in `deployment/aws/lib/aws-stack.ts`.
    2.  Re-run the deployment script as above. CDK will calculate and apply the infrastructure changes.

## Post-Deployment Manual Steps / Scripts

The `deploy_atomic_aws.sh` script attempts to automate post-deployment steps. However, you can run them manually if needed:

-   **Database Initialization:**
    ```bash
    ./deployment/aws/run_db_init_scripts.sh <rds_endpoint> <rds_db_name> <rds_secret_arn> [aws_region]
    ```
    (Get parameters from `cdk-outputs.json` or AWS console).
-   **Hasura Metadata Application:**
    ```bash
    ./deployment/aws/apply_hasura_metadata.sh <alb_dns_name> <hasura_admin_secret_arn> [aws_region]
    ```
    (Get parameters from `cdk-outputs.json` or AWS console).

## Tearing Down the Stack

To remove all AWS resources created by this deployment:

1.  Navigate to `deployment/aws`.
2.  Run: `cdk destroy <cdk_stack_name>` (e.g., `cdk destroy AwsStack`).
3.  Confirm the destruction when prompted.

**Notes on Teardown:**
-   Most resources are set with `removalPolicy: cdk.RemovalPolicy.DESTROY`, so they should be deleted.
-   ECR repositories are set to `autoDeleteImages: true`. If this were false, non-empty ECR repositories would prevent stack deletion and require manual image deletion first.
-   S3 buckets (if any were created by CDK with auto-generated names and retain policies) might need manual emptying and deletion. This stack does not explicitly create S3 buckets with retain policies.

## Troubleshooting

-   **CDK Errors:** Check the output of `cdk deploy -v` or `cdk synth`.
-   **ECS Task Failures:**
    -   Check CloudWatch Logs: Go to AWS Console -> CloudWatch -> Log groups. Look for groups like `/ecs/AwsStack-YourServiceName-XYZ`.
    -   Check ECS service events in the AWS ECS console.
-   **ALB Issues:** Check ALB access logs (if enabled) and target group health checks in the EC2 console.
-   **Application Errors:** Use browser developer tools and check application logs in CloudWatch.
-   **Secret Population:** Double-check that the placeholder secrets were correctly updated in AWS Secrets Manager after the first deployment.
-   **Amazon EFS:** Ensure EFS mount targets are correctly provisioned in private subnets. Verify security group rules allow NFS traffic (port 2049) between the `python-agent` service's security group and the EFS security group. Check `python-agent` logs for any mount issues.
-   **Amazon MSK Serverless:** Check the cluster status in the AWS MSK console. Verify that the `functions` service has the correct `KAFKA_BOOTSTRAP_SERVERS` configured and that its IAM role (`ecsTaskRole`) has the necessary `kafka-cluster:*` and `kafka:GetBootstrapBrokers` permissions for the cluster ARN. Security groups (`functionsSG` and `mskClusterClientSG`) must allow traffic on port 9098 (for IAM auth).

**Dockerfile Dependencies Note:**
- The `python-agent` service requires specific Python libraries. Ensure that the `atomic-docker/python_agent_build_docker/Dockerfile` includes `lancedb pyarrow sentence-transformers notion-client deepgram-sdk requests httpx` in its `pip install` instructions for full functionality. This list should be up-to-date.
