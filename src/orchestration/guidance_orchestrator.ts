import { NLULeadAgent } from '../nlu_agents/nlu_lead_agent';
import { AnalyticalAgent } from '../nlu_agents/analytical_agent';
import { CreativeAgent } from '../nlu_agents/creative_agent';
import { PracticalAgent } from '../nlu_agents/practical_agent';
import { SynthesizingAgent } from '../nlu_agents/synthesizing_agent';
import {
  SubAgentInput,
  EnrichedIntent,
  DEFAULT_MODEL_FOR_AGENTS,
} from '../nlu_agents/nlu_types';

import {
  LearningAndGuidanceSkill,
  LearningAndGuidanceInput,
  LearningAndGuidanceResult,
} from '../skills/learningAndGuidanceSkill';
import { MockLLMService, RealLLMService } from '../lib/llmUtils';

const mockLLM = new MockLLMService();

const realLLMServiceForAnalytical = new RealLLMService(
  process.env.LLM_API_KEY || 'YOUR_API_KEY_PLACEHOLDER',
  DEFAULT_MODEL_FOR_AGENTS
);
const analyticalAgent = new AnalyticalAgent(realLLMServiceForAnalytical);

const realLLMServiceForCreative = new RealLLMService(
  process.env.LLM_API_KEY || 'YOUR_API_KEY_PLACEHOLDER',
  DEFAULT_MODEL_FOR_AGENTS
);
const creativeAgent = new CreativeAgent(realLLMServiceForCreative);

const realLLMServiceForPractical = new RealLLMService(
  process.env.LLM_API_KEY || 'YOUR_API_KEY_PLACEHOLDER',
  DEFAULT_MODEL_FOR_AGENTS
);
const practicalAgent = new PracticalAgent(realLLMServiceForPractical);

const realLLMServiceForSynthesizing = new RealLLMService(
  process.env.LLM_API_KEY || 'YOUR_API_KEY_PLACEHOLDER',
  DEFAULT_MODEL_FOR_AGENTS
);
const synthesizingAgent = new SynthesizingAgent(realLLMServiceForSynthesizing);

const nluLeadAgent = new NLULeadAgent(
  analyticalAgent,
  creativeAgent,
  practicalAgent,
  synthesizingAgent
);

const learningAndGuidanceSkill = new LearningAndGuidanceSkill(mockLLM);

// --- Orchestration Logic ---

export interface OrchestratorResponse {
  messageToUser: string;
  guidanceResult?: LearningAndGuidanceResult;
  enrichedIntent?: EnrichedIntent; // For debugging or further use
}

/**
 * Processes a user query for learning and guidance,
 * first using NLULeadAgent, then potentially LearningAndGuidanceSkill.
 */
