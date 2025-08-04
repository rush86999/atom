import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import * as Aws from '../lib/aws-stack';

describe('AwsStack Synthesized Template', () => {
  let app: cdk.App;
  let stack: Aws.AwsStack;
  let template: Template;

  beforeAll(() => {
    app = new cdk.App();
    // Note: Testing features dependent on HostedZone.fromLookup (like ACM certificate creation)
    // can be challenging without pre-populating cdk.context.json or refactoring the stack
    // to inject a dummy hosted zone for tests. CfnParameters for DomainName and OperatorEmail
    // will be unresolved tokens during this test synthesis.
    stack = new Aws.AwsStack(app, 'MyTestStack');
    template = Template.fromStack(stack);
  });

  test('Snapshot Test', () => {
    expect(template.toJSON()).toMatchSnapshot();
  });

  test('ALB HTTPS Listener is configured', () => {
    template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
      Protocol: 'HTTPS',
      Port: 443,
      DefaultActions: Match.anyValue(), // Default action varies, check presence
      Certificates: Match.anyValue(), // Certificate ARN will depend on parameter/lookup
    });
  });

  test('ALB HTTP Listener redirects to HTTPS', () => {
    template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
      Protocol: 'HTTP',
      Port: 80,
      DefaultActions: [
        {
          Type: 'redirect',
          RedirectConfig: {
            Protocol: 'HTTPS',
            Port: '443',
            StatusCode: 'HTTP_301',
          },
        },
      ],
    });
  });

  test('RDS Instance has MultiAZ enabled', () => {
    template.hasResourceProperties('AWS::RDS::DBInstance', {
      MultiAZ: true,
    });
  });

  test('RDS Instance has DeletionProtection enabled', () => {
    template.hasResourceProperties('AWS::RDS::DBInstance', {
      DeletionProtection: true,
    });
  });

  test('RDS Instance has correct BackupRetention period', () => {
    template.hasResourceProperties('AWS::RDS::DBInstance', {
      BackupRetentionPeriod: 14, // As we set cdk.Duration.days(14)
    });
  });

  test('SNS Topic for Alarms is created', () => {
    template.resourceCountIs('AWS::SNS::Topic', 1);
  });

  // Example for an ALB 5XX Alarm (structure may vary based on exact CDK output)
  test('ALB 5XX Alarm is created and configured', () => {
    template.hasResourceProperties('AWS::CloudWatch::Alarm', {
      AlarmDescription: 'Alarm if ALB experiences a high number of 5XX errors.',
      Namespace: 'AWS/ApplicationELB',
      MetricName: 'HTTPCode_ELB_5XX_Count',
      Statistic: 'Sum',
      Period: 300, // 5 minutes
      Threshold: 5,
      ComparisonOperator: 'GreaterThanOrEqualToThreshold',
      AlarmActions: Match.anyValue(), // Check that it has an action (the SNS topic)
      Dimensions: [
        {
          Name: 'LoadBalancer',
          Value: Match.anyValue(), // ALB ARN or Name/ID
        },
      ],
    });
  });

  // Add more tests for other alarms (RDS CPU, ECS CPU etc.) following similar pattern

  test('CloudWatch Dashboard is created', () => {
    template.resourceCountIs('AWS::CloudWatch::Dashboard', 1);
    template.hasResourceProperties('AWS::CloudWatch::Dashboard', {
      DashboardName: Match.stringLikeRegexp('-SystemHealthOverview$'), // Checks if the name ends with -SystemHealthOverview
      // DashboardBody will be a large JSON string, difficult to assert specific widgets
      // without making the test very brittle. Snapshot test covers the body.
      // We can check for the presence of a string indicating a known widget title if needed.
      DashboardBody: Match.stringLikeRegexp('Key Alarm Status'), // Check if a known widget title is in the body
    });
  });

  test('ECS Task Role has X-Ray permissions', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: ['xray:PutTraceSegments', 'xray:PutTelemetryRecords'],
            Effect: 'Allow',
            Resource: '*',
          }),
        ]),
      },
      Roles: Match.arrayWith([
        { Ref: Match.stringLikeRegexp('ECSTaskRole') }, // Match the logical ID of the ECS Task Role
      ]),
    });
  });

  test('ALB has X-Ray tracing enabled', () => {
    template.hasResourceProperties(
      'AWS::ElasticLoadBalancingV2::LoadBalancer',
      {
        LoadBalancerAttributes: Match.arrayWith([
          {
            Key: 'routing.http.xray.enabled',
            Value: 'true',
          },
        ]),
      }
    );
  });
});
