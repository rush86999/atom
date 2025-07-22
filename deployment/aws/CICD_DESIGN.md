# Foundational CI/CD Pipeline Design for AWS Deployment

This document outlines the foundational design for a CI/CD (Continuous Integration/Continuous Deployment) pipeline to automate the deployment of the Atomic project to AWS.

## 1. Chosen CI/CD Platform: GitHub Actions

**Rationale:**

*   **Native GitHub Integration:** Seamlessly integrates with the project's source code if hosted on GitHub. Pipeline definitions live in-repo (`.github/workflows/*.yml`).
*   **AWS OIDC Integration:** Supports OpenID Connect (OIDC) for secure, keyless authentication with AWS, enhancing security by avoiding long-lived AWS access keys.
*   **Managed Infrastructure:** GitHub provides managed runners, reducing operational overhead (self-hosted runners are also an option).
*   **Marketplace & Community:** Access to a large marketplace of pre-built actions simplifies common tasks.
*   **Cost-Effective:** Offers a generous free tier for public repositories and reasonable pricing for private ones.
*   **Workflow Visualization & Environment Protection:** Provides clear UI for runs, logs, and supports environment protection rules (e.g., manual approvals for production).

## 2. Pipeline Triggers and Workflow Structure

The CI/CD process will be structured around different events and branches to support code quality checks and deployments to various environments (e.g., staging, production).

**Triggers:**

1.  **Pull Requests to `develop` or `main` branches:**
    *   **Purpose:** Ensure code quality and preview infrastructure changes before merging.
    *   **Actions:** Linting, unit testing, CDK diff.
2.  **Pushes to `develop` branch:**
    *   **Purpose:** Automatically deploy to a "staging" environment for testing.
    *   **Actions:** Build Docker images, push to ECR (staging tags), deploy CDK stack to staging, run post-deployment scripts.
3.  **Pushes to `main` branch:**
    *   **Purpose:** Deploy to the "production" environment.
    *   **Actions:** Build Docker images, push to ECR (production tags), **require manual approval**, deploy CDK stack to production, run post-deployment scripts.

**Proposed Workflow Structure (GitHub Actions):**

It's recommended to use separate workflow files for clarity:

*   `pr-checks.yml`: Handles triggers on pull requests.
*   `deploy.yml`: Handles triggers on pushes to `develop` and `main` branches.

## 3. Core Pipeline Stages and Jobs

### Workflow: `pr-checks.yml` (Trigger: Pull Request to `develop`/`main`)

*   **Job: `lint_and_static_analysis`**
    *   Checks out code, sets up Node.js, installs dependencies.
    *   Runs linters (e.g., ESLint for CDK/TypeScript).
    *   **CDK Static Analysis:** Runs `cdk synth` (e.g., as part of `cdk diff` or a dedicated linting step like `npm run lint:iac`) which will trigger `cdk-nag` checks (e.g., `AwsSolutionsChecks`) to validate the CDK stack against AWS best practices. Findings from `cdk-nag` should ideally fail the pipeline if critical.
    *   (Placeholder for CR1) Integrates additional static security analysis tools (e.g., Snyk, SonarCloud for broader code analysis if applicable).
*   **Job: `unit_tests`**
    *   Checks out code, sets up Node.js, installs dependencies.
    *   Runs CDK unit tests (`npm test` from `deployment/aws`). These tests should use `aws-cdk-lib/assertions` to validate the synthesized CloudFormation template, focusing on critical resource properties, security configurations (e.g., HTTPS listeners, security group rules), and reliability features (e.g., RDS MultiAZ, deletion protection).
    *   (Placeholder for CR2) Runs any application-specific unit tests for individual microservices (this might involve different setup steps per service).
*   **Job: `cdk_diff`**
    *   Checks out code, sets up Node.js, installs CDK dependencies.
    *   Configures AWS credentials (ideally via OIDC).
    *   Runs `cdk diff AwsStack --parameters ...` against a staging-like configuration. This step also implicitly runs `cdk-nag` checks due to the synthesis. The diff output can be posted as a PR comment.

### Workflow: `deploy.yml` (Trigger: Push to `develop`/`main`)

