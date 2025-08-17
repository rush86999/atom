// Complete Autonomous System Demonstration
// Run with: npx ts-node autonomous-demo.ts

import { AutonomousAgentSystem } from './src/orchestration/autonomousAgentSystem';
import { createAutonomousCommunicationSystem } from './src/autonomous-communication';

// =============================================================================
// 1. SMALL BUSINESS AUTONOMOUS SETUP - COFFEE SHOP EXAMPLE
// =============================================================================

const coffeeShopConfig = {
  userId: 'cafe-owner-001',
  shopifyStore: 'roasted-bean-coffee.myshopify.com',
  websiteUrl: 'https://roastedbean.coffee',
  slackWebhook: 'https://hooks.slack.com/services/YOUR/WEBHOOK/HERE'
};

async function startAutonomousBusiness() {
  console.log('☕ Starting autonomous system for coffee shop...');

  // 1. Start the main autonomous agent system
  const autonomousSystem = new AutonomousAgentSystem({
    userId: coffeeShopConfig.userId,
    mode: 'learning',
    apiEndpoint: 'http://localhost:8004',
    enableLearning: true
  });

  // 2. Setup event listeners
  autonomousSystem.on('started', () => {
    console.log('✅ Autonomous system operational!');
    deployBusinessTriggers();
  });

  autonomousSystem.on('heartbeat', (status) => {
    console.log(`💓 Health: ${status.health}, Triggers: ${status.activeTriggers}`);
  });

  await autonomousSystem.start();

  // 3. Setup autonomous communication (CRM automation)
  console.log('🔧 Initializing autonomous communications...');
  const comms = await createAutonomousCommunicationSystem(coffeeShopConfig.userId);
  await comms.start();
  console.log('📊 Autonomous communications ready');
}

// =============================================================================
// 2. BUSINESS-SPECIFIC AUTONOMOUS TRIGGERS
// =============================================================================

async function deployBusinessTriggers() {
  console.log('📊 Deploying business triggers...');
+
  const triggers = [
+    // Sales performance monitoring
+    {
+      workflow_id: `cafe-sales-${coffeeShopConfig.userId}`,
+      trigger_type: 'sales-threshold',
+      parameters: { threshold: 25, store: coffeeShopConfig.shopifyStore },
+      schedule: '*/10 * * * *'
+    },
+    // Website health checks
+    {
+      workflow_id: `cafe-website-${coffeeShopConfig.userId}`,
+      trigger_type: 'web-polling',
+      parameters: { url: coffeeShopConfig.websiteUrl, condition: 'responsive' },
+      schedule: '*/5 * * * *'
+    },
+    // Customer relationship automation
+    {
+      workflow_id: `cafe-relationships-${coffeeShopConfig.userId}`,
+      trigger_type: 'relationship-maintenance',
+      parameters: { stale_days: 30, type: 'coffee-customers' },
+      schedule: '0 9 * * 1'  // Mondays at 9 AM
+    }
+  ];

  const results = await Promise.allSettled(
    triggers.map(trigger => registerTrigger(trigger))
  );

  const successes = results.filter(r => r.status === 'fulfilled').length;
  console.log(`✅ Deployed ${successes}/${triggers.length} triggers`);
+}
+
+async function registerTrigger(trigger: any) {
+  const response = await fetch('http://localhost:8004/triggers/smart', {
+    method: 'POST',
+    headers: { 'Content-Type': 'application/json' },
+    body: JSON.stringify(trigger)
+  });
+  return response.json();
}

// =============================================================================
// 3. MONITORING DASHBOARD
// =============================================================================

class AutonomousDashboard {
+  private systemStatus = {
+    triggersDeployed: 0,
+    runsCompleted: 0,
+    alertsSent: 0,
+    emailsScheduled: 0
+  };

+  async displayStatus() {
+    console.clear();
+    console.log('🤖 AUTONOMOUS BUSINESS DASHBOARD');
+    console.log('===============================
+    console.log(`📊 Triggers: ${this.systemStatus.triggersDeployed}`);
+    console.log(`🔄 Completed: ${this.systemStatus.runsCompleted}`);
+    console.log(`⚠️  Alerts: ${this.systemStatus.alertsSent}`);
+    console.log(`📧 Emails: ${this.systemStatus.emailsScheduled}`);
+  }
}

// =============================================================================
// 4. QUICK START EXECUTION
// =============================================================================

async function runDemo() {
  console.log('🚀 AUTONOMOUS SYSTEM DEMO STARTING...\n');
  console.log('Services launching: Redis, Celery Workers, API Server');
  console.log('Monitoring: Business metrics, relationships, website health');
  console.log('Learning: Optimizing
