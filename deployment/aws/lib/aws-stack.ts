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
import * as efs from 'aws-cdk-lib/aws-efs';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cw_actions from 'aws-cdk-lib/aws-cloudwatch-actions';
import { NagSuppressions } from 'cdk-nag';

export class AwsStack extends cdk.Stack {
  private readonly vpc: ec2.Vpc;
  private readonly cluster: ecs.Cluster;
  private readonly alb: elbv2.ApplicationLoadBalancer;
  private readonly dbInstance: rds.DatabaseInstance;
  private readonly dbSecret: secretsmanager.ISecret;
  private readonly ecsTaskRole: iam.Role;
  private readonly albSecurityGroup: ec2.SecurityGroup;
  private readonly rdsSecurityGroup: ec2.SecurityGroup;
  private readonly dataBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // --- CfnParameters ---
    // const domainNameParameter = new cdk.CfnParameter(this, "DomainName", {
    //   type: "String",
    //   description: "The domain name for the application (e.g., app.example.com)",
    // });
    const certificateArnParameter = new cdk.CfnParameter(
      this,
      'CertificateArn',
      {
        type: 'String',
        description:
          'Optional: ARN of an existing ACM certificate for the domain name.',
        default: '',
      }
    );
    const operatorEmailParameter = new cdk.CfnParameter(this, 'OperatorEmail', {
      type: 'String',
      description: 'Email address for operational alerts and notifications.',
      allowedPattern: '.+@.+\\..+',
    });
    const deploymentStageParameter = new cdk.CfnParameter(
      this,
      'DeploymentStage',
      {
        type: 'String',
        description: 'The deployment stage (dev, staging, prod).',
        allowedValues: ['dev', 'staging', 'prod'],
        default: 'dev',
      }
    );

    const domainName = 'app.example.com';
    const certificateArn = certificateArnParameter.valueAsString;
    const operatorEmail = operatorEmailParameter.valueAsString;
    const deploymentStage = deploymentStageParameter.valueAsString;
    const isProd = deploymentStage === 'prod';
    const isProdStageCondition = new cdk.CfnCondition(
      this,
      'IsProdStageCondition',
      {
        expression: cdk.Fn.conditionEquals(deploymentStage, 'prod'),
      }
    );

    // --- Foundational Resources ---
    const alarmTopic = new sns.Topic(this, 'AlarmTopic');
    alarmTopic.addSubscription(
      new subscriptions.EmailSubscription(operatorEmail)
    );