export async function processGuidanceRequest(
  originalQuery: string,
  userId: string,
  applicationContext?: string
): Promise<OrchestratorResponse> {
  console.log(
    `[GuidanceOrchestrator] Received query: "${originalQuery}" from user: ${userId}`
  );

  const subAgentInput: SubAgentInput = {
    userInput: originalQuery,
    userId: userId,
  };

  const enrichedIntent = await nluLeadAgent.analyzeIntent(subAgentInput);
  console.log(
    `[GuidanceOrchestrator] NLULeadAgent suggested action: ${enrichedIntent.suggestedNextAction?.actionType}`
  );
  console.log(
    `[GuidanceOrchestrator] NLULeadAgent primary goal: ${enrichedIntent.primaryGoal} (Confidence: ${enrichedIntent.primaryGoalConfidence?.toFixed(2)})`
  );

  // 2. Decide next step based on EnrichedIntent
  if (enrichedIntent.suggestedNextAction?.actionType === 'clarify_query') {
    return {
      messageToUser:
        enrichedIntent.suggestedNextAction.clarificationQuestion ||
        'I need more information to help you. Could you please rephrase?',
      enrichedIntent: enrichedIntent,
    };
  }

  if (
    enrichedIntent.suggestedNextAction?.actionType === 'invoke_skill' &&
    enrichedIntent.suggestedNextAction.skillId === 'BrowserAutomationSkill'
  ) {
    if (typeof window !== 'undefined' && window.__TAURI__) {
      console.log('[GuidanceOrchestrator] Invoking BrowserAutomationSkill.');
      // Placeholder for actually invoking the skill
      return {
        messageToUser: 'Browser automation skill invoked.',
        enrichedIntent: enrichedIntent,
      };
    } else {
      return {
        messageToUser: 'This feature is only available in the desktop app.',
        enrichedIntent: enrichedIntent,
      };
    }
  }

  if (
    enrichedIntent.suggestedNextAction?.actionType === 'invoke_skill' &&
    (enrichedIntent.suggestedNextAction.skillId ===
      'LearningAndGuidanceSkill' ||
      !enrichedIntent.suggestedNextAction.skillId)
  ) {
    console.log('[GuidanceOrchestrator] Invoking LearningAndGuidanceSkill.');

    // Prepare input for the LearningAndGuidanceSkill
    // We can use information from enrichedIntent to make this more targeted
    const skillInput: LearningAndGuidanceInput = {
      userId: userId,
      query: enrichedIntent.primaryGoal || originalQuery, // Use refined goal if available
      applicationContext: applicationContext,
      // Potentially use enrichedIntent.extractedParameters or identifiedTasks to refine skill input
      // e.g., if primaryGoal is "find_tutorial_for_pivot_tables"
      // guidanceTypeHint could be set here.
    };

    // If NLU already classified the guidance type, we can pass it as a hint
    if (
      enrichedIntent.primaryGoal?.toLowerCase().includes('tutorial') ||
      enrichedIntent.identifiedTasks?.some((t) => t.includes('tutorial'))
    ) {
      skillInput.guidanceTypeHint = 'find_tutorial';
    } else if (
      enrichedIntent.primaryGoal?.toLowerCase().includes('explain') ||
      enrichedIntent.primaryGoal?.toLowerCase().includes('explanation')
    ) {
      skillInput.guidanceTypeHint = 'general_explanation';
    }
    // etc. for other types based on primaryGoal or identifiedTasks

    try {
      const guidanceResult = await learningAndGuidanceSkill.execute(skillInput);
      // Ideally, the message to user would be constructed based on guidanceResult
      let friendlyMessage = `Here's what I found for "${originalQuery}":\n`;
      if (guidanceResult.guidanceProvided.length > 0) {
        guidanceResult.guidanceProvided.forEach((g) => {
          friendlyMessage += `\nTitle: ${g.title}\n`;
          if (g.contentSnippet)
            friendlyMessage += `Snippet: ${g.contentSnippet.substring(0, 100)}...\n`;
          if (g.steps) friendlyMessage += `${g.steps.length} steps found.\n`;
        });
      } else {
        friendlyMessage = `I couldn't find specific guidance for "${originalQuery}", but I'll keep learning!`;
      }
      if (
        guidanceResult.followUpSuggestions &&
        guidanceResult.followUpSuggestions.length > 0
      ) {
        friendlyMessage += `\n\nFollow-up suggestions: ${guidanceResult.followUpSuggestions.join(', ')}`;
      }

      return {
        messageToUser: friendlyMessage,
        guidanceResult: guidanceResult,
        enrichedIntent: enrichedIntent,
      };
    } catch (error: any) {
      console.error(
        '[GuidanceOrchestrator] Error executing LearningAndGuidanceSkill:',
        error
      );
      return {
        messageToUser: `Sorry, I encountered an error while trying to get guidance for "${originalQuery}". Error: ${error.message}`,
        enrichedIntent: enrichedIntent,
      };
    }
  }

  // Fallback for other action types or if the skill doesn't match
  let fallbackMessage = `I've analyzed your query: "${originalQuery}".\n`;
  fallbackMessage += `Goal: ${enrichedIntent.primaryGoal || 'Not clearly identified'}.\n`;
  if (
    enrichedIntent.suggestedNextAction?.actionType &&
    enrichedIntent.suggestedNextAction?.actionType !== 'unable_to_determine'
  ) {
    fallbackMessage += `Suggested next step: ${enrichedIntent.suggestedNextAction.actionType}`;
    if (enrichedIntent.suggestedNextAction.reason)
      fallbackMessage += ` (${enrichedIntent.suggestedNextAction.reason})`;
  } else {
    fallbackMessage +=
      "I'm not sure how to proceed with this specific request yet.";
  }

  return {
    messageToUser: fallbackMessage,
    enrichedIntent: enrichedIntent,
  };
}

