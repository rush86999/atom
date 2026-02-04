import { EventEmitter } from "events";
import { Logger } from "../utils/logger";
import { IntegrationCapability, IntegrationState } from "./MultiIntegrationWorkflowEngine";

/**
 * Integration Registry Service
 * 
 * Central registry for managing all integrations, their capabilities,
 * connections, and lifecycle management.
 */

export interface IntegrationMetadata {
  id: string;
  name: string;
  displayName: string;
  description: string;
  category: 'communication' | 'productivity' | 'development' | 'business' | 'data' | 'monitoring' | 'security';
  version: string;
  author: string;
  documentation?: string;
  icon: string;
  color: string;
  tags: string[];
  supportedFeatures: string[];
  pricing?: {
    model: 'free' | 'tiered' | 'usage' | 'enterprise';
    limits?: Record<string, any>;
  };
  dependencies?: string[];
  systemRequirements?: Record<string, any>;
}

export interface IntegrationConfiguration {
  integrationId: string;
  userId: string;
  isActive: boolean;
  settings: Record<string, any>;
  credentials: {
    type: 'oauth' | 'api_key' | 'basic' | 'certificate' | 'none';
    data: Record<string, any>;
    encrypted: boolean;
    lastValidated?: Date;
    expiresAt?: Date;
  };
  permissions: string[];
  rateLimits?: {
    requestsPerSecond: number;
    requestsPerHour: number;
    requestsPerDay: number;
    currentUsage?: {
      requestsToday: number;
      requestsThisHour: number;
      lastReset: Date;
    };
  };
  webhooks?: {
    id: string;
    url: string;
    events: string[];
    secret?: string;
    isActive: boolean;
  }[];
  createdAt: Date;
  updatedAt: Date;
  lastUsed?: Date;
}

export interface IntegrationConnection {
  id: string;
  integrationId: string;
  userId: string;
  status: 'connected' | 'disconnected' | 'error' | 'connecting' | 'reconnecting';
  connectionDetails: {
    endpoint?: string;
    version?: string;
    region?: string;
    environment?: string;
  };
  health: {
    isHealthy: boolean;
    lastCheck: Date;
    responseTime: number;
    uptime: number;
    errorRate: number;
    lastError?: string;
  };
  metrics: {
    totalRequests: number;
    successfulRequests: number;
    failedRequests: number;
    averageResponseTime: number;
    dataTransferred: number;
  };
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface IntegrationEvent {
  id: string;
  integrationId: string;
  type: string;
  data: Record<string, any>;
  timestamp: Date;
  userId?: string;
  correlationId?: string;
  processed: boolean;
  retries: number;
}

export interface IntegrationHealthCheck {
  integrationId: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  checks: Array<{
    name: string;
    status: 'pass' | 'fail' | 'warn';
    message?: string;
    responseTime?: number;
    details?: Record<string, any>;
  }>;
  overallScore: number; // 0-100
  timestamp: Date;
  recommendations?: string[];
}

export interface IntegrationAnalytics {
  integrationId: string;
  timeRange: {
    start: Date;
    end: Date;
  };
  usage: {
    totalRequests: number;
    uniqueUsers: number;
    activeConnections: number;
    dataTransferred: number;
    errors: number;
  };
  performance: {
    averageResponseTime: number;
    p95ResponseTime: number;
    p99ResponseTime: number;
    throughput: number; // requests per minute
    availability: number; // percentage
  };
  costs: {
    total: number;
    breakdown: {
      requests: number;
      data: number;
      storage: number;
      compute: number;
    };
    trends: Array<{
      date: string;
      cost: number;
    }>;
  };
  errors: Array<{
    type: string;
    count: number;
    lastOccurred: Date;
    sampleError: string;
  }>;
}

export interface IntegrationTemplate {
  id: string;
  name: string;
  description: string;
  integrationId: string;
  category: 'automation' | 'monitoring' | 'data_sync' | 'notification' | 'analytics';
  complexity: 'basic' | 'intermediate' | 'advanced';
  estimatedTime: number; // minutes
  steps: Array<{
    id: string;
    name: string;
    type: 'configuration' | 'authentication' | 'validation' | 'testing';
    description: string;
    parameters: Record<string, any>;
    required: boolean;
  }>;
  prerequisites: string[];
  tags: string[];
  popularity: number;
  isRecommended: boolean;
}

export class IntegrationRegistry extends EventEmitter {
  private logger: Logger;
  private integrations: Map<string, IntegrationMetadata>;
  private configurations: Map<string, IntegrationConfiguration>; // key: integrationId:userId
  private connections: Map<string, IntegrationConnection>;
  private events: IntegrationEvent[];
  private healthChecks: Map<string, IntegrationHealthCheck>;
  private analytics: Map<string, IntegrationAnalytics>;
  private templates: Map<string, IntegrationTemplate>;

