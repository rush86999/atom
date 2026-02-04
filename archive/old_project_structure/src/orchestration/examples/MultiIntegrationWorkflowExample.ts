/**
 * Multi-Integration Workflow Orchestration Engine Example
 * 
 * This example demonstrates how to set up and use the comprehensive
 * multi-integration workflow orchestration system.
 */

import { OrchestrationManager } from './OrchestrationManager';
import { WorkflowDefinition, WorkflowTrigger, WorkflowStep } from './MultiIntegrationWorkflowEngine';

async function demonstrateMultiIntegrationOrchestration() {
  console.log('🚀 Starting Multi-Integration Workflow Orchestration Demo...\n');

  // Initialize the orchestration manager
  const orchestrationManager = new OrchestrationManager({
    maxConcurrentExecutions: 10,
    maxStepsPerExecution: 50,
    defaultTimeout: 300000,
    enableAutoOptimization: true,
    enableMetricsCollection: true,
    enableAIOptimizations: true,
    enablePredictiveScaling: true,
  });

  try {
    // Set up event listeners
    setupEventListeners(orchestrationManager);

    // Step 1: Configure integrations
    console.log('📡 Step 1: Configuring Integrations');
    await setupIntegrations(orchestrationManager);

    // Step 2: Create workflows
    console.log('\n🔄 Step 2: Creating Workflows');
    const workflows = await createWorkflows(orchestrationManager);

    // Step 3: Execute workflows
    console.log('\n⚡ Step 3: Executing Workflows');
    const executions = await executeWorkflows(orchestrationManager, workflows);

    // Step 4: Monitor and optimize
    console.log('\n📊 Step 4: Monitoring and Optimization');
    await monitorAndOptimize(orchestrationManager, executions);

    // Step 5: System metrics and health
    console.log('\n🏥 Step 5: System Health and Metrics');
    await showSystemHealth(orchestrationManager);

    // Keep the demo running for a bit to see background operations
    console.log('\n⏳ Running background operations for 30 seconds...');
    await new Promise(resolve => setTimeout(resolve, 30000));

  } catch (error) {
    console.error('❌ Demo failed:', error);
  } finally {
    // Cleanup
    console.log('\n🧹 Shutting down orchestration manager...');
    await orchestrationManager.shutdown();
  }

  console.log('\n✅ Demo completed!');
}

function setupEventListeners(manager: OrchestrationManager) {
  manager.on('workflow-created', (data) => {
    console.log(`📝 Workflow created: ${data.name} (${data.workflowId})`);
  });

  manager.on('workflow-execution-triggered', (data) => {
    console.log(`🚀 Workflow execution triggered: ${data.workflowId} -> ${data.executionId}`);
  });

  manager.on('workflow-completed', (data) => {
    console.log(`✅ Workflow completed: ${data.executionId}`);
  });

  manager.on('workflow-failed', (data) => {
    console.log(`❌ Workflow failed: ${data.executionId} - ${data.error?.message || 'Unknown error'}`);
  });

  manager.on('integration-activated', (data) => {
    console.log(`🔗 Integration activated: ${data.integrationId} for user ${data.userId}`);
  });

  manager.on('alert-created', (data) => {
    console.log(`🚨 Alert created: [${data.alert.type.toUpperCase()}] ${data.alert.title}`);
  });

  manager.on('integration-health-changed', (data) => {
    console.log(`💓 Integration health changed: ${data.integrationId} is now ${data.isHealthy ? 'healthy' : 'unhealthy'}`);
  });

  manager.on('workflow-optimized', (data) => {
    console.log(`🎯 Workflow optimized: ${data.workflowId} (score: ${data.result.overallScore})`);
  });
}