// --- Example Test ---
/*
async function testOrchestrator() {
    console.log("--- Test Case 1: Pivot Table Query (Rule-based NLU) ---");
    let response = await processGuidanceRequest("How do I create a pivot table in SpreadsheetApp?", "user123", "SpreadsheetApp");
    console.log("Orchestrator Response:\n", response.messageToUser);
    // console.log("Full Enriched Intent:", JSON.stringify(response.enrichedIntent, null, 2));


    console.log("\\n--- Test Case 2: Vague 'Help me' Query (Rule-based NLU) ---");
    response = await processGuidanceRequest("Help me.", "user456");
    console.log("Orchestrator Response:\n", response.messageToUser);
    // console.log("Full Enriched Intent:", JSON.stringify(response.enrichedIntent, null, 2));


    console.log("\\n--- Test Case 3: Efficient Report Query (Rule-based NLU) ---");
    response = await processGuidanceRequest(
        "How can I make my Q3 marketing report generation more efficient, maybe using that new AI thing?",
        "user789",
        "MarketingSuite"
    );
    console.log("Orchestrator Response:\n", response.messageToUser);
    // console.log("Full Enriched Intent:", JSON.stringify(response.enrichedIntent, null, 2));

    // console.log("\\n--- Test Case 4: Efficient Report Query (Mock LLM-based NLU) ---");
    // response = await processGuidanceRequest(
    //     "How can I make my Q3 marketing report generation more efficient, maybe using that new AI thing?",
    //     "user789",
    //     "MarketingSuite",
    //     true // Enable LLM Synthesis for NLU
    // );
    // console.log("Orchestrator Response:\n", response.messageToUser);
    // console.log("Full Enriched Intent (LLM NLU):", JSON.stringify(response.enrichedIntent, null, 2));
}

// testOrchestrator();
*/

// --- Integration Test Runner ---
interface TestCase {
  description: string;
  query: string;
  userId: string;
  applicationContext?: string;
  useLLMSynthesis?: boolean;
  expectedResponseType:
    | 'clarification'
    | 'guidance_success'
    | 'fallback_info'
    | 'error';
  expectedMessageContains?: string | string[]; // Substring(s) expected in the messageToUser
  expectedGuidanceTitles?: string[]; // if guidance_success, check for these titles
}

