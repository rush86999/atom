/**
 * Atom Autonomous Workflow System Demo
 * This script demonstrates the complete autonomous workflow capabilities
 * integrated with React Flow and trigger-based automation
 */

import { AutonomousWorkflowSystem } from '../src/autonomous-ui/index';
import { AutonomousWorkflowIntegration } from '../src/autonomous-ui/AutonomousWorkflowIntegration';

// Demo configuration
const DEMO_CONFIG = {
  enableLearning: true,
  enablePredictions: true,
  enableSelfHealing: true,
  monitoringInterval: 5000,
  webhookTimeout: 30000
};

// Sample workflow data from existing React Flow system
const SAMPLE_WORKFLOW = {
  id: 'demo-autonomous-workflow',
  name: 'Intelligent Shopify Sales Automation',
  nodes: [
    {
      id: 'trigger-1',
      type: 'autonomousTrigger',
      position: { x: 50, y: 50 },
      data: {
        config: {
          triggerType: 'sales-threshold',
          isTrigger: true,
          autoStart: true,
          schedule: '*/10 * * * *', // Every 10 minutes
          conditions: [
            { type: 'sales-increase', threshold: 25, percentage: true }
          ]
        }
      }
    },
    {
      id: 'notification-1',
      type: 'slackSendMessage',
      position: { x: 300, y: 50 },
      data: {
        config: {
          channel: '#sales-team',
          message: '📈 Sales increased by {{percentage}}%'
        }
      }
    }
  ],
  edges: [
    {
      id: 'e1-2',
      source: 'trigger-1',
      target: 'notification-1',
      animated: true
    }
  ],
  metadata: {
    createdBy: 'autonomous-system',
    priority: 'high',
    tags: ['sales', 'automation', 'predictive']
  }
};

class AutonomousWorkflowDemo {
  private autonomousSystem: AutonomousWorkflowSystem;
  private integration: AutonomousWorkflowIntegration;

  constructor() {
    this.autonomousSystem = new AutonomousWorkflowSystem();
    this.integration = new AutonomousWorkflowIntegration();
  }

  async runCompleteDemo(): Promise<void> {
    console.log('🤖 Starting Autonomous Workflow Demo...\n');

    await this.initializeSystem();
    await this.createIntelligentTriggers();
    await this.setupWebhooks();
    await this.runPredictiveScheduling();
    await this.demoSelfHealing();
    await this.showAnalytics();

    console.log('\n✅ Demo completed successfully!');
  }

  private async initializeSystem(): Promise<void> {
    console.log('📦 Initializing autonomous system...');
    await this.autonomousSystem.initialize();
    await this.integration.initialize();

    // Register the sample workflow
    const workflowId = await this.autonomousSystem.registerWorkflow(SAMPLE_WORKFLOW);
    console.log(`✅ Registered workflow: ${workflowId}`);
  }

  private async createIntelligentTriggers(): Promise<void> {
    console.log('\n⚡ Creating intelligent triggers...');

    // 1. Web Content Monitoring
    await this.integration.addSmartMonitoring('demo-autonomous-workflow', {
      type: 'web-scraping',
      url: 'https://example-shop.com/products',
      selector: '.product-price',
      expectedChange: 'decrease',
      frequency: '*/5 * * * *'
    });

    // 2. API Response Monitoring
    await this.integration.addSmartMonitoring('demo-autonomous-workflow', {
      type: 'api-response',
      endpoint: 'https://api.example.com/sales-data',
      threshold: 1000,
      condition: 'greater-than',
      webhook: true
    });

    // 3. Performance Monitoring
    await this.integration.addSmartMonitoring('demo-autonomous-workflow', {
      type: 'performance-check',
      url: 'https://example-shop.com',
      maxLoadTime: 3000,
      alertOnDegradation: true
    });

    console.log('✅ Smart triggers created and activated');
  }

  private async setupWebhooks(): Promise<void> {
    console.log('\n🔗 Setting up autonomous webhook monitoring...');

    // Create webhook triggers
    const webhooks = [
      {
        name: 'Shopify Order Webhook',
        url: 'https://hooks.example.com/shopify-order',
        webhookUrl: '/webhooks/shopify/order-created',
        secret: 'demo-secret-key',
        filters: {
          event_type: 'order_created',
          total_price: { operator: '>', value: 100 }
        }
      },
      {
        name: 'GitHub Repository Events',
        url: 'https://api.github.com/repos/example/repo/events',
        types: ['push', 'release', 'issues'],
        filters: {
          type: 'push',
          actor: 'dependabot'
        }
      }
    ];

    for