async function setupIntegrations(manager: OrchestrationManager) {
  // Configure Slack integration
  console.log('  🔧 Configuring Slack integration...');
  await manager.configureIntegration(
    'slack',
    'user1',
    {
      workspace: 'atom-workspace',
      defaultChannel: '#general',
    },
    {
      type: 'oauth',
      data: {
        accessToken: 'xoxb-slack-token',
        refreshToken: 'refresh-token',
      },
      encrypted: true,
    }
  );

  // Activate Slack integration
  await manager.activateIntegration('slack', 'user1');

  // Configure Notion integration
  console.log('  🔧 Configuring Notion integration...');
  await manager.configureIntegration(
    'notion',
    'user1',
    {
      workspace: 'Atom Workspace',
      defaultDatabase: 'project-tasks',
    },
    {
      type: 'oauth',
      data: {
        accessToken: 'secret_notion-token',
        workspaceId: 'workspace-123',
      },
      encrypted: true,
    }
  );

  // Activate Notion integration
  await manager.activateIntegration('notion', 'user1');

  // Configure GitHub integration
  console.log('  🔧 Configuring GitHub integration...');
  await manager.configureIntegration(
    'github',
    'user1',
    {
      username: 'atom-user',
      defaultRepository: 'atom-automation',
    },
    {
      type: 'oauth',
      data: {
        accessToken: 'ghp_github-token',
        refreshToken: 'github-refresh',
      },
      encrypted: true,
    }
  );

  // Activate GitHub integration
  await manager.activateIntegration('github', 'user1');

  console.log('  ✅ All integrations configured and activated\n');
}

