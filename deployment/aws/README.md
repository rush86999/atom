# Deploying Atomic Calendar on AWS (Optimized for Small Businesses)

This guide details how to deploy the Atomic Calendar application on AWS using the provided AWS Cloud Development Kit (CDK) scripts. This setup is optimized for small businesses, balancing cost-effectiveness, scalability, and maintainability by leveraging AWS managed services.

## AWS Deployment Overview

This guide details how to deploy the Atom application to your personal AWS account using the AWS Cloud Development Kit (CDK). This deployment method is optimized for performance, scalability, and cost-effectiveness, making it ideal for small businesses and individuals who want full control over their environment.

### Core Architecture

The CDK script in `lib/aws-stack.ts` provisions a robust and scalable infrastructure:

*   **Serverless Compute:** Application services are deployed as containers using **Amazon ECS on AWS Fargate**, eliminating the need to manage servers.
*   **Cost Optimization:** The stack is designed to be cost-effective, using **Fargate Spot** for stateless services and **auto-scaling** to adjust resources based on demand.
*   **Reliable Database:** A **multi-AZ Amazon RDS for PostgreSQL** instance ensures high availability and data durability, with automated backups and deletion protection.
*   **Secure Networking:** A dedicated **VPC** with public and private subnets, along with an **Application Load Balancer (ALB)**, provides a secure and scalable network environment.
*   **Centralized Operations:** The stack includes **centralized logging with CloudWatch**, **foundational distributed tracing with AWS X-Ray**, and **persistent storage with Amazon S3 and EFS**.

## Prerequisites

1.  **AWS Account:** An active AWS account.
2.  **AWS CLI:** Configured with credentials and a default region.
3.  **Node.js and npm/yarn:** Required for CDK.
4.  **AWS CDK Toolkit:** Installed globally (`npm install -g aws-cdk`).
5.  **Docker:** Installed locally if you need to build and push Docker images to ECR.
6.  **Git:** To clone the repository.

## Deployment Steps

### 1. Initial Setup

1.  **Clone the repository** and navigate to the AWS deployment directory:
    ```bash
    git clone <your_repository_url>
    cd <repository_directory>/deployment/aws
    ```
2.  **Install CDK dependencies:**
    ```bash
    npm install
    ```
3.  **Bootstrap your AWS account** (only required if you have never used CDK in this account and region):
    ```bash
    cdk bootstrap aws://<YOUR_AWS_ACCOUNT_ID>/<YOUR_AWS_REGION>
    ```

### 2. Review and Configure the Stack

Before deploying, review the configuration in `lib/aws-stack.ts`. You can customize:
*   **Service sizes and auto-scaling parameters:** Adjust the default CPU, memory, and scaling policies for each service to match your expected load and budget.
*   **RDS instance type:** The default is `db.t3.small`. You can choose a different instance type based on your needs.

### 3. Build and Push Docker Images

The CDK stack will create Amazon ECR repositories for each service. You need to build your application's Docker images and push them to these repositories.

1.  **Authenticate Docker with your ECR registry:**
    ```bash
    aws ecr get-login-password --region <YOUR_AWS_REGION> | docker login --username AWS --password-stdin <YOUR_AWS_ACCOUNT_ID>.dkr.ecr.<YOUR_AWS_REGION>.amazonaws.com
    ```
2.  **Run the build and push script:** The `build_and_push_all.sh` script in the `build_scripts` directory is provided to streamline this process.
    ```bash
    cd build_scripts
    ./build_and_push_all.sh <YOUR_AWS_ACCOUNT_ID>.dkr.ecr.<YOUR_AWS_REGION>.amazonaws.com <TAG_NAME>
    ```
    Replace the placeholders with your ECR registry URL and a tag (e.g., `latest`).

### 4. Deploy the CDK Stack

1.  **Synthesize the stack** (optional, to generate a CloudFormation template):
    ```bash
    cdk synth
    ```
2.  **Deploy the stack:**
    ```bash
    cdk deploy AwsStack
    ```
    This process will take 15-30 minutes to provision all the resources. You may be prompted to approve IAM-related changes.

### 5. Post-Deployment Configuration

After the deployment is complete, you need to perform a few manual configuration steps:

1.  **Update secrets in AWS Secrets Manager:**
    *   The CDK stack automatically creates secrets in AWS Secrets Manager. However, you must manually populate the values for external services (e.g., `OpenAiApiKey`, `NotionApiToken`) and database connection strings.
    *   Navigate to the AWS Secrets Manager console, find the secrets created by the stack, and update their values. The required format for each secret is provided in its description.