async function runGuidanceOrchestratorTests() {
  console.log('\\n--- Starting GuidanceOrchestrator Tests ---');
  const testCases: TestCase[] = [
    {
      description: 'Test 1: Vague query, expecting clarification',
      query: 'Help me fix stuff.',
      userId: 'user-test-001',
      expectedResponseType: 'clarification',
      expectedMessageContains: 'I need more information',
    },
    {
      description:
        "Test 2: Specific 'how-to' query, expecting guidance success",
      query: 'How do I create a pivot table in SpreadsheetApp?',
      userId: 'user-test-002',
      applicationContext: 'SpreadsheetApp',
      expectedResponseType: 'guidance_success',
      expectedMessageContains: "Here's what I found",
      expectedGuidanceTitles: ['How to Create Pivot Tables in SpreadsheetApp'],
    },
    {
      description: 'Test 3: Complex query, expecting skill invocation',
      query:
        'my marketing report for Q3 is hard to do, how can AI make it efficient?',
      userId: 'user-test-003',
      applicationContext: 'MarketingSuite',
      expectedResponseType: 'fallback_info',
      expectedMessageContains: 'Suggested next step: invoke_skill',
    },
  ];

  let testsPassed = 0;
  for (const tc of testCases) {
    console.log(`\nRunning: ${tc.description}`);

    const response = await processGuidanceRequest(
      tc.query,
      tc.userId,
      tc.applicationContext
    );

    let pass = false;
    switch (tc.expectedResponseType) {
      case 'clarification':
        pass =
          response.messageToUser.toLowerCase().includes('clarify') ||
          response.messageToUser.toLowerCase().includes('more information') ||
          response.messageToUser.toLowerCase().includes('rephrase') ||
          response.messageToUser
            .toLowerCase()
            .includes('inconsistent or unclear');
        if (tc.expectedMessageContains) {
          const messages = Array.isArray(tc.expectedMessageContains)
            ? tc.expectedMessageContains
            : [tc.expectedMessageContains];
          pass =
            pass && messages.every((m) => response.messageToUser.includes(m));
        }
        break;
      case 'guidance_success':
        pass =
          !!response.guidanceResult &&
          response.guidanceResult.guidanceProvided.length > 0;
        if (pass && tc.expectedMessageContains) {
          const messages = Array.isArray(tc.expectedMessageContains)
            ? tc.expectedMessageContains
            : [tc.expectedMessageContains];
          pass =
            pass && messages.every((m) => response.messageToUser.includes(m));
        }
        if (pass && tc.expectedGuidanceTitles && response.guidanceResult) {
          pass =
            pass &&
            tc.expectedGuidanceTitles.every((title) =>
              response.guidanceResult?.guidanceProvided.some(
                (g) => g.title === title
              )
            );
        }
        break;
      case 'fallback_info': // For when NLU is good, but skill isn't the one we're testing deeply
        pass =
          !response.guidanceResult ||
          response.guidanceResult.guidanceProvided.length === 0;
        if (tc.expectedMessageContains) {
          const messages = Array.isArray(tc.expectedMessageContains)
            ? tc.expectedMessageContains
            : [tc.expectedMessageContains];
          pass =
            pass && messages.every((m) => response.messageToUser.includes(m));
        }
        break;
      case 'error':
        pass = response.messageToUser.toLowerCase().includes('error');
        break;
    }

    if (pass) {
      testsPassed++;
      console.log(`PASS: ${tc.description}`);
    } else {
      console.error(`FAIL: ${tc.description}`);
      console.log('  Expected response type:', tc.expectedResponseType);
      if (tc.expectedMessageContains)
        console.log('  Expected message contains:', tc.expectedMessageContains);
      console.log('  Actual messageToUser:', response.messageToUser);
      if (tc.expectedResponseType === 'guidance_success')
        console.log(
          '  Actual guidanceResult:',
          JSON.stringify(response.guidanceResult, null, 2).substring(0, 300) +
            '...'
        );
    }
    console.log(
      '  NLU Primary Goal:',
      response.enrichedIntent?.primaryGoal,
      '(Confidence:',
      response.enrichedIntent?.primaryGoalConfidence?.toFixed(2),
      ')'
    );
    console.log(
      '  NLU Suggested Action:',
      response.enrichedIntent?.suggestedNextAction?.actionType,
      'Reason:',
      response.enrichedIntent?.suggestedNextAction?.reason
    );
  }

  console.log(`\n--- GuidanceOrchestrator Tests Complete ---`);
  console.log(`${testsPassed}/${testCases.length} test cases passed.`);
  if (testsPassed === testCases.length) {
    console.log('All tests passed successfully!');
    return true;
  } else {
    console.error(`${testCases.length - testsPassed} test(s) failed.`);
    return false;
  }
}

// To run tests:
// runGuidanceOrchestratorTests();

console.log(
  'GuidanceOrchestrator loaded. Call runGuidanceOrchestratorTests() to run integration tests.'
);