    this.vpc = new ec2.Vpc(this, 'AtomicVpc', { maxAzs: 2, natGateways: 1 });
    NagSuppressions.addResourceSuppressions(
      this.vpc,
      [
        {
          id: 'AwsSolutions-VPC7',
          reason: 'Suppressing VPC flow logs for this workshop',
        },
      ],
      true
    );
    NagSuppressions.addResourceSuppressions(this.vpc, [
      {
        id: 'AwsSolutions-VPC7',
        reason: 'VPC Flow Logs are not enabled for this workshop',
      },
    ]);
    this.cluster = new ecs.Cluster(this, 'AtomicCluster', {
      vpc: this.vpc,
      enableFargateCapacityProviders: true,
    });
    NagSuppressions.addResourceSuppressions(
      this.cluster,
      [
        {
          id: 'AwsSolutions-ECS4',
          reason: 'Suppressing Container Insights for this workshop',
        },
      ],
      true
    );
    NagSuppressions.addResourceSuppressions(this.cluster, [
      {
        id: 'AwsSolutions-ECS4',
        reason: 'Container Insights are not enabled for this workshop',
      },
    ]);
    this.ecsTaskRole = new iam.Role(this, 'ECSTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });
    NagSuppressions.addResourceSuppressions(
      this.ecsTaskRole,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Suppressing IAM wildcard permissions for this workshop',
        },
      ],
      true
    );
    NagSuppressions.addResourceSuppressions(this.ecsTaskRole, [
      {
        id: 'AwsSolutions-IAM5',
        reason:
          'Allowing wildcard permissions for this workshop as per service requirements for S3 and ECR.',
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
    this.ecsTaskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['ecr:GetAuthorizationToken'],
        resources: ['*'],
      })
    );
    this.ecsTaskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'ecr:BatchCheckLayerAvailability',
          'ecr:GetDownloadUrlForLayer',
          'ecr:BatchGetImage',
        ],
        resources: Object.values(repositories).map(
          (repo) => repo.repositoryArn
        ),
      })
    );

    this.rdsSecurityGroup = new ec2.SecurityGroup(this, 'RdsSecurityGroup', {
      vpc: this.vpc,
      allowAllOutbound: true,
    });
    this.dbInstance = new rds.DatabaseInstance(this, 'AtomicPostgresDB', {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_15,
      }),
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.BURSTABLE3,
        ec2.InstanceSize.SMALL
      ),
      vpc: this.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [this.rdsSecurityGroup],
      credentials: rds.Credentials.fromGeneratedSecret(
        'PostgresAdminCredentials'
      ),
      databaseName: 'atomicdb',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      storageEncrypted: true,
      multiAz: true,
      backupRetention: isProd ? cdk.Duration.days(14) : cdk.Duration.days(1),
      deletionProtection: true,
    });
    this.dbSecret = this.dbInstance.secret!;
    NagSuppressions.addResourceSuppressions(
      this.dbInstance,
      [
        {
          id: 'AwsSolutions-SMG4',
          reason:
            'RDS managed secret rotation is not required for this workshop.',
        },
      ],
      true
    );

    const secrets = this.createSecrets();
    this.ecsTaskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['secretsmanager:GetSecretValue'],
        resources: [
          this.dbSecret.secretArn,
          ...Object.values(secrets).map((s) => s.secretArn),
        ],
      })
    );

    let certificate: acm.ICertificate;
    // const zone = route53.HostedZone.fromLookup(this, "HostedZone", {
    //   domainName,
    // });
    if (certificateArn && certificateArn !== '') {
      certificate = acm.Certificate.fromCertificateArn(
        this,
        'ImportedCertificate',
        certificateArn
      );
    } else {
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
        image: ecs.ContainerImage.fromRegistry(
          'registry.supertokens.io/supertokens/supertokens-postgresql:6.0'
        ),
        secrets: {
          POSTGRESQL_CONNECTION_URI: ecs.Secret.fromSecretsManager(
            secrets.supertokensDbConnStringSecret
          ),
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
    supertokensService.connections.allowTo(
      this.rdsSecurityGroup,
      ec2.Port.tcp(5432)
    );

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

  private createEcrRepository(repositoryName: string): ecr.Repository {
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

  private createSecrets(): { [id: string]: secretsmanager.ISecret } {
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

    const createdSecrets: { [id: string]: secretsmanager.ISecret } = {};
    for (const id of secretIds) {
      const secret = new secretsmanager.Secret(this, id, {
        secretName: `${this.stackName}/${id}`,
      });
      NagSuppressions.addResourceSuppressions(
        secret,
        [
          {
            id: 'AwsSolutions-SMG4',
            reason: 'Secret rotation is not required for this workshop.',
          },
        ],
        true
      );
      createdSecrets[id.charAt(0).toLowerCase() + id.slice(1) + 'Secret'] =
        secret;
    }
    return createdSecrets;
  }

  private createService(
    name: string,
    props: {
      taskDefProps: { cpu: number; memoryMiB: number; family: string };
      containerProps: ecs.ContainerDefinitionOptions;
      listener: elbv2.ApplicationListener;
      pathPattern: string;
      priority: number;
      targetPort: number;
      healthCheckPath: string;
    }
  ): ecs.FargateService {
    const sg = new ec2.SecurityGroup(this, `${name}SG`, {
      vpc: this.vpc,
      allowAllOutbound: true,
    });
    sg.connections.allowFrom(
      this.albSecurityGroup,
      ec2.Port.tcp(props.targetPort)
    );

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

    const targetGroup = new elbv2.ApplicationTargetGroup(
      this,
      `${name}TargetGroup`,
      {
        vpc: this.vpc,
        port: props.targetPort,
        protocol: elbv2.ApplicationProtocol.HTTP,
        targets: [service],
        healthCheck: { path: props.healthCheckPath },
      }
    );

    props.listener.addAction(name, {
      priority: props.priority,
      conditions: [elbv2.ListenerCondition.pathPatterns([props.pathPattern])],
      action: elbv2.ListenerAction.forward([targetGroup]),
    });

    return service;
  }
}
