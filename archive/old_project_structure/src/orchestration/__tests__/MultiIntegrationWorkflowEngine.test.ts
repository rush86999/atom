import { MultiIntegrationWorkflowEngine, IntegrationCapability, WorkflowDefinition } from '../MultiIntegrationWorkflowEngine';
import { EnhancedWorkflowService } from '../EnhancedWorkflowService';
import { IntegrationRegistry } from '../IntegrationRegistry';
import { OrchestrationManager } from '../OrchestrationManager';

/**
 * Comprehensive Test Suite for Multi-Integration Workflow Orchestration Engine
 * 
 * This test suite validates the functionality, performance, and reliability
 * of the orchestration system.
 */

describe('Multi-Integration Workflow Orchestration Engine', () => {
  let workflowEngine: MultiIntegrationWorkflowEngine;
  let workflowService: EnhancedWorkflowService;
  let integrationRegistry: IntegrationRegistry;
  let orchestrationManager: OrchestrationManager;

  beforeEach(() => {
    // Initialize fresh components for each test
    workflowEngine = new MultiIntegrationWorkflowEngine({
      maxConcurrentExecutions: 5,
      maxStepsPerExecution: 20,
      defaultTimeout: 30000,
      enableCaching: true,
      enableMetrics: true,
      enableOptimization: true,
      logLevel: 'error', // Reduce noise in tests
    });

    workflowService = new EnhancedWorkflowService(workflowEngine);
    integrationRegistry = new IntegrationRegistry();
    
    orchestrationManager = new OrchestrationManager({
      maxConcurrentExecutions: 5,
      maxStepsPerExecution: 20,
      defaultTimeout: 30000,
      enableAutoOptimization: false, // Disable for tests
      enableMetricsCollection: true,
      logLevel: 'error',
    });
  });

  afterEach(async () => {
    // Cleanup after each test
    if (orchestrationManager) {
      await orchestrationManager.shutdown();
    }
  });

  describe('MultiIntegrationWorkflowEngine', () => {
    describe('Integration Management', () => {
      test('should register integration capability', async () => {
        const capability: IntegrationCapability = {
          id: 'test-integration',
          name: 'Test Integration',
          integrationType: 'test',
          supportedActions: ['test_action'],
          supportedTriggers: ['test_trigger'],
          rateLimit: {
            requestsPerSecond: 10,
            requestsPerHour: 1000,
          },
          requiresAuth: true,
          authType: 'oauth',
          healthStatus: 'healthy',
          lastHealthCheck: new Date(),
          metadata: {},
        };

        await workflowEngine.registerIntegration(capability);
        
        const integrations = workflowEngine.getRegisteredIntegrations();
        expect(integrations).toHaveLength(1);
        expect(integrations[0].id).toBe('test-integration');
      });

      test('should unregister integration', async () => {
        const capability: IntegrationCapability = {
          id: 'test-integration',
          name: 'Test Integration',
          integrationType: 'test',
          supportedActions: ['test_action'],
          supportedTriggers: ['test_trigger'],
          rateLimit: { requestsPerSecond: 10, requestsPerHour: 1000 },
          requiresAuth: false,
          authType: 'none',
          healthStatus: 'healthy',
          lastHealthCheck: new Date(),
          metadata: {},
        };

        await workflowEngine.registerIntegration(capability);
        await workflowEngine.unregisterIntegration('test-integration');
        
        const integrations = workflowEngine.getRegisteredIntegrations();
        expect(integrations).toHaveLength(0);
      });

      test('should track integration state', async () => {
        const capability: IntegrationCapability = {
          id: 'test-integration',
          name: 'Test Integration',
          integrationType: 'test',
          supportedActions: ['test_action'],
          supportedTriggers: ['test_trigger'],
          rateLimit: { requestsPerSecond: 10, requestsPerHour: 1000 },
          requiresAuth: false,
          authType: 'none',
          healthStatus: 'healthy',
          lastHealthCheck: new Date(),
          metadata: {},
        };

        await workflowEngine.registerIntegration(capability);
        
        const health = await workflowEngine.getIntegrationHealth();
        expect(health).toBeInstanceOf(Map);
        expect(health.size).toBeGreaterThan(0);
      });
    });

    describe('Workflow Execution', () => {
      test('should execute simple workflow', async () => {
        const workflow: WorkflowDefinition = {
          id: 'simple-workflow',
          name: 'Simple Test Workflow',
          description: 'A simple workflow for testing',
          version: '1.0.0',
          category: 'test',
          steps: [
            {
              id: 'test-step',
              name: 'Test Step',
              type: 'wait',
              parameters: { duration: 100 },
              dependsOn: [],
              retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
              timeout: 5000,
              metadata: {},
            },
          ],
          triggers: [
            {
              id: 'manual-trigger',
              type: 'manual',
              enabled: true,
              metadata: {},
            },
          ],
          variables: {},
          settings: {
            timeout: 30000,
            retryPolicy: { maxAttempts: 1, delay: 5000 },
            priority: 'normal',
            parallelExecution: false,
          },
          integrations: [],
          tags: ['test'],
          enabled: true,
          createdAt: new Date(),
          updatedAt: new Date(),
        };

        await workflowEngine.registerWorkflow(workflow);
        const executionId = await workflowEngine.executeWorkflow(
          workflow.id,
          'test-user',
          {}
        );

        // Wait for execution to complete
        await new Promise(resolve => setTimeout(resolve, 200));

        const execution = await workflowEngine.getExecution(executionId);
        expect(execution).toBeDefined();
        expect(execution!.status).toBe('completed');
      });

      test('should handle workflow with dependencies', async () => {
        const workflow: WorkflowDefinition = {
          id: 'dependency-workflow',
          name: 'Dependency Test Workflow',
          description: 'Test workflow with step dependencies',
          version: '1.0.0',
          category: 'test',
          steps: [
            {
              id: 'step-1',
              name: 'First Step',
              type: 'wait',
              parameters: { duration: 100 },
              dependsOn: [],
              retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
              timeout: 5000,
              metadata: {},
            },
            {
              id: 'step-2',
              name: 'Second Step',
              type: 'wait',
              parameters: { duration: 100 },
              dependsOn: ['step-1'],
              retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
              timeout: 5000,
              metadata: {},
            },
            {
              id: 'step-3',
              name: 'Third Step',
              type: 'wait',
              parameters: { duration: 100 },
              dependsOn: ['step-2'],
              retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
              timeout: 5000,
              metadata: {},
            },
          ],
          triggers: [
            {
              id: 'manual-trigger',
              type: 'manual',
              enabled: true,
              metadata: {},
            },
          ],
          variables: {},
          settings: {
            timeout: 30000,
            retryPolicy: { maxAttempts: 1, delay: 5000 },
            priority: 'normal',
            parallelExecution: false,
          },
          integrations: [],
          tags: ['test'],
          enabled: true,
          createdAt: new Date(),
          updatedAt: new Date(),
        };

        await workflowEngine.registerWorkflow(workflow);
        const executionId = await workflowEngine.executeWorkflow(
          workflow.id,
          'test-user',
          {}
        );

        // Wait for execution to complete
        await new Promise(resolve => setTimeout(resolve, 500));

        const execution = await workflowEngine.getExecution(executionId);
        expect(execution).toBeDefined();
        expect(execution!.status).toBe('completed');

        // Verify step execution order
        const step1 = execution!.stepExecutions.get('step-1');
        const step2 = execution!.stepExecutions.get('step-2');
        const step3 = execution!.stepExecutions.get('step-3');

        expect(step1?.status).toBe('completed');
        expect(step2?.status).toBe('completed');
        expect(step3?.status).toBe('completed');

        // Verify execution order
        expect(step1!.startedAt!.getTime()).toBeLessThanOrEqual(step2!.startedAt!.getTime());
        expect(step2!.startedAt!.getTime()).toBeLessThanOrEqual(step3!.startedAt!.getTime());
      });

      test('should handle workflow failures', async () => {
        const workflow: WorkflowDefinition = {
          id: 'failing-workflow',
          name: 'Failing Test Workflow',
          description: 'Test workflow that intentionally fails',
          version: '1.0.0',
          category: 'test',
          steps: [
            {
              id: 'failing-step',
              name: 'Failing Step',
              type: 'integration_action',
              integrationId: 'non-existent-integration',
              action: 'invalid_action',
              parameters: {},
              dependsOn: [],
              retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
              timeout: 5000,
              metadata: {},
            },
          ],
          triggers: [
            {
              id: 'manual-trigger',
              type: 'manual',
              enabled: true,
              metadata: {},
            },
          ],
          variables: {},
          settings: {
            timeout: 30000,
            retryPolicy: { maxAttempts: 1, delay: 5000 },
            priority: 'normal',
            parallelExecution: false,
          },
          integrations: ['non-existent-integration'],
          tags: ['test'],
          enabled: true,
          createdAt: new Date(),
          updatedAt: new Date(),
        };

        await workflowEngine.registerWorkflow(workflow);

        await expect(
          workflowEngine.executeWorkflow(workflow.id, 'test-user', {})
        ).rejects.toThrow();

        // Check analytics for failure
        const analytics = await workflowEngine.getWorkflowAnalytics(workflow.id);
        expect(analytics).toBeDefined();
        expect(analytics!.failedExecutions).toBe(1);
      });
    });

    describe('Data Transformation', () => {
      test('should transform data using map_fields', async () => {
        const workflow: WorkflowDefinition = {
          id: 'transform-workflow',
          name: 'Data Transform Test',
          description: 'Test data transformation',
          version: '1.0.0',
          category: 'test',
          steps: [
            {
              id: 'transform-step',
              name: 'Transform Step',
              type: 'data_transform',
              parameters: {
                transformType: 'map_fields',
                mapping: {
                  'output.name': 'input.fullName',
                  'output.email': 'input.emailAddress',
                  'output.age': 'input.person.age',
                },
              },
              dependsOn: [],
              retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
              timeout: 5000,
              metadata: {},
            },
          ],
          triggers: [
            {
              id: 'manual-trigger',
              type: 'manual',
              enabled: true,
              metadata: {},
            },
          ],
          variables: {
            input: {
              fullName: 'John Doe',
              emailAddress: 'john.doe@example.com',
              person: {
                age: 30,
              },
            },
          },
          settings: {
            timeout: 30000,
            retryPolicy: { maxAttempts: 1, delay: 5000 },
            priority: 'normal',
            parallelExecution: false,
          },
          integrations: [],
          tags: ['test'],
          enabled: true,
          createdAt: new Date(),
          updatedAt: new Date(),
        };

        await workflowEngine.registerWorkflow(workflow);
        const executionId = await workflowEngine.executeWorkflow(
          workflow.id,
          'test-user',
          {}
        );

        // Wait for execution to complete
        await new Promise(resolve => setTimeout(resolve, 200));

        const execution = await workflowEngine.getExecution(executionId);
        expect(execution).toBeDefined();
        expect(execution!.status).toBe('completed');

        const stepExecution = execution!.stepExecutions.get('transform-step');
        expect(stepExecution?.status).toBe('completed');
        expect(stepExecution?.output).toEqual({
          output: {
            name: 'John Doe',
            email: 'john.doe@example.com',
            age: 30,
          },
        });
      });

      test('should aggregate data', async () => {
        const workflow: WorkflowDefinition = {
          id: 'aggregate-workflow',
          name: 'Data Aggregation Test',
          description: 'Test data aggregation',
          version: '1.0.0',
          category: 'test',
          steps: [
            {
              id: 'aggregate-step',
              name: 'Aggregate Step',
              type: 'data_transform',
              parameters: {
                transformType: 'aggregate',
                aggregation: {
                  'values.count': 'count',
                  'values.sum': 'sum',
                  'values.avg': 'avg',
                  'values.min': 'min',
                  'values.max': 'max',
                },
              },
              dependsOn: [],
              retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
              timeout: 5000,
              metadata: {},
            },
          ],
          triggers: [
            {
              id: 'manual-trigger',
              type: 'manual',
              enabled: true,
              metadata: {},
            },
          ],
          variables: {
            values: [10, 20, 30, 40, 50],
          },
          settings: {
            timeout: 30000,
            retryPolicy: { maxAttempts: 1, delay: 5000 },
            priority: 'normal',
            parallelExecution: false,
          },
          integrations: [],
          tags: ['test'],
          enabled: true,
          createdAt: new Date(),
          updatedAt: new Date(),
        };

        await workflowEngine.registerWorkflow(workflow);
        const executionId = await workflowEngine.executeWorkflow(
          workflow.id,
          'test-user',
          {}
        );

        // Wait for execution to complete
        await new Promise(resolve => setTimeout(resolve, 200));

        const execution = await workflowEngine.getExecution(executionId);
        expect(execution).toBeDefined();
        expect(execution!.status).toBe('completed');

        const stepExecution = execution!.stepExecutions.get('aggregate-step');
        expect(stepExecution?.status).toBe('completed');
        expect(stepExecution?.output).toEqual({
          'values.count': 5,
          'values.sum': 150,
          'values.avg': 30,
          'values.min': 10,
          'values.max': 50,
        });
      });
    });

    describe('Performance and Scalability', () => {
      test('should handle concurrent executions', async () => {
        const workflow: WorkflowDefinition = {
          id: 'concurrent-workflow',
          name: 'Concurrent Test Workflow',
          description: 'Test concurrent execution',
          version: '1.0.0',
          category: 'test',
          steps: [
            {
              id: 'wait-step',
              name: 'Wait Step',
              type: 'wait',
              parameters: { duration: 1000 },
              dependsOn: [],
              retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
              timeout: 5000,
              metadata: {},
            },
          ],
          triggers: [
            {
              id: 'manual-trigger',
              type: 'manual',
              enabled: true,
              metadata: {},
            },
          ],
          variables: {},
          settings: {
            timeout: 30000,
            retryPolicy: { maxAttempts: 1, delay: 5000 },
            priority: 'normal',
            parallelExecution: true,
          },
          integrations: [],
          tags: ['test'],
          enabled: true,
          createdAt: new Date(),
          updatedAt: new Date(),
        };

        await workflowEngine.registerWorkflow(workflow);

        // Start multiple concurrent executions
        const numExecutions = 5;
        const executionPromises = Array.from({ length: numExecutions }, () =>
          workflowEngine.executeWorkflow(workflow.id, 'test-user', {})
        );

        const executionIds = await Promise.all(executionPromises);
        expect(executionIds).toHaveLength(numExecutions);

        // Wait for all executions to complete
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Check that all executions completed successfully
        for (const executionId of executionIds) {
          const execution = await workflowEngine.getExecution(executionId);
          expect(execution).toBeDefined();
          expect(execution!.status).toBe('completed');
        }
      });

      test('should track performance metrics', async () => {
        const workflow: WorkflowDefinition = {
          id: 'metrics-workflow',
          name: 'Metrics Test Workflow',
          description: 'Test performance metrics',
          version: '1.0.0',
          category: 'test',
          steps: [
            {
              id: 'test-step',
              name: 'Test Step',
              type: 'wait',
              parameters: { duration: 500 },
              dependsOn: [],
              retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
              timeout: 5000,
              metadata: {},
            },
          ],
          triggers: [
            {
              id: 'manual-trigger',
              type: 'manual',
              enabled: true,
              metadata: {},
            },
          ],
          variables: {},
          settings: {
            timeout: 30000,
            retryPolicy: { maxAttempts: 1, delay: 5000 },
            priority: 'normal',
            parallelExecution: false,
          },
          integrations: [],
          tags: ['test'],
          enabled: true,
          createdAt: new Date(),
          updatedAt: new Date(),
        };

        await workflowEngine.registerWorkflow(workflow);

        // Execute workflow multiple times
        const numExecutions = 3;
        for (let i = 0; i < numExecutions; i++) {
          const executionId = await workflowEngine.executeWorkflow(
            workflow.id,
            'test-user',
            {}
          );
          
          // Wait for execution to complete
          await new Promise(resolve => setTimeout(resolve, 600));
        }

        // Check analytics
        const analytics = await workflowEngine.getWorkflowAnalytics(workflow.id);
        expect(analytics).toBeDefined();
        expect(analytics!.totalExecutions).toBe(numExecutions);
        expect(analytics!.successfulExecutions).toBe(numExecutions);
        expect(analytics!.failedExecutions).toBe(0);
        expect(analytics!.successRate).toBe(1.0);
        expect(analytics!.averageExecutionTime).toBeGreaterThan(0);
      });
    });
  });

  describe('EnhancedWorkflowService', () => {
    test('should create workflow from template', async () => {
      const templateId = 'slack-bot-setup';
      const template = await workflowService.getTemplate(templateId);
      
      expect(template).toBeDefined();
      expect(template!.name).toBe('Slack Bot Setup');
      expect(template!.category).toBe('automation');
    });

    test('should list available templates', async () => {
      const templates = await workflowService.listTemplates();
      
      expect(templates.length).toBeGreaterThan(0);
      expect(templates[0]).toHaveProperty('id');
      expect(templates[0]).toHaveProperty('name');
      expect(templates[0]).toHaveProperty('category');
    });

    test('should create workflow instance', async () => {
      const templateId = 'slack-bot-setup';
      const instanceId = await workflowService.createInstance(
        templateId,
        'Test Slack Bot',
        'A test instance for Slack bot',
        {
          appName: 'Test Bot',
          workspace: 'test-workspace',
        },
        'test-user'
      );

      expect(instanceId).toBeDefined();
      expect(instanceId).toMatch(/^instance_/);

      const instance = await workflowService.getInstance(instanceId);
      expect(instance).toBeDefined();
      expect(instance!.name).toBe('Test Slack Bot');
      expect(instance!.templateId).toBe(templateId);
    });

    test('should execute workflow instance', async () => {
      // First create an instance from a simple template
      const templates = await workflowService.listTemplates({ text: 'simple' });
      if (templates.length === 0) {
        // Skip test if no simple template found
        return;
      }

      const template = templates[0];
      const instanceId = await workflowService.createInstance(
        template.id,
        'Test Instance',
        'A test instance',
        {},
        'test-user'
      );

      const executionId = await workflowService.executeInstance(
        instanceId,
        'test-user'
      );

      expect(executionId).toBeDefined();

      // Wait a bit for execution
      await new Promise(resolve => setTimeout(resolve, 200));

      const execution = await workflowService.getExecution(executionId);
      expect(execution).toBeDefined();
    });
  });

  describe('IntegrationRegistry', () => {
    test('should list builtin integrations', async () => {
      const integrations = await integrationRegistry.listIntegrations();
      
      expect(integrations.length).toBeGreaterThan(0);
      expect(integrations[0]).toHaveProperty('id');
      expect(integrations[0]).toHaveProperty('name');
      expect(integrations[0]).toHaveProperty('category');
    });

    test('should filter integrations by category', async () => {
      const communicationIntegrations = await integrationRegistry.listIntegrations('communication');
      
      expect(communicationIntegrations.length).toBeGreaterThan(0);
      communicationIntegrations.forEach(integration => {
        expect(integration.category).toBe('communication');
      });
    });

    test('should get integration templates', async () => {
      const templates = await integrationRegistry.listTemplates();
      
      expect(templates.length).toBeGreaterThan(0);
      expect(templates[0]).toHaveProperty('id');
      expect(templates[0]).toHaveProperty('name');
      expect(templates[0]).toHaveProperty('integrationId');
    });

    test('should configure integration', async () => {
      const integrationId = 'slack';
      const userId = 'test-user';
      const settings = {
        workspace: 'test-workspace',
        defaultChannel: '#general',
      };
      const credentials = {
        type: 'oauth' as const,
        data: {
          accessToken: 'test-token',
          refreshToken: 'test-refresh',
        },
        encrypted: true,
      };

      const configKey = await integrationRegistry.createConfiguration(
        integrationId,
        userId,
        settings,
        credentials
      );

      expect(configKey).toBeDefined();
      expect(configKey).toBe(`${integrationId}:${userId}`);

      const config = await integrationRegistry.getConfiguration(integrationId, userId);
      expect(config).toBeDefined();
      expect(config!.integrationId).toBe(integrationId);
      expect(config!.userId).toBe(userId);
      expect(config!.isActive).toBe(false);
    });

    test('should activate and deactivate integration', async () => {
      const integrationId = 'slack';
      const userId = 'test-user-2';

      // Configure integration
      await integrationRegistry.createConfiguration(
        integrationId,
        userId,
        { workspace: 'test-workspace' },
        {
          type: 'oauth' as const,
          data: { accessToken: 'test-token' },
          encrypted: true,
        }
      );

      // Activate integration
      const activated = await integrationRegistry.activateConfiguration(integrationId, userId);
      expect(activated).toBe(true);

      // Check configuration is active
      const config = await integrationRegistry.getConfiguration(integrationId, userId);
      expect(config!.isActive).toBe(true);

      // Deactivate integration
      const deactivated = await integrationRegistry.deactivateConfiguration(integrationId, userId);
      expect(deactivated).toBe(true);

      // Check configuration is inactive
      const configAfter = await integrationRegistry.getConfiguration(integrationId, userId);
      expect(configAfter!.isActive).toBe(false);
    });

    test('should get integration health', async () => {
      const integrationId = 'slack';
      const userId = 'test-user-3';

      // Configure and activate integration
      await integrationRegistry.createConfiguration(
        integrationId,
        userId,
        { workspace: 'test-workspace' },
        {
          type: 'oauth' as const,
          data: { accessToken: 'test-token' },
          encrypted: true,
        }
      );
      await integrationRegistry.activateConfiguration(integrationId, userId);

      // Get health
      const health = await integrationRegistry.getIntegrationHealth(integrationId);
      expect(health).toBeDefined();
      expect(health!.integrationId).toBe(integrationId);
      expect(['healthy', 'degraded', 'unhealthy']).toContain(health!.status);
      expect(health!.overallScore).toBeGreaterThanOrEqual(0);
      expect(health!.overallScore).toBeLessThanOrEqual(100);
    });
  });

  describe('OrchestrationManager', () => {
    test('should get system status', () => {
      const status = orchestrationManager.getSystemStatus();
      
      expect(status).toBeDefined();
      expect(status).toHaveProperty('uptime');
      expect(status).toHaveProperty('version');
      expect(status).toHaveProperty('components');
      expect(status).toHaveProperty('health');
      
      expect(status.components.workflowEngine).toBe(true);
      expect(status.components.workflowService).toBe(true);
      expect(status.components.integrationRegistry).toBe(true);
      
      expect(['healthy', 'degraded', 'unhealthy']).toContain(status.health.overall);
    });

    test('should create and execute workflow', async () => {
      const workflow: WorkflowDefinition = {
        id: 'orchestration-test-workflow',
        name: 'Orchestration Test Workflow',
        description: 'Test workflow for orchestration manager',
        version: '1.0.0',
        category: 'test',
        steps: [
          {
            id: 'test-step',
            name: 'Test Step',
            type: 'wait',
            parameters: { duration: 100 },
            dependsOn: [],
            retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
            timeout: 5000,
            metadata: {},
          },
        ],
        triggers: [
          {
            id: 'manual-trigger',
            type: 'manual',
            enabled: true,
            metadata: {},
          },
        ],
        variables: {},
        settings: {
          timeout: 30000,
          retryPolicy: { maxAttempts: 1, delay: 5000 },
          priority: 'normal',
          parallelExecution: false,
        },
        integrations: [],
        tags: ['test'],
        enabled: true,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      const workflowId = await orchestrationManager.createWorkflow(workflow);
      expect(workflowId).toBe(workflow.id);

      const executionId = await orchestrationManager.executeWorkflow(
        workflowId,
        'test-user',
        {}
      );
      expect(executionId).toBeDefined();

      // Wait for execution
      await new Promise(resolve => setTimeout(resolve, 200));

      const execution = await orchestrationManager.getWorkflowExecution(executionId);
      expect(execution).toBeDefined();
      expect(execution!.status).toBe('completed');
    });

    test('should configure and activate integration', async () => {
      const integrationId = 'slack';
      const userId = 'test-user';

      const configKey = await orchestrationManager.configureIntegration(
        integrationId,
        userId,
        { workspace: 'test-workspace' },
        {
          type: 'oauth',
          data: { accessToken: 'test-token' },
          encrypted: true,
        }
      );
      expect(configKey).toBeDefined();

      const activated = await orchestrationManager.activateIntegration(integrationId, userId);
      expect(activated).toBe(true);

      const health = await orchestrationManager.getIntegrationHealth(integrationId);
      expect(health).toBeDefined();
    });

    test('should collect metrics', async () => {
      const metrics = await orchestrationManager.getCurrentMetrics();
      
      expect(metrics).toBeDefined();
      expect(metrics).toHaveProperty('timestamp');
      expect(metrics).toHaveProperty('system');
      expect(metrics).toHaveProperty('performance');
      expect(metrics).toHaveProperty('costs');
      expect(metrics).toHaveProperty('predictions');
      
      expect(metrics.system.totalWorkflows).toBeGreaterThanOrEqual(0);
      expect(metrics.system.totalIntegrations).toBeGreaterThanOrEqual(0);
      expect(metrics.performance.successRate).toBeGreaterThanOrEqual(0);
      expect(metrics.performance.successRate).toBeLessThanOrEqual(1);
    });

    test('should create and manage alerts', async () => {
      const alertId = await orchestrationManager.createAlert(
        'warning',
        'system',
        'Test Alert',
        'This is a test alert',
        { test: true },
        'medium'
      );

      expect(alertId).toBeDefined();

      const alerts = await orchestrationManager.getAlerts();
      expect(alerts.length).toBeGreaterThan(0);

      const testAlert = alerts.find(alert => alert.id === alertId);
      expect(testAlert).toBeDefined();
      expect(testAlert!.title).toBe('Test Alert');
      expect(testAlert!.resolved).toBe(false);

      const resolved = await orchestrationManager.resolveAlert(alertId, 'test-user');
      expect(resolved).toBe(true);

      const alertsAfter = await orchestrationManager.getAlerts();
      const resolvedAlert = alertsAfter.find(alert => alert.id === alertId);
      expect(resolvedAlert).toBeUndefined(); // Should be filtered out as resolved
    });

    test('should get system snapshot', async () => {
      const snapshot = await orchestrationManager.getSystemSnapshot();
      
      expect(snapshot).toBeDefined();
      expect(snapshot).toHaveProperty('timestamp');
      expect(snapshot).toHaveProperty('workflows');
      expect(snapshot).toHaveProperty('integrations');
      expect(snapshot).toHaveProperty('system');
      expect(snapshot).toHaveProperty('alerts');
      
      expect(snapshot.workflows.total).toBeGreaterThanOrEqual(0);
      expect(snapshot.integrations.total).toBeGreaterThanOrEqual(0);
      expect(snapshot.system.uptime).toBeGreaterThan(0);
    });
  });

  describe('Integration Tests', () => {
    test('should complete end-to-end workflow execution', async () => {
      // 1. Configure integrations
      await orchestrationManager.configureIntegration(
        'slack',
        'test-user',
        { workspace: 'test-workspace' },
        {
          type: 'oauth',
          data: { accessToken: 'test-token' },
          encrypted: true,
        }
      );
      await orchestrationManager.activateIntegration('slack', 'test-user');

      await orchestrationManager.configureIntegration(
        'notion',
        'test-user',
        { workspace: 'notion-workspace' },
        {
          type: 'oauth',
          data: { accessToken: 'test-notion-token' },
          encrypted: true,
        }
      );
      await orchestrationManager.activateIntegration('notion', 'test-user');

      // 2. Create workflow
      const workflowId = await orchestrationManager.createWorkflow({
        id: 'end-to-end-test',
        name: 'End-to-End Test Workflow',
        description: 'Complete end-to-end test',
        version: '1.0.0',
        category: 'integration',
        steps: [
          {
            id: 'slack-step',
            name: 'Slack Step',
            type: 'integration_action',
            integrationId: 'slack',
            action: 'send_message',
            parameters: {
              channel: '#test',
              message: 'Starting workflow test...',
            },
            dependsOn: [],
            retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
            timeout: 5000,
            metadata: {},
          },
          {
            id: 'transform-step',
            name: 'Transform Step',
            type: 'data_transform',
            parameters: {
              transformType: 'map_fields',
              mapping: {
                'title': 'slackStep.message',
                'content': 'workflow.description',
              },
            },
            dependsOn: ['slack-step'],
            retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
            timeout: 5000,
            metadata: {},
          },
          {
            id: 'notion-step',
            name: 'Notion Step',
            type: 'integration_action',
            integrationId: 'notion',
            action: 'create_page',
            parameters: {
              databaseId: 'test-db',
              properties: '{{transformedData}}',
            },
            dependsOn: ['transform-step'],
            retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
            timeout: 5000,
            metadata: {},
          },
        ],
        triggers: [
          {
            id: 'manual-trigger',
            type: 'manual',
            enabled: true,
            metadata: {},
          },
        ],
        variables: {},
        settings: {
          timeout: 30000,
          retryPolicy: { maxAttempts: 1, delay: 5000 },
          priority: 'normal',
          parallelExecution: false,
        },
        integrations: ['slack', 'notion'],
        tags: ['test', 'integration'],
        enabled: true,
        createdAt: new Date(),
        updatedAt: new Date(),
      });

      // 3. Execute workflow
      const executionId = await orchestrationManager.executeWorkflow(
        workflowId,
        'test-user',
        {
          workflow: {
            description: 'Test workflow execution',
          },
        }
      );

      // 4. Wait for completion
      await new Promise(resolve => setTimeout(resolve, 1000));

      // 5. Verify execution
      const execution = await orchestrationManager.getWorkflowExecution(executionId);
      expect(execution).toBeDefined();
      expect(execution!.status).toBe('completed');

      // 6. Verify analytics
      const analytics = await orchestrationManager.getWorkflowAnalytics(workflowId);
      expect(analytics).toBeDefined();
      expect(analytics!.totalExecutions).toBe(1);
      expect(analytics!.successfulExecutions).toBe(1);
    });
  });
});

// Performance benchmarks
describe('Performance Benchmarks', () => {
  let orchestrationManager: OrchestrationManager;

  beforeAll(() => {
    orchestrationManager = new OrchestrationManager({
      maxConcurrentExecutions: 20,
      maxStepsPerExecution: 50,
      defaultTimeout: 30000,
      enableAutoOptimization: false,
      enableMetricsCollection: true,
      logLevel: 'error',
    });
  });

  afterAll(async () => {
    await orchestrationManager.shutdown();
  });

  test('should handle 100 concurrent workflow executions', async () => {
    const workflow = {
      id: 'performance-test',
      name: 'Performance Test Workflow',
      description: 'Performance test workflow',
      version: '1.0.0',
      category: 'test',
      steps: [
        {
          id: 'wait-step',
          name: 'Wait Step',
          type: 'wait',
          parameters: { duration: 100 },
          dependsOn: [],
          retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
          timeout: 5000,
          metadata: {},
        },
      ],
      triggers: [
        {
          id: 'manual-trigger',
          type: 'manual',
          enabled: true,
          metadata: {},
        },
      ],
      variables: {},
      settings: {
        timeout: 30000,
        retryPolicy: { maxAttempts: 1, delay: 5000 },
        priority: 'normal',
        parallelExecution: true,
      },
      integrations: [],
      tags: ['test'],
      enabled: true,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    await orchestrationManager.createWorkflow(workflow);

    const numExecutions = 100;
    const startTime = Date.now();

    // Start all executions
    const executionPromises = Array.from({ length: numExecutions }, () =>
      orchestrationManager.executeWorkflow(workflow.id, 'test-user', {})
    );

    const executionIds = await Promise.all(executionPromises);
    const submissionTime = Date.now() - startTime;

    // Wait for all executions to complete
    await new Promise(resolve => setTimeout(resolve, 2000));

    const endTime = Date.now();
    const totalTime = endTime - startTime;

    // Verify all executions completed
    let completedCount = 0;
    for (const executionId of executionIds) {
      const execution = await orchestrationManager.getWorkflowExecution(executionId);
      if (execution!.status === 'completed') {
        completedCount++;
      }
    }

    console.log(`Performance Test Results:`);
    console.log(`  Executions: ${numExecutions}`);
    console.log(`  Completed: ${completedCount}`);
    console.log(`  Submission Time: ${submissionTime}ms`);
    console.log(`  Total Time: ${totalTime}ms`);
    console.log(`  Throughput: ${(numExecutions / totalTime * 1000).toFixed(2)} executions/sec`);

    expect(completedCount).toBe(numExecutions);
    expect(totalTime).toBeLessThan(10000); // Should complete within 10 seconds
    expect(submissionTime).toBeLessThan(1000); // Should submit within 1 second
  });
});

// Error handling tests
describe('Error Handling', () => {
  test('should handle invalid workflow definitions', async () => {
    const workflowEngine = new MultiIntegrationWorkflowEngine({
      maxConcurrentExecutions: 5,
      logLevel: 'error',
    });

    const invalidWorkflow = {
      id: '', // Invalid: empty ID
      name: 'Invalid Workflow',
      description: 'Invalid workflow',
      version: '1.0.0',
      category: 'test',
      steps: [],
      triggers: [],
      variables: {},
      settings: {
        timeout: 30000,
        retryPolicy: { maxAttempts: 1, delay: 5000 },
        priority: 'normal',
        parallelExecution: false,
      },
      integrations: [],
      tags: ['test'],
      enabled: true,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    await expect(workflowEngine.registerWorkflow(invalidWorkflow)).rejects.toThrow();
  });

  test('should handle circular dependencies', async () => {
    const workflowEngine = new MultiIntegrationWorkflowEngine({
      maxConcurrentExecutions: 5,
      logLevel: 'error',
    });

    const circularWorkflow = {
      id: 'circular-workflow',
      name: 'Circular Dependency Workflow',
      description: 'Workflow with circular dependencies',
      version: '1.0.0',
      category: 'test',
      steps: [
        {
          id: 'step-1',
          name: 'Step 1',
          type: 'wait',
          parameters: { duration: 100 },
          dependsOn: ['step-2'], // Circular dependency
          retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
          timeout: 5000,
          metadata: {},
        },
        {
          id: 'step-2',
          name: 'Step 2',
          type: 'wait',
          parameters: { duration: 100 },
          dependsOn: ['step-1'], // Circular dependency
          retryPolicy: { maxAttempts: 1, delay: 100, backoffMultiplier: 1 },
          timeout: 5000,
          metadata: {},
        },
      ],
      triggers: [
        {
          id: 'manual-trigger',
          type: 'manual',
          enabled: true,
          metadata: {},
        },
      ],
      variables: {},
      settings: {
        timeout: 30000,
        retryPolicy: { maxAttempts: 1, delay: 5000 },
        priority: 'normal',
        parallelExecution: false,
      },
      integrations: [],
      tags: ['test'],
      enabled: true,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    await expect(workflowEngine.registerWorkflow(circularWorkflow)).rejects.toThrow();
  });
});