  constructor() {
    super();
    this.logger = new Logger("IntegrationRegistry");
    this.integrations = new Map();
    this.configurations = new Map();
    this.connections = new Map();
    this.events = [];
    this.healthChecks = new Map();
    this.analytics = new Map();
    this.templates = new Map();

    this.loadBuiltinIntegrations();
    this.loadTemplates();
    this.startHealthMonitoring();
    this.startEventProcessing();

    this.logger.info("Integration Registry initialized");
  }

  private loadBuiltinIntegrations(): void {
    const builtinIntegrations: IntegrationMetadata[] = [
      // Communication Platforms
      {
        id: 'slack',
        name: 'slack',
        displayName: 'Slack',
        description: 'Team communication and collaboration platform',
        category: 'communication',
        version: '2.0.0',
        author: 'ATOM Team',
        documentation: 'https://api.slack.com',
        icon: '💬',
        color: '#4A154B',
        tags: ['chat', 'team', 'communication', 'messaging'],
        supportedFeatures: [
          'real-time_messaging',
          'channels',
          'webhooks',
          'slash_commands',
          'file_sharing',
          'video_calls',
          'workflow_builder'
        ],
        pricing: {
          model: 'tiered',
          limits: {
            free_requests_per_minute: 20,
            paid_requests_per_minute: 300
          }
        }
      },
      {
        id: 'microsoft_teams',
        name: 'microsoft_teams',
        displayName: 'Microsoft Teams',
        description: 'Unified communication and collaboration platform',
        category: 'communication',
        version: '1.0.0',
        author: 'ATOM Team',
        documentation: 'https://docs.microsoft.com/en-us/graph/api/teams-overview',
        icon: '👥',
        color: '#6264A7',
        tags: ['chat', 'video', 'collaboration', 'microsoft'],
        supportedFeatures: [
          'chat_messages',
          'channels',
          'meetings',
          'file_sharing',
          'calls',
          'app_integration'
        ],
        pricing: {
          model: 'tiered'
        }
      },
      {
        id: 'discord',
        name: 'discord',
        displayName: 'Discord',
        description: 'Voice, video, and text communication for communities',
        category: 'communication',
        version: '2.0.0',
        author: 'ATOM Team',
        documentation: 'https://discord.com/developers/docs/intro',
        icon: '🎮',
        color: '#5865F2',
        tags: ['gaming', 'community', 'voice', 'chat'],
        supportedFeatures: [
          'guild_management',
          'channel_management',
          'message_sending',
          'voice_channels',
          'webhooks',
          'bot_commands'
        ],
        pricing: {
          model: 'free'
        }
      },

      // Productivity & Collaboration
      {
        id: 'notion',
        name: 'notion',
        displayName: 'Notion',
        description: 'All-in-one workspace for notes, tasks, and databases',
        category: 'productivity',
        version: '2022.0.0',
        author: 'ATOM Team',
        documentation: 'https://developers.notion.com/docs',
        icon: '📝',
        color: '#000000',
        tags: ['notes', 'database', 'tasks', 'wiki', 'collaboration'],
        supportedFeatures: [
          'pages',
          'databases',
          'blocks',
          'search',
          'comments',
          'sharing'
        ],
        pricing: {
          model: 'usage',
          limits: {
            api_requests_per_minute: 3
          }
        }
      },
      {
        id: 'google_drive',
        name: 'google_drive',
        displayName: 'Google Drive',
        description: 'Cloud storage and file collaboration platform',
        category: 'productivity',
        version: 'v3',
        author: 'ATOM Team',
        documentation: 'https://developers.google.com/drive/api/v3/about-sdk',
        icon: '📁',
        color: '#4285F4',
        tags: ['storage', 'files', 'collaboration', 'google'],
        supportedFeatures: [
          'file_upload',
          'file_download',
          'folder_management',
          'sharing',
          'search',
          'real_time_sync'
        ],
        pricing: {
          model: 'tiered',
          limits: {
            free_storage_gb: 15,
            api_requests_per_day: 1000000000
          }
        }
      },
      {
        id: 'onedrive',
        name: 'onedrive',
        displayName: 'OneDrive',
        description: 'Microsoft cloud storage and file sharing',
        category: 'productivity',
        version: 'v2.0',
        author: 'ATOM Team',
        documentation: 'https://docs.microsoft.com/en-us/graph/api/resources/onedrive',
        icon: '☁️',
        color: '#0078D4',
        tags: ['storage', 'files', 'microsoft', 'office'],
        supportedFeatures: [
          'file_management',
          'sharing',
          'sync',
          'versioning',
          'collaboration'
        ],
        pricing: {
          model: 'tiered'
        }
      },

      // Development Tools
      {
        id: 'github',
        name: 'github',
        displayName: 'GitHub',
        description: 'Code hosting and collaboration platform',
        category: 'development',
        version: 'v4',
        author: 'ATOM Team',
        documentation: 'https://docs.github.com/en/rest',
        icon: '🐙',
        color: '#181717',
        tags: ['git', 'code', 'repository', 'cicd', 'collaboration'],
        supportedFeatures: [
          'repositories',
          'issues',
          'pull_requests',
          'actions',
          'webhooks',
          'api_access'
        ],
        pricing: {
          model: 'tiered',
          limits: {
            api_requests_per_hour: 5000,
            private_repositories: 0
          }
        }
      },
      {
        id: 'jira',
        name: 'jira',
        displayName: 'Jira',
        description: 'Issue tracking and project management',
        category: 'development',
        version: '3.0.0',
        author: 'ATOM Team',
        documentation: 'https://developer.atlassian.com/cloud/jira/platform/rest/v3/',
        icon: '🎯',
        color: '#0052CC',
        tags: ['issues', 'project_management', 'agile', 'development'],
        supportedFeatures: [
          'issue_tracking',
          'project_management',
          'agile_boards',
          'time_tracking',
          'reporting',
          'workflows'
        ],
        pricing: {
          model: 'tiered'
        }
      },
      {
        id: 'gitlab',
        name: 'gitlab',
        displayName: 'GitLab',
        description: 'Complete DevOps platform',
        category: 'development',
        version: 'v4',
        author: 'ATOM Team',
        documentation: 'https://docs.gitlab.com/ee/api/',
        icon: '🦊',
        color: '#FC6D26',
        tags: ['git', 'cicd', 'devops', 'repository'],
        supportedFeatures: [
          'repositories',
          'ci_cd',
          'issues',
          'merge_requests',
          'wiki',
          'container_registry'
        ],
        pricing: {
          model: 'tiered'
        }
      },

      // Business & CRM
      {
        id: 'salesforce',
        name: 'salesforce',
        displayName: 'Salesforce',
        description: 'Customer relationship management platform',
        category: 'business',
        version: 'v56.0',
        author: 'ATOM Team',
        documentation: 'https://developer.salesforce.com/docs/api',
        icon: '☁️',
        color: '#00A1E0',
        tags: ['crm', 'sales', 'customer', 'business'],
        supportedFeatures: [
          'accounts',
          'contacts',
          'opportunities',
          'leads',
          'reports',
          'automation'
        ],
        pricing: {
          model: 'tiered'
        }
      },
      {
        id: 'hubspot',
        name: 'hubspot',
        displayName: 'HubSpot',
        description: 'Inbound marketing, sales, and service platform',
        category: 'business',
        version: 'v3',
        author: 'ATOM Team',
        documentation: 'https://developers.hubspot.com/docs/api/overview',
        icon: '🎯',
        color: '#FF7A59',
        tags: ['marketing', 'sales', 'crm', 'service'],
        supportedFeatures: [
          'contacts',
          'deals',
          'marketing_automation',
          'email_marketing',
          'analytics',
          'chat_bots'
        ],
        pricing: {
          model: 'tiered'
        }
      },
      {
        id: 'stripe',
        name: 'stripe',
        displayName: 'Stripe',
        description: 'Payment processing platform',
        category: 'business',
        version: '2022-11-15',
        author: 'ATOM Team',
        documentation: 'https://stripe.com/docs/api',
        icon: '💳',
        color: '#635BFF',
        tags: ['payments', 'billing', 'fintech', 'ecommerce'],
        supportedFeatures: [
          'payments',
          'subscriptions',
          'invoicing',
          'fraud_detection',
          'financial_reporting'
        ],
        pricing: {
          model: 'usage'
        }
      },

      // Data & Analytics
      {
        id: 'aws',
        name: 'aws',
        displayName: 'Amazon Web Services',
        description: 'Cloud computing platform',
        category: 'data',
        version: 'v1.0',
        author: 'ATOM Team',
        documentation: 'https://aws.amazon.com/documentation/',
        icon: '☁️',
        color: '#FF9900',
        tags: ['cloud', 'computing', 'storage', 'analytics'],
        supportedFeatures: [
          'ec2',
          's3',
          'lambda',
          'rds',
          'cloudwatch',
          'iam'
        ],
        pricing: {
          model: 'usage'
        }
      },
      {
        id: 'tableau',
        name: 'tableau',
        displayName: 'Tableau',
        description: 'Business intelligence and data visualization',
        category: 'data',
        version: '3.15',
        author: 'ATOM Team',
        documentation: 'https://help.tableau.com/current/api/rest_api/en-us/help.htm',
        icon: '📊',
        color: '#E97627',
        tags: ['analytics', 'visualization', 'business_intelligence', 'dashboard'],
        supportedFeatures: [
          'data_visualization',
          'dashboards',
          'data_sources',
          'embed_views',
          'analytics'
        ],
        pricing: {
          model: 'tiered'
        }
      }
    ];

    for (const integration of builtinIntegrations) {
      this.integrations.set(integration.id, integration);
    }

    this.logger.info(`Loaded ${builtinIntegrations.length} builtin integrations`);
  }

