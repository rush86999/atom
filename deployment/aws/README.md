# Deploying Atomic Calendar on AWS (Optimized for Small Businesses)

This guide details how to deploy the Atomic Calendar application on AWS using the provided AWS Cloud Development Kit (CDK) scripts. This setup is optimized for small businesses, balancing cost-effectiveness, scalability, and maintainability by leveraging AWS managed services.

## Overview of the AWS CDK Strategy

The CDK script in `lib/aws-stack.ts` provisions the necessary AWS infrastructure to run the Atomic Calendar application. Key features of this optimized strategy include:

*   **ECS on Fargate:** Application services (frontend, backend functions, Hasura, SuperTokens, etc.) are deployed as containers orchestrated by Amazon ECS using AWS Fargate for serverless compute.
*   **Cost Optimization:**
    *   **Right-sized Services:** Default CPU and memory for Fargate services are set to reasonable starting points (e.g., 256 CPU units / 512 MiB RAM) and can be adjusted.
    *   **Fargate Spot:** Key stateless services (e.g., App, Functions) are configured to use Fargate Spot instances, potentially offering significant cost savings (up to 70%) compared to On-Demand Fargate. On-Demand Fargate is used as a fallback.
    *   **Auto-Scaling:** Application services are configured with auto-scaling based on CPU and memory utilization, allowing the system to handle varying loads efficiently by scaling out during peak times and scaling in during quieter periods.
*   **Scalable Database:** Uses Amazon RDS for PostgreSQL (defaulting to `db.t3.small`). For highly variable workloads, consider evaluating Amazon Aurora Serverless v2.
*   **Networking:** A dedicated VPC with public and private subnets is created. An Application Load Balancer (ALB) distributes incoming traffic to the services.
*   **Security:** IAM roles and security groups are defined to ensure secure communication between services. Secrets are managed using AWS Secrets Manager.
*   **Persistent Storage:** Amazon S3 is used for general data storage, and Amazon EFS is used for persistent storage for services like LanceDB (used by the Python agent).

## Prerequisites

1.  **AWS Account:** An active AWS account.
2.  **AWS CLI:** Configured with credentials and a default region.
3.  **Node.js and npm/yarn:** Required for CDK.
4.  **AWS CDK Toolkit:** Installed globally (`npm install -g aws-cdk`).
5.  **Docker:** Installed locally if you need to build and push Docker images to ECR.
6.  **Git:** To clone the repository.

## Deployment Steps

1.  **Clone the Repository:**
    ```bash
    git clone <your_repository_url>
    cd <repository_directory>/deployment/aws
    ```

2.  **Install CDK Dependencies:**
    ```bash
    npm install
    # or
    # yarn install
    ```