2.  **Configure your DNS:**
    *   The CDK deployment will output the DNS name of the Application Load Balancer (`AlbDnsName`).
    *   In your DNS provider, create a CNAME record that points your custom domain to this ALB DNS name.
3.  **Initialize the database schema:**
    *   PostGraphile automatically detects your database schema. You can use a tool like `sqitch` or run the SQL scripts in the `db_init_scripts` directory to initialize the schema.

## Cost Management

Running this stack on AWS will incur costs. Key cost drivers include:
*   **AWS Fargate:** Billed per second for vCPU and memory.
*   **Amazon RDS:** Billed per hour for the database instance.
*   **Application Load Balancer:** Billed per hour and per unit of traffic.
*   **NAT Gateway:** Billed per hour and per gigabyte of data processed.

To manage costs, we recommend that you:
*   **Monitor your usage:** Regularly review your AWS bill and use AWS Cost Explorer to understand your spending.
*   **Set up billing alerts:** Configure AWS Budgets to notify you when your costs exceed a certain threshold.
*   **Fine-tune auto-scaling:** Adjust the auto-scaling parameters for your Fargate services to match your usage patterns.
*   **Clean up unused resources:** Use `cdk destroy AwsStack` to remove the stack and all its resources when they are no longer needed.

## Infrastructure as Code

This repository contains configurations for both AWS CDK and Terraform. However, the **CDK setup is the primary and most comprehensive method** for deploying the application. We strongly recommend using the CDK for all deployments to ensure consistency and avoid configuration drift.

## Troubleshooting

If you encounter issues during deployment or runtime, here are some steps you can take:

*   **Check CloudWatch Logs:** This is the best place to start. Review the logs for your Fargate tasks, ALB, and RDS instance to identify any errors.
*   **Verify ECS service status:** In the Amazon ECS console, check the status of your services and tasks. Look for any stopped tasks and review their logs.
*   **Check security groups and IAM roles:** Ensure that your security groups allow traffic between services and that your IAM roles have the necessary permissions.
*   **Use the CDK toolkit:** The `cdk doctor` command can help diagnose issues with your CDK environment. For more detailed output during deployment, use the `-v` flag (`cdk deploy -v`).

This optimized AWS CDK strategy provides a robust and scalable platform for small businesses while incorporating measures for cost control.

---

## Advanced Configuration

### HTTPS and Custom Domains

For a production-ready deployment, it is essential to configure HTTPS and a custom domain. The CDK stack simplifies this process.

**CloudFormation Parameters**

When you deploy the stack, you will be prompted for the following parameters:

*   `DeploymentStage`: The deployment stage (`dev`, `staging`, or `prod`).
*   `DomainName`: Your custom domain name (e.g., `app.yourcompany.com`).
*   `CertificateArn`: (Optional) The ARN of an existing ACM certificate. If you leave this blank, the stack will attempt to create a new one.
*   `OperatorEmail`: The email address for operational alerts.

**Certificate Creation**

*   **With Route 53:** If your domain is managed in AWS Route 53, the stack will automatically create and validate a new ACM certificate.
*   **Without Route 53:** If your domain is managed by another provider, you will need to manually create the required CNAME records in your DNS provider's console to validate the certificate.

**Post-Deployment Verification**

1.  **Configure your DNS:** Create a CNAME or Alias record in your DNS provider that points your custom domain to the ALB's DNS name (provided as a CloudFormation output).
2.  **Test your setup:** Navigate to `https://<YourDomainName>` to verify that your application is accessible over HTTPS. Also, test that navigating to the `http` version automatically redirects to `https`.

### Monitoring and Alerting

The CDK stack includes a comprehensive monitoring and alerting setup using CloudWatch.

**CloudWatch Alarms**

The following alarms are configured by default:

*   **ALB Alarms:** High 5XX error rates, unhealthy hosts, and high target latency for each service.
*   **ECS Service Alarms:** High CPU utilization for key services.
*   **RDS Instance Alarms:** High CPU utilization, low free storage space, low freeable memory, and high database connections.

**SNS Notifications**

All alarms send notifications to an SNS topic. You must confirm the subscription sent to the `OperatorEmail` to start receiving alerts.

**System Health Dashboard**

A CloudWatch Dashboard is automatically created to provide a centralized view of your system's health. The URL for this dashboard is provided as a CloudFormation output.