  private loadTemplates(): void {
    const templates: IntegrationTemplate[] = [
      {
        id: 'slack-bot-setup',
        name: 'Slack Bot Setup',
        description: 'Configure a Slack bot with basic permissions',
        integrationId: 'slack',
        category: 'automation',
        complexity: 'basic',
        estimatedTime: 10,
        steps: [
          {
            id: 'create-app',
            name: 'Create Slack App',
            type: 'configuration',
            description: 'Create a new Slack app in your workspace',
            parameters: {
              appName: 'string',
              workspace: 'string'
            },
            required: true
          },
          {
            id: 'configure-permissions',
            name: 'Configure Bot Permissions',
            type: 'configuration',
            description: 'Set up required bot token scopes',
            parameters: {
              scopes: ['channels:read', 'chat:write', 'users:read']
            },
            required: true
          },
          {
            id: 'install-bot',
            name: 'Install Bot to Workspace',
            type: 'authentication',
            description: 'Install the bot and get access tokens',
            parameters: {},
            required: true
          }
        ],
        prerequisites: ['Slack workspace admin access'],
        tags: ['slack', 'bot', 'basic'],
        popularity: 95,
        isRecommended: true
      },
      {
        id: 'github-webhook-setup',
        name: 'GitHub Repository Webhook',
        description: 'Set up webhooks for GitHub repository events',
        integrationId: 'github',
        category: 'automation',
        complexity: 'intermediate',
        estimatedTime: 15,
        steps: [
          {
            id: 'repo-access',
            name: 'Repository Access',
            type: 'authentication',
            description: 'Configure access to target repository',
            parameters: {
              repository: 'string',
              permissions: 'string'
            },
            required: true
          },
          {
            id: 'create-webhook',
            name: 'Create Webhook',
            type: 'configuration',
            description: 'Create webhook for repository events',
            parameters: {
              events: ['push', 'pull_request', 'issues'],
              url: 'string'
            },
            required: true
          },
          {
            id: 'test-webhook',
            name: 'Test Webhook',
            type: 'testing',
            description: 'Test webhook delivery and event processing',
            parameters: {},
            required: true
          }
        ],
        prerequisites: ['GitHub repository admin access'],
        tags: ['github', 'webhook', 'automation'],
        popularity: 87,
        isRecommended: false
      }
    ];

    for (const template of templates) {
      this.templates.set(template.id, template);
    }

    this.logger.info(`Loaded ${templates.length} integration templates`);
  }