3.  **Bootstrap CDK (if you haven't used CDK in this account/region before):**
    ```bash
    cdk bootstrap aws://<YOUR_AWS_ACCOUNT_ID>/<YOUR_AWS_REGION>
    ```
    Replace placeholders with your actual AWS account ID and region.

4.  **Review Configuration in `lib/aws-stack.ts`:**
    *   **Service Sizes & Scaling:** Review the default CPU/memory settings and auto-scaling parameters (`minCapacity`, `maxCapacity`, `targetUtilizationPercent`) for each Fargate service. Adjust them based on your expected load and budget.
    *   **RDS Instance Type:** The default is `db.t3.small`. If you anticipate higher database load, you can change this. Note the comment regarding Aurora Serverless v2 for spiky workloads.
    *   **Secrets:** Many secrets are created as placeholders in AWS Secrets Manager (e.g., for OpenAI API Key, Google API credentials, Zoom credentials, a strong Hasura JWT secret). After the initial deployment, you **MUST** update these placeholder values in the AWS Secrets Manager console with your actual secrets.
        *   The CDK script outputs the ARNs of these secrets.
        *   Database connection strings for SuperTokens, Hasura, and OptaPlanner also require manual population in Secrets Manager, using the actual RDS endpoint after it's created. The CDK script provides descriptions for these secrets indicating the format.

5.  **Build and Push Docker Images to ECR:**
    *   The CDK script will create ECR repositories for each service.
    *   You need to build your application's Docker images and push them to these repositories. The build scripts are located in `deployment/aws/build_scripts/`.
    *   Example for the `functions` service (after ECR repo is created by `cdk deploy` or if you know the name):
        ```bash
        # Authenticate Docker to your ECR registry
        aws ecr get-login-password --region <YOUR_AWS_REGION> | docker login --username AWS --password-stdin <YOUR_AWS_ACCOUNT_ID>.dkr.ecr.<YOUR_AWS_REGION>.amazonaws.com

        # Navigate to the build script directory
        cd build_scripts

        # Run the build and push script (modify script if needed for image names/tags)
        ./build_functions.sh <YOUR_AWS_ACCOUNT_ID>.dkr.ecr.<YOUR_AWS_REGION>.amazonaws.com/atomic-functions:latest
        # Repeat for other services: app, handshake, oauth, optaplanner, python-agent
        ./build_and_push_all.sh <YOUR_AWS_ACCOUNT_ID>.dkr.ecr.<YOUR_AWS_REGION>.amazonaws.com <TAG_NAME>
        ```
    *   **Note:** The `build_and_push_all.sh` script is a good starting point. You'll need to provide your ECR registry URL and a tag.
    *   The CDK stack defines ECR repositories like `atomic-functions`, `atomic-app`, etc. The image names used in the `ecs.ContainerImage.fromEcrRepository(...)` calls within `aws-stack.ts` must match the images you push.

6.  **Synthesize and Deploy the CDK Stack:**
    *   **Synthesize (optional, to see CloudFormation template):**
        ```bash
        cdk synth
        ```
    *   **Deploy:**
        ```bash
        cdk deploy AwsStack # Or your stack name if different
        ```
    *   This process can take 15-30 minutes or more, as it provisions all the resources.
    *   Approve any IAM-related changes if prompted.

7.  **Post-Deployment Steps:**
    *   **Update Secrets:**
        *   Go to AWS Secrets Manager in the AWS console.
        *   Locate the secrets created by the stack (they will be prefixed with the stack name, e.g., `AwsStack/SupertokensDbConnString`).
        *   Update the **plain text** values of placeholder secrets:
            *   `SupertokensDbConnStringSecret`: `postgresql://<DB_USER>:<DB_PASS>@<RDS_ENDPOINT_ADDRESS>:<RDS_PORT>/atomicdb`
            *   `HasuraDbConnStringSecret`: `postgres://<DB_USER>:<DB_PASS>@<RDS_ENDPOINT_ADDRESS>:<RDS_PORT>/atomicdb`
            *   `OptaplannerDbConnStringSecret`: `jdbc:postgresql://<RDS_ENDPOINT_ADDRESS>:<RDS_PORT>/atomicdb` (ensure user/pass are appended if not part of the JDBC URL, or handle via separate env vars if OptaPlanner supports it)
            *   `PlaceholderHasuraJwtSecret`: Replace with a strong JSON JWT configuration.
            *   API keys for OpenAI, Google, Notion, Deepgram, etc.
        *   The RDS instance endpoint (`<RDS_ENDPOINT_ADDRESS>`) and the admin username/password (if you let RDS generate it) can be found in the AWS RDS console or in the output of the CDK deployment (for the secret ARN containing credentials).
    *   **Configure DNS:**
        *   The CDK deployment will output the DNS name of the Application LoadBalancer (`AlbDnsName`).
        *   Create a CNAME record in your DNS provider to point your desired domain (e.g., `app.yourbusiness.com`) to this ALB DNS name.
    *   **Hasura Metadata:**
        *   Once Hasura is running and connected to the database, you may need to apply Hasura metadata (tables, permissions, relationships, etc.). The `deployment/aws/apply_hasura_metadata.sh` script might be relevant, but you'll need to configure it with your Hasura endpoint and admin secret. Access the Hasura console via the ALB (e.g., `http://<ALB_DNS_NAME>/v1/graphql` - though direct console access might need specific path routing or temporary direct exposure).

## Cost Considerations and Monitoring

*   **Fargate:** Costs are based on vCPU and memory allocated per second, and the number of tasks running. The use of Fargate Spot significantly reduces this. Monitor usage via CloudWatch.
*   **RDS:** Cost depends on instance type, storage, and data transfer. `db.t3.small` is a cost-effective starting point.
*   **ALB:** Hourly cost plus LCU (Load Balancer Capacity Units) charges based on traffic.
*   **NAT Gateway:** Hourly cost plus data processing charges.
*   **S3 & EFS:** Storage costs, data transfer, and request costs.
*   **CloudWatch:** Logs and metrics storage and API usage.
*   **Secrets Manager:** Small cost per secret per month.
*   **Recommendations:**
    *   Regularly review your AWS bill and Cost Explorer.
    *   Set up billing alerts.
    *   Fine-tune Fargate service auto-scaling parameters (`minCapacity`, `maxCapacity`, `targetUtilizationPercent`) based on observed load.
    *   Consider AWS Savings Plans or Reserved Instances for stable workloads (RDS, On-Demand portion of Fargate) if you can commit to 1 or 3-year terms.
    *   Delete unused resources or stacks if not needed (e.g., development/staging stacks). `cdk destroy AwsStack` will remove the stack.

## Infrastructure as Code (IaC) - CDK and Terraform

This repository contains IaC configurations in both AWS CDK (`deployment/aws/`) and Terraform (`terraform/aws/`).

*   **Current Status:** The CDK setup is more comprehensive and directly manages the deployment of application services on ECS. The Terraform configuration sets up some base infrastructure but does not deploy the application services themselves.
*   **Recommendation:** For managing this application and its infrastructure on AWS, we strongly recommend **consolidating to AWS CDK as the primary IaC tool.** This simplifies management, reduces the risk of configuration drift between tools, and leverages CDK's strengths in defining application infrastructure. If you choose to use Terraform for foundational networking, ensure a very clear and strict separation of managed resources to avoid conflicts.

## Troubleshooting

*   Check CloudWatch Logs for Fargate tasks, ALB, and RDS.
*   Verify security group rules and NACLs.
*   Ensure IAM permissions are correctly configured.
*   Check the status of ECS services and tasks in the ECS console.
*   For CDK issues, use `cdk doctor` or increase verbosity during deployment (`cdk deploy -v`).

This optimized AWS CDK strategy provides a robust and scalable platform for small businesses while incorporating measures for cost control.
