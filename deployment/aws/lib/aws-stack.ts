import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as opensearch from 'aws-cdk-lib/aws-opensearchservice';

export class AwsStack extends cdk.Stack {
  // Define class properties for resources that need to be accessed across methods or by other constructs
  public dataBucket: s3.Bucket; // Made public for now, can be private if only accessed internally
  private readonly vpc: ec2.Vpc;
  private readonly cluster: ecs.Cluster;
  private readonly alb: elbv2.ApplicationLoadBalancer;
  private readonly httpListener: elbv2.ApplicationListener;
  private readonly dbInstance: rds.DatabaseInstance;
  private readonly dbSecret: secretsmanager.ISecret;
  private readonly rdsSecurityGroup: ec2.SecurityGroup;
  private readonly albSecurityGroup: ec2.SecurityGroup;

  // ECR Repositories
  private readonly functionsRepo: ecr.IRepository;
  private readonly handshakeRepo: ecr.IRepository;
  private readonly oauthRepo: ecr.IRepository;
  private readonly appRepo: ecr.IRepository;
  public optaplannerRepo: ecr.IRepository; // Made public for now if needed by other constructs, else private

  // ECS Task Role
  private readonly ecsTaskRole: iam.Role;

  // Secrets
  private readonly hasuraAdminSecret: secretsmanager.ISecret;
  private readonly supertokensDbConnStringSecret: secretsmanager.ISecret;
  private readonly hasuraDbConnStringSecret: secretsmanager.ISecret;
  private readonly placeholderHasuraJwtSecret: secretsmanager.ISecret;
  private readonly apiTokenSecret: secretsmanager.ISecret;
  private readonly openAiApiKeySecret: secretsmanager.ISecret;
  public optaplannerDbConnStringSecret: secretsmanager.ISecret; // Made public for now

  // SuperTokens specific resources (if needed by other services, e.g. SG)
  private readonly supertokensSG: ec2.SecurityGroup;
  private readonly supertokensTaskDef: ecs.TaskDefinition;