  // Integration Registration
  async registerIntegration(metadata: IntegrationMetadata): Promise<void> {
    // Validate integration metadata
    this.validateIntegrationMetadata(metadata);

    this.integrations.set(metadata.id, metadata);
    this.logger.info(`Integration registered: ${metadata.displayName} (${metadata.id})`);
    this.emit("integration-registered", { integrationId: metadata.id, name: metadata.displayName });
  }

  async unregisterIntegration(integrationId: string): Promise<void> {
    const integration = this.integrations.get(integrationId);
    if (integration) {
      this.integrations.delete(integrationId);
      
      // Clean up related data
      this.cleanupIntegrationData(integrationId);
      
      this.logger.info(`Integration unregistered: ${integration.displayName} (${integrationId})`);
      this.emit("integration-unregistered", { integrationId, name: integration.displayName });
    }
  }

  // Configuration Management
  async createConfiguration(
    integrationId: string,
    userId: string,
    settings: Record<string, any>,
    credentials: IntegrationConfiguration['credentials']
  ): Promise<string> {
    const integration = this.integrations.get(integrationId);
    if (!integration) {
      throw new Error(`Integration ${integrationId} not found`);
    }

    const configKey = `${integrationId}:${userId}`;
    
    // Check if configuration already exists
    if (this.configurations.has(configKey)) {
      throw new Error(`Configuration for ${integrationId} and user ${userId} already exists`);
    }

    const configuration: IntegrationConfiguration = {
      integrationId,
      userId,
      isActive: false,
      settings,
      credentials,
      permissions: [],
      createdAt: new Date(),
      updatedAt: new Date()
    };

    this.configurations.set(configKey, configuration);
    this.logger.info(`Configuration created for ${integration.displayName} (${configKey})`);
    this.emit("configuration-created", { integrationId, userId, configKey });

    return configKey;
  }

