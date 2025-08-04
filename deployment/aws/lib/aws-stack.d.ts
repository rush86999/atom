import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
export declare class AwsStack extends cdk.Stack {
    private readonly vpc;
    private readonly cluster;
    private readonly alb;
    private readonly dbInstance;
    private readonly dbSecret;
    private readonly ecsTaskRole;
    private readonly albSecurityGroup;
    private readonly rdsSecurityGroup;
    private readonly dataBucket;
    constructor(scope: Construct, id: string, props?: cdk.StackProps);
    private createEcrRepository;
    private createSecrets;
    private createService;
}
