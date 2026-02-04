import { OrchestrationManager } from '../OrchestrationManager';
import { SkillRegistry } from '../../skills';
import { Logger } from '../../utils/logger';

async function runFinancialPlanningExample() {
  const logger = new Logger('FinancialPlanningExample');

  console.log('🚀 Starting Advanced Autonomous System - Financial Planning Example\n');

  // Initialize the orchestration system
  const skillRegistry = new SkillRegistry();
  const orchestration = new OrchestrationManager(skillRegistry, {
    autoOptimization: true,
    performanceMonitoring: true,
    loadBalancing: true
  });

  // Example 1: Small Business Financial Planning
  const workflow1 = {
    type: 'financial-planning' as const,
    description: 'Comprehensive business financial planning including cash flow optimization, investment strategy, and growth planning',
    requirements: ['financial-analysis', 'business-intelligence', 'predictive-modeling', 'risk-assessment', 'strategy-optimization'],
    priority: 9,
    businessContext: {
      industry: 'retail',
      companySize: 'small',
      technicalSkill: 'beginner',
      goals: ['optimize cash flow', 'plan for expansion', 'reduce expenses', 'increase revenue'],
      constraints: ['limited budget', 'seasonal revenue', 'competitive market']
    }
  };

  console.log('📊 Submitting financial planning workflow for small business...');
  const workflowId1 = await orchestration.submitWorkflow(workflow1);
  console.log(`✅ Workflow submitted with ID: ${workflowId1}`);

  // Simulate monitoring
  const status1 = await orchestration.getWorkflowStatus(workflowId1);
  console.log('📈 Current status:', status1);

  // Example 2: Personal Finance Management
  const workflow2 = {
    type: 'financial-planning' as const,
    description: 'Personal retirement planning with investment portfolio optimization and tax strategy',
    requirements: ['personal-finance', 'investment-planning', 'tax-optimization', 'risk-analysis', 'retirement-strategy'],
    priority: 8,
    businessContext: {
      companySize: 'solo',
      technicalSkill: 'advanced',
      goals: ['retirement at 45', 'financial independence', 'passive income generation']
    }
  };

  console.log('\n💰 Submitting personal finance planning workflow...');
  const workflowId2 = await orchestration.submitWorkflow(workflow2);
  console.log(`✅ Workflow submitted with ID: ${workflowId2}`);

  // Display system metrics
  console.log('\n🔍 System Metrics:');
  const metrics = orchestration.getSystemMetrics();
  console.table(metrics);

  // Display active agents
  console.log('\n🤖 Registered Agents:');
  const agents = orchestration['engine'].getRegisteredAgents().map(agent => ({
+    'Agent': agent.name,
+    'Skills': agent.skills.length,
+    'Confidence': (agent.confidence * 100).toFixed(1) + '%',
+    'Priority': agent.priority
+  }));
+  console.table(agents);

  console.log('\n🎉 Orchestration system successfully initialized and running!');
}

// Example usage with different business scenarios
async function runBusinessScenarios() {
  console.log('\n📋 Running Business Scenario Examples:');

  const scenarios = [
+    {
+      type: 'marketing-campaign',
+      description: 'Launch automated marketing campaign for new product launch',
+      context: { companySize: 'small', technicalSkill: 'beginner', industry: 'e-commerce' }
+    },
+    {
+      type: 'business-automation',
+      description: 'Automate appointment scheduling and customer onboarding',
+      context: { companySize: 'medium', technicalSkill: 'intermediate', industry: 'healthcare' }
+    },
+    {
+      type: 'content-creation',
+      description: 'Generate weekly social media content and blog posts',
+      context: { companySize: 'solo', technicalSkill: 'beginner', industry: 'consulting' }
+    }
+  ];

  const skillRegistry = new SkillRegistry();
  const orchestration = new OrchestrationManager(skillRegistry);

  for (const scenario of scenarios) {
+    console.log(`\n🎯 Processing: ${scenario.description}`);
+    const workflowId = await orchestration.submitWorkflow({
+      type: scenario.type,
+      description: scenario.description,
+      requirements: [],
+      priority: 7,
+      businessContext: scenario.context
+    });
+    console.log(`   ✅ Workflow ID: ${workflowId}`);
+  }
+}
+
// Export everything for testing/integration
+export const exampleRunner = {
+  runFinancialPlanningExample,
+  runBusinessScenarios
+};

// CLI runner
+if (require.main ===