  async updateConfiguration(
    integrationId: string,
    userId: string,
    updates: Partial<IntegrationConfiguration>
  ): Promise<boolean> {
    const configKey = `${integrationId}:${userId}`;
    const configuration = this.configurations.get(configKey);

    if (!configuration) {
      return false;
    }

    Object.assign(configuration, updates);
    configuration.updatedAt = new Date();

    this.configurations.set(configKey, configuration);
    this.logger.info(`Configuration updated for ${configKey}`);
    this.emit("configuration-updated", { configKey });

    return true;
  }

  async activateConfiguration(integrationId: string, userId: string): Promise<boolean> {
    const configKey = `${integrationId}:${userId}`;
    const configuration = this.configurations.get(configKey);

    if (!configuration) {
      return false;
    }

    // Validate credentials
    const isValid = await this.validateCredentials(integrationId, configuration.credentials);
    if (!isValid) {
      throw new Error('Invalid credentials');
    }

    configuration.isActive = true;
    configuration.updatedAt = new Date();

    // Create connection
    await this.createConnection(integrationId, userId);

    this.configurations.set(configKey, configuration);
    this.logger.info(`Configuration activated for ${configKey}`);
    this.emit("configuration-activated", { configKey });

    return true;
  }

  async deactivateConfiguration(integrationId: string, userId: string): Promise<boolean> {
    const configKey = `${integrationId}:${userId}`;
    const configuration = this.configurations.get(configKey);

    if (!configuration) {
      return false;
    }

    configuration.isActive = false;
    configuration.updatedAt = new Date();

    // Close connection
    await this.closeConnection(integrationId, userId);

    this.configurations.set(configKey, configuration);
    this.logger.info(`Configuration deactivated for ${configKey}`);
    this.emit("configuration-deactivated", { configKey });

    return true;
  }

