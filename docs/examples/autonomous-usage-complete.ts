// Complete Autonomous System Usage Example
// Production-ready implementation with monitoring and dashboard

import { AutonomousAgentSystem } from '../src/orchestration/autonomousAgentSystem';
import { createAutonomousCommunicationSystem } from '../src/autonomous-communication';

// =============================================================================
// 1. REAL-WORLD SMALL BUSINESS SETUP
// =============================================================================

interface SmallBusinessConfig {
  shopifyStore: string;
  websiteUrl: string;
  slackWebhook: string;
  emailProvider: 'gmail' | 'outlook';
  userId: string;
}

async function setupCoffeeShopAutonomousSystem(config: SmallBusinessConfig) {
  console.log('☕ Setting up autonomous system for coffee shop...');

  // 1. Initialize the autonomous agent system
  const agentSystem = new AutonomousAgentSystem({
    userId: config.userId,
    mode: 'learning', // Start in learning mode
    apiEndpoint: 'http://localhost:8004',
    enableLearning: true
  });

  // 2. Track startup events
  agentSystem.on('started', () => {
    console.log('🎯 Autonomous system operational for:', config.shopifyStore);
    startBusinessMonitoring(config);
  });

  agentSystem.on('heartbeat', (status) => {
    console.log(`💓 Health check - Triggers: ${status.activeTriggers}, Status: ${status.health}`);
  });

  await agentSystem.start();

  // 3. Setup autonomous communications (CRM)
  const comms = await createAutonomousCommunicationSystem(config.userId);
  await comms.start();

  console.log('✅ Coffee shop autonomous system fully deployed');
  return { agent: agentSystem, comms };
}

// =============================================================================
// 2. BUSINESS-SPECIFIC MONITORING SETUP
// =============================================================================

async function startBusinessMonitoring(config: SmallBusinessConfig) {
  console.log('📊 Business monitoring deployment...');

  const triggers = [
    // Daily Sales Spike Monitor
    {
      workflow_id: `coffee-sales-${config.userId}`,
      trigger_type: 'sales-threshold',
      parameters: {
        store: config.shopifyStore,
        threshold: 25,
        metric: 'revenue_increase',
        threshold_currency: 'USD',
        time_window: 'daily'
      },
      schedule: '*/30 * * * *', // Check every 30 minutes
      response: {
        action: 'slack_alert',
        webhook_url: config.slackWebhook,
        message: "🚀 Sales spike detected! Revenue up 25%+"
      }
    },

    // Customer Relationship Health
    {
      workflow_id: `customer-crm-${config.userId}`,
      trigger_type: 'relationship-maintenance',
      parameters: {
        customer_library: 'google-contacts',
        stale_threshold_days: 21,
        outreach_frequency: 'weekly',
        personalization: 'high'
      },
      schedule: '0 9 * * 1', // Mondays at 9 AM
      response: {
        action: 'draft_followup_email',
        template: 'personalized-coffee-promo',
        track_engagement: true
      }
    },

    // Website Performance
    {
      workflow_id: `website-monitor-${config.userId}`,
      trigger_type: 'web-polling',
      parameters: {
        url: config.websiteUrl,
        checks: ['response_time', 'ssl_validity', 'mobile_responsive'],
        expected_response_time_ms: 1500,
        ssl_warning_days: 14
      },
      schedule: '*/10 * * * *', // Every 10 minutes
      response: {
        action: 'email_alert',
        recipient: 'tech@yourdomain.com',
        template: 'website-health-report'
      }
    },

    // Inventory Alerting
    {
      workflow_id: `inventory-alert-${config.userId}`,
      trigger_type: 'stock-level',
      parameters: {
        products: ['espresso-beans', 'oat-milk', 'pastries'],
        low_stock_threshold: 20,
        supplier_api: 'square',
        procurement_lead_time_days: 3
      },
      schedule: '0 8 * * *', // Daily at 8 AM
      response: {
        action: 'generate_order',
        supplier_notification: true,
        budget_tracking: true
      }
    }
  ];

  // Deploy all triggers
  const results = await Promise.allSettled(
    triggers.map(async (trigger) => {
      try {
        const response = await fetch('http://localhost:8004/triggers/smart', {
          method: 'POST',
+          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(trigger)
        });
+
+        if (response.ok) {
+          console.log(`✅ ${trigger.workflow_id}: Active`);
+          return trigger.workflow_id;
+        } else {
+          console.error(`❌ ${trigger.workflow_id}: Failed`);
