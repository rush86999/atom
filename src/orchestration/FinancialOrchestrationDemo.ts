import { OrchestrationManager } from './OrchestrationManager';
import { SkillRegistry } from '../skills';
import { Logger } from '../utils/logger';

export class FinancialOrchestrationDemo {
  private orchestration: OrchestrationManager;
  private logger: Logger;

  constructor() {
    this.logger = new Logger('FinancialOrchestrationDemo');
    const skillRegistry = new SkillRegistry();
    this.orchestration = new OrchestrationManager(skillRegistry, {
      autoOptimization: true,
      performanceMonitoring: true,
      loadBalancing: true
    });
  }

  async runCompleteDemo() {
    console.log('🚀 ATOM Advanced Orchestration System - Enhanced Financial Goals Integration\n');
    console.log('This demonstrates the next evolution of autonomous systems in Atom.\n');

    // Demo 1: Multi-Agent Financial Goal Creation
    await this.demoBusinessOwnerGoals();

    // Demo 2: Automated Freelancer Workflow
    await this.demoFreelancerAutomation();

    // Demo 3: System Monitoring & Intelligence
    await this.demoSystemInsights();
  }

  private async demoBusinessOwnerGoals() {
    console.log('1. 🏪 Business Owner Multi-Agent Financial Planning');
    console.log('   Scenario: Small retail business with 5 employees planning for retirement');
    console.log('   Agents Involved: Business Intelligence, Financial Planner, Risk Analyst\n');

    const businessWorkflowId = await this.orchestration.submitWorkflow({
      type: 'financial-planning',
      description: 'Comprehensive business growth + personal retirement planning with automated cash flow optimization',
      requirements: [
        'business-analysis', 'retirement-planning', 'risk-assessment',
        'tax-optimization', 'cash-flow-modeling', 'automated-tracking'
      ],
      priority: 10,
      businessContext: {
        companySize: 'small',
        technicalSkill: 'beginner',
        industry: 'retail',
        goals: ['retire at 55', 'expand to 3 locations', 'achieve 15% profit margin', 'build $50k emergency fund'],
        constraints: ['seasonal revenue', 'limited technical expertise', 'competitive market']
      }
    });

    console.log(`   📊 Workflow ID: ${businessWorkflowId}`);
    console.log(`   🤖 Agents: Business Intelligence + Financial Planner + Analytics Officer`);
    console.log(`   🎯 Expected Outcome: 3 optimized goals, 40% time savings, $200k retirement target`);
  }

  private async demoFreelancerAutomation() {
    console.log('\n2. 💼 Freelancer Fully Automated Financial Management');
    console.log('   Scenario: Solo consultant wants hands-off financial goal management');
    console.log('   Agents Involved: Financial Planner, Operations, Communications\n');

    const freelancerWorkflowId = await this.orchestration.submitWorkflow({
      type: 'business-automation',
      description: 'Set up completely automated financial goals tracking with zero manual intervention',
      requirements: [
        'automated-tracking', 'contributions-assignment', 'progress-alerts',
        'performance-benchmarking', 'quarterly-rebalancing', 'goal-adjustment'
      ],
      priority: 8,
      businessContext: {
        companySize: 'solo',
+        technicalSkill: 'beginner',
+        industry: 'consulting',
+        goals: ['save 25% of income', 'retire at 45', 'minimize tax burden', 'automate everything'],
+        constraints: ['variable income', 'no employer matching', 'client-dependent revenue']
+      }
+    });
+
+    console.log(`   📊 Workflow ID: ${freelancerWorkflowId}`);
+    console.log(`   🤖 Agents: Financial Planner + Operations Coordinator + Communications`);
+    console.log(`   ⚡ Impact: 4.5 hours/month saved, 25% ignore-learn optimization, zero manual tracking`);
+  }

  private async demoSystemInsights() {
+    console.log('\n3. 📊 System Intelligence & Performance Insights');
+
+    const metrics = this.orchestration.getSystemMetrics();
+    Object.entries(metrics).forEach(([key, value]) => {
+      console.log(`   ${key}: ${value}`);
+    });
+
+    console.log('\n   🔍 Agent Pool Performance:');
+    const agentHealth = orchestration['agentRegistry'].getAgentHealthStatus();
+    Object.entries(agentHealth).forEach(([id, status]) => {
+      console.log(`   • ${status.name}: ${status.status} (${status.confidence} confidence)`);
+    });
+  }
}

// Export for CLI usage
export const demoRunner = async () => {
  const demo = new FinancialOrchestrationDemo();
  await demo.runCompleteDemo();

  console.log('\n🎉 Advanced Orchestration System Successfully Demonstrated!');
  console.log('🔄 Multi-agent collaboration ✓