  // Connection Management
  private async createConnection(integrationId: string, userId: string): Promise<string> {
    const connectionId = `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const connection: IntegrationConnection = {
      id: connectionId,
      integrationId,
      userId,
      status: 'connecting',
      connectionDetails: {},
      health: {
        isHealthy: false,
        lastCheck: new Date(),
        responseTime: 0,
        uptime: 0,
        errorRate: 0
      },
      metrics: {
        totalRequests: 0,
        successfulRequests: 0,
        failedRequests: 0,
        averageResponseTime: 0,
        dataTransferred: 0
      },
      isActive: true,
      createdAt: new Date(),
      updatedAt: new Date()
    };

    this.connections.set(connectionId, connection);

    // Attempt to establish connection
    try {
      await this.establishConnection(connection);
      connection.status = 'connected';
      connection.health.isHealthy = true;
      connection.health.lastCheck = new Date();
    } catch (error) {
      connection.status = 'error';
      connection.health.lastError = error.message;
      this.logger.error(`Failed to establish connection for ${connectionId}:`, error);
    }

    connection.updatedAt = new Date();
    this.emit("connection-created", { connectionId, integrationId, userId });

    return connectionId;
  }

  private async establishConnection(connection: IntegrationConnection): Promise<void> {
    const integration = this.integrations.get(connection.integrationId);
    if (!integration) {
      throw new Error(`Integration ${connection.integrationId} not found`);
    }

    // Simulate connection establishment
    const startTime = Date.now();
    
    // This would integrate with the actual integration
    await new Promise(resolve => setTimeout(resolve, 100 + Math.random() * 400));
    
    const endTime = Date.now();
    connection.health.responseTime = endTime - startTime;
    
    // Set connection details
    connection.connectionDetails = {
      endpoint: `https://api.${integration.id}.com`,
      version: integration.version,
      environment: 'production'
    };

    this.logger.info(`Connection established for ${connection.id}`);
  }

  private async closeConnection(integrationId: string, userId: string): Promise<void> {
    const connections = Array.from(this.connections.values())
      .filter(conn => conn.integrationId === integrationId && conn.userId === userId);

    for (const connection of connections) {
      connection.status = 'disconnected';
      connection.isActive = false;
      connection.updatedAt = new Date();
      
      this.logger.info(`Connection closed: ${connection.id}`);
      this.emit("connection-closed", { connectionId: connection.id });
    }
  }

  // Health Monitoring
  private startHealthMonitoring(): void {
    setInterval(async () => {
      const connections = Array.from(this.connections.values())
        .filter(conn => conn.isActive && conn.status === 'connected');

      for (const connection of connections) {
        await this.performHealthCheck(connection);
      }
    }, 60000); // Check every minute
  }

  private async performHealthCheck(connection: IntegrationConnection): Promise<void> {
    const startTime = Date.now();
    
    try {
      // Simulate health check
      await new Promise(resolve => setTimeout(resolve, 50 + Math.random() * 200));
      
      const endTime = Date.now();
      const responseTime = endTime - startTime;
      
      // Update health metrics
      connection.health.lastCheck = new Date();
      connection.health.responseTime = responseTime;
      connection.health.uptime += 60; // seconds
      connection.metrics.totalRequests++;
      connection.metrics.successfulRequests++;
      
      // Update average response time
      const totalRequests = connection.metrics.totalRequests;
      connection.metrics.averageResponseTime = 
        (connection.metrics.averageResponseTime * (totalRequests - 1) + responseTime) / totalRequests;
      
      // Determine health status
      const isHealthy = responseTime < 5000 && connection.health.errorRate < 0.1;
      const wasHealthy = connection.health.isHealthy;
      
      connection.health.isHealthy = isHealthy;
      
      if (wasHealthy !== isHealthy) {
        this.emit("connection-health-changed", { 
          connectionId: connection.id,
          isHealthy,
          wasHealthy
        });
      }
      
    } catch (error) {
      connection.health.lastError = error.message;
      connection.health.isHealthy = false;
      connection.metrics.totalRequests++;
      connection.metrics.failedRequests++;
      
      const errorRate = connection.metrics.failedRequests / connection.metrics.totalRequests;
      connection.health.errorRate = errorRate;
      
      this.logger.warn(`Health check failed for connection ${connection.id}: ${error.message}`);
    }
    
    connection.updatedAt = new Date();
  }

