#!/usr/bin/env ts-node

import * as process from 'process';
import { initializeMeetingPrepScheduler } from './atom-agent/meetingPrepScheduler';
import { handleMeetingPreparationRequest } from './atom-agent/command_handlers/meetingPrepCommandHandler';
import { handleGetDailyBriefingRequest } from './atom-agent/command_handlers/dailyBriefingCommandHandler';
import { handleMessage } from './atom-agent/handler';
import { logger } from './atom-agent/_utils/logger';

async function testLLMSchedulingIntegration() {
  console.log('🔍 LLM Scheduling Integration Test Suite');
  console.log('========================================\n');

  const testUserId = process.env.TEST_USER_ID || 'test_integration_user';
  const mockMlContext = {
    userId: testUserId,
    isTest: true
  };

  const tests = [
    {
      name: 'Enhanced Meeting Prep Scheduler',
      test: async () => {
        console.log('  📅 Initializing scheduler with LLM capabilities...');
        await initializeMeetingPrepScheduler();
        return '✅ Scheduler initialized with intelligent meeting prep';
      }
    },
    {
      name: 'Single Meeting Preparation',
      test: async () => {
        console.log('  🎯 Testing meeting prep generation...');
        const result = await handleMeetingPreparationRequest(testUserId, {
          meeting_reference: 'Q4 planning meeting with investors',
          specific_focus_areas: ['investor backgrounds', 'agenda prep', 'recent emails'],
          context_type: 'investor-presentation'
        });
        const success = result.includes('gathered some information') || result.includes('found');
        return success ? '✅ Meeting prep generated successfully' : '❌ Failed to generate meeting prep';
      }
    },
    {
      name: 'Daily Briefing Generation',
      test: async () => {
        console.log('  📊 Testing daily briefing system...');
        const result = await handleGetDailyBriefingRequest(testUserId, {
          date_context: 'today',
          include_productivity_insights: true,
          include_meeting_context: true
        });
        const hasData = result && result.hasOwnProperty('priority_items');
        return hasData ? '✅ Daily briefing generated successfully' : '❌ Failed to generate briefing';
      }
    },
    {
      name: 'Atom Agent Integration',
      test: async () => {
        console.log('  🤖 Testing Atom Agent handler integration...');
        const result = await handleMessage('Prepare for my client meeting tomorrow at 2pm', {
          userId: testUserId
        });
        const success = result.hasOwnProperty('text') && !result.error;
        return success ? '✅ Atom Agent handler working correctly' : '❌ Atom Agent handler failed';
      }
    }
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    try {
      console.log(`\n🧪 Running test: ${test.name}`);
      const result = await test.test();
      console.log(`   ${result}`);
      if (result.startsWith('✅')) {
        passed++;
      } else {
        failed++;
      }
    } catch (error) {
      console.error(`   ❌ Test failed: ${error}`);
      failed++;
    }
  }

  console.log('\n' + '='.repeat(50));
  console.log(`📈 Test Results: ${passed} passed, ${failed} failed`);
  console.log('='.repeat(50));

  if (failed === 0) {
    console.log('🎉 All LLM scheduling integration tests PASSED!');
    console.log('\n📋 Quick Usage Examples:');
    console.log('   • "Prepare for my investor meeting tomorrow"');
    console.log('   • "Generate my daily briefing for today"');
    console.log('   • Atom Agent will auto-schedule prep for important meetings');
    process.exit(0);
  } else {
    console.error('💥 Some integration tests FAILED!');
    process.exit(1);
  }
}

// Run if executed directly
if (require.main === module) {
  testLLMSchedulingIntegration()
    .catch(console.error);
}

export { testLLMSchedulingIntegration };
