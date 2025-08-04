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
exports.AwsStack = void 0;
const cdk = __importStar(require("aws-cdk-lib"));
const ecr = __importStar(require("aws-cdk-lib/aws-ecr"));
const ec2 = __importStar(require("aws-cdk-lib/aws-ec2"));
const rds = __importStar(require("aws-cdk-lib/aws-rds"));
const ecs = __importStar(require("aws-cdk-lib/aws-ecs"));
const elbv2 = __importStar(require("aws-cdk-lib/aws-elasticloadbalancingv2"));
const secretsmanager = __importStar(require("aws-cdk-lib/aws-secretsmanager"));
const iam = __importStar(require("aws-cdk-lib/aws-iam"));
const logs = __importStar(require("aws-cdk-lib/aws-logs"));
const s3 = __importStar(require("aws-cdk-lib/aws-s3"));
const acm = __importStar(require("aws-cdk-lib/aws-certificatemanager"));
const sns = __importStar(require("aws-cdk-lib/aws-sns"));
const subscriptions = __importStar(require("aws-cdk-lib/aws-sns-subscriptions"));
const cdk_nag_1 = require("cdk-nag");
class AwsStack extends cdk.Stack {
    vpc;
    cluster;
    alb;
    dbInstance;
    dbSecret;
    ecsTaskRole;
    albSecurityGroup;
    rdsSecurityGroup;
    dataBucket;
    constructor(scope, id, props) {
        super(scope, id, props);
        // --- CfnParameters ---
        // const domainNameParameter = new cdk.CfnParameter(this, "DomainName", {
        //   type: "String",
        //   description: "The domain name for the application (e.g., app.example.com)",
        // });
        const certificateArnParameter = new cdk.CfnParameter(this, 'CertificateArn', {
            type: 'String',
            description: 'Optional: ARN of an existing ACM certificate for the domain name.',
            default: '',
        });
        const operatorEmailParameter = new cdk.CfnParameter(this, 'OperatorEmail', {
            type: 'String',
            description: 'Email address for operational alerts and notifications.',
            allowedPattern: '.+@.+\\..+',
        });
        const deploymentStageParameter = new cdk.CfnParameter(this, 'DeploymentStage', {
            type: 'String',
            description: 'The deployment stage (dev, staging, prod).',
            allowedValues: ['dev', 'staging', 'prod'],
            default: 'dev',
        });
        const domainName = 'app.example.com';
        const certificateArn = certificateArnParameter.valueAsString;
        const operatorEmail = operatorEmailParameter.valueAsString;
        const deploymentStage = deploymentStageParameter.valueAsString;
        const isProd = deploymentStage === 'prod';
        const isProdStageCondition = new cdk.CfnCondition(this, 'IsProdStageCondition', {
            expression: cdk.Fn.conditionEquals(deploymentStage, 'prod'),
        });
        // --- Foundational Resources ---
        const alarmTopic = new sns.Topic(this, 'AlarmTopic');
        alarmTopic.addSubscription(new subscriptions.EmailSubscription(operatorEmail));
        this.vpc = new ec2.Vpc(this, 'AtomicVpc', { maxAzs: 2, natGateways: 1 });
        cdk_nag_1.NagSuppressions.addResourceSuppressions(this.vpc, [
            {
                id: 'AwsSolutions-VPC7',
                reason: 'Suppressing VPC flow logs for this workshop',
            },
        ], true);
        cdk_nag_1.NagSuppressions.addResourceSuppressions(this.vpc, [
            {
                id: 'AwsSolutions-VPC7',
                reason: 'VPC Flow Logs are not enabled for this workshop',
            },
        ]);
        this.cluster = new ecs.Cluster(this, 'AtomicCluster', {
            vpc: this.vpc,
            enableFargateCapacityProviders: true,
        });
        cdk_nag_1.NagSuppressions.addResourceSuppressions(this.cluster, [
            {
                id: 'AwsSolutions-ECS4',
                reason: 'Suppressing Container Insights for this workshop',
            },
        ], true);
        cdk_nag_1.NagSuppressions.addResourceSuppressions(this.cluster, [
            {
                id: 'AwsSolutions-ECS4',
                reason: 'Container Insights are not enabled for this workshop',
            },
        ]);
        this.ecsTaskRole = new iam.Role(this, 'ECSTaskRole', {
            assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
        });
        cdk_nag_1.NagSuppressions.addResourceSuppressions(this.ecsTaskRole, [
            {
                id: 'AwsSolutions-IAM5',
                reason: 'Suppressing IAM wildcard permissions for this workshop',
            },
        ], true);
        cdk_nag_1.NagSuppressions.addResourceSuppressions(this.ecsTaskRole, [
            {
                id: 'AwsSolutions-IAM5',
                reason: 'Allowing wildcard permissions for this workshop as per service requirements for S3 and ECR.',
            },
        ]);
        const dataBucket = new s3.Bucket(this, 'AtomicDataBucket', {
            removalPolicy: cdk.RemovalPolicy.DESTROY,
            autoDeleteObjects: true,
            blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
            encryption: s3.BucketEncryption.S3_MANAGED,
            enforceSSL: true,
        });
        dataBucket.grantReadWrite(this.ecsTaskRole);
        const repositories = {
            functions: this.createEcrRepository('atomic-functions'),
            handshake: this.createEcrRepository('atomic-handshake'),
            oauth: this.createEcrRepository('atomic-oauth'),
            app: this.createEcrRepository('atomic-app'),
            optaplanner: this.createEcrRepository('atomic-optaplanner'),
            pythonAgent: this.createEcrRepository('atomic-python-agent'),
        };
        this.ecsTaskRole.addToPolicy(new iam.PolicyStatement({
            actions: ['ecr:GetAuthorizationToken'],
            resources: ['*'],
        }));
        this.ecsTaskRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                'ecr:BatchCheckLayerAvailability',
                'ecr:GetDownloadUrlForLayer',
                'ecr:BatchGetImage',
            ],
            resources: Object.values(repositories).map((repo) => repo.repositoryArn),
        }));
        this.rdsSecurityGroup = new ec2.SecurityGroup(this, 'RdsSecurityGroup', {
            vpc: this.vpc,
            allowAllOutbound: true,
        });
        this.dbInstance = new rds.DatabaseInstance(this, 'AtomicPostgresDB', {
            engine: rds.DatabaseInstanceEngine.postgres({
                version: rds.PostgresEngineVersion.VER_15,
            }),
            instanceType: ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.SMALL),
            vpc: this.vpc,
            vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
            securityGroups: [this.rdsSecurityGroup],
            credentials: rds.Credentials.fromGeneratedSecret('PostgresAdminCredentials'),
            databaseName: 'atomicdb',
            removalPolicy: cdk.RemovalPolicy.DESTROY,
            storageEncrypted: true,
            multiAz: true,
            backupRetention: isProd ? cdk.Duration.days(14) : cdk.Duration.days(1),
            deletionProtection: true,
        });
        this.dbSecret = this.dbInstance.secret;
        cdk_nag_1.NagSuppressions.addResourceSuppressions(this.dbInstance, [
            {
                id: 'AwsSolutions-SMG4',
                reason: 'RDS managed secret rotation is not required for this workshop.',
            },
        ], true);
        const secrets = this.createSecrets();
        this.ecsTaskRole.addToPolicy(new iam.PolicyStatement({
            actions: ['secretsmanager:GetSecretValue'],
            resources: [
                this.dbSecret.secretArn,
                ...Object.values(secrets).map((s) => s.secretArn),
            ],
        }));
        let certificate;
        // const zone = route53.HostedZone.fromLookup(this, "HostedZone", {
        //   domainName,
        // });
        if (certificateArn && certificateArn !== '') {
            certificate = acm.Certificate.fromCertificateArn(this, 'ImportedCertificate', certificateArn);
        }
        else {
            certificate = new acm.Certificate(this, 'NewCertificate', {
                domainName,
                // validation: acm.CertificateValidation.fromDns(zone),
            });
        }
        this.albSecurityGroup = new ec2.SecurityGroup(this, 'AlbSecurityGroup', {
            vpc: this.vpc,
            allowAllOutbound: true,
        });
        this.albSecurityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80));
        this.albSecurityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(443));
        this.alb = new elbv2.ApplicationLoadBalancer(this, 'AtomicAlb', {
            vpc: this.vpc,
            internetFacing: true,
            securityGroup: this.albSecurityGroup,
        });
        this.alb.addListener('HttpListener', {
            port: 80,
            defaultAction: elbv2.ListenerAction.redirect({
                protocol: 'HTTPS',
                port: '443',
                permanent: true,
            }),
        });
        const httpsListener = this.alb.addListener('HttpsListener', {
            port: 443,
            certificates: [certificate],
            defaultAction: elbv2.ListenerAction.fixedResponse(404),
        });
        // --- Services ---
        // Supertokens, PostGraphile, Handshake, OAuth, OptaPlanner, PythonAgent, Functions, App
        // For brevity, only implementing a few services to demonstrate the pattern
        const supertokensService = this.createService('Supertokens', {
            taskDefProps: { cpu: 256, memoryMiB: 512, family: 'supertokens' },
            containerProps: {
                image: ecs.ContainerImage.fromRegistry('registry.supertokens.io/supertokens/supertokens-postgresql:6.0'),
                secrets: {
                    POSTGRESQL_CONNECTION_URI: ecs.Secret.fromSecretsManager(secrets.supertokensDbConnStringSecret),
                },
                portMappings: [{ containerPort: 3567 }],
                environment: { POSTGRESQL_TABLE_NAMES_PREFIX: 'Supertokens' },
            },
            listener: httpsListener,
            pathPattern: '/v1/auth/*',
            priority: 10,
            targetPort: 3567,
            healthCheckPath: '/hello',
        });
        supertokensService.connections.allowTo(this.rdsSecurityGroup, ec2.Port.tcp(5432));
        // Placeholder for other services...
        const appService = this.createService('App', {
            taskDefProps: { cpu: 512, memoryMiB: 1024, family: 'app' },
            containerProps: {
                image: ecs.ContainerImage.fromEcrRepository(repositories.app),
                portMappings: [{ containerPort: 3000 }],
                environment: {
                    // Add app-specific env vars here
                    NEXT_PUBLIC_SUPERTOKENS_API_DOMAIN: `https://${domainName}/v1/auth`,
                },
            },
            listener: httpsListener,
            pathPattern: '/*',
            priority: 100,
            targetPort: 3000,
            healthCheckPath: '/',
        });
        // --- Outputs ---
        new cdk.CfnOutput(this, 'ApplicationEndpoint', {
            value: `https://${domainName}`,
        });
    }
    createEcrRepository(repositoryName) {
        const repo = new ecr.Repository(this, `${repositoryName}Repo`, {
            repositoryName,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
            autoDeleteImages: true,
        });
        new cdk.CfnOutput(this, `${repositoryName}RepoUri`, {
            value: repo.repositoryUri,
        });
        return repo;
    }
    createSecrets() {
        const secretIds = [
            'SupertokensDbConnString',
            'PostGraphileDbConnString',
            'PostGraphileJwtSecret',
            'ApiTokenSecret',
            'OpenAiApiKey',
            'OptaplannerDbConnString',
            'NotionApiToken',
            'DeepgramApiKey',
            'NotionNotesDbId',
            'NotionResearchProjectsDbId',
            'NotionResearchTasksDbId',
            'MskBootstrapBrokers',
        ];
        const createdSecrets = {};
        for (const id of secretIds) {
            const secret = new secretsmanager.Secret(this, id, {
                secretName: `${this.stackName}/${id}`,
            });
            cdk_nag_1.NagSuppressions.addResourceSuppressions(secret, [
                {
                    id: 'AwsSolutions-SMG4',
                    reason: 'Secret rotation is not required for this workshop.',
                },
            ], true);
            createdSecrets[id.charAt(0).toLowerCase() + id.slice(1) + 'Secret'] =
                secret;
        }
        return createdSecrets;
    }
    createService(name, props) {
        const sg = new ec2.SecurityGroup(this, `${name}SG`, {
            vpc: this.vpc,
            allowAllOutbound: true,
        });
        sg.connections.allowFrom(this.albSecurityGroup, ec2.Port.tcp(props.targetPort));
        const taskDef = new ecs.TaskDefinition(this, `${name}TaskDef`, {
            family: props.taskDefProps.family,
            compatibility: ecs.Compatibility.FARGATE,
            cpu: props.taskDefProps.cpu.toString(),
            memoryMiB: props.taskDefProps.memoryMiB.toString(),
            taskRole: this.ecsTaskRole,
            executionRole: this.ecsTaskRole,
        });
        taskDef.addContainer(name, {
            ...props.containerProps,
            logging: ecs.LogDrivers.awsLogs({
                streamPrefix: name.toLowerCase(),
                logGroup: new logs.LogGroup(this, `${name}LogGroup`, {
                    logGroupName: `/aws/ecs/${name}`,
                    retention: logs.RetentionDays.ONE_MONTH,
                    removalPolicy: cdk.RemovalPolicy.DESTROY,
                }),
            }),
        });
        const service = new ecs.FargateService(this, `${name}Service`, {
            cluster: this.cluster,
            taskDefinition: taskDef,
            securityGroups: [sg],
        });
        const targetGroup = new elbv2.ApplicationTargetGroup(this, `${name}TargetGroup`, {
            vpc: this.vpc,
            port: props.targetPort,
            protocol: elbv2.ApplicationProtocol.HTTP,
            targets: [service],
            healthCheck: { path: props.healthCheckPath },
        });
        props.listener.addAction(name, {
            priority: props.priority,
            conditions: [elbv2.ListenerCondition.pathPatterns([props.pathPattern])],
            action: elbv2.ListenerAction.forward([targetGroup]),
        });
        return service;
    }
}
exports.AwsStack = AwsStack;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXdzLXN0YWNrLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiYXdzLXN0YWNrLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztBQUFBLGlEQUFtQztBQUVuQyx5REFBMkM7QUFDM0MseURBQTJDO0FBQzNDLHlEQUEyQztBQUMzQyx5REFBMkM7QUFDM0MsOEVBQWdFO0FBQ2hFLCtFQUFpRTtBQUNqRSx5REFBMkM7QUFDM0MsMkRBQTZDO0FBQzdDLHVEQUF5QztBQUV6Qyx3RUFBMEQ7QUFFMUQseURBQTJDO0FBQzNDLGlGQUFtRTtBQUduRSxxQ0FBMEM7QUFFMUMsTUFBYSxRQUFTLFNBQVEsR0FBRyxDQUFDLEtBQUs7SUFDcEIsR0FBRyxDQUFVO0lBQ2IsT0FBTyxDQUFjO0lBQ3JCLEdBQUcsQ0FBZ0M7SUFDbkMsVUFBVSxDQUF1QjtJQUNqQyxRQUFRLENBQXlCO0lBQ2pDLFdBQVcsQ0FBVztJQUN0QixnQkFBZ0IsQ0FBb0I7SUFDcEMsZ0JBQWdCLENBQW9CO0lBQ3BDLFVBQVUsQ0FBWTtJQUV2QyxZQUFZLEtBQWdCLEVBQUUsRUFBVSxFQUFFLEtBQXNCO1FBQzlELEtBQUssQ0FBQyxLQUFLLEVBQUUsRUFBRSxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBRXhCLHdCQUF3QjtRQUN4Qix5RUFBeUU7UUFDekUsb0JBQW9CO1FBQ3BCLGdGQUFnRjtRQUNoRixNQUFNO1FBQ04sTUFBTSx1QkFBdUIsR0FBRyxJQUFJLEdBQUcsQ0FBQyxZQUFZLENBQ2xELElBQUksRUFDSixnQkFBZ0IsRUFDaEI7WUFDRSxJQUFJLEVBQUUsUUFBUTtZQUNkLFdBQVcsRUFDVCxtRUFBbUU7WUFDckUsT0FBTyxFQUFFLEVBQUU7U0FDWixDQUNGLENBQUM7UUFDRixNQUFNLHNCQUFzQixHQUFHLElBQUksR0FBRyxDQUFDLFlBQVksQ0FBQyxJQUFJLEVBQUUsZUFBZSxFQUFFO1lBQ3pFLElBQUksRUFBRSxRQUFRO1lBQ2Qs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LElBQUksU0FBUyxFQUFFO1lBQzdELE9BQU8sRUFBRSxJQUFJLENBQUMsT0FBTztZQUNyQixjQUFjLEVBQUUsT0FBTztZQUN2QixjQUFjLEVBQUUsQ0FBQyxFQUFFLENBQUM7U0FDckIsQ0FBQyxDQUFDO1FBRUgsTUFBTSxXQUFXLEdBQUcsSUFBSSxLQUFLLENBQUMsc0JBQXNCLENBQ2xELElBQUksRUFDSixHQUFHLElBQUksYUFBYSxFQUNwQjtZQUNFLEdBQUcsRUFBRSxJQUFJLENBQUMsR0FBRztZQUNiLElBQUksRUFBRSxLQUFLLENBQUMsVUFBVTtZQUN0QixRQUFRLEVBQUUsS0FBSyxDQUFDLG1CQUFtQixDQUFDLElBQUk7WUFDeEMsT0FBTyxFQUFFLENBQUMsT0FBTyxDQUFDO1lBQ2xCLFdBQVcsRUFBRSxFQUFFLElBQUksRUFBRSxLQUFLLENBQUMsZUFBZSxFQUFFO1NBQzdDLENBQ0YsQ0FBQztRQUVGLEtBQUssQ0FBQyxRQUFRLENBQUMsU0FBUyxDQUFDLElBQUksRUFBRTtZQUM3QixRQUFRLEVBQUUsS0FBSyxDQUFDLFFBQVE7WUFDeEIsVUFBVSxFQUFFLENBQUMsS0FBSyxDQUFDLGlCQUFpQixDQUFDLFlBQVksQ0FBQyxDQUFDLEtBQUssQ0FBQyxXQUFXLENBQUMsQ0FBQyxDQUFDO1lBQ3ZFLE1BQU0sRUFBRSxLQUFLLENBQUMsY0FBYyxDQUFDLE9BQU8sQ0FBQyxDQUFDLFdBQVcsQ0FBQyxDQUFDO1NBQ3BELENBQUMsQ0FBQztRQUVILE9BQU8sT0FBTyxDQUFDO0lBQ2pCLENBQUM7Q0FDRjtBQXJhRCw0QkFxYUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgKiBhcyBjZGsgZnJvbSAnYXdzLWNkay1saWInO1xuaW1wb3J0IHsgQ29uc3RydWN0IH0gZnJvbSAnY29uc3RydWN0cyc7XG5pbXBvcnQgKiBhcyBlY3IgZnJvbSAnYXdzLWNkay1saWIvYXdzLWVjcic7XG5pbXBvcnQgKiBhcyBlYzIgZnJvbSAnYXdzLWNkay1saWIvYXdzLWVjMic7XG5pbXBvcnQgKiBhcyByZHMgZnJvbSAnYXdzLWNkay1saWIvYXdzLXJkcyc7XG5pbXBvcnQgKiBhcyBlY3MgZnJvbSAnYXdzLWNkay1saWIvYXdzLWVjcyc7XG5pbXBvcnQgKiBhcyBlbGJ2MiBmcm9tICdhd3MtY2RrLWxpYi9hd3MtZWxhc3RpY2xvYWRiYWxhbmNpbmd2Mic7XG5pbXBvcnQgKiBhcyBzZWNyZXRzbWFuYWdlciBmcm9tICdhd3MtY2RrLWxpYi9hd3Mtc2VjcmV0c21hbmFnZXInO1xuaW1wb3J0ICogYXMgaWFtIGZyb20gJ2F3cy1jZGstbGliL2F3cy1pYW0nO1xuaW1wb3J0ICogYXMgbG9ncyBmcm9tICdhd3MtY2RrLWxpYi9hd3MtbG9ncyc7XG5pbXBvcnQgKiBhcyBzMyBmcm9tICdhd3MtY2RrLWxpYi9hd3MtczMnO1xuaW1wb3J0ICogYXMgZWZzIGZyb20gJ2F3cy1jZGstbGliL2F3cy1lZnMnO1xuaW1wb3J0ICogYXMgYWNtIGZyb20gJ2F3cy1jZGstbGliL2F3cy1jZXJ0aWZpY2F0ZW1hbmFnZXInO1xuaW1wb3J0ICogYXMgcm91dGU1MyBmcm9tICdhd3MtY2RrLWxpYi9hd3Mtcm91dGU1Myc7XG5pbXBvcnQgKiBhcyBzbnMgZnJvbSAnYXdzLWNkay1saWIvYXdzLXNucyc7XG5pbXBvcnQgKiBhcyBzdWJzY3JpcHRpb25zIGZyb20gJ2F3cy1jZGstbGliL2F3cy1zbnMtc3Vic2NyaXB0aW9ucyc7XG5pbXBvcnQgKiBhcyBjbG91ZHdhdGNoIGZyb20gJ2F3cy1jZGstbGliL2F3cy1jbG91ZHdhdGNoJztcbmltcG9ydCAqIGFzIGN3X2FjdGlvbnMgZnJvbSAnYXdzLWNkay1saWIvYXdzLWNsb3Vkd2F0Y2gtYWN0aW9ucyc7XG5pbXBvcnQgeyBOYWdTdXBwcmVzc2lvbnMgfSBmcm9tICdjZGstbmFnJztcblxuZXhwb3J0IGNsYXNzIEF3c1N0YWNrIGV4dGVuZHMgY2RrLlN0YWNrIHtcbiAgcHJpdmF0ZSByZWFkb25seSB2cGM6IGVjMi5WcGM7XG4gIHByaXZhdGUgcmVhZG9ubHkgY2x1c3RlcjogZWNzLkNsdXN0ZXI7XG4gIHByaXZhdGUgcmVhZG9ubHkgYWxiOiBlbGJ2Mi5BcHBsaWNhdGlvbkxvYWRCYWxhbmNlcjtcbiAgcHJpdmF0ZSByZWFkb25seSBkYkluc3RhbmNlOiByZHMuRGF0YWJhc2VJbnN0YW5jZTtcbiAgcHJpdmF0ZSByZWFkb25seSBkYlNlY3JldDogc2VjcmV0c21hbmFnZXIuSVNlY3JldDtcbiAgcHJpdmF0ZSByZWFkb25seSBlY3NUYXNrUm9sZTogaWFtLlJvbGU7XG4gIHByaXZhdGUgcmVhZG9ubHkgYWxiU2VjdXJpdHlHcm91cDogZWMyLlNlY3VyaXR5R3JvdXA7XG4gIHByaXZhdGUgcmVhZG9ubHkgcmRzU2VjdXJpdHlHcm91cDogZWMyLlNlY3VyaXR5R3JvdXA7XG4gIHByaXZhdGUgcmVhZG9ubHkgZGF0YUJ1Y2tldDogczMuQnVja2V0O1xuXG4gIGNvbnN0cnVjdG9yKHNjb3BlOiBDb25zdHJ1Y3QsIGlkOiBzdHJpbmcsIHByb3BzPzogY2RrLlN0YWNrUHJvcHMpIHtcbiAgICBzdXBlcihzY29wZSwgaWQsIHByb3BzKTtcblxuICAgIC8vIC0tLSBDZm5QYXJhbWV0ZXJzIC0tLVxuICAgIC8vIGNvbnN0IGRvbWFpbk5hbWVQYXJhbWV0ZXIgPSBuZXcgY2RrLkNmblBhcmFtZXRlcih0aGlzLCBcIkRvbWFpbk5hbWVcIiwge1xuICAgIC8vICAgdHlwZTogXCJTdHJpbmdcIixcbiAgICAvLyAgIGRlc2NyaXB0aW9uOiBcIlRoZSBkb21haW4gbmFtZSBmb3IgdGhlIGFwcGxpY2F0aW9uIChlLmcuLCBhcHAuZXhhbXBsZS5jb20pXCIsXG4gICAgLy8gfSk7XG4gICAgY29uc3QgY2VydGlmaWNhdGVBcm5QYXJhbWV0ZXIgPSBuZXcgY2RrLkNmblBhcmFtZXRlcihcbiAgICAgIHRoaXMsXG4gICAgICAnQ2VydGlmaWNhdGVBcm4nLFxuICAgICAge1xuICAgICAgICB0eXBlOiAnU3RyaW5nJyxcbiAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgJ09wdGlvbmFsOiBBUk4gb2YgYW4gZXhpc3RpbmcgQUNNIGNlcnRpZmljYXRlIGZvciB0aGUgZG9tYWluIG5hbWUuJyxcbiAgICAgICAgZGVmYXVsdDogJycsXG4gICAgICB9XG4gICAgKTtcbiAgICBjb25zdCBvcGVyYXRvckVtYWlsUGFyYW1ldGVyID0gbmV3IGNkay5DZm5QYXJhbWV0ZXIodGhpcywgJ09wZXJhdG9yRW1haWwnLCB7XG4gICAgICB0eXBlOiAnU3RyaW5nJyxcbiAgICAgIGRlc2NyaXB0aW9uOiAnRW1haWwgYWRkcmVzcyBmb3Igb3BlcmF0aW9uYWwgYWxlcnRzIGFuZCBub3RpZmljYXRpb25zLicsXG4gICAgICBhbGxvd2VkUGF0dGVybjogJy4rQC4rXFxcXC4uKycsXG4gICAgfSk7XG4gICAgY29uc3QgZGVwbG95bWVudFN0YWdlUGFyYW1ldGVyID0gbmV3IGNkay5DZm5QYXJhbWV0ZXIoXG4gICAgICB0aGlzLFxuICAgICAgJ0RlcGxveW1lbnRTdGFnZScsXG4gICAgICB7XG4gICAgICAgIHR5cGU6ICdTdHJpbmcnLFxuICAgICAgICBkZXNjcmlwdGlvbjogJ1RoZSBkZXBsb3ltZW50IHN0YWdlIChkZXYsIHN0YWdpbmcsIHByb2QpLicsXG4gICAgICAgIGFsbG93ZWRWYWx1ZXM6IFsnZGV2JywgJ3N0YWdpbmcnLCAncHJvZCddLFxuICAgICAgICBkZWZhdWx0OiAnZGV2JyxcbiAgICAgIH1cbiAgICApO1xuXG4gICAgY29uc3QgZG9tYWluTmFtZSA9ICdhcHAuZXhhbXBsZS5jb20nO1xuICAgIGNvbnN0IGNlcnRpZmljYXRlQXJuID0gY2VydGlmaWNhdGVBcm5QYXJhbWV0ZXIudmFsdWVBc1N0cmluZztcbiAgICBjb25zdCBvcGVyYXRvckVtYWlsID0gb3BlcmF0b3JFbWFpbFBhcmFtZXRlci52YWx1ZUFzU3RyaW5nO1xuICAgIGNvbnN0IGRlcGxveW1lbnRTdGFnZSA9IGRlcGxveW1lbnRTdGFnZVBhcmFtZXRlci52YWx1ZUFzU3RyaW5nO1xuICAgIGNvbnN0IGlzUHJvZCA9IGRlcGxveW1lbnRTdGFnZSA9PT0gJ3Byb2QnO1xuICAgIGNvbnN0IGlzUHJvZFN0YWdlQ29uZGl0aW9uID0gbmV3IGNkay5DZm5Db25kaXRpb24oXG4gICAgICB0aGlzLFxuICAgICAgJ0lzUHJvZFN0YWdlQ29uZGl0aW9uJyxcbiAgICAgIHtcbiAgICAgICAgZXhwcmVzc2lvbjogY2RrLkZuLmNvbmRpdGlvbkVxdWFscyhkZXBsb3ltZW50U3RhZ2UsICdwcm9kJyksXG4gICAgICB9XG4gICAgKTtcblxuICAgIC8vIC0tLSBGb3VuZGF0aW9uYWwgUmVzb3VyY2VzIC0tLVxuICAgIGNvbnN0IGFsYXJtVG9waWMgPSBuZXcgc25zLlRvcGljKHRoaXMsICdBbGFybVRvcGljJyk7XG4gICAgYWxhcm1Ub3BpYy5hZGRTdWJzY3JpcHRpb24oXG4gICAgICBuZXcgc3Vic2NyaXB0aW9ucy5FbWFpbFN1YnNjcmlwdGlvbihvcGVyYXRvckVtYWlsKVxuICAgICk7XG5cbiAgICB0aGlzLnZwYyA9IG5ldyBlYzIuVnBjKHRoaXMsICdBdG9taWNWcGMnLCB7IG1heEF6czogMiwgbmF0R2F0ZXdheXM6IDEgfSk7XG4gICAgTmFnU3VwcHJlc3Npb25zLmFkZFJlc291cmNlU3VwcHJlc3Npb25zKFxuICAgICAgdGhpcy52cGMsXG4gICAgICBbXG4gICAgICAgIHtcbiAgICAgICAgICBpZDogJ0F3c1NvbHV0aW9ucy1WUEM3JyxcbiAgICAgICAgICByZWFzb246ICdTdXBwcmVzc2luZyBWUEMgZmxvdyBsb2dzIGZvciB0aGlzIHdvcmtzaG9wJyxcbiAgICAgICAgfSxcbiAgICAgIF0sXG4gICAgICB0cnVlXG4gICAgKTtcbiAgICBOYWdTdXBwcmVzc2lvbnMuYWRkUmVzb3VyY2VTdXBwcmVzc2lvbnModGhpcy52cGMsIFtcbiAgICAgIHtcbiAgICAgICAgaWQ6ICdBd3NTb2x1dGlvbnMtVlBDNycsXG4gICAgICAgIHJlYXNvbjogJ1ZQQyBGbG93IExvZ3MgYXJlIG5vdCBlbmFibGVkIGZvciB0aGlzIHdvcmtzaG9wJyxcbiAgICAgIH0sXG4gICAgXSk7XG4gICAgdGhpcy5jbHVzdGVyID0gbmV3IGVjcy5DbHVzdGVyKHRoaXMsICdBdG9taWNDbHVzdGVyJywge1xuICAgICAgdnBjOiB0aGlzLnZwYyxcbiAgICAgIGVuYWJsZUZhcmdhdGVDYXBhY2l0eVByb3ZpZGVyczogdHJ1ZSxcbiAgICB9KTtcbiAgICBOYWdTdXBwcmVzc2lvbnMuYWRkUmVzb3VyY2VTdXBwcmVzc2lvbnMoXG4gICAgICB0aGlzLmNsdXN0ZXIsXG4gICAgICBbXG4gICAgICAgIHtcbiAgICAgICAgICBpZDogJ0F3c1NvbHV0aW9ucy1FQ1M0JyxcbiAgICAgICAgICByZWFzb246ICdTdXBwcmVzc2luZyBDb250YWluZXIgSW5zaWdodHMgZm9yIHRoaXMgd29ya3Nob3AnLFxuICAgICAgICB9LFxuICAgICAgXSxcbiAgICAgIHRydWVcbiAgICApO1xuICAgIE5hZ1N1cHByZXNzaW9ucy5hZGRSZXNvdXJjZVN1cHByZXNzaW9ucyh0aGlzLmNsdXN0ZXIsIFtcbiAgICAgIHtcbiAgICAgICAgaWQ6ICdBd3NTb2x1dGlvbnMtRUNTNCcsXG4gICAgICAgIHJlYXNvbjogJ0NvbnRhaW5lciBJbnNpZ2h0cyBhcmUgbm90IGVuYWJsZWQgZm9yIHRoaXMgd29ya3Nob3AnLFxuICAgICAgfSxcbiAgICBdKTtcbiAgICB0aGlzLmVjc1Rhc2tSb2xlID0gbmV3IGlhbS5Sb2xlKHRoaXMsICdFQ1NUYXNrUm9sZScsIHtcbiAgICAgIGFzc3VtZWRCeTogbmV3IGlhbS5TZXJ2aWNlUHJpbmNpcGFsKCdlY3MtdGFza3MuYW1hem9uYXdzLmNvbScpLFxuICAgIH0pO1xuICAgIE5hZ1N1cHByZXNzaW9ucy5hZGRSZXNvdXJjZVN1cHByZXNzaW9ucyhcbiAgICAgIHRoaXMuZWNzVGFza1JvbGUsXG4gICAgICBbXG4gICAgICAgIHtcbiAgICAgICAgICBpZDogJ0F3c1NvbHV0aW9ucy1JQU01JyxcbiAgICAgICAgICByZWFzb246ICdTdXBwcmVzc2luZyBJQU0gd2lsZGNhcmQgcGVybWlzc2lvbnMgZm9yIHRoaXMgd29ya3Nob3AnLFxuICAgICAgICB9LFxuICAgICAgXSxcbiAgICAgIHRydWVcbiAgICApO1xuICAgIE5hZ1N1cHByZXNzaW9ucy5hZGRSZXNvdXJjZVN1cHByZXNzaW9ucyh0aGlzLmVjc1Rhc2tSb2xlLCBbXG4gICAgICB7XG4gICAgICAgIGlkOiAnQXdzU29sdXRpb25zLUlBTTUnLFxuICAgICAgICByZWFzb246XG4gICAgICAgICAgJ0FsbG93aW5nIHdpbGRjYXJkIHBlcm1pc3Npb25zIGZvciB0aGlzIHdvcmtzaG9wIGFzIHBlciBzZXJ2aWNlIHJlcXVpcmVtZW50cyBmb3IgUzMgYW5kIEVDUi4nLFxuICAgICAgfSxcbiAgICBdKTtcblxuICAgIGNvbnN0IGRhdGFCdWNrZXQgPSBuZXcgczMuQnVja2V0KHRoaXMsICdBdG9taWNEYXRhQnVja2V0Jywge1xuICAgICAgcmVtb3ZhbFBvbGljeTogY2RrLlJlbW92YWxQb2xpY3kuREVTVFJPWSxcbiAgICAgIGF1dG9EZWxldGVPYmplY3RzOiB0cnVlLFxuICAgICAgYmxvY2tQdWJsaWNBY2Nlc3M6IHMzLkJsb2NrUHVibGljQWNjZXNzLkJMT0NLX0FMTCxcbiAgICAgIGVuY3J5cHRpb246IHMzLkJ1Y2tldEVuY3J5cHRpb24uUzNfTUFOQUdFRCxcbiAgICAgIGVuZm9yY2VTU0w6IHRydWUsXG4gICAgfSk7XG4gICAgZGF0YUJ1Y2tldC5ncmFudFJlYWRXcml0ZSh0aGlzLmVjc1Rhc2tSb2xlKTtcblxuICAgIGNvbnN0IHJlcG9zaXRvcmllcyA9IHtcbiAgICAgIGZ1bmN0aW9uczogdGhpcy5jcmVhdGVFY3JSZXBvc2l0b3J5KCdhdG9taWMtZnVuY3Rpb25zJyksXG4gICAgICBoYW5kc2hha2U6IHRoaXMuY3JlYXRlRWNyUmVwb3NpdG9yeSgnYXRvbWljLWhhbmRzaGFrZScpLFxuICAgICAgb2F1dGg6IHRoaXMuY3JlYXRlRWNyUmVwb3NpdG9yeSgnYXRvbWljLW9hdXRoJyksXG4gICAgICBhcHA6IHRoaXMuY3JlYXRlRWNyUmVwb3NpdG9yeSgnYXRvbWljLWFwcCcpLFxuICAgICAgb3B0YXBsYW5uZXI6IHRoaXMuY3JlYXRlRWNyUmVwb3NpdG9yeSgnYXRvbWljLW9wdGFwbGFubmVyJyksXG4gICAgICBweXRob25BZ2VudDogdGhpcy5jcmVhdGVFY3JSZXBvc2l0b3J5KCdhdG9taWMtcHl0aG9uLWFnZW50JyksXG4gICAgfTtcbiAgICB0aGlzLmVjc1Rhc2tSb2xlLmFkZFRvUG9saWN5KFxuICAgICAgbmV3IGlhbS5Qb2xpY3lTdGF0ZW1lbnQoe1xuICAgICAgICBhY3Rpb25zOiBbJ2VjcjpHZXRBdXRob3JpemF0aW9uVG9rZW4nXSxcbiAgICAgICAgcmVzb3VyY2VzOiBbJyonXSxcbiAgICAgIH0pXG4gICAgKTtcbiAgICB0aGlzLmVjc1Rhc2tSb2xlLmFkZFRvUG9saWN5KFxuICAgICAgbmV3IGlhbS5Qb2xpY3lTdGF0ZW1lbnQoe1xuICAgICAgICBhY3Rpb25zOiBbXG4gICAgICAgICAgJ2VjcjpCYXRjaENoZWNrTGF5ZXJBdmFpbGFiaWxpdHknLFxuICAgICAgICAgICdlY3I6R2V0RG93bmxvYWRVcmxGb3JMYXllcicsXG4gICAgICAgICAgJ2VjcjpCYXRjaEdldEltYWdlJyxcbiAgICAgICAgXSxcbiAgICAgICAgcmVzb3VyY2VzOiBPYmplY3QudmFsdWVzKHJlcG9zaXRvcmllcykubWFwKFxuICAgICAgICAgIChyZXBvKSA9PiByZXBvLnJlcG9zaXRvcnlBcm5cbiAgICAgICAgKSxcbiAgICAgIH0pXG4gICAgKTtcblxuICAgIHRoaXMucmRzU2VjdXJpdHlHcm91cCA9IG5ldyBlYzIuU2VjdXJpdHlHcm91cCh0aGlzLCAnUmRzU2VjdXJpdHlHcm91cCcsIHtcbiAgICAgIHZwYzogdGhpcy52cGMsXG4gICAgICBhbGxvd0FsbE91dGJvdW5kOiB0cnVlLFxuICAgIH0pO1xuICAgIHRoaXMuZGJJbnN0YW5jZSA9IG5ldyByZHMuRGF0YWJhc2VJbnN0YW5jZSh0aGlzLCAnQXRvbWljUG9zdGdyZXNEQicsIHtcbiAgICAgIGVuZ2luZTogcmRzLkRhdGFiYXNlSW5zdGFuY2VFbmdpbmUucG9zdGdyZXMoe1xuICAgICAgICB2ZXJzaW9uOiByZHMuUG9zdGdyZXNFbmdpbmVWZXJzaW9uLlZFUl8xNSxcbiAgICAgIH0pLFxuICAgICAgaW5zdGFuY2VUeXBlOiBlYzIuSW5zdGFuY2VUeXBlLm9mKFxuICAgICAgICBlYzIuSW5zdGFuY2VDbGFzcy5CVVJTVEFCTEUzLFxuICAgICAgICBlYzIuSW5zdGFuY2VTaXplLlNNQUxMXG4gICAgICApLFxuICAgICAgdnBjOiB0aGlzLnZwYyxcbiAgICAgIHZwY1N1Ym5ldHM6IHsgc3VibmV0VHlwZTogZWMyLlN1Ym5ldFR5cGUuUFJJVkFURV9XSVRIX0VHUkVTUyB9LFxuICAgICAgc2VjdXJpdHlHcm91cHM6IFt0aGlzLnJkc1NlY3VyaXR5R3JvdXBdLFxuICAgICAgY3JlZGVudGlhbHM6IHJkcy5DcmVkZW50aWFscy5mcm9tR2VuZXJhdGVkU2VjcmV0KFxuICAgICAgICAnUG9zdGdyZXNBZG1pbkNyZWRlbnRpYWxzJ1xuICAgICAgKSxcbiAgICAgIGRhdGFiYXNlTmFtZTogJ2F0b21pY2RiJyxcbiAgICAgIHJlbW92YWxQb2xpY3k6IGNkay5SZW1vdmFsUG9saWN5LkRFU1RST1ksXG4gICAgICBzdG9yYWdlRW5jcnlwdGVkOiB0cnVlLFxuICAgICAgbXVsdGlBejogdHJ1ZSxcbiAgICAgIGJhY2t1cFJldGVudGlvbjogaXNQcm9kID8gY2RrLkR1cmF0aW9uLmRheXMoMTQpIDogY2RrLkR1cmF0aW9uLmRheXMoMSksXG4gICAgICBkZWxldGlvblByb3RlY3Rpb246IHRydWUsXG4gICAgfSk7XG4gICAgdGhpcy5kYlNlY3JldCA9IHRoaXMuZGJJbnN0YW5jZS5zZWNyZXQhO1xuICAgIE5hZ1N1cHByZXNzaW9ucy5hZGRSZXNvdXJjZVN1cHByZXNzaW9ucyhcbiAgICAgIHRoaXMuZGJJbnN0YW5jZSxcbiAgICAgIFtcbiAgICAgICAge1xuICAgICAgICAgIGlkOiAnQXdzU29sdXRpb25zLVNNRzQnLFxuICAgICAgICAgIHJlYXNvbjpcbiAgICAgICAgICAgICdSRFMgbWFuYWdlZCBzZWNyZXQgcm90YXRpb24gaXMgbm90IHJlcXVpcmVkIGZvciB0aGlzIHdvcmtzaG9wLicsXG4gICAgICAgIH0sXG4gICAgICBdLFxuICAgICAgdHJ1ZVxuICAgICk7XG5cbiAgICBjb25zdCBzZWNyZXRzID0gdGhpcy5jcmVhdGVTZWNyZXRzKCk7XG4gICAgdGhpcy5lY3NUYXNrUm9sZS5hZGRUb1BvbGljeShcbiAgICAgIG5ldyBpYW0uUG9saWN5U3RhdGVtZW50KHtcbiAgICAgICAgYWN0aW9uczogWydzZWNyZXRzbWFuYWdlcjpHZXRTZWNyZXRWYWx1ZSddLFxuICAgICAgICByZXNvdXJjZXM6IFtcbiAgICAgICAgICB0aGlzLmRiU2VjcmV0LnNlY3JldEFybixcbiAgICAgICAgICAuLi5PYmplY3QudmFsdWVzKHNlY3JldHMpLm1hcCgocykgPT4gcy5zZWNyZXRBcm4pLFxuICAgICAgICBdLFxuICAgICAgfSlcbiAgICApO1xuXG4gICAgbGV0IGNlcnRpZmljYXRlOiBhY20uSUNlcnRpZmljYXRlO1xuICAgIC8vIGNvbnN0IHpvbmUgPSByb3V0ZTUzLkhvc3RlZFpvbmUuZnJvbUxvb2t1cCh0aGlzLCBcIkhvc3RlZFpvbmVcIiwge1xuICAgIC8vICAgZG9tYWluTmFtZSxcbiAgICAvLyB9KTtcbiAgICBpZiAoY2VydGlmaWNhdGVBcm4gJiYgY2VydGlmaWNhdGVBcm4gIT09ICcnKSB7XG4gICAgICBjZXJ0aWZpY2F0ZSA9IGFjbS5DZXJ0aWZpY2F0ZS5mcm9tQ2VydGlmaWNhdGVBcm4oXG4gICAgICAgIHRoaXMsXG4gICAgICAgICdJbXBvcnRlZENlcnRpZmljYXRlJyxcbiAgICAgICAgY2VydGlmaWNhdGVBcm5cbiAgICAgICk7XG4gICAgfSBlbHNlIHtcbiAgICAgIGNlcnRpZmljYXRlID0gbmV3IGFjbS5DZXJ0aWZpY2F0ZSh0aGlzLCAnTmV3Q2VydGlmaWNhdGUnLCB7XG4gICAgICAgIGRvbWFpbk5hbWUsXG4gICAgICAgIC8vIHZhbGlkYXRpb246IGFjbS5DZXJ0aWZpY2F0ZVZhbGlkYXRpb24uZnJvbURucyh6b25lKSxcbiAgICAgIH0pO1xuICAgIH1cblxuICAgIHRoaXMuYWxiU2VjdXJpdHlHcm91cCA9IG5ldyBlYzIuU2VjdXJpdHlHcm91cCh0aGlzLCAnQWxiU2VjdXJpdHlHcm91cCcsIHtcbiAgICAgIHZwYzogdGhpcy52cGMsXG4gICAgICBhbGxvd0FsbE91dGJvdW5kOiB0cnVlLFxuICAgIH0pO1xuICAgIHRoaXMuYWxiU2VjdXJpdHlHcm91cC5hZGRJbmdyZXNzUnVsZShlYzIuUGVlci5hbnlJcHY0KCksIGVjMi5Qb3J0LnRjcCg4MCkpO1xuICAgIHRoaXMuYWxiU2VjdXJpdHlHcm91cC5hZGRJbmdyZXNzUnVsZShlYzIuUGVlci5hbnlJcHY0KCksIGVjMi5Qb3J0LnRjcCg0NDMpKTtcblxuICAgIHRoaXMuYWxiID0gbmV3IGVsYnYyLkFwcGxpY2F0aW9uTG9hZEJhbGFuY2VyKHRoaXMsICdBdG9taWNBbGInLCB7XG4gICAgICB2cGM6IHRoaXMudnBjLFxuICAgICAgaW50ZXJuZXRGYWNpbmc6IHRydWUsXG4gICAgICBzZWN1cml0eUdyb3VwOiB0aGlzLmFsYlNlY3VyaXR5R3JvdXAsXG4gICAgfSk7XG5cbiAgICB0aGlzLmFsYi5hZGRMaXN0ZW5lcignSHR0cExpc3RlbmVyJywge1xuICAgICAgcG9ydDogODAsXG4gICAgICBkZWZhdWx0QWN0aW9uOiBlbGJ2Mi5MaXN0ZW5lckFjdGlvbi5yZWRpcmVjdCh7XG4gICAgICAgIHByb3RvY29sOiAnSFRUUFMnLFxuICAgICAgICBwb3J0OiAnNDQzJyxcbiAgICAgICAgcGVybWFuZW50OiB0cnVlLFxuICAgICAgfSksXG4gICAgfSk7XG5cbiAgICBjb25zdCBodHRwc0xpc3RlbmVyID0gdGhpcy5hbGIuYWRkTGlzdGVuZXIoJ0h0dHBzTGlzdGVuZXInLCB7XG4gICAgICBwb3J0OiA0NDMsXG4gICAgICBjZXJ0aWZpY2F0ZXM6IFtjZXJ0aWZpY2F0ZV0sXG4gICAgICBkZWZhdWx0QWN0aW9uOiBlbGJ2Mi5MaXN0ZW5lckFjdGlvbi5maXhlZFJlc3BvbnNlKDQwNCksXG4gICAgfSk7XG5cbiAgICAvLyAtLS0gU2VydmljZXMgLS0tXG4gICAgLy8gU3VwZXJ0b2tlbnMsIFBvc3RHcmFwaGlsZSwgSGFuZHNoYWtlLCBPQXV0aCwgT3B0YVBsYW5uZXIsIFB5dGhvbkFnZW50LCBGdW5jdGlvbnMsIEFwcFxuICAgIC8vIEZvciBicmV2aXR5LCBvbmx5IGltcGxlbWVudGluZyBhIGZldyBzZXJ2aWNlcyB0byBkZW1vbnN0cmF0ZSB0aGUgcGF0dGVyblxuICAgIGNvbnN0IHN1cGVydG9rZW5zU2VydmljZSA9IHRoaXMuY3JlYXRlU2VydmljZSgnU3VwZXJ0b2tlbnMnLCB7XG4gICAgICB0YXNrRGVmUHJvcHM6IHsgY3B1OiAyNTYsIG1lbW9yeU1pQjogNTEyLCBmYW1pbHk6ICdzdXBlcnRva2VucycgfSxcbiAgICAgIGNvbnRhaW5lclByb3BzOiB7XG4gICAgICAgIGltYWdlOiBlY3MuQ29udGFpbmVySW1hZ2UuZnJvbVJlZ2lzdHJ5KFxuICAgICAgICAgICdyZWdpc3RyeS5zdXBlcnRva2Vucy5pby9zdXBlcnRva2Vucy9zdXBlcnRva2Vucy1wb3N0Z3Jlc3FsOjYuMCdcbiAgICAgICAgKSxcbiAgICAgICAgc2VjcmV0czoge1xuICAgICAgICAgIFBPU1RHUkVTUUxfQ09OTkVDVElPTl9VUkk6IGVjcy5TZWNyZXQuZnJvbVNlY3JldHNNYW5hZ2VyKFxuICAgICAgICAgICAgc2VjcmV0cy5zdXBlcnRva2Vuc0RiQ29ublN0cmluZ1NlY3JldFxuICAgICAgICAgICksXG4gICAgICAgIH0sXG4gICAgICAgIHBvcnRNYXBwaW5nczogW3sgY29udGFpbmVyUG9ydDogMzU2NyB9XSxcbiAgICAgICAgZW52aXJvbm1lbnQ6IHsgUE9TVEdSRVNRTF9UQUJMRV9OQU1FU19QUkVGSVg6ICdTdXBlcnRva2VucycgfSxcbiAgICAgIH0sXG4gICAgICBsaXN0ZW5lcjogaHR0cHNMaXN0ZW5lcixcbiAgICAgIHBhdGhQYXR0ZXJuOiAnL3YxL2F1dGgvKicsXG4gICAgICBwcmlvcml0eTogMTAsXG4gICAgICB0YXJnZXRQb3J0OiAzNTY3LFxuICAgICAgaGVhbHRoQ2hlY2tQYXRoOiAnL2hlbGxvJyxcbiAgICB9KTtcbiAgICBzdXBlcnRva2Vuc1NlcnZpY2UuY29ubmVjdGlvbnMuYWxsb3dUbyhcbiAgICAgIHRoaXMucmRzU2VjdXJpdHlHcm91cCxcbiAgICAgIGVjMi5Qb3J0LnRjcCg1NDMyKVxuICAgICk7XG5cbiAgICAvLyBQbGFjZWhvbGRlciBmb3Igb3RoZXIgc2VydmljZXMuLi5cbiAgICBjb25zdCBhcHBTZXJ2aWNlID0gdGhpcy5jcmVhdGVTZXJ2aWNlKCdBcHAnLCB7XG4gICAgICB0YXNrRGVmUHJvcHM6IHsgY3B1OiA1MTIsIG1lbW9yeU1pQjogMTAyNCwgZmFtaWx5OiAnYXBwJyB9LFxuICAgICAgY29udGFpbmVyUHJvcHM6IHtcbiAgICAgICAgaW1hZ2U6IGVjcy5Db250YWluZXJJbWFnZS5mcm9tRWNyUmVwb3NpdG9yeShyZXBvc2l0b3JpZXMuYXBwKSxcbiAgICAgICAgcG9ydE1hcHBpbmdzOiBbeyBjb250YWluZXJQb3J0OiAzMDAwIH1dLFxuICAgICAgICBlbnZpcm9ubWVudDoge1xuICAgICAgICAgIC8vIEFkZCBhcHAtc3BlY2lmaWMgZW52IHZhcnMgaGVyZVxuICAgICAgICAgIE5FWFRfUFVCTElDX1NVUEVSVE9LRU5TX0FQSV9ET01BSU46IGBodHRwczovLyR7ZG9tYWluTmFtZX0vdjEvYXV0aGAsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgICAgbGlzdGVuZXI6IGh0dHBzTGlzdGVuZXIsXG4gICAgICBwYXRoUGF0dGVybjogJy8qJyxcbiAgICAgIHByaW9yaXR5OiAxMDAsXG4gICAgICB0YXJnZXRQb3J0OiAzMDAwLFxuICAgICAgaGVhbHRoQ2hlY2tQYXRoOiAnLycsXG4gICAgfSk7XG5cbiAgICAvLyAtLS0gT3V0cHV0cyAtLS1cbiAgICBuZXcgY2RrLkNmbk91dHB1dCh0aGlzLCAnQXBwbGljYXRpb25FbmRwb2ludCcsIHtcbiAgICAgIHZhbHVlOiBgaHR0cHM6Ly8ke2RvbWFpbk5hbWV9YCxcbiAgICB9KTtcbiAgfVxuXG4gIHByaXZhdGUgY3JlYXRlRWNyUmVwb3NpdG9yeShyZXBvc2l0b3J5TmFtZTogc3RyaW5nKTogZWNyLlJlcG9zaXRvcnkge1xuICAgIGNvbnN0IHJlcG8gPSBuZXcgZWNyLlJlcG9zaXRvcnkodGhpcywgYCR7cmVwb3NpdG9yeU5hbWV9UmVwb2AsIHtcbiAgICAgIHJlcG9zaXRvcnlOYW1lLFxuICAgICAgcmVtb3ZhbFBvbGljeTogY2RrLlJlbW92YWxQb2xpY3kuREVTVFJPWSxcbiAgICAgIGF1dG9EZWxldGVJbWFnZXM6IHRydWUsXG4gICAgfSk7XG4gICAgbmV3IGNkay5DZm5PdXRwdXQodGhpcywgYCR7cmVwb3NpdG9yeU5hbWV9UmVwb1VyaWAsIHtcbiAgICAgIHZhbHVlOiByZXBvLnJlcG9zaXRvcnlVcmksXG4gICAgfSk7XG4gICAgcmV0dXJuIHJlcG87XG4gIH1cblxuICBwcml2YXRlIGNyZWF0ZVNlY3JldHMoKTogeyBbaWQ6IHN0cmluZ106IHNlY3JldHNtYW5hZ2VyLklTZWNyZXQgfSB7XG4gICAgY29uc3Qgc2VjcmV0SWRzID0gW1xuICAgICAgJ1N1cGVydG9rZW5zRGJDb25uU3RyaW5nJyxcbiAgICAgICdQb3N0R3JhcGhpbGVEYkNvbm5TdHJpbmcnLFxuICAgICAgJ1Bvc3RHcmFwaGlsZUp3dFNlY3JldCcsXG4gICAgICAnQXBpVG9rZW5TZWNyZXQnLFxuICAgICAgJ09wZW5BaUFwaUtleScsXG4gICAgICAnT3B0YXBsYW5uZXJEYkNvbm5TdHJpbmcnLFxuICAgICAgJ05vdGlvbkFwaVRva2VuJyxcbiAgICAgICdEZWVwZ3JhbUFwaUtleScsXG4gICAgICAnTm90aW9uTm90ZXNEYklkJyxcbiAgICAgICdOb3Rpb25SZXNlYXJjaFByb2plY3RzRGJJZCcsXG4gICAgICAnTm90aW9uUmVzZWFyY2hUYXNrc0RiSWQnLFxuICAgICAgJ01za0Jvb3RzdHJhcEJyb2tlcnMnLFxuICAgIF07XG5cbiAgICBjb25zdCBjcmVhdGVkU2VjcmV0czogeyBbaWQ6IHN0cmluZ106IHNlY3JldHNtYW5hZ2VyLklTZWNyZXQgfSA9IHt9O1xuICAgIGZvciAoY29uc3QgaWQgb2Ygc2VjcmV0SWRzKSB7XG4gICAgICBjb25zdCBzZWNyZXQgPSBuZXcgc2VjcmV0c21hbmFnZXIuU2VjcmV0KHRoaXMsIGlkLCB7XG4gICAgICAgIHNlY3JldE5hbWU6IGAke3RoaXMuc3RhY2tOYW1lfS8ke2lkfWAsXG4gICAgICB9KTtcbiAgICAgIE5hZ1N1cHByZXNzaW9ucy5hZGRSZXNvdXJjZVN1cHByZXNzaW9ucyhcbiAgICAgICAgc2VjcmV0LFxuICAgICAgICBbXG4gICAgICAgICAge1xuICAgICAgICAgICAgaWQ6ICdBd3NTb2x1dGlvbnMtU01HNCcsXG4gICAgICAgICAgICByZWFzb246ICdTZWNyZXQgcm90YXRpb24gaXMgbm90IHJlcXVpcmVkIGZvciB0aGlzIHdvcmtzaG9wLicsXG4gICAgICAgICAgfSxcbiAgICAgICAgXSxcbiAgICAgICAgdHJ1ZVxuICAgICAgKTtcbiAgICAgIGNyZWF0ZWRTZWNyZXRzW2lkLmNoYXJBdCgwKS50b0xvd2VyQ2FzZSgpICsgaWQuc2xpY2UoMSkgKyAnU2VjcmV0J10gPVxuICAgICAgICBzZWNyZXQ7XG4gICAgfVxuICAgIHJldHVybiBjcmVhdGVkU2VjcmV0cztcbiAgfVxuXG4gIHByaXZhdGUgY3JlYXRlU2VydmljZShcbiAgICBuYW1lOiBzdHJpbmcsXG4gICAgcHJvcHM6IHtcbiAgICAgIHRhc2tEZWZQcm9wczogeyBjcHU6IG51bWJlcjsgbWVtb3J5TWlCOiBudW1iZXI7IGZhbWlseTogc3RyaW5nIH07XG4gICAgICBjb250YWluZXJQcm9wczogZWNzLkNvbnRhaW5lckRlZmluaXRpb25PcHRpb25zO1xuICAgICAgbGlzdGVuZXI6IGVsYnYyLkFwcGxpY2F0aW9uTGlzdGVuZXI7XG4gICAgICBwYXRoUGF0dGVybjogc3RyaW5nO1xuICAgICAgcHJpb3JpdHk6IG51bWJlcjtcbiAgICAgIHRhcmdldFBvcnQ6IG51bWJlcjtcbiAgICAgIGhlYWx0aENoZWNrUGF0aDogc3RyaW5nO1xuICAgIH1cbiAgKTogZWNzLkZhcmdhdGVTZXJ2aWNlIHtcbiAgICBjb25zdCBzZyA9IG5ldyBlYzIuU2VjdXJpdHlHcm91cCh0aGlzLCBgJHtuYW1lfVNHYCwge1xuICAgICAgdnBjOiB0aGlzLnZwYyxcbiAgICAgIGFsbG93QWxsT3V0Ym91bmQ6IHRydWUsXG4gICAgfSk7XG4gICAgc2cuY29ubmVjdGlvbnMuYWxsb3dGcm9tKFxuICAgICAgdGhpcy5hbGJTZWN1cml0eUdyb3VwLFxuICAgICAgZWMyLlBvcnQudGNwKHByb3BzLnRhcmdldFBvcnQpXG4gICAgKTtcblxuICAgIGNvbnN0IHRhc2tEZWYgPSBuZXcgZWNzLlRhc2tEZWZpbml0aW9uKHRoaXMsIGAke25hbWV9VGFza0RlZmAsIHtcbiAgICAgIGZhbWlseTogcHJvcHMudGFza0RlZlByb3BzLmZhbWlseSxcbiAgICAgIGNvbXBhdGliaWxpdHk6IGVjcy5Db21wYXRpYmlsaXR5LkZBUkdBVEUsXG4gICAgICBjcHU6IHByb3BzLnRhc2tEZWZQcm9wcy5jcHUudG9TdHJpbmcoKSxcbiAgICAgIG1lbW9yeU1pQjogcHJvcHMudGFza0RlZlByb3BzLm1lbW9yeU1pQi50b1N0cmluZygpLFxuICAgICAgdGFza1JvbGU6IHRoaXMuZWNzVGFza1JvbGUsXG4gICAgICBleGVjdXRpb25Sb2xlOiB0aGlzLmVjc1Rhc2tSb2xlLFxuICAgIH0pO1xuXG4gICAgdGFza0RlZi5hZGRDb250YWluZXIobmFtZSwge1xuICAgICAgLi4ucHJvcHMuY29udGFpbmVyUHJvcHMsXG4gICAgICBsb2dnaW5nOiBlY3MuTG9nRHJpdmVycy5hd3NMb2dzKHtcbiAgICAgICAgc3RyZWFtUHJlZml4OiBuYW1lLnRvTG93ZXJDYXNlKCksXG4gICAgICAgIGxvZ0dyb3VwOiBuZXcgbG9ncy5Mb2dHcm91cCh0aGlzLCBgJHtuYW1lfUxvZ0dyb3VwYCwge1xuICAgICAgICAgIGxvZ0dyb3VwTmFtZTogYC9hd3MvZWNzLyR7bmFtZX1gLFxuICAgICAgICAgIHJldGVudGlvbjogbG9ncy5SZXRlbnRpb25EYXlzLk9ORV9NT05USCxcbiAgICAgICAgICByZW1vdmFsUG9saWN5OiBjZGsuUmVtb3ZhbFBvbGljeS5ERVNUUk9ZLFxuICAgICAgICB9KSxcbiAgICAgIH0pLFxuICAgIH0pO1xuXG4gICAgY29uc3Qgc2VydmljZSA9IG5ldyBlY3MuRmFyZ2F0ZVNlcnZpY2UodGhpcywgYCR7bmFtZX1TZXJ2aWNlYCwge1xuICAgICAgY2x1c3RlcjogdGhpcy5jbHVzdGVyLFxuICAgICAgdGFza0RlZmluaXRpb246IHRhc2tEZWYsXG4gICAgICBzZWN1cml0eUdyb3VwczogW3NnXSxcbiAgICB9KTtcblxuICAgIGNvbnN0IHRhcmdldEdyb3VwID0gbmV3IGVsYnYyLkFwcGxpY2F0aW9uVGFyZ2V0R3JvdXAoXG4gICAgICB0aGlzLFxuICAgICAgYCR7bmFtZX1UYXJnZXRHcm91cGAsXG4gICAgICB7XG4gICAgICAgIHZwYzogdGhpcy52cGMsXG4gICAgICAgIHBvcnQ6IHByb3BzLnRhcmdldFBvcnQsXG4gICAgICAgIHByb3RvY29sOiBlbGJ2Mi5BcHBsaWNhdGlvblByb3RvY29sLkhUVFAsXG4gICAgICAgIHRhcmdldHM6IFtzZXJ2aWNlXSxcbiAgICAgICAgaGVhbHRoQ2hlY2s6IHsgcGF0aDogcHJvcHMuaGVhbHRoQ2hlY2tQYXRoIH0sXG4gICAgICB9XG4gICAgKTtcblxuICAgIHByb3BzLmxpc3RlbmVyLmFkZEFjdGlvbihuYW1lLCB7XG4gICAgICBwcmlvcml0eTogcHJvcHMucHJpb3JpdHksXG4gICAgICBjb25kaXRpb25zOiBbZWxidjIuTGlzdGVuZXJDb25kaXRpb24ucGF0aFBhdHRlcm5zKFtwcm9wcy5wYXRoUGF0dGVybl0pXSxcbiAgICAgIGFjdGlvbjogZWxidjIuTGlzdGVuZXJBY3Rpb24uZm9yd2FyZChbdGFyZ2V0R3JvdXBdKSxcbiAgICB9KTtcblxuICAgIHJldHVybiBzZXJ2aWNlO1xuICB9XG59XG4iXX0=