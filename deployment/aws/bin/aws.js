#!/usr/bin/env node
"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const cdk = __importStar(require("aws-cdk-lib"));
const aws_stack_1 = require("../lib/aws-stack");
const aws_cdk_lib_1 = require("aws-cdk-lib");
const cdk_nag_1 = require("cdk-nag");
const app = new cdk.App();
const awsStack = new aws_stack_1.AwsStack(app, 'AwsStack', {
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
aws_cdk_lib_1.Aspects.of(app).add(new cdk_nag_1.AwsSolutionsChecks({ verbose: true }));
cdk_nag_1.NagSuppressions.addStackSuppressions(awsStack, [
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
        reason: 'S3 server access logging is not implemented for the data bucket in this phase.',
    },
    {
        id: 'AwsSolutions-ELB2',
        reason: 'ALB access logging is not implemented in this phase.',
    },
    {
        id: 'AwsSolutions-RDS6',
        reason: 'IAM DB Authentication is not currently a requirement; using native DB auth with Secrets Manager.',
    },
    {
        id: 'AwsSolutions-RDS11',
        reason: 'Using standard DB port is acceptable for this internal RDS instance.',
    },
    {
        id: 'AwsSolutions-EC23',
        reason: 'Restricting all security group egress is a larger hardening task deferred for now.',
    },
    {
        id: 'AwsSolutions-ECS2',
        reason: 'Read-only root filesystem for ECS tasks requires per-service analysis and is deferred.',
    },
    {
        id: 'AwsSolutions-EFS3',
        reason: 'EFS default encryption (AWS-managed KMS key) is considered sufficient for this phase.',
    },
    {
        id: 'AwsSolutions-LOG1',
        reason: 'CloudWatch Log groups are not encrypted with KMS by default in this stack; using default AWS-managed encryption.',
    },
]);
const nagPack = new cdk_nag_1.AwsSolutionsChecks({ verbose: true });
aws_cdk_lib_1.Aspects.of(app).add(nagPack);
// Add suppressions globally or to specific constructs as needed.
// Example global suppressions for common findings that might be acceptable
// or out of scope for immediate remediation for this project stage.
// Always provide a clear reason for suppression.
cdk_nag_1.NagSuppressions.addStackSuppressions(awsStack, [
    {
        id: 'AwsSolutions-S1',
        reason: 'S3 server access logging is not implemented for the data bucket in this phase.',
    },
    {
        id: 'AwsSolutions-ELB2',
        reason: 'ALB access logging is not implemented in this phase.',
    },
    {
        id: 'AwsSolutions-RDS6',
        reason: 'IAM DB Authentication is not currently a requirement; using native DB auth with Secrets Manager.',
    },
    {
        id: 'AwsSolutions-RDS11',
        reason: 'Using standard DB port is acceptable for this internal RDS instance.',
    },
    {
        id: 'AwsSolutions-EC23',
        reason: 'Restricting all security group egress is a larger hardening task deferred for now.',
    },
    {
        id: 'AwsSolutions-ECS2',
        reason: 'Read-only root filesystem for ECS tasks requires per-service analysis and is deferred.',
    },
    {
        id: 'AwsSolutions-EFS3',
        reason: 'EFS default encryption (AWS-managed KMS key) is considered sufficient for this phase.',
    },
    {
        id: 'AwsSolutions-LOG1',
        reason: 'CloudWatch Log groups are not encrypted with KMS by default in this stack; using default AWS-managed encryption.',
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXdzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiYXdzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztBQUNBLGlEQUFtQztBQUNuQyxnREFBNEM7QUFFNUMsNkNBQXNDO0FBQ3RDLHFDQUE4RDtBQUU5RCxNQUFNLEdBQUcsR0FBRyxJQUFJLEdBQUcsQ0FBQyxHQUFHLEVBQUUsQ0FBQztBQUMxQixNQUFNLFFBQVEsR0FBRyxJQUFJLG9CQUFRLENBQUMsR0FBRyxFQUFFLFVBQVUsRUFBRTtJQUM3Qzs7cUVBRWlFO0lBQ2pFO3VFQUNtRTtJQUNuRSxHQUFHLEVBQUU7UUFDSCxPQUFPLEVBQUUsT0FBTyxDQUFDLEdBQUcsQ0FBQyxtQkFBbUI7UUFDeEMsTUFBTSxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsa0JBQWtCO0tBQ3ZDO0lBQ0Q7c0NBQ2tDO0lBQ2xDLHlEQUF5RDtJQUV6RCw4RkFBOEY7Q0FDL0YsQ0FBQyxDQUFDO0FBRUgsb0RBQW9EO0FBQ3BELHFCQUFPLENBQUMsRUFBRSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxJQUFJLDRCQUFrQixDQUFDLEVBQUUsT0FBTyxFQUFFLElBQUksRUFBRSxDQUFDLENBQUMsQ0FBQztBQUUvRCx5QkFBZSxDQUFDLG9CQUFvQixDQUFDLFFBQVEsRUFBRTtJQUM3QztRQUNFLEVBQUUsRUFBRSxtQkFBbUI7UUFDdkIsTUFBTSxFQUFFLHlDQUF5QztLQUNsRDtJQUNEO1FBQ0UsRUFBRSxFQUFFLG1CQUFtQjtRQUN2QixNQUFNLEVBQUUsNkNBQTZDO0tBQ3REO0lBQ0Q7UUFDRSxFQUFFLEVBQUUsbUJBQW1CO1FBQ3ZCLE1BQU0sRUFBRSxrREFBa0Q7S0FDM0Q7SUFDRDtRQUNFLEVBQUUsRUFBRSxtQkFBbUI7UUFDdkIsTUFBTSxFQUFFLHdEQUF3RDtLQUNqRTtJQUNEO1FBQ0UsRUFBRSxFQUFFLG1CQUFtQjtRQUN2QixNQUFNLEVBQUUsc0RBQXNEO0tBQy9EO0lBQ0Q7UUFDRSxFQUFFLEVBQUUsbUJBQW1CO1FBQ3ZCLE1BQU0sRUFBRSw0Q0FBNEM7S0FDckQ7SUFDRDtRQUNFLEVBQUUsRUFBRSxvQkFBb0I7UUFDeEIsTUFBTSxFQUFFLHVEQUF1RDtLQUNoRTtJQUNEO1FBQ0UsRUFBRSxFQUFFLGlCQUFpQjtRQUNyQixNQUFNLEVBQ0osZ0ZBQWdGO0tBQ25GO0lBQ0Q7UUFDRSxFQUFFLEVBQUUsbUJBQW1CO1FBQ3ZCLE1BQU0sRUFBRSxzREFBc0Q7S0FDL0Q7SUFDRDtRQUNFLEVBQUUsRUFBRSxtQkFBbUI7UUFDdkIsTUFBTSxFQUNKLGtHQUFrRztLQUNyRztJQUNEO1FBQ0UsRUFBRSxFQUFFLG9CQUFvQjtRQUN4QixNQUFNLEVBQ0osc0VBQXNFO0tBQ3pFO0lBQ0Q7UUFDRSxFQUFFLEVBQUUsbUJBQW1CO1FBQ3ZCLE1BQU0sRUFDSixvRkFBb0Y7S0FDdkY7SUFDRDtRQUNFLEVBQUUsRUFBRSxtQkFBbUI7UUFDdkIsTUFBTSxFQUNKLHdGQUF3RjtLQUMzRjtJQUNEO1FBQ0UsRUFBRSxFQUFFLG1CQUFtQjtRQUN2QixNQUFNLEVBQ0osdUZBQXVGO0tBQzFGO0lBQ0Q7UUFDRSxFQUFFLEVBQUUsbUJBQW1CO1FBQ3ZCLE1BQU0sRUFDSixrSEFBa0g7S0FDckg7Q0FDRixDQUFDLENBQUM7QUFDSCxNQUFNLE9BQU8sR0FBRyxJQUFJLDRCQUFrQixDQUFDLEVBQUUsT0FBTyxFQUFFLElBQUksRUFBRSxDQUFDLENBQUM7QUFDMUQscUJBQU8sQ0FBQyxFQUFFLENBQUMsR0FBRyxDQUFDLENBQUMsR0FBRyxDQUFDLE9BQU8sQ0FBQyxDQUFDO0FBRTdCLGlFQUFpRTtBQUNqRSwyRUFBMkU7QUFDM0Usb0VBQW9FO0FBQ3BFLGlEQUFpRDtBQUVqRCx5QkFBZSxDQUFDLG9CQUFvQixDQUFDLFFBQVEsRUFBRTtJQUM3QztRQUNFLEVBQUUsRUFBRSxpQkFBaUI7UUFDckIsTUFBTSxFQUNKLGdGQUFnRjtLQUNuRjtJQUNEO1FBQ0UsRUFBRSxFQUFFLG1CQUFtQjtRQUN2QixNQUFNLEVBQUUsc0RBQXNEO0tBQy9EO0lBQ0Q7UUFDRSxFQUFFLEVBQUUsbUJBQW1CO1FBQ3ZCLE1BQU0sRUFDSixrR0FBa0c7S0FDckc7SUFDRDtRQUNFLEVBQUUsRUFBRSxvQkFBb0I7UUFDeEIsTUFBTSxFQUNKLHNFQUFzRTtLQUN6RTtJQUNEO1FBQ0UsRUFBRSxFQUFFLG1CQUFtQjtRQUN2QixNQUFNLEVBQ0osb0ZBQW9GO0tBQ3ZGO0lBQ0Q7UUFDRSxFQUFFLEVBQUUsbUJBQW1CO1FBQ3ZCLE1BQU0sRUFDSix3RkFBd0Y7S0FDM0Y7SUFDRDtRQUNFLEVBQUUsRUFBRSxtQkFBbUI7UUFDdkIsTUFBTSxFQUNKLHVGQUF1RjtLQUMxRjtJQUNEO1FBQ0UsRUFBRSxFQUFFLG1CQUFtQjtRQUN2QixNQUFNLEVBQ0osa0hBQWtIO0tBQ3JIO0NBQ0YsQ0FBQyxDQUFDO0FBRUgsNkVBQTZFO0FBQzdFLGdGQUFnRjtBQUNoRix5REFBeUQ7QUFDekQsaUZBQWlGO0FBQ2pGLGlHQUFpRztBQUNqRyw4REFBOEQ7QUFDOUQsNEdBQTRHO0FBQzVHLHFOQUFxTjtBQUNyTix3RUFBd0U7QUFDeEUsNEhBQTRIO0FBRTVILHdHQUF3RztBQUN4RyxpSEFBaUg7QUFDakgsMElBQTBJIiwic291cmNlc0NvbnRlbnQiOlsiIyEvdXNyL2Jpbi9lbnYgbm9kZVxuaW1wb3J0ICogYXMgY2RrIGZyb20gJ2F3cy1jZGstbGliJztcbmltcG9ydCB7IEF3c1N0YWNrIH0gZnJvbSAnLi4vbGliL2F3cy1zdGFjayc7XG5cbmltcG9ydCB7IEFzcGVjdHMgfSBmcm9tICdhd3MtY2RrLWxpYic7XG5pbXBvcnQgeyBBd3NTb2x1dGlvbnNDaGVja3MsIE5hZ1N1cHByZXNzaW9ucyB9IGZyb20gJ2Nkay1uYWcnO1xuXG5jb25zdCBhcHAgPSBuZXcgY2RrLkFwcCgpO1xuY29uc3QgYXdzU3RhY2sgPSBuZXcgQXdzU3RhY2soYXBwLCAnQXdzU3RhY2snLCB7XG4gIC8qIElmIHlvdSBkb24ndCBzcGVjaWZ5ICdlbnYnLCB0aGlzIHN0YWNrIHdpbGwgYmUgZW52aXJvbm1lbnQtYWdub3N0aWMuXG4gICAqIEFjY291bnQvUmVnaW9uLWRlcGVuZGVudCBmZWF0dXJlcyBhbmQgY29udGV4dCBsb29rdXBzIHdpbGwgbm90IHdvcmssXG4gICAqIGJ1dCBhIHNpbmdsZSBzeW50aGVzaXplZCB0ZW1wbGF0ZSBjYW4gYmUgZGVwbG95ZWQgYW55d2hlcmUuICovXG4gIC8qIFVuY29tbWVudCB0aGUgbmV4dCBsaW5lIHRvIHNwZWNpYWxpemUgdGhpcyBzdGFjayBmb3IgdGhlIEFXUyBBY2NvdW50XG4gICAqIGFuZCBSZWdpb24gdGhhdCBhcmUgaW1wbGllZCBieSB0aGUgY3VycmVudCBDTEkgY29uZmlndXJhdGlvbi4gKi9cbiAgZW52OiB7XG4gICAgYWNjb3VudDogcHJvY2Vzcy5lbnYuQ0RLX0RFRkFVTFRfQUNDT1VOVCxcbiAgICByZWdpb246IHByb2Nlc3MuZW52LkNES19ERUZBVUxUX1JFR0lPTixcbiAgfSxcbiAgLyogVW5jb21tZW50IHRoZSBuZXh0IGxpbmUgaWYgeW91IGtub3cgZXhhY3RseSB3aGF0IEFjY291bnQgYW5kIFJlZ2lvbiB5b3VcbiAgICogd2FudCB0byBkZXBsb3kgdGhlIHN0YWNrIHRvLiAqL1xuICAvLyBlbnY6IHsgYWNjb3VudDogJzEyMzQ1Njc4OTAxMicsIHJlZ2lvbjogJ3VzLWVhc3QtMScgfSxcblxuICAvKiBGb3IgbW9yZSBpbmZvcm1hdGlvbiwgc2VlIGh0dHBzOi8vZG9jcy5hd3MuYW1hem9uLmNvbS9jZGsvbGF0ZXN0L2d1aWRlL2Vudmlyb25tZW50cy5odG1sICovXG59KTtcblxuLy8gQXBwbHkgY2RrLW5hZyBjaGVja3MgYW5kIHN1cHByZXNzIGNvbW1vbiBmaW5kaW5nc1xuQXNwZWN0cy5vZihhcHApLmFkZChuZXcgQXdzU29sdXRpb25zQ2hlY2tzKHsgdmVyYm9zZTogdHJ1ZSB9KSk7XG5cbk5hZ1N1cHByZXNzaW9ucy5hZGRTdGFja1N1cHByZXNzaW9ucyhhd3NTdGFjaywgW1xuICB7XG4gICAgaWQ6ICdBd3NTb2x1dGlvbnMtU05TMycsXG4gICAgcmVhc29uOiAnU3VwcHJlc3NpbmcgU1NMIGNoZWNrIGZvciB0aGlzIHdvcmtzaG9wJyxcbiAgfSxcbiAge1xuICAgIGlkOiAnQXdzU29sdXRpb25zLVZQQzcnLFxuICAgIHJlYXNvbjogJ1N1cHByZXNzaW5nIFZQQyBmbG93IGxvZ3MgZm9yIHRoaXMgd29ya3Nob3AnLFxuICB9LFxuICB7XG4gICAgaWQ6ICdBd3NTb2x1dGlvbnMtRUNTNCcsXG4gICAgcmVhc29uOiAnU3VwcHJlc3NpbmcgQ29udGFpbmVyIEluc2lnaHRzIGZvciB0aGlzIHdvcmtzaG9wJyxcbiAgfSxcbiAge1xuICAgIGlkOiAnQXdzU29sdXRpb25zLUlBTTUnLFxuICAgIHJlYXNvbjogJ1N1cHByZXNzaW5nIElBTSB3aWxkY2FyZCBwZXJtaXNzaW9ucyBmb3IgdGhpcyB3b3Jrc2hvcCcsXG4gIH0sXG4gIHtcbiAgICBpZDogJ0F3c1NvbHV0aW9ucy1SRFMyJyxcbiAgICByZWFzb246ICdTdXBwcmVzc2luZyBSRFMgc3RvcmFnZSBlbmNyeXB0aW9uIGZvciB0aGlzIHdvcmtzaG9wJyxcbiAgfSxcbiAge1xuICAgIGlkOiAnQXdzU29sdXRpb25zLVJEUzMnLFxuICAgIHJlYXNvbjogJ1N1cHByZXNzaW5nIFJEUyBtdWx0aS1BWiBmb3IgdGhpcyB3b3Jrc2hvcCcsXG4gIH0sXG4gIHtcbiAgICBpZDogJ0F3c1NvbHV0aW9ucy1SRFMxMCcsXG4gICAgcmVhc29uOiAnU3VwcHJlc3NpbmcgUkRTIGRlbGV0aW9uIHByb3RlY3Rpb24gZm9yIHRoaXMgd29ya3Nob3AnLFxuICB9LFxuICB7XG4gICAgaWQ6ICdBd3NTb2x1dGlvbnMtUzEnLFxuICAgIHJlYXNvbjpcbiAgICAgICdTMyBzZXJ2ZXIgYWNjZXNzIGxvZ2dpbmcgaXMgbm90IGltcGxlbWVudGVkIGZvciB0aGUgZGF0YSBidWNrZXQgaW4gdGhpcyBwaGFzZS4nLFxuICB9LFxuICB7XG4gICAgaWQ6ICdBd3NTb2x1dGlvbnMtRUxCMicsXG4gICAgcmVhc29uOiAnQUxCIGFjY2VzcyBsb2dnaW5nIGlzIG5vdCBpbXBsZW1lbnRlZCBpbiB0aGlzIHBoYXNlLicsXG4gIH0sXG4gIHtcbiAgICBpZDogJ0F3c1NvbHV0aW9ucy1SRFM2JyxcbiAgICByZWFzb246XG4gICAgICAnSUFNIERCIEF1dGhlbnRpY2F0aW9uIGlzIG5vdCBjdXJyZW50bHkgYSByZXF1aXJlbWVudDsgdXNpbmcgbmF0aXZlIERCIGF1dGggd2l0aCBTZWNyZXRzIE1hbmFnZXIuJyxcbiAgfSxcbiAge1xuICAgIGlkOiAnQXdzU29sdXRpb25zLVJEUzExJyxcbiAgICByZWFzb246XG4gICAgICAnVXNpbmcgc3RhbmRhcmQgREIgcG9ydCBpcyBhY2NlcHRhYmxlIGZvciB0aGlzIGludGVybmFsIFJEUyBpbnN0YW5jZS4nLFxuICB9LFxuICB7XG4gICAgaWQ6ICdBd3NTb2x1dGlvbnMtRUMyMycsXG4gICAgcmVhc29uOlxuICAgICAgJ1Jlc3RyaWN0aW5nIGFsbCBzZWN1cml0eSBncm91cCBlZ3Jlc3MgaXMgYSBsYXJnZXIgaGFyZGVuaW5nIHRhc2sgZGVmZXJyZWQgZm9yIG5vdy4nLFxuICB9LFxuICB7XG4gICAgaWQ6ICdBd3NTb2x1dGlvbnMtRUNTMicsXG4gICAgcmVhc29uOlxuICAgICAgJ1JlYWQtb25seSByb290IGZpbGVzeXN0ZW0gZm9yIEVDUyB0YXNrcyByZXF1aXJlcyBwZXItc2VydmljZSBhbmFseXNpcyBhbmQgaXMgZGVmZXJyZWQuJyxcbiAgfSxcbiAge1xuICAgIGlkOiAnQXdzU29sdXRpb25zLUVGUzMnLFxuICAgIHJlYXNvbjpcbiAgICAgICdFRlMgZGVmYXVsdCBlbmNyeXB0aW9uIChBV1MtbWFuYWdlZCBLTVMga2V5KSBpcyBjb25zaWRlcmVkIHN1ZmZpY2llbnQgZm9yIHRoaXMgcGhhc2UuJyxcbiAgfSxcbiAge1xuICAgIGlkOiAnQXdzU29sdXRpb25zLUxPRzEnLFxuICAgIHJlYXNvbjpcbiAgICAgICdDbG91ZFdhdGNoIExvZyBncm91cHMgYXJlIG5vdCBlbmNyeXB0ZWQgd2l0aCBLTVMgYnkgZGVmYXVsdCBpbiB0aGlzIHN0YWNrOyB1c2luZyBkZWZhdWx0IEFXUy1tYW5hZ2VkIGVuY3J5cHRpb24uJyxcbiAgfSxcbl0pO1xuY29uc3QgbmFnUGFjayA9IG5ldyBBd3NTb2x1dGlvbnNDaGVja3MoeyB2ZXJib3NlOiB0cnVlIH0pO1xuQXNwZWN0cy5vZihhcHApLmFkZChuYWdQYWNrKTtcblxuLy8gQWRkIHN1cHByZXNzaW9ucyBnbG9iYWxseSBvciB0byBzcGVjaWZpYyBjb25zdHJ1Y3RzIGFzIG5lZWRlZC5cbi8vIEV4YW1wbGUgZ2xvYmFsIHN1cHByZXNzaW9ucyBmb3IgY29tbW9uIGZpbmRpbmdzIHRoYXQgbWlnaHQgYmUgYWNjZXB0YWJsZVxuLy8gb3Igb3V0IG9mIHNjb3BlIGZvciBpbW1lZGlhdGUgcmVtZWRpYXRpb24gZm9yIHRoaXMgcHJvamVjdCBzdGFnZS5cbi8vIEFsd2F5cyBwcm92aWRlIGEgY2xlYXIgcmVhc29uIGZvciBzdXBwcmVzc2lvbi5cblxuTmFnU3VwcHJlc3Npb25zLmFkZFN0YWNrU3VwcHJlc3Npb25zKGF3c1N0YWNrLCBbXG4gIHtcbiAgICBpZDogJ0F3c1NvbHV0aW9ucy1TMScsXG4gICAgcmVhc29uOlxuICAgICAgJ1MzIHNlcnZlciBhY2Nlc3MgbG9nZ2luZyBpcyBub3QgaW1wbGVtZW50ZWQgZm9yIHRoZSBkYXRhIGJ1Y2tldCBpbiB0aGlzIHBoYXNlLicsXG4gIH0sXG4gIHtcbiAgICBpZDogJ0F3c1NvbHV0aW9ucy1FTEIyJyxcbiAgICByZWFzb246ICdBTEIgYWNjZXNzIGxvZ2dpbmcgaXMgbm90IGltcGxlbWVudGVkIGluIHRoaXMgcGhhc2UuJyxcbiAgfSxcbiAge1xuICAgIGlkOiAnQXdzU29sdXRpb25zLVJEUzYnLFxuICAgIHJlYXNvbjpcbiAgICAgICdJQU0gREIgQXV0aGVudGljYXRpb24gaXMgbm90IGN1cnJlbnRseSBhIHJlcXVpcmVtZW50OyB1c2luZyBuYXRpdmUgREIgYXV0aCB3aXRoIFNlY3JldHMgTWFuYWdlci4nLFxuICB9LFxuICB7XG4gICAgaWQ6ICdBd3NTb2x1dGlvbnMtUkRTMTEnLFxuICAgIHJlYXNvbjpcbiAgICAgICdVc2luZyBzdGFuZGFyZCBEQiBwb3J0IGlzIGFjY2VwdGFibGUgZm9yIHRoaXMgaW50ZXJuYWwgUkRTIGluc3RhbmNlLicsXG4gIH0sXG4gIHtcbiAgICBpZDogJ0F3c1NvbHV0aW9ucy1FQzIzJyxcbiAgICByZWFzb246XG4gICAgICAnUmVzdHJpY3RpbmcgYWxsIHNlY3VyaXR5IGdyb3VwIGVncmVzcyBpcyBhIGxhcmdlciBoYXJkZW5pbmcgdGFzayBkZWZlcnJlZCBmb3Igbm93LicsXG4gIH0sXG4gIHtcbiAgICBpZDogJ0F3c1NvbHV0aW9ucy1FQ1MyJyxcbiAgICByZWFzb246XG4gICAgICAnUmVhZC1vbmx5IHJvb3QgZmlsZXN5c3RlbSBmb3IgRUNTIHRhc2tzIHJlcXVpcmVzIHBlci1zZXJ2aWNlIGFuYWx5c2lzIGFuZCBpcyBkZWZlcnJlZC4nLFxuICB9LFxuICB7XG4gICAgaWQ6ICdBd3NTb2x1dGlvbnMtRUZTMycsXG4gICAgcmVhc29uOlxuICAgICAgJ0VGUyBkZWZhdWx0IGVuY3J5cHRpb24gKEFXUy1tYW5hZ2VkIEtNUyBrZXkpIGlzIGNvbnNpZGVyZWQgc3VmZmljaWVudCBmb3IgdGhpcyBwaGFzZS4nLFxuICB9LFxuICB7XG4gICAgaWQ6ICdBd3NTb2x1dGlvbnMtTE9HMScsXG4gICAgcmVhc29uOlxuICAgICAgJ0Nsb3VkV2F0Y2ggTG9nIGdyb3VwcyBhcmUgbm90IGVuY3J5cHRlZCB3aXRoIEtNUyBieSBkZWZhdWx0IGluIHRoaXMgc3RhY2s7IHVzaW5nIGRlZmF1bHQgQVdTLW1hbmFnZWQgZW5jcnlwdGlvbi4nLFxuICB9LFxuXSk7XG5cbi8vIE5vdGU6IEZpbmRpbmcgdGhlIGV4YWN0IHBhdGggZm9yIHJvbGUtc3BlY2lmaWMgc3VwcHJlc3Npb25zIGNhbiBiZSB0cmlja3kuXG4vLyBJdCBvZnRlbiBpbnZvbHZlcyBsb29raW5nIGF0IHRoZSBsb2dpY2FsIElEIHBhdGggaW4gdGhlIHN5bnRoZXNpemVkIHRlbXBsYXRlLlxuLy8gRXhhbXBsZTogJ0F3c1N0YWNrL0VDU1Rhc2tSb2xlL0RlZmF1bHRQb2xpY3kvUmVzb3VyY2UnXG4vLyBGb3Igbm93LCBpZiBBd3NTb2x1dGlvbnMtSUFNNSBpcyBmbGFnZ2VkIGZvciBYLVJheSBwZXJtaXNzaW9ucyBvbiBlY3NUYXNrUm9sZSxcbi8vIGEgbW9yZSB0YXJnZXRlZCBzdXBwcmVzc2lvbiB3b3VsZCBiZSBhZGRlZCBpbiBhd3Mtc3RhY2sudHMgZGlyZWN0bHkgb24gdGhlIHJvbGUgb3IgaXRzIHBvbGljeS5cbi8vIEEgZ2xvYmFsIHN1cHByZXNzaW9uIGZvciBJQU01IGlzIGdlbmVyYWxseSBub3QgcmVjb21tZW5kZWQuXG4vLyBIb3dldmVyLCB0aGUgWC1SYXkgcGVybWlzc2lvbnMgYXJlIHN0YW5kYXJkLCBzbyBpZiBhIGdsb2JhbCBzdXBwcmVzc2lvbiBmb3IgdGhpcyBzcGVjaWZpYyBjYXNlIGlzIG5lZWRlZDpcbi8vIG5hZ1BhY2suYWRkUmVhc29uVG9TdXBwcmVzcyhhd3NTdGFjaywgJ0F3c1NvbHV0aW9ucy1JQU01JywgJ0VDUyBUYXNrIFJvbGUgbmVlZHMgd2lsZGNhcmQgcmVzb3VyY2UgZm9yIHhyYXk6UHV0VHJhY2VTZWdtZW50cyBhbmQgeHJheTpQdXRUZWxlbWV0cnlSZWNvcmRzIGFzIHBlciBBV1MgWC1SYXkgZG9jdW1lbnRhdGlvbiBmb3Igc2VnbWVudCBzdWJtaXNzaW9uLicpO1xuLy8gSXQncyBiZXR0ZXIgdG8gYXBwbHkgdGhpcyBkaXJlY3RseSB0byB0aGUgcm9sZSBvciBwb2xpY3kgaWYgcG9zc2libGUuXG4vLyBXZSB3aWxsIGFzc3VtZSBmb3Igbm93IHRoYXQgaWYgdGhpcyBydWxlIHRyaWdnZXJzLCBpdCB3aWxsIGJlIGhhbmRsZWQgYnkgYSBtb3JlIHNwZWNpZmljIHN1cHByZXNzaW9uIGluIGxpYi9hd3Mtc3RhY2sudHMuXG5cbi8vIFNwZWNpZmljIHN1cHByZXNzaW9ucyBtaWdodCBiZSBuZWVkZWQgb24gY29uc3RydWN0cyB3aXRoaW4gYXdzLXN0YWNrLnRzIGlmIGdsb2JhbCBvbmVzIGFyZSB0b28gYnJvYWQuXG4vLyBGb3IgZXhhbXBsZSwgZm9yIElBTTUgb24gc3BlY2lmaWMgcm9sZXMgaWYgYSB3aWxkY2FyZCBpcyBqdXN0aWZpZWQgZm9yIGEgc3BlY2lmaWMgQVdTLW1hbmFnZWQgcG9saWN5IHNjZW5hcmlvLlxuLy8gRXhhbXBsZTogbmFnUGFjay5hZGRSZWFzb25Ub1N1cHByZXNzKHNvbWVDb25zdHJ1Y3QsICdBd3NTb2x1dGlvbnMtSUFNNScsICdSZWFzb24gZm9yIHRoaXMgc3BlY2lmaWMgcmVzb3VyY2UgbmVlZGluZyB0aGlzIHBlcm1pc3Npb24uJyk7XG4iXX0=