async function createWorkflows(manager: OrchestrationManager): Promise<string[]> {
  const workflows: string[] = [];

  // Workflow 1: Slack to Notion Sync
  console.log('  📝 Creating Slack to Notion sync workflow...');
  const slackToNotionWorkflow: WorkflowDefinition = {
    id: 'slack-notion-sync',
    name: 'Slack to Notion Message Sync',
    description: 'Sync important Slack messages to Notion database',
    version: '1.0.0',
    category: 'integration',
    steps: [
      {
        id: 'listen-slack',
        name: 'Listen to Slack Messages',
        type: 'integration_action',
        integrationId: 'slack',
        action: 'listen_messages',
        parameters: {
          channel: '#general',
          keywords: ['important', 'urgent', 'todo'],
        },
        dependsOn: [],
        retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
        timeout: 30000,
        metadata: {},
      },
      {
        id: 'filter-important',
        name: 'Filter Important Messages',
        type: 'condition',
        parameters: {
          condition: {
            field: 'message.importance',
            operator: 'gte',
            value: 0.7,
          },
        },
        dependsOn: ['listen-slack'],
        retryPolicy: { maxAttempts: 1, delay: 500, backoffMultiplier: 1 },
        timeout: 5000,
        metadata: {},
      },
      {
        id: 'transform-for-notion',
        name: 'Transform for Notion',
        type: 'data_transform',
        parameters: {
          transformType: 'map_fields',
          mapping: {
            'title': 'message.text',
            'content': 'message.content',
            'author': 'message.user.name',
            'timestamp': 'message.timestamp',
            'priority': 'message.importance',
          },
        },
        dependsOn: ['filter-important'],
        retryPolicy: { maxAttempts: 2, delay: 500, backoffMultiplier: 1.5 },
        timeout: 10000,
        metadata: {},
      },
      {
        id: 'create-notion-page',
        name: 'Create Notion Page',
        type: 'integration_action',
        integrationId: 'notion',
        action: 'create_page',
        parameters: {
          databaseId: 'project-tasks',
          properties: '{{transformedData}}',
        },
        dependsOn: ['transform-for-notion'],
        retryPolicy: { maxAttempts: 3, delay: 2000, backoffMultiplier: 2 },
        timeout: 30000,
        metadata: {},
      },
      {
        id: 'send-confirmation',
        name: 'Send Confirmation to Slack',
        type: 'notification',
        parameters: {
          type: 'slack',
          recipients: ['#general'],
          message: '✅ Important message synced to Notion: {{message.text}}',
        },
        dependsOn: ['create-notion-page'],
        retryPolicy: { maxAttempts: 2, delay: 1000, backoffMultiplier: 1.5 },
        timeout: 10000,
        metadata: {},
      },
    ],
    triggers: [
      {
        id: 'slack-message-trigger',
        type: 'integration_event',
        integrationId: 'slack',
        eventType: 'message_received',
        enabled: true,
        metadata: {},
      },
    ],
    variables: {},
    settings: {
      timeout: 120000,
      retryPolicy: { maxAttempts: 3, delay: 5000 },
      priority: 'normal',
      parallelExecution: false,
    },
    integrations: ['slack', 'notion'],
    tags: ['slack', 'notion', 'sync', 'automation'],
    enabled: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const workflow1Id = await manager.createWorkflow(slackToNotionWorkflow);
  workflows.push(workflow1Id);

  // Workflow 2: GitHub Issue to Jira Sync
  console.log('  📝 Creating GitHub to Jira sync workflow...');
  const githubToJiraWorkflow: WorkflowDefinition = {
    id: 'github-jira-sync',
    name: 'GitHub Issues to Jira Tickets',
    description: 'Sync GitHub issues and PRs to Jira tickets',
    version: '1.0.0',
    category: 'development',
    steps: [
      {
        id: 'listen-github',
        name: 'Listen to GitHub Events',
        type: 'integration_action',
        integrationId: 'github',
        action: 'listen_webhook',
        parameters: {
          events: ['issues', 'pull_request'],
          repository: 'atom-automation',
        },
        dependsOn: [],
        retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
        timeout: 30000,
        metadata: {},
      },
      {
        id: 'analyze-issue',
        name: 'Analyze Issue Priority',
        type: 'condition',
        parameters: {
          condition: {
            field: 'issue.labels',
            operator: 'contains',
            value: 'bug',
          },
        },
        dependsOn: ['listen-github'],
        retryPolicy: { maxAttempts: 1, delay: 500, backoffMultiplier: 1 },
        timeout: 5000,
        metadata: {},
      },
      {
        id: 'transform-github-data',
        name: 'Transform GitHub Data for Jira',
        type: 'data_transform',
        parameters: {
          transformType: 'map_fields',
          mapping: {
            'summary': 'issue.title',
            'description': 'issue.body',
            'priority': 'issue.labels',
            'assignee': 'issue.assignee.login',
            'labels': 'issue.labels',
          },
        },
        dependsOn: ['listen-github'],
        retryPolicy: { maxAttempts: 2, delay: 500, backoffMultiplier: 1.5 },
        timeout: 10000,
        metadata: {},
      },
      {
        id: 'create-jira-ticket',
        name: 'Create Jira Ticket',
        type: 'integration_action',
        integrationId: 'jira',
        action: 'create_issue',
        parameters: {
          project: 'ATOM',
          issueType: '{{issueType}}',
          fields: '{{transformedData}}',
        },
        dependsOn: ['transform-github-data'],
        retryPolicy: { maxAttempts: 3, delay: 2000, backoffMultiplier: 2 },
        timeout: 30000,
        metadata: {},
      },
      {
        id: 'link-github-jira',
        name: 'Link GitHub Issue to Jira Ticket',
        type: 'integration_action',
        integrationId: 'github',
        action: 'add_comment',
        parameters: {
          issueNumber: '{{issue.number}}',
          comment: '🎫 Jira ticket created: {{jiraTicketKey}}',
        },
        dependsOn: ['create-jira-ticket'],
        retryPolicy: { maxAttempts: 2, delay: 1000, backoffMultiplier: 1.5 },
        timeout: 15000,
        metadata: {},
      },
    ],
    triggers: [
      {
        id: 'github-webhook-trigger',
        type: 'webhook',
        webhookPath: '/webhooks/github',
        enabled: true,
        metadata: {},
      },
    ],
    variables: {
      issueType: 'Task',
    },
    settings: {
      timeout: 180000,
      retryPolicy: { maxAttempts: 3, delay: 5000 },
      priority: 'high',
      parallelExecution: false,
    },
    integrations: ['github', 'jira'],
    tags: ['github', 'jira', 'development', 'sync'],
    enabled: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const workflow2Id = await manager.createWorkflow(githubToJiraWorkflow);
  workflows.push(workflow2Id);

  // Workflow 3: System Health Monitor
  console.log('  📝 Creating system health monitoring workflow...');
  const healthMonitorWorkflow: WorkflowDefinition = {
    id: 'system-health-monitor',
    name: 'System Health Monitor',
    description: 'Monitor system health and send alerts',
    version: '1.0.0',
    category: 'monitoring',
    steps: [
      {
        id: 'check-integrations',
        name: 'Check Integration Health',
        type: 'integration_action',
        integrationId: 'system',
        action: 'health_check',
        parameters: {
          services: ['slack', 'notion', 'github'],
          threshold: 0.8,
        },
        dependsOn: [],
        retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
        timeout: 30000,
        metadata: {},
      },
      {
        id: 'evaluate-health',
        name: 'Evaluate Health Status',
        type: 'condition',
        parameters: {
          condition: {
            field: 'health.overall',
            operator: 'lt',
            value: 0.8,
          },
        },
        dependsOn: ['check-integrations'],
        retryPolicy: { maxAttempts: 1, delay: 1000, backoffMultiplier: 1 },
        timeout: 5000,
        metadata: {},
      },
      {
        id: 'send-alert',
        name: 'Send Health Alert',
        type: 'notification',
        parameters: {
          type: 'slack',
          recipients: ['#alerts'],
          message: '🚨 System health degraded: {{health.overall}}%\nDetails: {{health.details}}',
        },
        dependsOn: ['evaluate-health'],
        retryPolicy: { maxAttempts: 3, delay: 2000, backoffMultiplier: 2 },
        timeout: 15000,
        metadata: {},
      },
      {
        id: 'log-health-metrics',
        name: 'Log Health Metrics',
        type: 'data_transform',
        parameters: {
          transformType: 'calculate',
          calculations: {
            'healthScore': 'health.overall',
            'unhealthyCount': 'health.unhealthyServices.length',
            'timestamp': 'Date.now()',
          },
        },
        dependsOn: ['check-integrations'],
        retryPolicy: { maxAttempts: 1, delay: 500, backoffMultiplier: 1 },
        timeout: 5000,
        metadata: {},
      },
    ],
    triggers: [
      {
        id: 'scheduled-health-check',
        type: 'scheduled',
        schedule: '*/5 * * * *', // Every 5 minutes
        enabled: true,
        metadata: {},
      },
    ],
    variables: {},
    settings: {
      timeout: 60000,
      retryPolicy: { maxAttempts: 2, delay: 3000 },
      priority: 'high',
      parallelExecution: false,
    },
    integrations: ['system'],
    tags: ['monitoring', 'health', 'alerts'],
    enabled: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const workflow3Id = await manager.createWorkflow(healthMonitorWorkflow);
  workflows.push(workflow3Id);

  console.log(`  ✅ Created ${workflows.length} workflows\n`);
  return workflows;
}

async function executeWorkflows(manager: OrchestrationManager, workflows: string[]): Promise<string[]> {
  const executions: string[] = [];

  // Execute Slack to Notion sync
  console.log('  🚀 Executing Slack to Notion sync workflow...');
  const execution1 = await manager.executeWorkflow(
    workflows[0],
    'demo-user',
    {
      message: {
        text: '🚀 This is an important task that needs to be tracked',
        user: { name: 'John Doe' },
        importance: 0.9,
        timestamp: new Date().toISOString(),
        content: 'Detailed task description with all necessary information...',
      },
    }
  );
  executions.push(execution1);

  // Execute GitHub to Jira sync
  console.log('  🚀 Executing GitHub to Jira sync workflow...');
  const execution2 = await manager.executeWorkflow(
    workflows[1],
    'demo-user',
    {
      issue: {
        number: 123,
        title: 'Fix authentication bug in production',
        body: 'Users are reporting authentication failures...',
        assignee: { login: 'developer-1' },
        labels: ['bug', 'high-priority', 'production'],
      },
    }
  );
  executions.push(execution2);

  // Execute system health monitor
  console.log('  🚀 Executing system health monitor workflow...');
  const execution3 = await manager.executeWorkflow(
    workflows[2],
    'system',
    {}
  );
  executions.push(execution3);

  console.log(`  ✅ Started ${executions.length} workflow executions\n`);
  return executions;
}

async function monitorAndOptimize(manager: OrchestrationManager, executions: string[]) {
  console.log('  📊 Monitoring workflow executions...');

  // Wait a bit for executions to complete
  await new Promise(resolve => setTimeout(resolve, 10000));

  // Check execution status
  for (const executionId of executions) {
    const execution = await manager.getWorkflowExecution(executionId);
    if (execution) {
      console.log(`    📋 Execution ${executionId}: ${execution.status}`);
      
      if (execution.status === 'completed') {
        console.log(`      ✅ Completed in ${execution.executionTime}ms`);
      } else if (execution.status === 'failed') {
        console.log(`      ❌ Failed: ${execution.error}`);
      }
    }
  }

  // Perform optimization
  console.log('\n  🎯 Performing workflow optimization...');
  for (const executionId of executions) {
    const execution = await manager.getWorkflowExecution(executionId);
    if (execution) {
      const optimization = await manager.optimizeWorkflow(execution.workflowId, true);
      console.log(`    🔧 Workflow ${execution.workflowId} optimized:`);
      console.log(`      Score: ${optimization.overallScore}/100`);
      console.log(`      Optimizations: ${optimization.optimizations.length}`);
      console.log(`      Auto-applied: ${optimization.autoApplicable}`);
    }
  }

  console.log('  ✅ Monitoring and optimization completed\n');
}

async function showSystemHealth(manager: OrchestrationManager) {
  console.log('  🏥 Checking system health...');

  // Get current metrics
  const metrics = await manager.getCurrentMetrics();
  console.log('    📈 System Metrics:');
  console.log(`      Total Workflows: ${metrics.system.totalWorkflows}`);
  console.log(`      Active Executions: ${metrics.system.activeExecutions}`);
  console.log(`      Total Integrations: ${metrics.system.totalIntegrations}`);
  console.log(`      Healthy Integrations: ${metrics.system.healthyIntegrations}`);
  console.log(`      Success Rate: ${(metrics.performance.successRate * 100).toFixed(1)}%`);
  console.log(`      Average Execution Time: ${metrics.performance.averageExecutionTime}ms`);

  // Get integration health
  const integrationHealth = await manager.getIntegrationHealth();
  console.log('\n    🔗 Integration Health:');
  console.log(`      Total Integrations: ${integrationHealth.totalIntegrations}`);
  console.log(`      Healthy Integrations: ${integrationHealth.healthyIntegrations}`);

  // Get alerts
  const alerts = await manager.getAlerts();
  if (alerts.length > 0) {
    console.log('\n    🚨 Active Alerts:');
    alerts.forEach(alert => {
      console.log(`      [${alert.severity.toUpperCase()}] ${alert.title}`);
    });
  } else {
    console.log('\n    ✅ No active alerts');
  }

  // Get system snapshot
  const snapshot = await manager.getSystemSnapshot();
  console.log('\n    📸 System Snapshot:');
  console.log(`      Uptime: ${Math.floor(snapshot.system.uptime / 1000)}s`);
  console.log(`      Memory Usage: ${(snapshot.system.memoryUsage * 100).toFixed(1)}%`);

  console.log('  ✅ System health check completed\n');
}

// Run the demonstration
if (require.main === module) {
  demonstrateMultiIntegrationOrchestration().catch(console.error);
}

export { demonstrateMultiIntegrationOrchestration };