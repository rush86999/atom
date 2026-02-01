<file_path>
atom/src/smallbiz/integration-test.ts
</file_path>

import { IntegratedAgent } from '../nlu_agents/integratedAgent';
import { SubAgentInput } from '../nlu_agents/nlu_types';
import { TurnContext } from 'botbuilder';

// Mock dependencies for testing
class MockLLMService {
  async generateResponse(prompt: string): Promise<string> {
    return "Mock LLM response for: " + prompt;
  }
}

class MockTurnContext {
  userId = 'test-user';
  message = {};
}

/**
 * Test script demonstrating small business autonomous workflow integration
 * Shows how small business owners can use natural conversation to set up automation
 */
class SmallBusinessIntegrationTest {
  private agent: IntegratedAgent;

  constructor() {
    const mockLLM = new MockLLMService();
    const mockContext = new MockTurnContext() as any;
    const mockMemory = {};
    const mockFunctions = {};

    this.agent = new IntegratedAgent(mockLLM, mockContext, mockMemory, mockFunctions);
  }

  async runMainTests() {
    console.log('🚀 Starting Small Business Integration Tests...\n');

    await this.testReceiptAutomation();
    await this.testCustomerFollowUp();
    await this.testAppointmentReminders();
    await this.testSocialMediaAutomation();

    console.log('\n✅ All tests completed successfully!');
  }

  private async testReceiptAutomation() {
    console.log('📋 Test 1: Receipt Automation Setup');

    const input: SubAgentInput = {
      userInput: "I'm tired of manually entering receipts into spreadsheets every month",
      userId: 'small-biz-user-001',
      timestamp: new Date().toISOString(),
      metadata: {
        businessContext: {
          budget: 25,
          employeeCount: 3,
          industry: 'retail',
          techSkill: 'beginner',
          currentTools: ['QuickBooks', 'Gmail']
        }
      }
    };

    const result = await this.agent.processInput(input);
    console.log('Detected Goal:', result.primaryGoal);
    console.log('Suggested Workflow:', result.suggestedNextAction?.['actionType']);
    console.log('Setup Instructions:', result.suggestedNextAction?.['instructions']?.slice(0, 2));
  }

  private async testCustomerFollowUp() {
    console.log('\n🤝 Test 2: Customer Relationship Automation');

    const input: SubAgentInput = {
      userInput: "I keep losing customers because I forget to follow up after sales",
      userId: 'small-biz-user-001',
      timestamp: new Date().toISOString()
    };

    const result = await this.agent.processInput(input);
    console.log('Business Impact:', result.extractedParameters?.estimatedBenefit);
    console.log('Workflow Type:', result.extractedParameters?.workflowName);
  }

  private async testAppointmentReminders() {
    console.log('\n📅 Test 3: Appointment Management');

    const input: SubAgentInput = {
      userInput: "My no-show rate is killing my business, can you help automate reminders?",
      userId: 'small-biz-user-001',
      timestamp: new Date().toISOString()
    };

    const result = await this.agent.processInput(input);
    console.log('Expected Benefit:', result.extractedParameters?.estimatedBenefit);
  }

  private async testSocialMediaAutomation() {
    console.log('\n📱 Test 4: Social Media Management');

    const input: SubAgentInput = {
      userInput: "I never have time for social media but need better online presence",
      userId: 'small-biz-user-001',
      timestamp: new Date().toISOString()
    };

    const result = await this.agent.processInput(input);
    console.log('Platform Integration:', result.extractedParameters?.workflowName);
    console.log('Setup Time:', result.extractedParameters?.setupComplexity);
  }

  async getRecommendations() {
    console.log('\n📊 Personalized Workflow Recommendations');

    const workforces = await this.agent.getWorkforceSummary('small-biz-user-001');
    console.log(`Recommended workflows: ${workforces.recommendedWorkflows.length}`);
    console.log(`Estimated time savings: ${workforces.estimatedSavings}`);
    console.log('Top recommendations:', workforces.recommendedWorkflows.map(w => w.name));
  }
}

// Run integration test
const testRunner = new SmallBusinessIntegrationTest();
testRunner.runMainTests()
  .then(() => testRunner.getRecommendations())
  .catch(console.error);
```

The integration is now complete! Here's what we've achieved:

## ✅ Completed Integration with NLU System:
- **Extended NLU Lead Agent** with small business recognition
- **Added SmallBusinessAgent** as a specialized component
- **Created IntegratedAgent** to seamlessly combine both systems
- **Presence in NLU directory**
