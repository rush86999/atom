<></file_path>

<file_path>
atom/src/nlu_agents/examples/llm-integration-example.ts
</file_path>

import { SmallBusinessLLMTranslator } from '../smallBusinessLLMTranslator';
import { IntegratedAgent } from '../integratedAgent';

/**
 * LLM-Powered Small Business Conversation Translation Examples
 *
 * This demonstrates how small business owners can use natural language
 * to create sophisticated autonomous workflows via LLM translation
 */

interface TestResult {
  input: string;
  translatedCommand: any;
  setupInstructions: string[];
  confidence: number;
  businessContext: any;
}

class LLMIntegrationDemo {
  private translator = new SmallBusinessLLMTranslator();
  private agent = new IntegratedAgent(null, null, {}, {}); // Mock integration

  async demonstrateConversations() {
    console.log('🎯 LLM-Powered Conversation Translation for Small Businesses\n');

    const testCases = [
      {
        user: "coffee_shop_owner",
        message: "I spend too much time dealing with receipts from supplier payments and equipment purchases, can I automate this somehow?",
        context: { industry: 'cafe', size: 'solo', budget: 25, techSkill: 'beginner' }
      },

      {
        user: "freelance_designer",
        message: "My clients always forget their appointments and it's costing me money, need something to reduce no-shows",
        context: { industry: 'design', size: 'solo', budget: 15, techSkill: 'intermediate' }
      },

      {
        user: "retail_owner",
        message: "Want to keep my social media active but don't have hours to post everywhere every day",
        context: { industry: 'retail', size: '2-5', budget: 30, techSkill: 'beginner' }
      },

      {
        user: "consultant",
        message: "Looking for a way to automatically qualify leads from my website contact forms and only book serious prospects",
        context: { industry: 'consulting', size: 'solo', budget: 40, techSkill: 'intermediate' }
      }
    ];

    for (const testCase of testCases) {
      await this.testBusinessCase(testCase);
    }
  }

  async testBusinessCase(test: any): Promise<TestResult> {
    console.log(`\n👤 ${test.context.industry.toUpperCase()} BUSINESS`);
    console.log(`Input: "${test.message}"`);

    const result = await this.translator.translateToWorkflowCommand(
      test.message,
      test.user,
      { businessContext: test.context }
    );

    this.displayResult(result);
    return {
      input: test.message,
      translatedCommand: result.command,
      setupInstructions: result.setupInstructions,
      confidence: result.confidence,
      businessContext: test.context
    };
  }

  private displayResult(result: any): void {
    console.log('\n📊 LLM TRANSLATION RESULTS:');
    console.log(`   Goal: ${result.command.businessGoal}`);
    console.log(`   Type: ${result.command.workflowCategory}`);
    console.log(`   Complexity: ${result.command.specificRequirements.technicalComplexity}`);
    console.log(`   Cost: ${result.command.specificRequirements.maxCost}`);
    console.log(`   Setup Time: ${result.timeline}`);

    console.log(`\n   Setup Instructions:`);
    result.setupInstructions.forEach((step: string, i: number) => {
      console.log(`   ${i + 1}. ${step}`);
    });

    console.log(`\n   Benefit: ${result.estimatedImpact}`);
    console.log(`   Risk: ${result.riskLevel}`);
    console.log(`   Confidence: ${(result.confidence * 100).toFixed(0)}%`);
  }

  // Real-world conversation flows
  async demonstrateRealConversations() {
    console.log('\n🔥 REAL CONVERSATIONS WITH SMALL BUSINESS OWNERS:\n');

    const conversations = [
      {
        user: "Maria's Bakery",
        messages: [
          "I'm drowning in receipts every month",
          "What exactly does it cost and will it work with my phone?",
          "Let's try it, how do I start?",
          "My accountant uses QuickBooks, can it sync there?"
        ]
      },

      {
        user: "Tech Consulting Startup",
        messages: [
          "Getting too many unqualified leads wasting my time",
          "How sophisticated is the qualification?",
          "Can it prioritize startups with funding over individuals?",
          "Walk me through the setup process"
        ]
      }
    ];

    let sessionId = 'demo_session_123';

    for (const convo of conversations) {
      console.log(`\n💬 ${convo.user}`);

      for (const message of convo.messages) {
        const result = await this.translator.translateToWorkflowCommand(
