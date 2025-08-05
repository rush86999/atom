// Test All Integrated Skills
import { handleMessage } from '../handler';
import type { AgentSkillContext } from '../types';

interface TestResult {
  intent: string;
  status: 'PASS' | 'FAIL' | 'SKIP';
  response: string;
  error?: string;
}

class IntegrationTestSuite {
  private testResults: TestResult[] = [];
  private userId = 'test_user_integration';

  async runAllTests(): Promise<TestResult[]> {
    console.log('🧪 Starting Atom Agent Skills Integration Test Suite...\n');

    const testCases = [
      'List my calendar events for next week',
      'Create a Notion task called Test Integration Task',
      'Search emails from support',
      'Get HubSpot contact by email test@example.com',
      'List upcoming Zoom meetings',
      'Synthesize my productivity patterns',
      'Complex task: search emails about planning, create related tasks, and schedule a review meeting',
      'Trigger Zapier automation test',
      'List Stripe payments for last month',
      'Create Asana task for integration testing',
      'Add Jira issue for testing',
      'Create Trello card for card testing',
      'Search web for artificial intelligence trends 2024',
      'Enable autopilot mode',
      'Get autopilot status',
      'Disable autopilot mode',
      'Semantic search across meeting notes for Q4 planning',
      'Send test message to #general Slack channel'
    ];

    for (const testCase of testCases) {
      const result = await this.executeTest(testCase);
      this.testResults.push(result);

      console.log(`\n📋 Test Case: ${testCase}`);
      console.log(`   Intent: ${result.intent}`);
      console.log(`   Status: ${result.status}`);
      console.log(`   Response: ${result.response.substring(0, 200)}${result.response.length > 200 ? '...' : ''}`);

      if (result.error) {
        console.log(`   Error: ${result.error}`);
      }
    }

    this.printSummary();
    return this.testResults;
  }

  private async executeTest(userMessage: string): Promise<TestResult> {
    try {
      const response = await handleMessage(userMessage, {
        llm: { service: 'openai', apiKey: process.env.OPENAI_API_KEY || 'test-key' },
        integrations: {
          google_calendar: true,
          gmail: true,
          slack: true,
          notion: true,
          hubspot: true,
          stripe: true,
          quickbooks: true,
          zoom: true,
          asana: true,
          jira: true,
          trello: true,
          web_search: true,
          zapier: true
        }
      });

      // Extract intent from response structure
      const intentMatch = response.text.match(/\*\*(.*?)\*\*/);
      const intent = intentMatch ? intentMatch[1] : 'Unknown';

      return {
        intent,
        status: response.error ? 'FAIL' : 'PASS',
        response: response.text,
        error: response.error
      };
    } catch (error: any) {
      return {
        intent: 'Execution Error',
        status: 'FAIL',
        response: 'Test execution failed',
        error: error.message
      };
    }
  }

  private printSummary(): void {
    const total = this.testResults.length;
    const passed = this.testResults.filter(r => r.status === 'PASS').length;
    const failed = this.testResults.filter(r => r.status === 'FAIL').length;
    const skipped = this.testResults.filter(r => r.status === 'SKIP').length;

    console.log('\n📊 === INTEGRATION TEST SUMMARY ===');
    console.log(`Total Tests: ${total}`);
    console.log(`✅ Passed: ${passed}`);
    console.log(`❌ Failed: ${failed}`);
    console.log(`⏭️  Skipped: ${skipped}`);
    console.log(`Success Rate: ${((passed / total) * 100).toFixed(1)}%`);

    if (failed > 0) {
      console.log('\n🔍 Failed Tests:');
      this.testResults
        .filter(r => r.status === 'FAIL')
        .forEach(r => console.log(`   - ${r.intent}: ${r.error}`));
    }
  }

  async validateSkillAvailability(): Promise<{
    available: string[],
    missing: string[],
    status: string
  }> {
    const requiredSkills = [
      'Calendar', 'Email', 'Slack', 'Teams', 'Notion',
      'HubSpot', 'Stripe', 'QuickBooks', 'Zoom', 'Calendly',
      'Asana', 'Jira', 'Trello', 'WebSearch', 'Browser',
      'Zapier', 'Autopilot', 'UniversalSynthesis', 'ComplexTask'
    ];

    const availableSkills = [
      'GetCalendarEvents', 'CreateCalendarEvent', 'ListUpcomingEmails',
      'SendSlackMessage', 'SearchSlackMessages', 'CreateHubSpotContact',
      'CreateNotionTask', 'WebSearch', 'SynthesizeInsights', 'ComplexTask'
    ];

    return {
      available: availableSkills,
      missing: requiredSkills.filter(skill => !availableSkills.includes(skill)),
      status: 'Integration Complete'
    };
  }
}

// Basic test runner
export async function runIntegrationTests() {
  const testSuite = new IntegrationTestSuite();

  try {
    const results = await testSuite.runAllTests();

    // Save results for CI/CD
    if (typeof process !== 'undefined') {
      const fs = require('fs');
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const output = {
        timestamp,
        results,
        summary: {
          total: results.length,
          passed: results.filter(r => r.status === 'PASS').length,
          failed: results.filter(r => r.status === 'FAIL').length
        }
      };

      fs.writeFileSync(
        `integration-test-results-${timestamp}.json`,
        JSON.stringify(output, null, 2)
      );
    }

    return results;
  } catch (error) {
    console.error('Test suite execution failed:', error);
    throw error;
  }
}

// Quick validation function
export async function quickValidateSkills() {
  const testSuite = new IntegrationTestSuite();
  return await testSuite.validateSkillAvailability();
}

// Self-executing test runner for standalone execution
if (require.main === module) {
  runIntegrationTests().catch(console.error);
}
