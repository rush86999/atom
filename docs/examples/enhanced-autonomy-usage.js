<file_path>
atom/examples/enhanced-autonomy-usage.js
</file_path>
const { EnhancedAutonomousEngine } = require('../src/nlu_agents/enhancedAutonomousEngine');
const { AutonomousWorkflowService } = require('../src/services/autonomousWorkflowService');
const { ConversationWorkflowManager } = require('../src/orchestration/conversationalWorkflowManager');

/**
 * Enhanced Autonomous Workflow Usage Examples
 *
 * This file demonstrates how to use Atom's new conversational autonomous workflow system
 * to create, manage, and optimize complex workflows through natural language.
 */

class AutonomusWorkflowExamples {
  constructor(config = {}) {
    this.engine = new EnhancedAutonomousEngine();
    this.service = new AutonomousWorkflowService(config);
    this.manager = new ConversationWorkflowManager();
    this.userId = 'demo-user-001';
    this.sessionId = null;
  }

  /**
   * Example 1: Create comprehensive competitor monitoring via conversation
   */
  async example1_CompetitorMonitoring() {
    console.log('🎯 Example 1: Setting up competitor monitoring via conversation');

    const userInput = "I want to automatically monitor my top 3 competitors and get weekly reports about their pricing changes, new marketing campaigns, and when they hire new people. Send alerts to Slack when anything significant happens.";

    try {
      const response = await this.engine.processUserMessage(this.userId, userInput, {
        businessContext: {
          industry: 'SaaS',
          companySize: '50-200 employees',
          technicalLevel: 'intermediate'
        }
      });

      console.log('🤖 AI Response:', response.response);
      console.log('📊 Confirmed Workflow:', response.pendingWorkflow);
      console.log('📈 Business Impact:', response.estimatedBenefit);

      return response;
    } catch (error) {
      console.error('❌ Error in competitor monitoring setup:', error);
    }
  }

  /**
   * Example 2: Automated financial intelligence with smart budgeting
   */
  async example2_FinanceAutomation() {
    console.log('💰 Example 2: Advanced financial automation setup');

    const userInput = "Create an intelligent financial system that syncs all my banking and accounting data daily, predicts cash flow issues 30 days ahead, automatically categorizes transactions, and generates board-level financial reports every Friday. If cash flow drops below a threshold, alert the finance team.";

    try {
      const response = await this.engine.processUserMessage(this.userId, userInput, {
        businessContext: {
          role: 'Controller',
          companySize: '1000+ employees',
          technicalLevel: 'advanced'
        }
      });

      console.log('🤖 AI Response:', response.response);
      console.log('💼 Business Context:', response.pendingWorkflow);

      // Show the actual workflow that will be created
      const workflow = await this.parseWorkflowIntent(response.pendingWorkflow);
      console.log('🔄 Workflow Steps:', workflow.steps);
      console.log('📊 Success Metrics:', workflow.successCriteria);

      return response;
    } catch (error) {
      console.error('❌ Error in finance automation setup:', error);
    }
  }

  /**
   * Example 3: Customer success automation with predictive insights
   */
  async example3_CustomerSuccessAutomation() {
    console.log('🛍️ Example 3: Customer success and retention automation');

    const userInput = "I need a system that automatically identifies at-risk customers by analyzing their product usage, support tickets, contract renewals, and engagement patterns. Create personalized retention strategies and automatically schedule intervention calls with our success team when churn probability is high.";

    try {
      const response = await this.engine.processUserMessage(this.userId, userInput, {
        businessContext: {
          role: 'VP Customer Success',
          industry: 'Software',
          companySize: '500-1000 employees',
          technicalLevel: 'intermediate'
        }
      });

      console.log('🎯 AI Response:', response.response);

      // Execute the workflow
      if (response.permissionRequested && response.permissionGiven) {
        const execution = await this.service.executeWorkflow(
          response.pendingWorkflow,
          { autoApprove: false, sessionId: this.sessionId }
        );

        console.log('✅ Execution Results:', execution);
      }

      return response;
    } catch (error) {
      console.error('❌ Error in customer success setup:', error);
    }
  }

  /**
   * Example 4: Multi-platform social media automation
   */
  async example4_SocialMediaAutomation() {
    console.log('📱 Example 4: Strategic social media and marketing automation');

    const userInput = "Build me an automated marketing system that monitors relevant hashtags, analyzes competitor content performance, creates weekly content calendars based on trending topics, and auto-schedules posts across LinkedIn, Twitter, and Instagram. Track engagement metrics and automatically optimize posting