*   **Job: `build_and_push_images`**
    *   Runs for all services (e.g., using a matrix strategy for `app`, `functions`, etc.).
    *   Checks out code.
    *   Logs into AWS ECR (via OIDC role).
    *   Determines image tag based on branch (`develop` gets Git SHA, `main` gets `latest` or version tag).
    *   Builds the Docker image for the service.
    *   Pushes the image to its respective ECR repository.
*   **Job: `deploy_staging`**
    *   **Condition:** Runs on push to `develop` branch.
    *   **Depends on:** `build_and_push_images`.
    *   **GitHub Environment:** Uses `staging` environment for secrets/variables.
    *   **Steps:**
        *   Checkout code, setup Node.js, install CDK dependencies.
        *   Configure AWS credentials using OIDC and a role specific to staging deployment.
            *   Run `cdk deploy AwsStackStaging --require-approval never --parameters ...` (passing staging-specific parameters like domain name, email). Image tags generated in the `build_and_push_images` job need to be passed to the CDK application, for example, via `cdk.context.json` or as explicit CDK parameters.
        *   Run post-deployment scripts (e.g., database schema migrations).
*   **Job: `deploy_production`**
    *   **Condition:** Runs on push to `main` branch.
    *   **Depends on:** `build_and_push_images`.
    *   **GitHub Environment:** Uses `production` environment, configured with a **manual approval requirement**.
    *   **Steps:**
        *   (Manual approval step enforced by GitHub Environments).
        *   Checkout code, setup Node.js, install CDK dependencies.
        *   Configure AWS credentials using OIDC and a role specific to production deployment.
        *   Run `cdk deploy AwsStackProduction --require-approval never --parameters ...` (passing production-specific parameters). Image tags (e.g., `latest` or a version tag) from the `build_and_push_images` job need to be passed to the CDK application.
        *   Run post-deployment scripts for production.

## 4. Secret Management for CI/CD

Securely managing secrets and configuration is paramount.

*   **AWS Credentials for CI/CD:**
    *   **Method:** GitHub Actions OIDC with IAM Roles.
    *   **Setup:**
        1.  Configure an IAM OIDC provider in AWS trusting GitHub.
        2.  Create IAM roles (e.g., `GitHubActionsStagingDeployRole`, `GitHubActionsProductionDeployRole`) with necessary permissions (ECR push, CloudFormation deploy, Secrets Manager read for scripts if needed).
        3.  Trust policies on these roles will allow assumption by GitHub Actions workflows, scoped to specific repositories/branches.
    *   **Workflow:** Use `aws-actions/configure-aws-credentials` action with the appropriate `role-to-assume`.

*   **Application Secrets & Configuration Parameters (e.g., `DomainName`, `OperatorEmail`, `CertificateArn`):**
    *   **Method:** GitHub Environments with associated Environment Secrets (for sensitive values) and Environment Variables (for non-sensitive config).
    *   **Usage:** Define environments like `staging` and `production` in GitHub. Store parameters there and access them in workflow jobs via `secrets.MY_SECRET` or `vars.MY_VARIABLE`.

*   **Runtime Secrets for Post-Deployment Scripts:**
    *   **Ideal:** Scripts should use the IAM role assumed by the CI/CD job (which should have `secretsmanager:GetSecretValue` permission for the specific secret) to fetch the secret directly from AWS Secrets Manager using AWS CLI or SDK.
    *   **Alternative:** Store the ARN of the secret in GitHub Environment Secrets, and the script fetches it using that ARN.
    *   **Avoid:** Passing raw secret values directly as script arguments or environment variables in the CI/CD job logs.

## 5. Next Steps / Future Enhancements

*   Detailed implementation of the YAML workflow files based on this design.
*   **CR1 - Static Analysis:**
    *   Full configuration of `cdk-nag` suppressions or remediations for any findings.
    *   Integration of other static analysis tools (e.g., for application code security, Dockerfile best practices).
*   **CR2 - Unit Tests:**
    *   Expansion of CDK unit tests to cover more specific resource configurations and edge cases.
    *   Development and integration of unit tests for each application microservice.
*   More sophisticated image tagging strategies (e.g., semantic versioning based on Git tags).
*   Automated rollback strategies for failed deployments.
*   Notifications for pipeline status (success/failure) to relevant channels.

This design provides a solid foundation for automating AWS deployments for the Atomic project, enhancing reliability and speed of delivery.
