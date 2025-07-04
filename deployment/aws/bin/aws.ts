#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { AwsStack } from '../lib/aws-stack';

import { Aspects } from 'aws-cdk-lib';
import { AwsSolutionsChecks } from 'cdk-nag';

const app = new cdk.App();
const awsStack = new AwsStack(app, 'AwsStack', {
  /* If you don't specify 'env', this stack will be environment-agnostic.
   * Account/Region-dependent features and context lookups will not work,
   * but a single synthesized template can be deployed anywhere. */

  /* Uncomment the next line to specialize this stack for the AWS Account
   * and Region that are implied by the current CLI configuration. */
  // env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },

  /* Uncomment the next line if you know exactly what Account and Region you
   * want to deploy the stack to. */
  // env: { account: '123456789012', region: 'us-east-1' },

  /* For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html */
});

// Apply cdk-nag checks and suppress common findings
const nagPack = new AwsSolutionsChecks({ verbose: true });
Aspects.of(app).add(nagPack);

// Add suppressions globally or to specific constructs as needed.
// Example global suppressions for common findings that might be acceptable
// or out of scope for immediate remediation for this project stage.
// Always provide a clear reason for suppression.

nagPack.addReasonToSuppress(awsStack, 'AwsSolutions-S1', 'S3 server access logging is not implemented for the data bucket in this phase.');
nagPack.addReasonToSuppress(awsStack, 'AwsSolutions-ELB2', 'ALB access logging is not implemented in this phase.');
nagPack.addReasonToSuppress(awsStack, 'AwsSolutions-RDS6', 'IAM DB Authentication is not currently a requirement; using native DB auth with Secrets Manager.');
nagPack.addReasonToSuppress(awsStack, 'AwsSolutions-RDS11', 'Using standard DB port is acceptable for this internal RDS instance.');
nagPack.addReasonToSuppress(awsStack, 'AwsSolutions-EC23', 'Restricting all security group egress is a larger hardening task deferred for now.');
nagPack.addReasonToSuppress(awsStack, 'AwsSolutions-ECS2', 'Read-only root filesystem for ECS tasks requires per-service analysis and is deferred.');
nagPack.addReasonToSuppress(awsStack, 'AwsSolutions-EFS3', 'EFS default encryption (AWS-managed KMS key) is considered sufficient for this phase.');
nagPack.addReasonToSuppress(awsStack, 'AwsSolutions-LOG1', 'CloudWatch Log groups are not encrypted with KMS by default in this stack; using default AWS-managed encryption.');

// Specific suppressions might be needed on constructs within aws-stack.ts if global ones are too broad.
// For example, for IAM5 on specific roles if a wildcard is justified for a specific AWS-managed policy scenario.
// Example: nagPack.addReasonToSuppress(someConstruct, 'AwsSolutions-IAM5', 'Reason for this specific resource needing this permission.');