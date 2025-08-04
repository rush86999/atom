#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { AwsStack } from '../lib/aws-stack';

import { Aspects } from 'aws-cdk-lib';
import { AwsSolutionsChecks, NagSuppressions } from 'cdk-nag';

const app = new cdk.App();
const awsStack = new AwsStack(app, 'AwsStack', {
  /* If you don't specify 'env', this stack will be environment-agnostic.
   * Account/Region-dependent features and context lookups will not work,
   * but a single synthesized template can be deployed anywhere. */
  /* Uncomment the next line to specialize this stack for the AWS Account
   * and Region that are implied by the current CLI configuration. */
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  /* Uncomment the next line if you know exactly what Account and Region you
   * want to deploy the stack to. */
  // env: { account: '123456789012', region: 'us-east-1' },

  /* For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html */
});

// Apply cdk-nag checks and suppress common findings
Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

NagSuppressions.addStackSuppressions(awsStack, [
  {
    id: 'AwsSolutions-SNS3',
    reason: 'Suppressing SSL check for this workshop',
  },
  {
    id: 'AwsSolutions-VPC7',
    reason: 'Suppressing VPC flow logs for this workshop',
  },
  {
    id: 'AwsSolutions-ECS4',
    reason: 'Suppressing Container Insights for this workshop',
  },
  {
    id: 'AwsSolutions-IAM5',
    reason: 'Suppressing IAM wildcard permissions for this workshop',
  },
  {
    id: 'AwsSolutions-RDS2',
    reason: 'Suppressing RDS storage encryption for this workshop',
  },
  {
    id: 'AwsSolutions-RDS3',
    reason: 'Suppressing RDS multi-AZ for this workshop',
  },
  {
    id: 'AwsSolutions-RDS10',
    reason: 'Suppressing RDS deletion protection for this workshop',
  },
  {
    id: 'AwsSolutions-S1',
    reason:
      'S3 server access logging is not implemented for the data bucket in this phase.',
  },
  {
    id: 'AwsSolutions-ELB2',
    reason: 'ALB access logging is not implemented in this phase.',
  },
  {
    id: 'AwsSolutions-RDS6',
    reason:
      'IAM DB Authentication is not currently a requirement; using native DB auth with Secrets Manager.',
  },
  {
    id: 'AwsSolutions-RDS11',
    reason:
      'Using standard DB port is acceptable for this internal RDS instance.',
  },
  {
    id: 'AwsSolutions-EC23',
    reason:
      'Restricting all security group egress is a larger hardening task deferred for now.',
  },
  {
    id: 'AwsSolutions-ECS2',
    reason:
      'Read-only root filesystem for ECS tasks requires per-service analysis and is deferred.',
  },
  {
    id: 'AwsSolutions-EFS3',
    reason:
      'EFS default encryption (AWS-managed KMS key) is considered sufficient for this phase.',
  },
  {
    id: 'AwsSolutions-LOG1',
    reason:
      'CloudWatch Log groups are not encrypted with KMS by default in this stack; using default AWS-managed encryption.',
  },
]);
const nagPack = new AwsSolutionsChecks({ verbose: true });
Aspects.of(app).add(nagPack);

// Add suppressions globally or to specific constructs as needed.
// Example global suppressions for common findings that might be acceptable
// or out of scope for immediate remediation for this project stage.
// Always provide a clear reason for suppression.

NagSuppressions.addStackSuppressions(awsStack, [
  {
    id: 'AwsSolutions-S1',
    reason:
      'S3 server access logging is not implemented for the data bucket in this phase.',
  },
  {
    id: 'AwsSolutions-ELB2',
    reason: 'ALB access logging is not implemented in this phase.',
  },
  {
    id: 'AwsSolutions-RDS6',
    reason:
      'IAM DB Authentication is not currently a requirement; using native DB auth with Secrets Manager.',
  },
  {
    id: 'AwsSolutions-RDS11',
    reason:
      'Using standard DB port is acceptable for this internal RDS instance.',
  },
  {
    id: 'AwsSolutions-EC23',
    reason:
      'Restricting all security group egress is a larger hardening task deferred for now.',
  },
  {
    id: 'AwsSolutions-ECS2',
    reason:
      'Read-only root filesystem for ECS tasks requires per-service analysis and is deferred.',
  },
  {
    id: 'AwsSolutions-EFS3',
    reason:
      'EFS default encryption (AWS-managed KMS key) is considered sufficient for this phase.',
  },
  {
    id: 'AwsSolutions-LOG1',
    reason:
      'CloudWatch Log groups are not encrypted with KMS by default in this stack; using default AWS-managed encryption.',
  },
]);

// Note: Finding the exact path for role-specific suppressions can be tricky.
// It often involves looking at the logical ID path in the synthesized template.
// Example: 'AwsStack/ECSTaskRole/DefaultPolicy/Resource'
// For now, if AwsSolutions-IAM5 is flagged for X-Ray permissions on ecsTaskRole,
// a more targeted suppression would be added in aws-stack.ts directly on the role or its policy.
// A global suppression for IAM5 is generally not recommended.
// However, the X-Ray permissions are standard, so if a global suppression for this specific case is needed:
// nagPack.addReasonToSuppress(awsStack, 'AwsSolutions-IAM5', 'ECS Task Role needs wildcard resource for xray:PutTraceSegments and xray:PutTelemetryRecords as per AWS X-Ray documentation for segment submission.');
// It's better to apply this directly to the role or policy if possible.
// We will assume for now that if this rule triggers, it will be handled by a more specific suppression in lib/aws-stack.ts.

// Specific suppressions might be needed on constructs within aws-stack.ts if global ones are too broad.
// For example, for IAM5 on specific roles if a wildcard is justified for a specific AWS-managed policy scenario.
// Example: nagPack.addReasonToSuppress(someConstruct, 'AwsSolutions-IAM5', 'Reason for this specific resource needing this permission.');