  // Event Processing
  private startEventProcessing(): void {
    setInterval(async () => {
      const unprocessedEvents = this.events.filter(event => !event.processed);
      
      for (const event of unprocessedEvents) {
        try {
          await this.processEvent(event);
          event.processed = true;
        } catch (error) {
          this.logger.error(`Failed to process event ${event.id}:`, error);
          
          if (event.retries < 3) {
            event.retries++;
            event.processed = false;
          } else {
            event.processed = true; // Mark as processed to avoid infinite retries
          }
        }
      }
      
      // Clean up old processed events
      const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000); // 24 hours ago
      this.events = this.events.filter(event => 
        !event.processed || event.timestamp > cutoff
      );
      
    }, 5000); // Process every 5 seconds
  }

  private async processEvent(event: IntegrationEvent): Promise<void> {
    // Process integration events
    this.logger.info(`Processing event ${event.id} from ${event.integrationId}`);
    
    // Emit event for workflow engine to handle
    this.emit("integration-event", event);
  }

  // Utility Methods
  private validateIntegrationMetadata(metadata: IntegrationMetadata): void {
    const required = ['id', 'name', 'displayName', 'description', 'category', 'version', 'author'];
    
    for (const field of required) {
      if (!metadata[field]) {
        throw new Error(`Missing required field: ${field}`);
      }
    }
    
    if (!['communication', 'productivity', 'development', 'business', 'data', 'monitoring', 'security'].includes(metadata.category)) {
      throw new Error(`Invalid category: ${metadata.category}`);
    }
  }

  private async validateCredentials(integrationId: string, credentials: IntegrationConfiguration['credentials']): Promise<boolean> {
    // Simulate credential validation
    await new Promise(resolve => setTimeout(resolve, 100 + Math.random() * 300));
    
    // In a real implementation, this would validate with the integration
    return Math.random() > 0.1; // 90% success rate for simulation
  }

  private cleanupIntegrationData(integrationId: string): void {
    // Clean up configurations
    const configsToDelete = Array.from(this.configurations.keys())
      .filter(key => key.startsWith(`${integrationId}:`));
    
    for (const configKey of configsToDelete) {
      this.configurations.delete(configKey);
    }
    
    // Clean up connections
    const connectionsToDelete = Array.from(this.connections.values())
      .filter(conn => conn.integrationId === integrationId);
    
    for (const connection of connectionsToDelete) {
      this.connections.delete(connection.id);
    }
    
    // Clean up events
    this.events = this.events.filter(event => event.integrationId !== integrationId);
    
    // Clean up health checks
    this.healthChecks.delete(integrationId);
    
    // Clean up analytics
    this.analytics.delete(integrationId);
  }

  // Public API Methods
  async getIntegration(integrationId: string): Promise<IntegrationMetadata | null> {
    return this.integrations.get(integrationId) || null;
  }

  async listIntegrations(category?: string): Promise<IntegrationMetadata[]> {
    let integrations = Array.from(this.integrations.values());
    
    if (category) {
      integrations = integrations.filter(integration => integration.category === category);
    }
    
    return integrations.sort((a, b) => a.displayName.localeCompare(b.displayName));
  }

  async getConfiguration(integrationId: string, userId: string): Promise<IntegrationConfiguration | null> {
    const configKey = `${integrationId}:${userId}`;
    return this.configurations.get(configKey) || null;
  }

  async listUserConfigurations(userId: string): Promise<IntegrationConfiguration[]> {
    return Array.from(this.configurations.values())
      .filter(config => config.userId === userId)
      .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime());
  }

  async getConnection(connectionId: string): Promise<IntegrationConnection | null> {
    return this.connections.get(connectionId) || null;
  }

  async listConnections(integrationId?: string, userId?: string): Promise<IntegrationConnection[]> {
    let connections = Array.from(this.connections.values());
    
    if (integrationId) {
      connections = connections.filter(conn => conn.integrationId === integrationId);
    }
    
    if (userId) {
      connections = connections.filter(conn => conn.userId === userId);
    }
    
    return connections.sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime());
  }

  async getTemplate(templateId: string): Promise<IntegrationTemplate | null> {
    return this.templates.get(templateId) || null;
  }

  async listTemplates(integrationId?: string, category?: string): Promise<IntegrationTemplate[]> {
    let templates = Array.from(this.templates.values());
    
    if (integrationId) {
      templates = templates.filter(template => template.integrationId === integrationId);
    }
    
    if (category) {
      templates = templates.filter(template => template.category === category);
    }
    
    return templates.sort((a, b) => b.popularity - a.popularity);
  }

  async getIntegrationHealth(integrationId: string, userId?: string): Promise<IntegrationHealthCheck | null> {
    const connections = Array.from(this.connections.values())
      .filter(conn => conn.integrationId === integrationId && (!userId || conn.userId === userId));
    
    if (connections.length === 0) {
      return null;
    }
    
    // Aggregate health across all connections
    const totalConnections = connections.length;
    const healthyConnections = connections.filter(conn => conn.health.isHealthy).length;
    const overallScore = Math.round((healthyConnections / totalConnections) * 100);
    
    const checks = connections.map(conn => ({
      name: `Connection ${conn.id}`,
      status: conn.health.isHealthy ? 'pass' : 'fail',
      message: conn.health.lastError || 'Connection healthy',
      responseTime: conn.health.responseTime,
      details: {
        uptime: conn.health.uptime,
        errorRate: conn.health.errorRate
      }
    }));
    
    const healthCheck: IntegrationHealthCheck = {
      integrationId,
      status: overallScore >= 80 ? 'healthy' : overallScore >= 50 ? 'degraded' : 'unhealthy',
      checks,
      overallScore,
      timestamp: new Date()
    };
    
    // Generate recommendations
    if (overallScore < 80) {
      healthCheck.recommendations = [
        'Check network connectivity',
        'Verify credentials are valid',
        'Review integration rate limits'
      ];
    }
    
    this.healthChecks.set(integrationId, healthCheck);
    return healthCheck;
  }

  async getIntegrationAnalytics(integrationId: string, timeRange: { start: Date; end: Date }): Promise<IntegrationAnalytics | null> {
    const connections = Array.from(this.connections.values())
      .filter(conn => conn.integrationId === integrationId);
    
    if (connections.length === 0) {
      return null;
    }
    
    // Aggregate analytics across connections
    const totalRequests = connections.reduce((sum, conn) => sum + conn.metrics.totalRequests, 0);
    const successfulRequests = connections.reduce((sum, conn) => sum + conn.metrics.successfulRequests, 0);
    const failedRequests = connections.reduce((sum, conn) => sum + conn.metrics.failedRequests, 0);
    const averageResponseTime = connections.reduce((sum, conn) => sum + conn.metrics.averageResponseTime, 0) / connections.length;
    const dataTransferred = connections.reduce((sum, conn) => sum + conn.metrics.dataTransferred, 0);
    
    const analytics: IntegrationAnalytics = {
      integrationId,
      timeRange,
      usage: {
        totalRequests,
        uniqueUsers: new Set(connections.map(conn => conn.userId)).size,
        activeConnections: connections.filter(conn => conn.isActive).length,
        dataTransferred,
        errors: failedRequests
      },
      performance: {
        averageResponseTime,
        p95ResponseTime: averageResponseTime * 1.5, // Simplified calculation
        p99ResponseTime: averageResponseTime * 2, // Simplified calculation
        throughput: totalRequests / ((timeRange.end.getTime() - timeRange.start.getTime()) / (1000 * 60)), // requests per minute
        availability: totalRequests > 0 ? successfulRequests / totalRequests : 0
      },
      costs: {
        total: 0, // Would calculate actual costs
        breakdown: {
          requests: 0,
          data: 0,
          storage: 0,
          compute: 0
        },
        trends: []
      },
      errors: []
    };
    
    this.analytics.set(integrationId, analytics);
    return analytics;
  }

  async recordEvent(event: Omit<IntegrationEvent, 'id' | 'processed' | 'retries'>): Promise<string> {
    const eventId = `event_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const fullEvent: IntegrationEvent = {
      ...event,
      id: eventId,
      processed: false,
      retries: 0
    };
    
    this.events.push(fullEvent);
    this.emit("event-recorded", { eventId });
    
    return eventId;
  }

  getSystemHealth(): {
    totalIntegrations: number;
    activeConnections: number;
    healthyConnections: number;
    totalEvents: number;
    unprocessedEvents: number;
  } {
    const connections = Array.from(this.connections.values());
    const activeConnections = connections.filter(conn => conn.isActive).length;
    const healthyConnections = connections.filter(conn => conn.health.isHealthy).length;
    const unprocessedEvents = this.events.filter(event => !event.processed).length;

    return {
      totalIntegrations: this.integrations.size,
      activeConnections,
      healthyConnections,
      totalEvents: this.events.length,
      unprocessedEvents
    };
  }
}