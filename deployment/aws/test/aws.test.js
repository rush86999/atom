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
const assertions_1 = require("aws-cdk-lib/assertions");
const Aws = __importStar(require("../lib/aws-stack"));
describe('AwsStack Synthesized Template', () => {
    let app;
    let stack;
    let template;
    beforeAll(() => {
        app = new cdk.App();
        // Note: Testing features dependent on HostedZone.fromLookup (like ACM certificate creation)
        // can be challenging without pre-populating cdk.context.json or refactoring the stack
        // to inject a dummy hosted zone for tests. CfnParameters for DomainName and OperatorEmail
        // will be unresolved tokens during this test synthesis.
        stack = new Aws.AwsStack(app, 'MyTestStack');
        template = assertions_1.Template.fromStack(stack);
    });
    test('Snapshot Test', () => {
        expect(template.toJSON()).toMatchSnapshot();
    });
    test('ALB HTTPS Listener is configured', () => {
        template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
            Protocol: 'HTTPS',
            Port: 443,
            DefaultActions: assertions_1.Match.anyValue(), // Default action varies, check presence
            Certificates: assertions_1.Match.anyValue(), // Certificate ARN will depend on parameter/lookup
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
            AlarmActions: assertions_1.Match.anyValue(), // Check that it has an action (the SNS topic)
            Dimensions: [
                {
                    Name: 'LoadBalancer',
                    Value: assertions_1.Match.anyValue(), // ALB ARN or Name/ID
                },
            ],
        });
    });
    // Add more tests for other alarms (RDS CPU, ECS CPU etc.) following similar pattern
    test('CloudWatch Dashboard is created', () => {
        template.resourceCountIs('AWS::CloudWatch::Dashboard', 1);
        template.hasResourceProperties('AWS::CloudWatch::Dashboard', {
            DashboardName: assertions_1.Match.stringLikeRegexp('-SystemHealthOverview$'), // Checks if the name ends with -SystemHealthOverview
            // DashboardBody will be a large JSON string, difficult to assert specific widgets
            // without making the test very brittle. Snapshot test covers the body.
            // We can check for the presence of a string indicating a known widget title if needed.
            DashboardBody: assertions_1.Match.stringLikeRegexp('Key Alarm Status'), // Check if a known widget title is in the body
        });
    });
    test('ECS Task Role has X-Ray permissions', () => {
        template.hasResourceProperties('AWS::IAM::Policy', {
            PolicyDocument: {
                Statement: assertions_1.Match.arrayWith([
                    assertions_1.Match.objectLike({
                        Action: ['xray:PutTraceSegments', 'xray:PutTelemetryRecords'],
                        Effect: 'Allow',
                        Resource: '*',
                    }),
                ]),
            },
            Roles: assertions_1.Match.arrayWith([
                { Ref: assertions_1.Match.stringLikeRegexp('ECSTaskRole') }, // Match the logical ID of the ECS Task Role
            ]),
        });
    });
    test('ALB has X-Ray tracing enabled', () => {
        template.hasResourceProperties('AWS::ElasticLoadBalancingV2::LoadBalancer', {
            LoadBalancerAttributes: assertions_1.Match.arrayWith([
                {
                    Key: 'routing.http.xray.enabled',
                    Value: 'true',
                },
            ]),
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXdzLnRlc3QuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJhd3MudGVzdC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztBQUFBLGlEQUFtQztBQUNuQyx1REFBeUQ7QUFDekQsc0RBQXdDO0FBRXhDLFFBQVEsQ0FBQywrQkFBK0IsRUFBRSxHQUFHLEVBQUU7SUFDN0MsSUFBSSxHQUFZLENBQUM7SUFDakIsSUFBSSxLQUFtQixDQUFDO0lBQ3hCLElBQUksUUFBa0IsQ0FBQztJQUV2QixTQUFTLENBQUMsR0FBRyxFQUFFO1FBQ2IsR0FBRyxHQUFHLElBQUksR0FBRyxDQUFDLEdBQUcsRUFBRSxDQUFDO1FBQ3BCLDRGQUE0RjtRQUM1RixzRkFBc0Y7UUFDdEYsMEZBQTBGO1FBQzFGLHdEQUF3RDtRQUN4RCxLQUFLLEdBQUcsSUFBSSxHQUFHLENBQUMsUUFBUSxDQUFDLEdBQUcsRUFBRSxhQUFhLENBQUMsQ0FBQztRQUM3QyxRQUFRLEdBQUcscUJBQVEsQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUM7SUFDdkMsQ0FBQyxDQUFDLENBQUM7SUFFSCxJQUFJLENBQUMsZUFBZSxFQUFFLEdBQUcsRUFBRTtRQUN6QixNQUFNLENBQUMsUUFBUSxDQUFDLE1BQU0sRUFBRSxDQUFDLENBQUMsZUFBZSxFQUFFLENBQUM7SUFDOUMsQ0FBQyxDQUFDLENBQUM7SUFFSCxJQUFJLENBQUMsa0NBQWtDLEVBQUUsR0FBRyxFQUFFO1FBQzVDLFFBQVEsQ0FBQyxxQkFBcUIsQ0FBQyx1Q0FBdUMsRUFBRTtZQUN0RSxRQUFRLEVBQUUsT0FBTztZQUNqQixJQUFJLEVBQUUsR0FBRztZQUNULGNBQWMsRUFBRSxrQkFBSyxDQUFDLFFBQVEsRUFBRSxFQUFFLHdDQUF3QztZQUMxRSxZQUFZLEVBQUUsa0JBQUssQ0FBQyxRQUFRLEVBQUUsRUFBRSxrREFBa0Q7U0FDbkYsQ0FBQyxDQUFDO0lBQ0wsQ0FBQyxDQUFD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QkFBdUIsRUFBRSwwQkFBMEIsQ0FBQzt3QkFDN0QsTUFBTSxFQUFFLE9BQU87d0JBQ2YsUUFBUSxFQUFFLEdBQUc7cUJBQ2QsQ0FBQztpQkFDSCxDQUFDO2FBQ0g7WUFDRCxLQUFLLEVBQUUsa0JBQUssQ0FBQyxTQUFTLENBQUM7Z0JBQ3JCLEVBQUUsR0FBRyxFQUFFLGtCQUFLLENBQUMsZ0JBQWdCLENBQUMsYUFBYSxDQUFDLEVBQUUsRUFBRSw0Q0FBNEM7YUFDN0YsQ0FBQztTQUNILENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0lBRUgsSUFBSSxDQUFDLCtCQUErQixFQUFFLEdBQUcsRUFBRTtRQUN6QyxRQUFRLENBQUMscUJBQXFCLENBQzVCLDJDQUEyQyxFQUMzQztZQUNFLHNCQUFzQixFQUFFLGtCQUFLLENBQUMsU0FBUyxDQUFDO2dCQUN0QztvQkFDRSxHQUFHLEVBQUUsMkJBQTJCO29CQUNoQyxLQUFLLEVBQUUsTUFBTTtpQkFDZDthQUNGLENBQUM7U0FDSCxDQUNGLENBQUM7SUFDSixDQUFDLENBQUMsQ0FBQztBQUNMLENBQUMsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0ICogYXMgY2RrIGZyb20gJ2F3cy1jZGstbGliJztcbmltcG9ydCB7IFRlbXBsYXRlLCBNYXRjaCB9IGZyb20gJ2F3cy1jZGstbGliL2Fzc2VydGlvbnMnO1xuaW1wb3J0ICogYXMgQXdzIGZyb20gJy4uL2xpYi9hd3Mtc3RhY2snO1xuXG5kZXNjcmliZSgnQXdzU3RhY2sgU3ludGhlc2l6ZWQgVGVtcGxhdGUnLCAoKSA9PiB7XG4gIGxldCBhcHA6IGNkay5BcHA7XG4gIGxldCBzdGFjazogQXdzLkF3c1N0YWNrO1xuICBsZXQgdGVtcGxhdGU6IFRlbXBsYXRlO1xuXG4gIGJlZm9yZUFsbCgoKSA9PiB7XG4gICAgYXBwID0gbmV3IGNkay5BcHAoKTtcbiAgICAvLyBOb3RlOiBUZXN0aW5nIGZlYXR1cmVzIGRlcGVuZGVudCBvbiBIb3N0ZWRab25lLmZyb21Mb29rdXAgKGxpa2UgQUNNIGNlcnRpZmljYXRlIGNyZWF0aW9uKVxuICAgIC8vIGNhbiBiZSBjaGFsbGVuZ2luZyB3aXRob3V0IHByZS1wb3B1bGF0aW5nIGNkay5jb250ZXh0Lmpzb24gb3IgcmVmYWN0b3JpbmcgdGhlIHN0YWNrXG4gICAgLy8gdG8gaW5qZWN0IGEgZHVtbXkgaG9zdGVkIHpvbmUgZm9yIHRlc3RzLiBDZm5QYXJhbWV0ZXJzIGZvciBEb21haW5OYW1lIGFuZCBPcGVyYXRvckVtYWlsXG4gICAgLy8gd2lsbCBiZSB1bnJlc29sdmVkIHRva2VucyBkdXJpbmcgdGhpcyB0ZXN0IHN5bnRoZXNpcy5cbiAgICBzdGFjayA9IG5ldyBBd3MuQXdzU3RhY2soYXBwLCAnTXlUZXN0U3RhY2snKTtcbiAgICB0ZW1wbGF0ZSA9IFRlbXBsYXRlLmZyb21TdGFjayhzdGFjayk7XG4gIH0pO1xuXG4gIHRlc3QoJ1NuYXBzaG90IFRlc3QnLCAoKSA9PiB7XG4gICAgZXhwZWN0KHRlbXBsYXRlLnRvSlNPTigpKS50b01hdGNoU25hcHNob3QoKTtcbiAgfSk7XG5cbiAgdGVzdCgnQUxCIEhUVFBTIExpc3RlbmVyIGlzIGNvbmZpZ3VyZWQnLCAoKSA9PiB7XG4gICAgdGVtcGxhdGUuaGFzUmVzb3VyY2VQcm9wZXJ0aWVzKCdBV1M6OkVsYXN0aWNMb2FkQmFsYW5jaW5nVjI6Okxpc3RlbmVyJywge1xuICAgICAgUHJvdG9jb2w6ICdIVFRQUycsXG4gICAgICBQb3J0OiA0NDMsXG4gICAgICBEZWZhdWx0QWN0aW9uczogTWF0Y2guYW55VmFsdWUoKSwgLy8gRGVmYXVsdCBhY3Rpb24gdmFyaWVzLCBjaGVjayBwcmVzZW5jZVxuICAgICAgQ2VydGlmaWNhdGVzOiBNYXRjaC5hbnlWYWx1ZSgpLCAvLyBDZXJ0aWZpY2F0ZSBBUk4gd2lsbCBkZXBlbmQgb24gcGFyYW1ldGVyL2xvb2t1cFxuICAgIH0pO1xuICB9KTtcblxuICB0ZXN0KCdBTEIgSFRUUCBMaXN0ZW5lciByZWRpcmVjdHMgdG8gSFRUUFMnLCAoKSA9PiB7XG4gICAgdGVtcGxhdGUuaGFzUmVzb3VyY2VQcm9wZXJ0aWVzKCdBV1M6OkVsYXN0aWNMb2FkQmFsYW5jaW5nVjI6Okxpc3RlbmVyJywge1xuICAgICAgUHJvdG9jb2w6ICdIVFRQJyxcbiAgICAgIFBvcnQ6IDgwLFxuICAgICAgRGVmYXVsdEFjdGlvbnM6IFtcbiAgICAgICAge1xuICAgICAgICAgIFR5cGU6ICdyZWRpcmVjdCcsXG4gICAgICAgICAgUmVkaXJlY3RDb25maWc6IHtcbiAgICAgICAgICAgIFByb3RvY29sOiAnSFRUUFMnLFxuICAgICAgICAgICAgUG9ydDogJzQ0MycsXG4gICAgICAgICAgICBTdGF0dXNDb2RlOiAnSFRUUF8zMDEnLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICBdLFxuICAgIH0pO1xuICB9KTtcblxuICB0ZXN0KCdSRFMgSW5zdGFuY2UgaGFzIE11bHRpQVogZW5hYmxlZCcsICgpID0+IHtcbiAgICB0ZW1wbGF0ZS5oYXNSZXNvdXJjZVByb3BlcnRpZXMoJ0FXUzo6UkRTOjpEQkluc3RhbmNlJywge1xuICAgICAgTXVsdGlBWjogdHJ1ZSxcbiAgICB9KTtcbiAgfSk7XG5cbiAgdGVzdCgnUkRTIEluc3RhbmNlIGhhcyBEZWxldGlvblByb3RlY3Rpb24gZW5hYmxlZCcsICgpID0+IHtcbiAgICB0ZW1wbGF0ZS5oYXNSZXNvdXJjZVByb3BlcnRpZXMoJ0FXUzo6UkRTOjpEQkluc3RhbmNlJywge1xuICAgICAgRGVsZXRpb25Qcm90ZWN0aW9uOiB0cnVlLFxuICAgIH0pO1xuICB9KTtcblxuICB0ZXN0KCdSRFMgSW5zdGFuY2UgaGFzIGNvcnJlY3QgQmFja3VwUmV0ZW50aW9uIHBlcmlvZCcsICgpID0+IHtcbiAgICB0ZW1wbGF0ZS5oYXNSZXNvdXJjZVByb3BlcnRpZXMoJ0FXUzo6UkRTOjpEQkluc3RhbmNlJywge1xuICAgICAgQmFja3VwUmV0ZW50aW9uUGVyaW9kOiAxNCwgLy8gQXMgd2Ugc2V0IGNkay5EdXJhdGlvbi5kYXlzKDE0KVxuICAgIH0pO1xuICB9KTtcblxuICB0ZXN0KCdTTlMgVG9waWMgZm9yIEFsYXJtcyBpcyBjcmVhdGVkJywgKCkgPT4ge1xuICAgIHRlbXBsYXRlLnJlc291cmNlQ291bnRJcygnQVdTOjpTTlM6OlRvcGljJywgMSk7XG4gIH0pO1xuXG4gIC8vIEV4YW1wbGUgZm9yIGFuIEFMQiA1WFggQWxhcm0gKHN0cnVjdHVyZSBtYXkgdmFyeSBiYXNlZCBvbiBleGFjdCBDREsgb3V0cHV0KVxuICB0ZXN0KCdBTEIgNVhYIEFsYXJtIGlzIGNyZWF0ZWQgYW5kIGNvbmZpZ3VyZWQnLCAoKSA9PiB7XG4gICAgdGVtcGxhdGUuaGFzUmVzb3VyY2VQcm9wZXJ0aWVzKCdBV1M6OkNsb3VkV2F0Y2g6OkFsYXJtJywge1xuICAgICAgQWxhcm1EZXNjcmlwdGlvbjogJ0FsYXJtIGlmIEFMQiBleHBlcmllbmNlcyBhIGhpZ2ggbnVtYmVyIG9mIDVYWCBlcnJvcnMuJyxcbiAgICAgIE5hbWVzcGFjZTogJ0FXUy9BcHBsaWNhdGlvbkVMQicsXG4gICAgICBNZXRyaWNOYW1lOiAnSFRUUENvZGVfRUxCXzVYWF9Db3VudCcsXG4gICAgICBTdGF0aXN0aWM6ICdTdW0nLFxuICAgICAgUGVyaW9kOiAzMDAsIC8vIDUgbWludXRlc1xuICAgICAgVGhyZXNob2xkOiA1LFxuICAgICAgQ29tcGFyaXNvbk9wZXJhdG9yOiAnR3JlYXRlclRoYW5PckVxdWFsVG9UaHJlc2hvbGQnLFxuICAgICAgQWxhcm1BY3Rpb25zOiBNYXRjaC5hbnlWYWx1ZSgpLCAvLyBDaGVjayB0aGF0IGl0IGhhcyBhbiBhY3Rpb24gKHRoZSBTTlMgdG9waWMpXG4gICAgICBEaW1lbnNpb25zOiBbXG4gICAgICAgIHtcbiAgICAgICAgICBOYW1lOiAnTG9hZEJhbGFuY2VyJyxcbiAgICAgICAgICBWYWx1ZTogTWF0Y2guYW55VmFsdWUoKSwgLy8gQUxCIEFSTiBvciBOYW1lL0lEXG4gICAgICAgIH0sXG4gICAgICBdLFxuICAgIH0pO1xuICB9KTtcblxuICAvLyBBZGQgbW9yZSB0ZXN0cyBmb3Igb3RoZXIgYWxhcm1zIChSRFMgQ1BVLCBFQ1MgQ1BVIGV0Yy4pIGZvbGxvd2luZyBzaW1pbGFyIHBhdHRlcm5cblxuICB0ZXN0KCdDbG91ZFdhdGNoIERhc2hib2FyZCBpcyBjcmVhdGVkJywgKCkgPT4ge1xuICAgIHRlbXBsYXRlLnJlc291cmNlQ291bnRJcygnQVdTOjpDbG91ZFdhdGNoOjpEYXNoYm9hcmQnLCAxKTtcbiAgICB0ZW1wbGF0ZS5oYXNSZXNvdXJjZVByb3BlcnRpZXMoJ0FXUzo6Q2xvdWRXYXRjaDo6RGFzaGJvYXJkJywge1xuICAgICAgRGFzaGJvYXJkTmFtZTogTWF0Y2guc3RyaW5nTGlrZVJlZ2V4cCgnLVN5c3RlbUhlYWx0aE92ZXJ2aWV3JCcpLCAvLyBDaGVja3MgaWYgdGhlIG5hbWUgZW5kcyB3aXRoIC1TeXN0ZW1IZWFsdGhPdmVydmlld1xuICAgICAgLy8gRGFzaGJvYXJkQm9keSB3aWxsIGJlIGEgbGFyZ2UgSlNPTiBzdHJpbmcsIGRpZmZpY3VsdCB0byBhc3NlcnQgc3BlY2lmaWMgd2lkZ2V0c1xuICAgICAgLy8gd2l0aG91dCBtYWtpbmcgdGhlIHRlc3QgdmVyeSBicml0dGxlLiBTbmFwc2hvdCB0ZXN0IGNvdmVycyB0aGUgYm9keS5cbiAgICAgIC8vIFdlIGNhbiBjaGVjayBmb3IgdGhlIHByZXNlbmNlIG9mIGEgc3RyaW5nIGluZGljYXRpbmcgYSBrbm93biB3aWRnZXQgdGl0bGUgaWYgbmVlZGVkLlxuICAgICAgRGFzaGJvYXJkQm9keTogTWF0Y2guc3RyaW5nTGlrZVJlZ2V4cCgnS2V5IEFsYXJtIFN0YXR1cycpLCAvLyBDaGVjayBpZiBhIGtub3duIHdpZGdldCB0aXRsZSBpcyBpbiB0aGUgYm9keVxuICAgIH0pO1xuICB9KTtcblxuICB0ZXN0KCdFQ1MgVGFzayBSb2xlIGhhcyBYLVJheSBwZXJtaXNzaW9ucycsICgpID0+IHtcbiAgICB0ZW1wbGF0ZS5oYXNSZXNvdXJjZVByb3BlcnRpZXMoJ0FXUzo6SUFNOjpQb2xpY3knLCB7XG4gICAgICBQb2xpY3lEb2N1bWVudDoge1xuICAgICAgICBTdGF0ZW1lbnQ6IE1hdGNoLmFycmF5V2l0aChbXG4gICAgICAgICAgTWF0Y2gub2JqZWN0TGlrZSh7XG4gICAgICAgICAgICBBY3Rpb246IFsneHJheTpQdXRUcmFjZVNlZ21lbnRzJywgJ3hyYXk6UHV0VGVsZW1ldHJ5UmVjb3JkcyddLFxuICAgICAgICAgICAgRWZmZWN0OiAnQWxsb3cnLFxuICAgICAgICAgICAgUmVzb3VyY2U6ICcqJyxcbiAgICAgICAgICB9KSxcbiAgICAgICAgXSksXG4gICAgICB9LFxuICAgICAgUm9sZXM6IE1hdGNoLmFycmF5V2l0aChbXG4gICAgICAgIHsgUmVmOiBNYXRjaC5zdHJpbmdMaWtlUmVnZXhwKCdFQ1NUYXNrUm9sZScpIH0sIC8vIE1hdGNoIHRoZSBsb2dpY2FsIElEIG9mIHRoZSBFQ1MgVGFzayBSb2xlXG4gICAgICBdKSxcbiAgICB9KTtcbiAgfSk7XG5cbiAgdGVzdCgnQUxCIGhhcyBYLVJheSB0cmFjaW5nIGVuYWJsZWQnLCAoKSA9PiB7XG4gICAgdGVtcGxhdGUuaGFzUmVzb3VyY2VQcm9wZXJ0aWVzKFxuICAgICAgJ0FXUzo6RWxhc3RpY0xvYWRCYWxhbmNpbmdWMjo6TG9hZEJhbGFuY2VyJyxcbiAgICAgIHtcbiAgICAgICAgTG9hZEJhbGFuY2VyQXR0cmlidXRlczogTWF0Y2guYXJyYXlXaXRoKFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICBLZXk6ICdyb3V0aW5nLmh0dHAueHJheS5lbmFibGVkJyxcbiAgICAgICAgICAgIFZhbHVlOiAndHJ1ZScsXG4gICAgICAgICAgfSxcbiAgICAgICAgXSksXG4gICAgICB9XG4gICAgKTtcbiAgfSk7XG59KTtcbiJdfQ==