  // Service-specific Security Groups (if they need to be referenced by other SGs)
  private readonly hasuraSG: ec2.SecurityGroup;
  private readonly functionsSG: ec2.SecurityGroup;
  private readonly appSG: ec2.SecurityGroup;
  private readonly handshakeSG: ec2.SecurityGroup;
  private readonly oauthSG: ec2.SecurityGroup;
  public optaplannerSG!: ec2.SecurityGroup; // Will be initialized later
  public optaplannerService!: ecs.FargateService; // Will be initialized later
  public openSearchDomain!: opensearch.IDomain; // opensearch was not imported yet


  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 Data Bucket
    this.dataBucket = new s3.Bucket(this, 'AtomicDataBucket', {
      bucketName: `${this.stackName.toLowerCase()}-atomic-data-bucket-${this.account}-${this.region}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      versioned: false,
      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
    });
    new cdk.CfnOutput(this, 'DataBucketName', { value: this.dataBucket.bucketName });


    this.functionsRepo = new ecr.Repository(this, 'AtomicFunctionsRepo', {
      repositoryName: 'atomic-functions',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteImages: true
    });
    new cdk.CfnOutput(this, 'FunctionsRepoUri', { value: this.functionsRepo.repositoryUri });

    this.handshakeRepo = new ecr.Repository(this, 'AtomicHandshakeRepo', {
      repositoryName: 'atomic-handshake',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteImages: true
    });
    new cdk.CfnOutput(this, 'HandshakeRepoUri', { value: this.handshakeRepo.repositoryUri });

    this.oauthRepo = new ecr.Repository(this, 'AtomicOauthRepo', {
      repositoryName: 'atomic-oauth',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteImages: true
    });
    new cdk.CfnOutput(this, 'OauthRepoUri', { value: this.oauthRepo.repositoryUri });

    this.appRepo = new ecr.Repository(this, 'AtomicAppRepo', {
      repositoryName: 'atomic-app',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteImages: true
    });
    new cdk.CfnOutput(this, 'AppRepoUri', { value: this.appRepo.repositoryUri });

    this.optaplannerRepo = new ecr.Repository(this, 'AtomicOptaplannerRepo', {
      repositoryName: 'atomic-optaplanner',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteImages: true,
    });
    new cdk.CfnOutput(this, 'OptaplannerRepoUri', { value: this.optaplannerRepo.repositoryUri });

    // VPC
    this.vpc = new ec2.Vpc(this, 'AtomicVpc', {
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        { cidrMask: 24, name: 'PublicSubnet', subnetType: ec2.SubnetType.PUBLIC },
        { cidrMask: 24, name: 'PrivateSubnet', subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      ],
    });
    new cdk.CfnOutput(this, 'VpcId', { value: this.vpc.vpcId });

    // RDS Security Group
    this.rdsSecurityGroup = new ec2.SecurityGroup(this, 'RdsSecurityGroup', {
      vpc: this.vpc,
      description: 'Allow inbound traffic to RDS from within VPC',
      allowAllOutbound: true
    });

    // RDS PostgreSQL Instance
    this.dbInstance = new rds.DatabaseInstance(this, 'AtomicPostgresDB', {
      engine: rds.DatabaseInstanceEngine.postgres({ version: rds.PostgresEngineVersion.VER_15 }),
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.SMALL),
      vpc: this.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [this.rdsSecurityGroup],
      credentials: rds.Credentials.fromGeneratedSecret('PostgresAdminCredentials'),
      databaseName: 'atomicdb',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      publiclyAccessible: false,
    });
    this.dbSecret = this.dbInstance.secret!;
    new cdk.CfnOutput(this, 'DbInstanceEndpoint', { value: this.dbInstance.dbInstanceEndpointAddress });
    new cdk.CfnOutput(this, 'DbSecretArn', { value: this.dbSecret.secretArn });

    // ECS Cluster
    this.cluster = new ecs.Cluster(this, 'AtomicCluster', {
      vpc: this.vpc,
    });
    new cdk.CfnOutput(this, 'ClusterName', { value: this.cluster.clusterName });

    // ALB Security Group
    this.albSecurityGroup = new ec2.SecurityGroup(this, 'AlbSecurityGroup', {
        vpc: this.vpc,
        description: 'Allow HTTP/HTTPS traffic to ALB',
        allowAllOutbound: true
    });
    this.albSecurityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80), 'Allow HTTP from anywhere');

    // Application Load Balancer
    this.alb = new elbv2.ApplicationLoadBalancer(this, 'AtomicAlb', {
      vpc: this.vpc,
      internetFacing: true,
      securityGroup: this.albSecurityGroup,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });
    new cdk.CfnOutput(this, 'AlbDnsName', { value: this.alb.loadBalancerDnsName });

    // ALB HTTP Listener
    this.httpListener = this.alb.addListener('HttpListener', {
        port: 80,
        protocol: elbv2.ApplicationProtocol.HTTP,
        open: false,
        defaultAction: elbv2.ListenerAction.fixedResponse(404, {
            contentType: 'text/plain',
            messageBody: 'Resource not found',
        }),
    });
    new cdk.CfnOutput(this, 'AlbHttpListenerArn', { value: this.httpListener.listenerArn });

    // Generic Task Role
    this.ecsTaskRole = new iam.Role(this, 'ECSTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      description: 'Role for ECS tasks to access other AWS services',
    });

    // Placeholder Secrets
    this.supertokensDbConnStringSecret = new secretsmanager.Secret(this, 'SupertokensDbConnStringSecret', {
      secretName: `${this.stackName}/SupertokensDbConnString`,
      description: "Manually populate with: postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}",
    });
    new cdk.CfnOutput(this, 'SupertokensDbConnStringSecretArn', { value: this.supertokensDbConnStringSecret.secretArn });

    this.hasuraDbConnStringSecret = new secretsmanager.Secret(this, 'HasuraDbConnStringSecret', {
      secretName: `${this.stackName}/HasuraDbConnString`,
      description: "Manually populate with: postgres://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}",
    });
    new cdk.CfnOutput(this, 'HasuraDbConnStringSecretArn', { value: this.hasuraDbConnStringSecret.secretArn });

    this.placeholderHasuraJwtSecret = new secretsmanager.Secret(this, 'PlaceholderHasuraJwtSecret', {
      secretName: `${this.stackName}/HasuraJwtSecret`,
      description: 'Placeholder for HASURA_GRAPHQL_JWT_SECRET. MUST be replaced in AWS Secrets Manager console with a valid JSON containing a strong 256-bit key. Example structure: {"type":"HS256","key":"YOUR_STRONG_SECRET_KEY","issuer":"supertokens"}',
      secretStringValue: cdk.SecretValue.unsafePlainText('{"type":"HS256","key":"REPLACE_WITH_A_STRONG_64_CHAR_HEX_SECRET_OR_MIN_32_CHAR_ASCII","issuer":"supertokens"}'),
    });
    new cdk.CfnOutput(this, 'PlaceholderHasuraJwtSecretArn', { value: this.placeholderHasuraJwtSecret.secretArn });

    this.apiTokenSecret = new secretsmanager.Secret(this, 'ApiTokenSecret', {
      secretName: `${this.stackName}/InternalApiToken`,
      description: 'Generic API token for inter-service communication.',
      generateSecretString: {
        passwordLength: 32,
        excludePunctuation: true,
      },
    });
    new cdk.CfnOutput(this, 'ApiTokenSecretArn', { value: this.apiTokenSecret.secretArn });

    this.openAiApiKeySecret = new secretsmanager.Secret(this, 'OpenAiApiKeySecret', {
      secretName: `${this.stackName}/OpenAiApiKey`,
      description: "Manually populate with actual OpenAI API Key",
    });
    new cdk.CfnOutput(this, 'OpenAiApiKeySecretArn', { value: this.openAiApiKeySecret.secretArn });

    this.optaplannerDbConnStringSecret = new secretsmanager.Secret(this, 'OptaplannerDbConnString', {
        secretName: `${this.stackName}/OptaplannerDbConnString`,
        description: "Manually populate with Optaplanner JDBC URL: jdbc:postgresql://${DB_HOST}:${DB_PORT}/${DB_NAME}",
    });
    new cdk.CfnOutput(this, 'OptaplannerDbConnStringArn', { value: this.optaplannerDbConnStringSecret.secretArn });

    this.hasuraAdminSecret = new secretsmanager.Secret(this, 'HasuraAdminSecret', {
      secretName: `${this.stackName}/HasuraAdminSecret`,
      description: 'Admin secret for Hasura GraphQL engine',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ HASURA_GRAPHQL_ADMIN_SECRET: 'dummyPasswordPlaceholder' }),
        generateStringKey: 'HASURA_GRAPHQL_ADMIN_SECRET_VALUE',
        passwordLength: 32,
        excludePunctuation: true,
      },
    });
    new cdk.CfnOutput(this, 'HasuraAdminSecretOutput', { value: this.hasuraAdminSecret.secretArn });

    // Add policies to ECS Task Role now that secrets are defined
    this.ecsTaskRole.addToPolicy(new iam.PolicyStatement({
        actions: ['secretsmanager:GetSecretValue'],
        resources: [
            this.dbSecret.secretArn,
            this.hasuraAdminSecret.secretArn,
            this.supertokensDbConnStringSecret.secretArn,
            this.hasuraDbConnStringSecret.secretArn,
            this.placeholderHasuraJwtSecret.secretArn,
            this.apiTokenSecret.secretArn,
            this.openAiApiKeySecret.secretArn,
            this.optaplannerDbConnStringSecret.secretArn,
            `arn:aws:secretsmanager:${this.region}:${this.account}:secret:${this.stackName}/*`
        ],
    }));
    // Grant ECS Task Role S3 Read/Write access to the data bucket
    this.dataBucket.grantReadWrite(this.ecsTaskRole);

    this.ecsTaskRole.addToPolicy(new iam.PolicyStatement({
        actions: [
            "ecr:GetAuthorizationToken", "ecr:BatchCheckLayerAvailability",
            "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"
        ],
        resources: ["*"]
    }));
    this.ecsTaskRole.addToPolicy(new iam.PolicyStatement({
        actions: ["logs:CreateLogStream", "logs:PutLogEvents"],
        resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/ecs/${this.cluster.clusterName}/*`],
    }));

    // SuperTokens Service
    this.supertokensSG = new ec2.SecurityGroup(this, 'SupertokensSG', { vpc: this.vpc, allowAllOutbound: true });
    this.supertokensSG.connections.allowFrom(this.albSecurityGroup, ec2.Port.tcp(3567), 'Allow SuperTokens from ALB');
    this.rdsSecurityGroup.addIngressRule(this.supertokensSG, ec2.Port.tcp(5432), 'Allow Supertokens to connect to RDS');

    this.supertokensTaskDef = new ecs.TaskDefinition(this, 'SupertokensTaskDef', {
      family: 'supertokens-fargate',
      compatibility: ecs.Compatibility.FARGATE,
      cpu: "256",
      memoryMiB: "512",
      runtimePlatform: {
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
        cpuArchitecture: ecs.CpuArchitecture.X86_64,
      },
      taskRole: this.ecsTaskRole,
    });

    this.supertokensTaskDef.addContainer('SupertokensContainer', {
      image: ecs.ContainerImage.fromRegistry('registry.supertokens.io/supertokens/supertokens-postgresql:6.0'),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'supertokens-ecs',
        logGroup: new logs.LogGroup(this, 'SupertokensLogGroup', {
          logGroupName: `/aws/ecs/${this.cluster.clusterName}/supertokens`,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
      }),
      environment: {
          POSTGRESQL_TABLE_NAMES_PREFIX: 'Supertokens',
      },
      secrets: {
        POSTGRESQL_CONNECTION_URI: ecs.Secret.fromSecretsManager(this.supertokensDbConnStringSecret)
      },
      portMappings: [{ containerPort: 3567, protocol: ecs.Protocol.TCP }],
    });

    const supertokensService = new ecs.FargateService(this, 'SupertokensService', {
      cluster: this.cluster,
      taskDefinition: this.supertokensTaskDef,
      desiredCount: 1,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [this.supertokensSG], // Corrected
      assignPublicIp: false,
    });

    const supertokensTargetGroup = new elbv2.ApplicationTargetGroup(this, 'SupertokensTargetGroup', {
      vpc: this.vpc,
      port: 3567,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      targets: [supertokensService],
      healthCheck: {
        path: '/hello',
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 2,
      },
    });

    new elbv2.ApplicationListenerRule(this, 'SupertokensListenerRule', {
      listener: this.httpListener,
      priority: 10,
      conditions: [elbv2.ListenerCondition.pathPatterns(['/v1/auth/*'])],
      action: elbv2.ListenerAction.forward([supertokensTargetGroup]),
    });

    // --- Hasura GraphQL Engine Service ---
    this.hasuraSG = new ec2.SecurityGroup(this, 'HasuraSG', { vpc: this.vpc, allowAllOutbound: true });
    this.hasuraSG.connections.allowFrom(this.albSecurityGroup, ec2.Port.tcp(8080), 'Allow Hasura from ALB');
    this.rdsSecurityGroup.addIngressRule(this.hasuraSG, ec2.Port.tcp(5432), 'Allow Hasura to connect to RDS');

    const hasuraTaskDef = new ecs.TaskDefinition(this, 'HasuraTaskDef', {
      family: 'hasura-fargate',
      compatibility: ecs.Compatibility.FARGATE,
      cpu: "512",
      memoryMiB: "1024",
      runtimePlatform: {
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
        cpuArchitecture: ecs.CpuArchitecture.X86_64,
      },
      taskRole: this.ecsTaskRole,
    });

    hasuraTaskDef.addContainer('HasuraContainer', {
      image: ecs.ContainerImage.fromRegistry('hasura/graphql-engine:v2.38.0'),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'hasura-ecs',
        logGroup: new logs.LogGroup(this, 'HasuraLogGroup', {
          logGroupName: `/aws/ecs/${this.cluster.clusterName}/hasura`,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
      }),
      environment: {
        HASURA_GRAPHQL_UNAUTHORIZED_ROLE: 'public',
        HASURA_GRAPHQL_LOG_LEVEL: 'debug',
        HASURA_GRAPHQL_ENABLE_CONSOLE: 'true',
        HASURA_GRAPHQL_DEV_MODE: 'true',
      },
      secrets: {
        HASURA_GRAPHQL_ADMIN_SECRET: ecs.Secret.fromSecretsManager(this.hasuraAdminSecret),
        HASURA_GRAPHQL_JWT_SECRET: ecs.Secret.fromSecretsManager(this.placeholderHasuraJwtSecret),
        HASURA_GRAPHQL_DATABASE_URL: ecs.Secret.fromSecretsManager(this.hasuraDbConnStringSecret),
      },
      portMappings: [{ containerPort: 8080, protocol: ecs.Protocol.TCP }],
    });

    const hasuraService = new ecs.FargateService(this, 'HasuraService', {
      cluster: this.cluster,
      taskDefinition: hasuraTaskDef,
      desiredCount: 1,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [this.hasuraSG],
      assignPublicIp: false,
    });

    const hasuraTargetGroup = new elbv2.ApplicationTargetGroup(this, 'HasuraTargetGroup', {
      vpc: this.vpc,
      port: 8080,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      targets: [hasuraService],
      healthCheck: {
        path: '/healthz',
        interval: cdk.Duration.seconds(30),
      },
    });

    new elbv2.ApplicationListenerRule(this, 'HasuraListenerRule', {
      listener: this.httpListener,
      priority: 20,
      conditions: [elbv2.ListenerCondition.pathPatterns(['/v1/graphql/*'])],
      action: elbv2.ListenerAction.forward([hasuraTargetGroup]),
    });

    // --- Functions Service ---
    this.functionsSG = new ec2.SecurityGroup(this, 'FunctionsSG', { vpc: this.vpc, allowAllOutbound: true });
    this.functionsSG.connections.allowFrom(this.albSecurityGroup, ec2.Port.tcp(80), 'Allow Functions from ALB on its container port');
    this.hasuraSG.connections.allowFrom(this.functionsSG, ec2.Port.tcp(8080), 'Allow Functions to connect to Hasura');

    const functionsTaskDef = new ecs.TaskDefinition(this, 'FunctionsTaskDef', {
      family: 'functions-fargate',
      compatibility: ecs.Compatibility.FARGATE,
      cpu: "512",
      memoryMiB: "1024",
      runtimePlatform: {
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
        cpuArchitecture: ecs.CpuArchitecture.X86_64,
      },
      taskRole: this.ecsTaskRole,
      executionRole: this.ecsTaskRole,
    });

    functionsTaskDef.addContainer('FunctionsContainer', {
      image: ecs.ContainerImage.fromEcrRepository(this.functionsRepo),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'functions-ecs',
        logGroup: new logs.LogGroup(this, 'FunctionsLogGroup', {
          logGroupName: `/aws/ecs/${this.cluster.clusterName}/functions`,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
      }),
      environment: {
        HASURA_GRAPHQL_GRAPHQL_URL: `http://${this.alb.loadBalancerDnsName}/v1/graphql`,
        FUNCTION_SERVER_URL: `http://${this.alb.loadBalancerDnsName}/v1/functions`,
        APP_CLIENT_URL: `http://${this.alb.loadBalancerDnsName}`,
        S3_BUCKET: this.dataBucket.bucketName,
        AWS_REGION: this.region,
      },
      secrets: {
        HASURA_GRAPHQL_ADMIN_SECRET: ecs.Secret.fromSecretsManager(this.hasuraAdminSecret),
        OPENAI_API_KEY: ecs.Secret.fromSecretsManager(this.openAiApiKeySecret),
      },
      portMappings: [{ containerPort: 80, protocol: ecs.Protocol.TCP }],
    });

    const functionsService = new ecs.FargateService(this, 'FunctionsService', {
      cluster: this.cluster,
      taskDefinition: functionsTaskDef,
      desiredCount: 1,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [this.functionsSG],
      assignPublicIp: false,
    });

    const functionsTargetGroup = new elbv2.ApplicationTargetGroup(this, 'FunctionsTargetGroup', {
      vpc: this.vpc,
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      targets: [functionsService],
      healthCheck: {
        path: '/v1/functions/healthz',
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
      },
    });

    new elbv2.ApplicationListenerRule(this, 'FunctionsListenerRule', {
      listener: this.httpListener,
      priority: 30,
      conditions: [elbv2.ListenerCondition.pathPatterns(['/v1/functions/*'])],
      action: elbv2.ListenerAction.forward([functionsTargetGroup]),
    });

    // --- App Service (Frontend) ---
    this.appSG = new ec2.SecurityGroup(this, 'AppSG', { vpc: this.vpc, allowAllOutbound: true }); // Corrected: this.appSG
    this.appSG.connections.allowFrom(this.albSecurityGroup, ec2.Port.tcp(3000), 'Allow App from ALB on its container port');

    const appTaskDef = new ecs.TaskDefinition(this, 'AppTaskDef', {
      family: 'app-fargate',
      compatibility: ecs.Compatibility.FARGATE,
      cpu: "256",
      memoryMiB: "512",
      runtimePlatform: {
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
        cpuArchitecture: ecs.CpuArchitecture.X86_64,
      },
      taskRole: this.ecsTaskRole,
      executionRole: this.ecsTaskRole,
    });

    appTaskDef.addContainer('AppContainer', {
      image: ecs.ContainerImage.fromEcrRepository(this.appRepo),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'app-ecs',
        logGroup: new logs.LogGroup(this, 'AppLogGroup', {
          logGroupName: `/aws/ecs/${this.cluster.clusterName}/app`,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
      }),
      environment: {
        NEXT_PUBLIC_HASURA_GRAPHQL_GRAPHQL_URL: `http://${this.alb.loadBalancerDnsName}/v1/graphql`,
        NEXT_PUBLIC_HASURA_GRAPHQL_GRAPHQL_WS_URL: `ws://${this.alb.loadBalancerDnsName}/v1/graphql`,
        NEXT_PUBLIC_SUPERTOKENS_API_DOMAIN: `http://${this.alb.loadBalancerDnsName}/v1/auth`,
        NEXT_PUBLIC_HANDSHAKE_URL: `http://${this.alb.loadBalancerDnsName}/v1/handshake/`,
        NEXT_PUBLIC_EVENT_TO_QUEUE_AUTH_URL: `http://${this.alb.loadBalancerDnsName}/v1/functions/eventToQueueAuth`,
      },
      portMappings: [{ containerPort: 3000, protocol: ecs.Protocol.TCP }],
    });

    const appService = new ecs.FargateService(this, 'AppService', {
      cluster: this.cluster,
      taskDefinition: appTaskDef,
      desiredCount: 1,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [this.appSG], // Corrected: this.appSG
      assignPublicIp: false,
    });

    const appTargetGroup = new elbv2.ApplicationTargetGroup(this, 'AppTargetGroup', {
      vpc: this.vpc,
      port: 3000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      targets: [appService],
      healthCheck: {
        path: '/',
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
      },
    });

    new elbv2.ApplicationListenerRule(this, 'AppListenerRule', {
      listener: this.httpListener,
      priority: 100,
      conditions: [elbv2.ListenerCondition.pathPatterns(['/*'])],
      action: elbv2.ListenerAction.forward([appTargetGroup]),
    });

    // --- Handshake Service ---
    this.handshakeSG = new ec2.SecurityGroup(this, 'HandshakeSG', { vpc: this.vpc, allowAllOutbound: true });
    this.handshakeSG.connections.allowFrom(this.albSecurityGroup, ec2.Port.tcp(80), 'Allow Handshake from ALB on its container port');
    this.hasuraSG.connections.allowFrom(this.handshakeSG, ec2.Port.tcp(8080), 'Allow Handshake to connect to Hasura');

    const handshakeTaskDef = new ecs.TaskDefinition(this, 'HandshakeTaskDef', {
      family: 'handshake-fargate',
      compatibility: ecs.Compatibility.FARGATE,
      cpu: "256",
      memoryMiB: "512",
      runtimePlatform: {
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
        cpuArchitecture: ecs.CpuArchitecture.X86_64,
      },
      taskRole: this.ecsTaskRole,
      executionRole: this.ecsTaskRole,
    });

    handshakeTaskDef.addContainer('HandshakeContainer', {
      image: ecs.ContainerImage.fromEcrRepository(this.handshakeRepo),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'handshake-ecs',
        logGroup: new logs.LogGroup(this, 'HandshakeLogGroup', {
          logGroupName: `/aws/ecs/${this.cluster.clusterName}/handshake`,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
      }),
      environment: {
        HASURA_GRAPHQL_GRAPHQL_URL: `http://${this.alb.loadBalancerDnsName}/v1/graphql`,
        MEETING_ASSIST_ADMIN_URL: `http://${this.alb.loadBalancerDnsName}/v1/functions/schedule-assist/placeholder`,
      },
      secrets: {
        API_TOKEN: ecs.Secret.fromSecretsManager(this.apiTokenSecret),
        HASURA_GRAPHQL_ADMIN_SECRET: ecs.Secret.fromSecretsManager(this.hasuraAdminSecret),
      },
      portMappings: [{ containerPort: 80, protocol: ecs.Protocol.TCP }],
    });

    const handshakeService = new ecs.FargateService(this, 'HandshakeService', {
      cluster: this.cluster,
      taskDefinition: handshakeTaskDef,
      desiredCount: 1,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [this.handshakeSG],
      assignPublicIp: false,
    });

    const handshakeTargetGroup = new elbv2.ApplicationTargetGroup(this, 'HandshakeTargetGroup', {
      vpc: this.vpc,
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      targets: [handshakeService],
      healthCheck: {
        path: '/health',
        interval: cdk.Duration.seconds(30),
      },
    });

    new elbv2.ApplicationListenerRule(this, 'HandshakeListenerRule', {
      listener: this.httpListener,
      priority: 40,
      conditions: [elbv2.ListenerCondition.pathPatterns(['/v1/handshake/*'])],
      action: elbv2.ListenerAction.forward([handshakeTargetGroup]),
    });

    // --- OAuth Service ---
    this.oauthSG = new ec2.SecurityGroup(this, 'OAuthSG', { vpc: this.vpc, allowAllOutbound: true });
    this.oauthSG.connections.allowFrom(this.albSecurityGroup, ec2.Port.tcp(80), 'Allow OAuth from ALB on its container port');
    this.hasuraSG.connections.allowFrom(this.oauthSG, ec2.Port.tcp(8080), 'Allow OAuth to connect to Hasura');
    this.handshakeSG.connections.allowFrom(this.oauthSG, ec2.Port.tcp(80), 'Allow OAuth to connect to Handshake');

    const oauthTaskDef = new ecs.TaskDefinition(this, 'OAuthTaskDef', {
      family: 'oauth-fargate',
      compatibility: ecs.Compatibility.FARGATE,
      cpu: "256",
      memoryMiB: "512",
      runtimePlatform: {
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
        cpuArchitecture: ecs.CpuArchitecture.X86_64,
      },
      taskRole: this.ecsTaskRole,
      executionRole: this.ecsTaskRole,
    });

    oauthTaskDef.addContainer('OAuthContainer', {
      image: ecs.ContainerImage.fromEcrRepository(this.oauthRepo),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'oauth-ecs',
        logGroup: new logs.LogGroup(this, 'OAuthLogGroup', {
          logGroupName: `/aws/ecs/${this.cluster.clusterName}/oauth`,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
      }),
      environment: {
        HASURA_GRAPHQL_GRAPHQL_URL: `http://${this.alb.loadBalancerDnsName}/v1/graphql`,
        HANDSHAKE_URL: `http://${this.alb.loadBalancerDnsName}/v1/handshake`,
      },
      secrets: {
        HASURA_GRAPHQL_ADMIN_SECRET: ecs.Secret.fromSecretsManager(this.hasuraAdminSecret),
      },
      portMappings: [{ containerPort: 80, protocol: ecs.Protocol.TCP }],
    });

    const oauthService = new ecs.FargateService(this, 'OAuthService', {
      cluster: this.cluster,
      taskDefinition: oauthTaskDef,
      desiredCount: 1,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [this.oauthSG], // Corrected: this.oauthSG, was this.supertokensSG in error
      assignPublicIp: false,
    });

    const oauthTargetGroup = new elbv2.ApplicationTargetGroup(this, 'OAuthTargetGroup', {
      vpc: this.vpc,
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      targets: [oauthService],
      healthCheck: {
        path: '/health',
        interval: cdk.Duration.seconds(30),
      },
    });

    new elbv2.ApplicationListenerRule(this, 'OAuthListenerRule', {
      listener: this.httpListener,
      priority: 50,
      conditions: [elbv2.ListenerCondition.pathPatterns(['/v1/oauth/*'])],
      action: elbv2.ListenerAction.forward([oauthTargetGroup]),
    });

    // Optaplanner Service
    this.optaplannerSG = new ec2.SecurityGroup(this, 'OptaplannerSG', { vpc: this.vpc, allowAllOutbound: true });
    this.rdsSecurityGroup.connections.allowFrom(this.optaplannerSG, ec2.Port.tcp(5432), 'Allow traffic from Optaplanner to RDS');

    const optaplannerTaskDef = new ecs.TaskDefinition(this, 'OptaplannerTaskDef', {
      family: `${this.stackName}-optaplanner`,
      compatibility: ecs.Compatibility.FARGATE,
      cpu: "1024",
      memoryMiB: "2048",
      runtimePlatform: {
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
        cpuArchitecture: ecs.CpuArchitecture.X86_64,
      },
      taskRole: this.ecsTaskRole,
      executionRole: this.ecsTaskRole,
    });

    optaplannerTaskDef.addContainer('OptaplannerContainer', {
      image: ecs.ContainerImage.fromEcrRepository(this.optaplannerRepo),
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: `${this.stackName}/optaplanner`, logGroup: new logs.LogGroup(this, 'OptaplannerLogGroup', { logGroupName: `/aws/ecs/${this.cluster.clusterName}/optaplanner`, removalPolicy: cdk.RemovalPolicy.DESTROY }) }),
      environment: {
        QUARKUS_DATASOURCE_DB_KIND: 'postgresql',
        USERNAME: 'admin', // Hardcoded as per subtask note
      },
      secrets: {
        QUARKUS_DATASOURCE_JDBC_URL: ecs.Secret.fromSecretsManager(this.optaplannerDbConnStringSecret),
        QUARKUS_DATASOURCE_USERNAME: ecs.Secret.fromSecretsManager(this.dbSecret, 'username'),
        QUARKUS_DATASOURCE_PASSWORD: ecs.Secret.fromSecretsManager(this.dbSecret, 'password'),
        PASSWORD: ecs.Secret.fromSecretsManager(this.apiTokenSecret),
      },
      portMappings: [{ containerPort: 8081, hostPort: 8081, protocol: ecs.Protocol.TCP }],
    });

    this.optaplannerService = new ecs.FargateService(this, 'OptaplannerService', {
      cluster: this.cluster,
      taskDefinition: optaplannerTaskDef,
      desiredCount: 1,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [this.optaplannerSG],
      assignPublicIp: false,
    });

    const optaplannerTargetGroup = new elbv2.ApplicationTargetGroup(this, 'OptaplannerTargetGroup', {
      vpc: this.vpc,
      port: 8081,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      targets: [this.optaplannerService],
      healthCheck: {
        path: '/q/health',
        interval: cdk.Duration.seconds(30),
      },
    });
    new elbv2.ApplicationListenerRule(this, 'OptaplannerListenerRule', {
      listener: this.httpListener,
      priority: 60,
      conditions: [elbv2.ListenerCondition.pathPatterns(['/v1/optaplanner/*'])],
      action: elbv2.ListenerAction.forward([optaplannerTargetGroup]),
    });
    this.optaplannerSG.connections.allowFrom(this.albSecurityGroup, ec2.Port.tcp(8081), 'Allow traffic from ALB to Optaplanner');

    // Note: OpenSearch Domain definition and related permissions will be added in the next step / subtask.
  }
}
