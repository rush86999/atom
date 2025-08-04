"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.processGuidanceRequest = processGuidanceRequest;
const nlu_lead_agent_1 = require("../nlu_agents/nlu_lead_agent");
const analytical_agent_1 = require("../nlu_agents/analytical_agent");
const creative_agent_1 = require("../nlu_agents/creative_agent");
const practical_agent_1 = require("../nlu_agents/practical_agent");
const synthesizing_agent_1 = require("../nlu_agents/synthesizing_agent");
const nlu_types_1 = require("../nlu_agents/nlu_types");
const learningAndGuidanceSkill_1 = require("../skills/learningAndGuidanceSkill");
const llmUtils_1 = require("../lib/llmUtils");
const mockLLM = new llmUtils_1.MockLLMService();
const realLLMServiceForAnalytical = new llmUtils_1.RealLLMService(process.env.LLM_API_KEY || 'YOUR_API_KEY_PLACEHOLDER', nlu_types_1.DEFAULT_MODEL_FOR_AGENTS);
const analyticalAgent = new analytical_agent_1.AnalyticalAgent(realLLMServiceForAnalytical);
const realLLMServiceForCreative = new llmUtils_1.RealLLMService(process.env.LLM_API_KEY || 'YOUR_API_KEY_PLACEHOLDER', nlu_types_1.DEFAULT_MODEL_FOR_AGENTS);
const creativeAgent = new creative_agent_1.CreativeAgent(realLLMServiceForCreative);
const realLLMServiceForPractical = new llmUtils_1.RealLLMService(process.env.LLM_API_KEY || 'YOUR_API_KEY_PLACEHOLDER', nlu_types_1.DEFAULT_MODEL_FOR_AGENTS);
const practicalAgent = new practical_agent_1.PracticalAgent(realLLMServiceForPractical);
const realLLMServiceForSynthesizing = new llmUtils_1.RealLLMService(process.env.LLM_API_KEY || 'YOUR_API_KEY_PLACEHOLDER', nlu_types_1.DEFAULT_MODEL_FOR_AGENTS);
const synthesizingAgent = new synthesizing_agent_1.SynthesizingAgent(realLLMServiceForSynthesizing);
const nluLeadAgent = new nlu_lead_agent_1.NLULeadAgent(analyticalAgent, creativeAgent, practicalAgent, synthesizingAgent);
const learningAndGuidanceSkill = new learningAndGuidanceSkill_1.LearningAndGuidanceSkill(mockLLM);
/**
 * Processes a user query for learning and guidance,
 * first using NLULeadAgent, then potentially LearningAndGuidanceSkill.
 */
async function processGuidanceRequest(originalQuery, userId, applicationContext) {
    console.log(`[GuidanceOrchestrator] Received query: "${originalQuery}" from user: ${userId}`);
    const subAgentInput = {
        userInput: originalQuery,
        userId: userId,
    };
    const enrichedIntent = await nluLeadAgent.analyzeIntent(subAgentInput);
    console.log(`[GuidanceOrchestrator] NLULeadAgent suggested action: ${enrichedIntent.suggestedNextAction?.actionType}`);
    console.log(`[GuidanceOrchestrator] NLULeadAgent primary goal: ${enrichedIntent.primaryGoal} (Confidence: ${enrichedIntent.primaryGoalConfidence?.toFixed(2)})`);
    // 2. Decide next step based on EnrichedIntent
    if (enrichedIntent.suggestedNextAction?.actionType === 'clarify_query') {
        return {
            messageToUser: enrichedIntent.suggestedNextAction.clarificationQuestion ||
                'I need more information to help you. Could you please rephrase?',
            enrichedIntent: enrichedIntent,
        };
    }
    if (enrichedIntent.suggestedNextAction?.actionType === 'invoke_skill' &&
        enrichedIntent.suggestedNextAction.skillId === 'BrowserAutomationSkill') {
        if (typeof window !== 'undefined' && window.__TAURI__) {
            console.log('[GuidanceOrchestrator] Invoking BrowserAutomationSkill.');
            // Placeholder for actually invoking the skill
            return {
                messageToUser: 'Browser automation skill invoked.',
                enrichedIntent: enrichedIntent,
            };
        }
        else {
            return {
                messageToUser: 'This feature is only available in the desktop app.',
                enrichedIntent: enrichedIntent,
            };
        }
    }
    if (enrichedIntent.suggestedNextAction?.actionType === 'invoke_skill' &&
        (enrichedIntent.suggestedNextAction.skillId ===
            'LearningAndGuidanceSkill' ||
            !enrichedIntent.suggestedNextAction.skillId)) {
        console.log('[GuidanceOrchestrator] Invoking LearningAndGuidanceSkill.');
        // Prepare input for the LearningAndGuidanceSkill
        // We can use information from enrichedIntent to make this more targeted
        const skillInput = {
            userId: userId,
            query: enrichedIntent.primaryGoal || originalQuery, // Use refined goal if available
            applicationContext: applicationContext,
            // Potentially use enrichedIntent.extractedParameters or identifiedTasks to refine skill input
            // e.g., if primaryGoal is "find_tutorial_for_pivot_tables"
            // guidanceTypeHint could be set here.
        };
        // If NLU already classified the guidance type, we can pass it as a hint
        if (enrichedIntent.primaryGoal?.toLowerCase().includes('tutorial') ||
            enrichedIntent.identifiedTasks?.some((t) => t.includes('tutorial'))) {
            skillInput.guidanceTypeHint = 'find_tutorial';
        }
        else if (enrichedIntent.primaryGoal?.toLowerCase().includes('explain') ||
            enrichedIntent.primaryGoal?.toLowerCase().includes('explanation')) {
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
                    if (g.steps)
                        friendlyMessage += `${g.steps.length} steps found.\n`;
                });
            }
            else {
                friendlyMessage = `I couldn't find specific guidance for "${originalQuery}", but I'll keep learning!`;
            }
            if (guidanceResult.followUpSuggestions &&
                guidanceResult.followUpSuggestions.length > 0) {
                friendlyMessage += `\n\nFollow-up suggestions: ${guidanceResult.followUpSuggestions.join(', ')}`;
            }
            return {
                messageToUser: friendlyMessage,
                guidanceResult: guidanceResult,
                enrichedIntent: enrichedIntent,
            };
        }
        catch (error) {
            console.error('[GuidanceOrchestrator] Error executing LearningAndGuidanceSkill:', error);
            return {
                messageToUser: `Sorry, I encountered an error while trying to get guidance for "${originalQuery}". Error: ${error.message}`,
                enrichedIntent: enrichedIntent,
            };
        }
    }
    // Fallback for other action types or if the skill doesn't match
    let fallbackMessage = `I've analyzed your query: "${originalQuery}".\n`;
    fallbackMessage += `Goal: ${enrichedIntent.primaryGoal || 'Not clearly identified'}.\n`;
    if (enrichedIntent.suggestedNextAction?.actionType &&
        enrichedIntent.suggestedNextAction?.actionType !== 'unable_to_determine') {
        fallbackMessage += `Suggested next step: ${enrichedIntent.suggestedNextAction.actionType}`;
        if (enrichedIntent.suggestedNextAction.reason)
            fallbackMessage += ` (${enrichedIntent.suggestedNextAction.reason})`;
    }
    else {
        fallbackMessage +=
            "I'm not sure how to proceed with this specific request yet.";
    }
    return {
        messageToUser: fallbackMessage,
        enrichedIntent: enrichedIntent,
    };
}
async function runGuidanceOrchestratorTests() {
    console.log('\\n--- Starting GuidanceOrchestrator Tests ---');
    const testCases = [
        {
            description: 'Test 1: Vague query, expecting clarification',
            query: 'Help me fix stuff.',
            userId: 'user-test-001',
            expectedResponseType: 'clarification',
            expectedMessageContains: 'I need more information',
        },
        {
            description: "Test 2: Specific 'how-to' query, expecting guidance success",
            query: 'How do I create a pivot table in SpreadsheetApp?',
            userId: 'user-test-002',
            applicationContext: 'SpreadsheetApp',
            expectedResponseType: 'guidance_success',
            expectedMessageContains: "Here's what I found",
            expectedGuidanceTitles: ['How to Create Pivot Tables in SpreadsheetApp'],
        },
        {
            description: 'Test 3: Complex query, expecting skill invocation',
            query: 'my marketing report for Q3 is hard to do, how can AI make it efficient?',
            userId: 'user-test-003',
            applicationContext: 'MarketingSuite',
            expectedResponseType: 'fallback_info',
            expectedMessageContains: 'Suggested next step: invoke_skill',
        },
    ];
    let testsPassed = 0;
    for (const tc of testCases) {
        console.log(`\nRunning: ${tc.description}`);
        const response = await processGuidanceRequest(tc.query, tc.userId, tc.applicationContext);
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
                            tc.expectedGuidanceTitles.every((title) => response.guidanceResult?.guidanceProvided.some((g) => g.title === title));
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
        }
        else {
            console.error(`FAIL: ${tc.description}`);
            console.log('  Expected response type:', tc.expectedResponseType);
            if (tc.expectedMessageContains)
                console.log('  Expected message contains:', tc.expectedMessageContains);
            console.log('  Actual messageToUser:', response.messageToUser);
            if (tc.expectedResponseType === 'guidance_success')
                console.log('  Actual guidanceResult:', JSON.stringify(response.guidanceResult, null, 2).substring(0, 300) +
                    '...');
        }
        console.log('  NLU Primary Goal:', response.enrichedIntent?.primaryGoal, '(Confidence:', response.enrichedIntent?.primaryGoalConfidence?.toFixed(2), ')');
        console.log('  NLU Suggested Action:', response.enrichedIntent?.suggestedNextAction?.actionType, 'Reason:', response.enrichedIntent?.suggestedNextAction?.reason);
    }
    console.log(`\n--- GuidanceOrchestrator Tests Complete ---`);
    console.log(`${testsPassed}/${testCases.length} test cases passed.`);
    if (testsPassed === testCases.length) {
        console.log('All tests passed successfully!');
        return true;
    }
    else {
        console.error(`${testCases.length - testsPassed} test(s) failed.`);
        return false;
    }
}
// To run tests:
// runGuidanceOrchestratorTests();
console.log('GuidanceOrchestrator loaded. Call runGuidanceOrchestratorTests() to run integration tests.');
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ3VpZGFuY2Vfb3JjaGVzdHJhdG9yLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ3VpZGFuY2Vfb3JjaGVzdHJhdG9yLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBaUVBLHdEQTZJQztBQTlNRCxpRUFBNEQ7QUFDNUQscUVBQWlFO0FBQ2pFLGlFQUE2RDtBQUM3RCxtRUFBK0Q7QUFDL0QseUVBQXFFO0FBQ3JFLHVEQUlpQztBQUVqQyxpRkFJNEM7QUFDNUMsOENBQWlFO0FBRWpFLE1BQU0sT0FBTyxHQUFHLElBQUkseUJBQWMsRUFBRSxDQUFDO0FBRXJDLE1BQU0sMkJBQTJCLEdBQUcsSUFBSSx5QkFBYyxDQUNwRCxPQUFPLENBQUMsR0FBRyxDQUFDLFdBQVcsSUFBSSwwQkFBMEIsRUFDckQsb0NBQXdCLENBQ3pCLENBQUM7QUFDRixNQUFNLGVBQWUsR0FBRyxJQUFJLGtDQUFlLENBQUMsMkJBQTJCLENBQUMsQ0FBQztBQUV6RSxNQUFNLHlCQUF5QixHQUFHLElBQUkseUJBQWMsQ0FDbEQsT0FBTyxDQUFDLEdBQUcsQ0FBQyxXQUFXLElBQUksMEJBQTBCLEVBQ3JELG9DQUF3QixDQUN6QixDQUFDO0FBQ0YsTUFBTSxhQUFhLEdBQUcsSUFBSSw4QkFBYSxDQUFDLHlCQUF5QixDQUFDLENBQUM7QUFFbkUsTUFBTSwwQkFBMEIsR0FBRyxJQUFJLHlCQUFjLENBQ25ELE9BQU8sQ0FBQyxHQUFHLENBQUMsV0FBVyxJQUFJLDBCQUEwQixFQUNyRCxvQ0FBd0IsQ0FDekIsQ0FBQztBQUNGLE1BQU0sY0FBYyxHQUFHLElBQUksZ0NBQWMsQ0FBQywwQkFBMEIsQ0FBQyxDQUFDO0FBRXRFLE1BQU0sNkJBQTZCLEdBQUcsSUFBSSx5QkFBYyxDQUN0RCxPQUFPLENBQUMsR0FBRyxDQUFDLFdBQVcsSUFBSSwwQkFBMEIsRUFDckQsb0NBQXdCLENBQ3pCLENBQUM7QUFDRixNQUFNLGlCQUFpQixHQUFHLElBQUksc0NBQWlCLENBQUMsNkJBQTZCLENBQUMs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QUFFLG1CQUFtQixFQUFFLE1BQU0sQ0FDckQsQ0FBQztJQUNKLENBQUM7SUFFRCxPQUFPLENBQUMsR0FBRyxDQUFDLCtDQUErQyxDQUFDLENBQUM7SUFDN0QsT0FBTyxDQUFDLEdBQUcsQ0FBQyxHQUFHLFdBQVcsSUFBSSxTQUFTLENBQUMsTUFBTSxxQkFBcUIsQ0FBQyxDQUFDO0lBQ3JFLElBQUksV0FBVyxLQUFLLFNBQVMsQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUNyQyxPQUFPLENBQUMsR0FBRyxDQUFDLGdDQUFnQyxDQUFDLENBQUM7UUFDOUMsT0FBTyxJQUFJLENBQUM7SUFDZCxDQUFDO1NBQU0sQ0FBQztRQUNOLE9BQU8sQ0FBQyxLQUFLLENBQUMsR0FBRyxTQUFTLENBQUMsTUFBTSxHQUFHLFdBQVcsa0JBQWtCLENBQUMsQ0FBQztRQUNuRSxPQUFPLEtBQUssQ0FBQztJQUNmLENBQUM7QUFDSCxDQUFDO0FBRUQsZ0JBQWdCO0FBQ2hCLGtDQUFrQztBQUVsQyxPQUFPLENBQUMsR0FBRyxDQUNULDRGQUE0RixDQUM3RixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgTkxVTGVhZEFnZW50IH0gZnJvbSAnLi4vbmx1X2FnZW50cy9ubHVfbGVhZF9hZ2VudCc7XG5pbXBvcnQgeyBBbmFseXRpY2FsQWdlbnQgfSBmcm9tICcuLi9ubHVfYWdlbnRzL2FuYWx5dGljYWxfYWdlbnQnO1xuaW1wb3J0IHsgQ3JlYXRpdmVBZ2VudCB9IGZyb20gJy4uL25sdV9hZ2VudHMvY3JlYXRpdmVfYWdlbnQnO1xuaW1wb3J0IHsgUHJhY3RpY2FsQWdlbnQgfSBmcm9tICcuLi9ubHVfYWdlbnRzL3ByYWN0aWNhbF9hZ2VudCc7XG5pbXBvcnQgeyBTeW50aGVzaXppbmdBZ2VudCB9IGZyb20gJy4uL25sdV9hZ2VudHMvc3ludGhlc2l6aW5nX2FnZW50JztcbmltcG9ydCB7XG4gIFN1YkFnZW50SW5wdXQsXG4gIEVucmljaGVkSW50ZW50LFxuICBERUZBVUxUX01PREVMX0ZPUl9BR0VOVFMsXG59IGZyb20gJy4uL25sdV9hZ2VudHMvbmx1X3R5cGVzJztcblxuaW1wb3J0IHtcbiAgTGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsLFxuICBMZWFybmluZ0FuZEd1aWRhbmNlSW5wdXQsXG4gIExlYXJuaW5nQW5kR3VpZGFuY2VSZXN1bHQsXG59IGZyb20gJy4uL3NraWxscy9sZWFybmluZ0FuZEd1aWRhbmNlU2tpbGwnO1xuaW1wb3J0IHsgTW9ja0xMTVNlcnZpY2UsIFJlYWxMTE1TZXJ2aWNlIH0gZnJvbSAnLi4vbGliL2xsbVV0aWxzJztcblxuY29uc3QgbW9ja0xMTSA9IG5ldyBNb2NrTExNU2VydmljZSgpO1xuXG5jb25zdCByZWFsTExNU2VydmljZUZvckFuYWx5dGljYWwgPSBuZXcgUmVhbExMTVNlcnZpY2UoXG4gIHByb2Nlc3MuZW52LkxMTV9BUElfS0VZIHx8ICdZT1VSX0FQSV9LRVlfUExBQ0VIT0xERVInLFxuICBERUZBVUxUX01PREVMX0ZPUl9BR0VOVFNcbik7XG5jb25zdCBhbmFseXRpY2FsQWdlbnQgPSBuZXcgQW5hbHl0aWNhbEFnZW50KHJlYWxMTE1TZXJ2aWNlRm9yQW5hbHl0aWNhbCk7XG5cbmNvbnN0IHJlYWxMTE1TZXJ2aWNlRm9yQ3JlYXRpdmUgPSBuZXcgUmVhbExMTVNlcnZpY2UoXG4gIHByb2Nlc3MuZW52LkxMTV9BUElfS0VZIHx8ICdZT1VSX0FQSV9LRVlfUExBQ0VIT0xERVInLFxuICBERUZBVUxUX01PREVMX0ZPUl9BR0VOVFNcbik7XG5jb25zdCBjcmVhdGl2ZUFnZW50ID0gbmV3IENyZWF0aXZlQWdlbnQocmVhbExMTVNlcnZpY2VGb3JDcmVhdGl2ZSk7XG5cbmNvbnN0IHJlYWxMTE1TZXJ2aWNlRm9yUHJhY3RpY2FsID0gbmV3IFJlYWxMTE1TZXJ2aWNlKFxuICBwcm9jZXNzLmVudi5MTE1fQVBJX0tFWSB8fCAnWU9VUl9BUElfS0VZX1BMQUNFSE9MREVSJyxcbiAgREVGQVVMVF9NT0RFTF9GT1JfQUdFTlRTXG4pO1xuY29uc3QgcHJhY3RpY2FsQWdlbnQgPSBuZXcgUHJhY3RpY2FsQWdlbnQocmVhbExMTVNlcnZpY2VGb3JQcmFjdGljYWwpO1xuXG5jb25zdCByZWFsTExNU2VydmljZUZvclN5bnRoZXNpemluZyA9IG5ldyBSZWFsTExNU2VydmljZShcbiAgcHJvY2Vzcy5lbnYuTExNX0FQSV9LRVkgfHwgJ1lPVVJfQVBJX0tFWV9QTEFDRUhPTERFUicsXG4gIERFRkFVTFRfTU9ERUxfRk9SX0FHRU5UU1xuKTtcbmNvbnN0IHN5bnRoZXNpemluZ0FnZW50ID0gbmV3IFN5bnRoZXNpemluZ0FnZW50KHJlYWxMTE1TZXJ2aWNlRm9yU3ludGhlc2l6aW5nKTtcblxuY29uc3Qgbmx1TGVhZEFnZW50ID0gbmV3IE5MVUxlYWRBZ2VudChcbiAgYW5hbHl0aWNhbEFnZW50LFxuICBjcmVhdGl2ZUFnZW50LFxuICBwcmFjdGljYWxBZ2VudCxcbiAgc3ludGhlc2l6aW5nQWdlbnRcbik7XG5cbmNvbnN0IGxlYXJuaW5nQW5kR3VpZGFuY2VTa2lsbCA9IG5ldyBMZWFybmluZ0FuZEd1aWRhbmNlU2tpbGwobW9ja0xMTSk7XG5cbi8vIC0tLSBPcmNoZXN0cmF0aW9uIExvZ2ljIC0tLVxuXG5leHBvcnQgaW50ZXJmYWNlIE9yY2hlc3RyYXRvclJlc3BvbnNlIHtcbiAgbWVzc2FnZVRvVXNlcjogc3RyaW5nO1xuICBndWlkYW5jZVJlc3VsdD86IExlYXJuaW5nQW5kR3VpZGFuY2VSZXN1bHQ7XG4gIGVucmljaGVkSW50ZW50PzogRW5yaWNoZWRJbnRlbnQ7IC8vIEZvciBkZWJ1Z2dpbmcgb3IgZnVydGhlciB1c2Vcbn1cblxuLyoqXG4gKiBQcm9jZXNzZXMgYSB1c2VyIHF1ZXJ5IGZvciBsZWFybmluZyBhbmQgZ3VpZGFuY2UsXG4gKiBmaXJzdCB1c2luZyBOTFVMZWFkQWdlbnQsIHRoZW4gcG90ZW50aWFsbHkgTGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gcHJvY2Vzc0d1aWRhbmNlUmVxdWVzdChcbiAgb3JpZ2luYWxRdWVyeTogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgYXBwbGljYXRpb25Db250ZXh0Pzogc3RyaW5nXG4pOiBQcm9taXNlPE9yY2hlc3RyYXRvclJlc3BvbnNlPiB7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBbR3VpZGFuY2VPcmNoZXN0cmF0b3JdIFJlY2VpdmVkIHF1ZXJ5OiBcIiR7b3JpZ2luYWxRdWVyeX1cIiBmcm9tIHVzZXI6ICR7dXNlcklkfWBcbiAgKTtcblxuICBjb25zdCBzdWJBZ2VudElucHV0OiBTdWJBZ2VudElucHV0ID0ge1xuICAgIHVzZXJJbnB1dDogb3JpZ2luYWxRdWVyeSxcbiAgICB1c2VySWQ6IHVzZXJJZCxcbiAgfTtcblxuICBjb25zdCBlbnJpY2hlZEludGVudCA9IGF3YWl0IG5sdUxlYWRBZ2VudC5hbmFseXplSW50ZW50KHN1YkFnZW50SW5wdXQpO1xuICBjb25zb2xlLmxvZyhcbiAgICBgW0d1aWRhbmNlT3JjaGVzdHJhdG9yXSBOTFVMZWFkQWdlbnQgc3VnZ2VzdGVkIGFjdGlvbjogJHtlbnJpY2hlZEludGVudC5zdWdnZXN0ZWROZXh0QWN0aW9uPy5hY3Rpb25UeXBlfWBcbiAgKTtcbiAgY29uc29sZS5sb2coXG4gICAgYFtHdWlkYW5jZU9yY2hlc3RyYXRvcl0gTkxVTGVhZEFnZW50IHByaW1hcnkgZ29hbDogJHtlbnJpY2hlZEludGVudC5wcmltYXJ5R29hbH0gKENvbmZpZGVuY2U6ICR7ZW5yaWNoZWRJbnRlbnQucHJpbWFyeUdvYWxDb25maWRlbmNlPy50b0ZpeGVkKDIpfSlgXG4gICk7XG5cbiAgLy8gMi4gRGVjaWRlIG5leHQgc3RlcCBiYXNlZCBvbiBFbnJpY2hlZEludGVudFxuICBpZiAoZW5yaWNoZWRJbnRlbnQuc3VnZ2VzdGVkTmV4dEFjdGlvbj8uYWN0aW9uVHlwZSA9PT0gJ2NsYXJpZnlfcXVlcnknKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG1lc3NhZ2VUb1VzZXI6XG4gICAgICAgIGVucmljaGVkSW50ZW50LnN1Z2dlc3RlZE5leHRBY3Rpb24uY2xhcmlmaWNhdGlvblF1ZXN0aW9uIHx8XG4gICAgICAgICdJIG5lZWQgbW9yZSBpbmZvcm1hdGlvbiB0byBoZWxwIHlvdS4gQ291bGQgeW91IHBsZWFzZSByZXBocmFzZT8nLFxuICAgICAgZW5yaWNoZWRJbnRlbnQ6IGVucmljaGVkSW50ZW50LFxuICAgIH07XG4gIH1cblxuICBpZiAoXG4gICAgZW5yaWNoZWRJbnRlbnQuc3VnZ2VzdGVkTmV4dEFjdGlvbj8uYWN0aW9uVHlwZSA9PT0gJ2ludm9rZV9za2lsbCcgJiZcbiAgICBlbnJpY2hlZEludGVudC5zdWdnZXN0ZWROZXh0QWN0aW9uLnNraWxsSWQgPT09ICdCcm93c2VyQXV0b21hdGlvblNraWxsJ1xuICApIHtcbiAgICBpZiAodHlwZW9mIHdpbmRvdyAhPT0gJ3VuZGVmaW5lZCcgJiYgd2luZG93Ll9fVEFVUklfXykge1xuICAgICAgY29uc29sZS5sb2coJ1tHdWlkYW5jZU9yY2hlc3RyYXRvcl0gSW52b2tpbmcgQnJvd3NlckF1dG9tYXRpb25Ta2lsbC4nKTtcbiAgICAgIC8vIFBsYWNlaG9sZGVyIGZvciBhY3R1YWxseSBpbnZva2luZyB0aGUgc2tpbGxcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG1lc3NhZ2VUb1VzZXI6ICdCcm93c2VyIGF1dG9tYXRpb24gc2tpbGwgaW52b2tlZC4nLFxuICAgICAgICBlbnJpY2hlZEludGVudDogZW5yaWNoZWRJbnRlbnQsXG4gICAgICB9O1xuICAgIH0gZWxzZSB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBtZXNzYWdlVG9Vc2VyOiAnVGhpcyBmZWF0dXJlIGlzIG9ubHkgYXZhaWxhYmxlIGluIHRoZSBkZXNrdG9wIGFwcC4nLFxuICAgICAgICBlbnJpY2hlZEludGVudDogZW5yaWNoZWRJbnRlbnQsXG4gICAgICB9O1xuICAgIH1cbiAgfVxuXG4gIGlmIChcbiAgICBlbnJpY2hlZEludGVudC5zdWdnZXN0ZWROZXh0QWN0aW9uPy5hY3Rpb25UeXBlID09PSAnaW52b2tlX3NraWxsJyAmJlxuICAgIChlbnJpY2hlZEludGVudC5zdWdnZXN0ZWROZXh0QWN0aW9uLnNraWxsSWQgPT09XG4gICAgICAnTGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsJyB8fFxuICAgICAgIWVucmljaGVkSW50ZW50LnN1Z2dlc3RlZE5leHRBY3Rpb24uc2tpbGxJZClcbiAgKSB7XG4gICAgY29uc29sZS5sb2coJ1tHdWlkYW5jZU9yY2hlc3RyYXRvcl0gSW52b2tpbmcgTGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsLicpO1xuXG4gICAgLy8gUHJlcGFyZSBpbnB1dCBmb3IgdGhlIExlYXJuaW5nQW5kR3VpZGFuY2VTa2lsbFxuICAgIC8vIFdlIGNhbiB1c2UgaW5mb3JtYXRpb24gZnJvbSBlbnJpY2hlZEludGVudCB0byBtYWtlIHRoaXMgbW9yZSB0YXJnZXRlZFxuICAgIGNvbnN0IHNraWxsSW5wdXQ6IExlYXJuaW5nQW5kR3VpZGFuY2VJbnB1dCA9IHtcbiAgICAgIHVzZXJJZDogdXNlcklkLFxuICAgICAgcXVlcnk6IGVucmljaGVkSW50ZW50LnByaW1hcnlHb2FsIHx8IG9yaWdpbmFsUXVlcnksIC8vIFVzZSByZWZpbmVkIGdvYWwgaWYgYXZhaWxhYmxlXG4gICAgICBhcHBsaWNhdGlvbkNvbnRleHQ6IGFwcGxpY2F0aW9uQ29udGV4dCxcbiAgICAgIC8vIFBvdGVudGlhbGx5IHVzZSBlbnJpY2hlZEludGVudC5leHRyYWN0ZWRQYXJhbWV0ZXJzIG9yIGlkZW50aWZpZWRUYXNrcyB0byByZWZpbmUgc2tpbGwgaW5wdXRcbiAgICAgIC8vIGUuZy4sIGlmIHByaW1hcnlHb2FsIGlzIFwiZmluZF90dXRvcmlhbF9mb3JfcGl2b3RfdGFibGVzXCJcbiAgICAgIC8vIGd1aWRhbmNlVHlwZUhpbnQgY291bGQgYmUgc2V0IGhlcmUuXG4gICAgfTtcblxuICAgIC8vIElmIE5MVSBhbHJlYWR5IGNsYXNzaWZpZWQgdGhlIGd1aWRhbmNlIHR5cGUsIHdlIGNhbiBwYXNzIGl0IGFzIGEgaGludFxuICAgIGlmIChcbiAgICAgIGVucmljaGVkSW50ZW50LnByaW1hcnlHb2FsPy50b0xvd2VyQ2FzZSgpLmluY2x1ZGVzKCd0dXRvcmlhbCcpIHx8XG4gICAgICBlbnJpY2hlZEludGVudC5pZGVudGlmaWVkVGFza3M/LnNvbWUoKHQpID0+IHQuaW5jbHVkZXMoJ3R1dG9yaWFsJykpXG4gICAgKSB7XG4gICAgICBza2lsbElucHV0Lmd1aWRhbmNlVHlwZUhpbnQgPSAnZmluZF90dXRvcmlhbCc7XG4gICAgfSBlbHNlIGlmIChcbiAgICAgIGVucmljaGVkSW50ZW50LnByaW1hcnlHb2FsPy50b0xvd2VyQ2FzZSgpLmluY2x1ZGVzKCdleHBsYWluJykgfHxcbiAgICAgIGVucmljaGVkSW50ZW50LnByaW1hcnlHb2FsPy50b0xvd2VyQ2FzZSgpLmluY2x1ZGVzKCdleHBsYW5hdGlvbicpXG4gICAgKSB7XG4gICAgICBza2lsbElucHV0Lmd1aWRhbmNlVHlwZUhpbnQgPSAnZ2VuZXJhbF9leHBsYW5hdGlvbic7XG4gICAgfVxuICAgIC8vIGV0Yy4gZm9yIG90aGVyIHR5cGVzIGJhc2VkIG9uIHByaW1hcnlHb2FsIG9yIGlkZW50aWZpZWRUYXNrc1xuXG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IGd1aWRhbmNlUmVzdWx0ID0gYXdhaXQgbGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsLmV4ZWN1dGUoc2tpbGxJbnB1dCk7XG4gICAgICAvLyBJZGVhbGx5LCB0aGUgbWVzc2FnZSB0byB1c2VyIHdvdWxkIGJlIGNvbnN0cnVjdGVkIGJhc2VkIG9uIGd1aWRhbmNlUmVzdWx0XG4gICAgICBsZXQgZnJpZW5kbHlNZXNzYWdlID0gYEhlcmUncyB3aGF0IEkgZm91bmQgZm9yIFwiJHtvcmlnaW5hbFF1ZXJ5fVwiOlxcbmA7XG4gICAgICBpZiAoZ3VpZGFuY2VSZXN1bHQuZ3VpZGFuY2VQcm92aWRlZC5sZW5ndGggPiAwKSB7XG4gICAgICAgIGd1aWRhbmNlUmVzdWx0Lmd1aWRhbmNlUHJvdmlkZWQuZm9yRWFjaCgoZykgPT4ge1xuICAgICAgICAgIGZyaWVuZGx5TWVzc2FnZSArPSBgXFxuVGl0bGU6ICR7Zy50aXRsZX1cXG5gO1xuICAgICAgICAgIGlmIChnLmNvbnRlbnRTbmlwcGV0KVxuICAgICAgICAgICAgZnJpZW5kbHlNZXNzYWdlICs9IGBTbmlwcGV0OiAke2cuY29udGVudFNuaXBwZXQuc3Vic3RyaW5nKDAsIDEwMCl9Li4uXFxuYDtcbiAgICAgICAgICBpZiAoZy5zdGVwcykgZnJpZW5kbHlNZXNzYWdlICs9IGAke2cuc3RlcHMubGVuZ3RofSBzdGVwcyBmb3VuZC5cXG5gO1xuICAgICAgICB9KTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGZyaWVuZGx5TWVzc2FnZSA9IGBJIGNvdWxkbid0IGZpbmQgc3BlY2lmaWMgZ3VpZGFuY2UgZm9yIFwiJHtvcmlnaW5hbFF1ZXJ5fVwiLCBidXQgSSdsbCBrZWVwIGxlYXJuaW5nIWA7XG4gICAgICB9XG4gICAgICBpZiAoXG4gICAgICAgIGd1aWRhbmNlUmVzdWx0LmZvbGxvd1VwU3VnZ2VzdGlvbnMgJiZcbiAgICAgICAgZ3VpZGFuY2VSZXN1bHQuZm9sbG93VXBTdWdnZXN0aW9ucy5sZW5ndGggPiAwXG4gICAgICApIHtcbiAgICAgICAgZnJpZW5kbHlNZXNzYWdlICs9IGBcXG5cXG5Gb2xsb3ctdXAgc3VnZ2VzdGlvbnM6ICR7Z3VpZGFuY2VSZXN1bHQuZm9sbG93VXBTdWdnZXN0aW9ucy5qb2luKCcsICcpfWA7XG4gICAgICB9XG5cbiAgICAgIHJldHVybiB7XG4gICAgICAgIG1lc3NhZ2VUb1VzZXI6IGZyaWVuZGx5TWVzc2FnZSxcbiAgICAgICAgZ3VpZGFuY2VSZXN1bHQ6IGd1aWRhbmNlUmVzdWx0LFxuICAgICAgICBlbnJpY2hlZEludGVudDogZW5yaWNoZWRJbnRlbnQsXG4gICAgICB9O1xuICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICdbR3VpZGFuY2VPcmNoZXN0cmF0b3JdIEVycm9yIGV4ZWN1dGluZyBMZWFybmluZ0FuZEd1aWRhbmNlU2tpbGw6JyxcbiAgICAgICAgZXJyb3JcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBtZXNzYWdlVG9Vc2VyOiBgU29ycnksIEkgZW5jb3VudGVyZWQgYW4gZXJyb3Igd2hpbGUgdHJ5aW5nIHRvIGdldCBndWlkYW5jZSBmb3IgXCIke29yaWdpbmFsUXVlcnl9XCIuIEVycm9yOiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICAgICAgZW5yaWNoZWRJbnRlbnQ6IGVucmljaGVkSW50ZW50LFxuICAgICAgfTtcbiAgICB9XG4gIH1cblxuICAvLyBGYWxsYmFjayBmb3Igb3RoZXIgYWN0aW9uIHR5cGVzIG9yIGlmIHRoZSBza2lsbCBkb2Vzbid0IG1hdGNoXG4gIGxldCBmYWxsYmFja01lc3NhZ2UgPSBgSSd2ZSBhbmFseXplZCB5b3VyIHF1ZXJ5OiBcIiR7b3JpZ2luYWxRdWVyeX1cIi5cXG5gO1xuICBmYWxsYmFja01lc3NhZ2UgKz0gYEdvYWw6ICR7ZW5yaWNoZWRJbnRlbnQucHJpbWFyeUdvYWwgfHwgJ05vdCBjbGVhcmx5IGlkZW50aWZpZWQnfS5cXG5gO1xuICBpZiAoXG4gICAgZW5yaWNoZWRJbnRlbnQuc3VnZ2VzdGVkTmV4dEFjdGlvbj8uYWN0aW9uVHlwZSAmJlxuICAgIGVucmljaGVkSW50ZW50LnN1Z2dlc3RlZE5leHRBY3Rpb24/LmFjdGlvblR5cGUgIT09ICd1bmFibGVfdG9fZGV0ZXJtaW5lJ1xuICApIHtcbiAgICBmYWxsYmFja01lc3NhZ2UgKz0gYFN1Z2dlc3RlZCBuZXh0IHN0ZXA6ICR7ZW5yaWNoZWRJbnRlbnQuc3VnZ2VzdGVkTmV4dEFjdGlvbi5hY3Rpb25UeXBlfWA7XG4gICAgaWYgKGVucmljaGVkSW50ZW50LnN1Z2dlc3RlZE5leHRBY3Rpb24ucmVhc29uKVxuICAgICAgZmFsbGJhY2tNZXNzYWdlICs9IGAgKCR7ZW5yaWNoZWRJbnRlbnQuc3VnZ2VzdGVkTmV4dEFjdGlvbi5yZWFzb259KWA7XG4gIH0gZWxzZSB7XG4gICAgZmFsbGJhY2tNZXNzYWdlICs9XG4gICAgICBcIkknbSBub3Qgc3VyZSBob3cgdG8gcHJvY2VlZCB3aXRoIHRoaXMgc3BlY2lmaWMgcmVxdWVzdCB5ZXQuXCI7XG4gIH1cblxuICByZXR1cm4ge1xuICAgIG1lc3NhZ2VUb1VzZXI6IGZhbGxiYWNrTWVzc2FnZSxcbiAgICBlbnJpY2hlZEludGVudDogZW5yaWNoZWRJbnRlbnQsXG4gIH07XG59XG5cbi8vIC0tLSBFeGFtcGxlIFRlc3QgLS0tXG4vKlxuYXN5bmMgZnVuY3Rpb24gdGVzdE9yY2hlc3RyYXRvcigpIHtcbiAgICBjb25zb2xlLmxvZyhcIi0tLSBUZXN0IENhc2UgMTogUGl2b3QgVGFibGUgUXVlcnkgKFJ1bGUtYmFzZWQgTkxVKSAtLS1cIik7XG4gICAgbGV0IHJlc3BvbnNlID0gYXdhaXQgcHJvY2Vzc0d1aWRhbmNlUmVxdWVzdChcIkhvdyBkbyBJIGNyZWF0ZSBhIHBpdm90IHRhYmxlIGluIFNwcmVhZHNoZWV0QXBwP1wiLCBcInVzZXIxMjNcIiwgXCJTcHJlYWRzaGVldEFwcFwiKTtcbiAgICBjb25zb2xlLmxvZyhcIk9yY2hlc3RyYXRvciBSZXNwb25zZTpcXG5cIiwgcmVzcG9uc2UubWVzc2FnZVRvVXNlcik7XG4gICAgLy8gY29uc29sZS5sb2coXCJGdWxsIEVucmljaGVkIEludGVudDpcIiwgSlNPTi5zdHJpbmdpZnkocmVzcG9uc2UuZW5yaWNoZWRJbnRlbnQsIG51bGwsIDIpKTtcblxuXG4gICAgY29uc29sZS5sb2coXCJcXFxcbi0tLSBUZXN0IENhc2UgMjogVmFndWUgJ0hlbHAgbWUnIFF1ZXJ5IChSdWxlLWJhc2VkIE5MVSkgLS0tXCIpO1xuICAgIHJlc3BvbnNlID0gYXdhaXQgcHJvY2Vzc0d1aWRhbmNlUmVxdWVzdChcIkhlbHAgbWUuXCIsIFwidXNlcjQ1NlwiKTtcbiAgICBjb25zb2xlLmxvZyhcIk9yY2hlc3RyYXRvciBSZXNwb25zZTpcXG5cIiwgcmVzcG9uc2UubWVzc2FnZVRvVXNlcik7XG4gICAgLy8gY29uc29sZS5sb2coXCJGdWxsIEVucmljaGVkIEludGVudDpcIiwgSlNPTi5zdHJpbmdpZnkocmVzcG9uc2UuZW5yaWNoZWRJbnRlbnQsIG51bGwsIDIpKTtcblxuXG4gICAgY29uc29sZS5sb2coXCJcXFxcbi0tLSBUZXN0IENhc2UgMzogRWZmaWNpZW50IFJlcG9ydCBRdWVyeSAoUnVsZS1iYXNlZCBOTFUpIC0tLVwiKTtcbiAgICByZXNwb25zZSA9IGF3YWl0IHByb2Nlc3NHdWlkYW5jZVJlcXVlc3QoXG4gICAgICAgIFwiSG93IGNhbiBJIG1ha2UgbXkgUTMgbWFya2V0aW5nIHJlcG9ydCBnZW5lcmF0aW9uIG1vcmUgZWZmaWNpZW50LCBtYXliZSB1c2luZyB0aGF0IG5ldyBBSSB0aGluZz9cIixcbiAgICAgICAgXCJ1c2VyNzg5XCIsXG4gICAgICAgIFwiTWFya2V0aW5nU3VpdGVcIlxuICAgICk7XG4gICAgY29uc29sZS5sb2coXCJPcmNoZXN0cmF0b3IgUmVzcG9uc2U6XFxuXCIsIHJlc3BvbnNlLm1lc3NhZ2VUb1VzZXIpO1xuICAgIC8vIGNvbnNvbGUubG9nKFwiRnVsbCBFbnJpY2hlZCBJbnRlbnQ6XCIsIEpTT04uc3RyaW5naWZ5KHJlc3BvbnNlLmVucmljaGVkSW50ZW50LCBudWxsLCAyKSk7XG5cbiAgICAvLyBjb25zb2xlLmxvZyhcIlxcXFxuLS0tIFRlc3QgQ2FzZSA0OiBFZmZpY2llbnQgUmVwb3J0IFF1ZXJ5IChNb2NrIExMTS1iYXNlZCBOTFUpIC0tLVwiKTtcbiAgICAvLyByZXNwb25zZSA9IGF3YWl0IHByb2Nlc3NHdWlkYW5jZVJlcXVlc3QoXG4gICAgLy8gICAgIFwiSG93IGNhbiBJIG1ha2UgbXkgUTMgbWFya2V0aW5nIHJlcG9ydCBnZW5lcmF0aW9uIG1vcmUgZWZmaWNpZW50LCBtYXliZSB1c2luZyB0aGF0IG5ldyBBSSB0aGluZz9cIixcbiAgICAvLyAgICAgXCJ1c2VyNzg5XCIsXG4gICAgLy8gICAgIFwiTWFya2V0aW5nU3VpdGVcIixcbiAgICAvLyAgICAgdHJ1ZSAvLyBFbmFibGUgTExNIFN5bnRoZXNpcyBmb3IgTkxVXG4gICAgLy8gKTtcbiAgICAvLyBjb25zb2xlLmxvZyhcIk9yY2hlc3RyYXRvciBSZXNwb25zZTpcXG5cIiwgcmVzcG9uc2UubWVzc2FnZVRvVXNlcik7XG4gICAgLy8gY29uc29sZS5sb2coXCJGdWxsIEVucmljaGVkIEludGVudCAoTExNIE5MVSk6XCIsIEpTT04uc3RyaW5naWZ5KHJlc3BvbnNlLmVucmljaGVkSW50ZW50LCBudWxsLCAyKSk7XG59XG5cbi8vIHRlc3RPcmNoZXN0cmF0b3IoKTtcbiovXG5cbi8vIC0tLSBJbnRlZ3JhdGlvbiBUZXN0IFJ1bm5lciAtLS1cbmludGVyZmFjZSBUZXN0Q2FzZSB7XG4gIGRlc2NyaXB0aW9uOiBzdHJpbmc7XG4gIHF1ZXJ5OiBzdHJpbmc7XG4gIHVzZXJJZDogc3RyaW5nO1xuICBhcHBsaWNhdGlvbkNvbnRleHQ/OiBzdHJpbmc7XG4gIHVzZUxMTVN5bnRoZXNpcz86IGJvb2xlYW47XG4gIGV4cGVjdGVkUmVzcG9uc2VUeXBlOlxuICAgIHwgJ2NsYXJpZmljYXRpb24nXG4gICAgfCAnZ3VpZGFuY2Vfc3VjY2VzcydcbiAgICB8ICdmYWxsYmFja19pbmZvJ1xuICAgIHwgJ2Vycm9yJztcbiAgZXhwZWN0ZWRNZXNzYWdlQ29udGFpbnM/OiBzdHJpbmcgfCBzdHJpbmdbXTsgLy8gU3Vic3RyaW5nKHMpIGV4cGVjdGVkIGluIHRoZSBtZXNzYWdlVG9Vc2VyXG4gIGV4cGVjdGVkR3VpZGFuY2VUaXRsZXM/OiBzdHJpbmdbXTsgLy8gaWYgZ3VpZGFuY2Vfc3VjY2VzcywgY2hlY2sgZm9yIHRoZXNlIHRpdGxlc1xufVxuXG5hc3luYyBmdW5jdGlvbiBydW5HdWlkYW5jZU9yY2hlc3RyYXRvclRlc3RzKCkge1xuICBjb25zb2xlLmxvZygnXFxcXG4tLS0gU3RhcnRpbmcgR3VpZGFuY2VPcmNoZXN0cmF0b3IgVGVzdHMgLS0tJyk7XG4gIGNvbnN0IHRlc3RDYXNlczogVGVzdENhc2VbXSA9IFtcbiAgICB7XG4gICAgICBkZXNjcmlwdGlvbjogJ1Rlc3QgMTogVmFndWUgcXVlcnksIGV4cGVjdGluZyBjbGFyaWZpY2F0aW9uJyxcbiAgICAgIHF1ZXJ5OiAnSGVscCBtZSBmaXggc3R1ZmYuJyxcbiAgICAgIHVzZXJJZDogJ3VzZXItdGVzdC0wMDEnLFxuICAgICAgZXhwZWN0ZWRSZXNwb25zZVR5cGU6ICdjbGFyaWZpY2F0aW9uJyxcbiAgICAgIGV4cGVjdGVkTWVzc2FnZUNvbnRhaW5zOiAnSSBuZWVkIG1vcmUgaW5mb3JtYXRpb24nLFxuICAgIH0sXG4gICAge1xuICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgIFwiVGVzdCAyOiBTcGVjaWZpYyAnaG93LXRvJyBxdWVyeSwgZXhwZWN0aW5nIGd1aWRhbmNlIHN1Y2Nlc3NcIixcbiAgICAgIHF1ZXJ5OiAnSG93IGRvIEkgY3JlYXRlIGEgcGl2b3QgdGFibGUgaW4gU3ByZWFkc2hlZXRBcHA/JyxcbiAgICAgIHVzZXJJZDogJ3VzZXItdGVzdC0wMDInLFxuICAgICAgYXBwbGljYXRpb25Db250ZXh0OiAnU3ByZWFkc2hlZXRBcHAnLFxuICAgICAgZXhwZWN0ZWRSZXNwb25zZVR5cGU6ICdndWlkYW5jZV9zdWNjZXNzJyxcbiAgICAgIGV4cGVjdGVkTWVzc2FnZUNvbnRhaW5zOiBcIkhlcmUncyB3aGF0IEkgZm91bmRcIixcbiAgICAgIGV4cGVjdGVkR3VpZGFuY2VUaXRsZXM6IFsnSG93IHRvIENyZWF0ZSBQaXZvdCBUYWJsZXMgaW4gU3ByZWFkc2hlZXRBcHAnXSxcbiAgICB9LFxuICAgIHtcbiAgICAgIGRlc2NyaXB0aW9uOiAnVGVzdCAzOiBDb21wbGV4IHF1ZXJ5LCBleHBlY3Rpbmcgc2tpbGwgaW52b2NhdGlvbicsXG4gICAgICBxdWVyeTpcbiAgICAgICAgJ215IG1hcmtldGluZyByZXBvcnQgZm9yIFEzIGlzIGhhcmQgdG8gZG8sIGhvdyBjYW4gQUkgbWFrZSBpdCBlZmZpY2llbnQ/JyxcbiAgICAgIHVzZXJJZDogJ3VzZXItdGVzdC0wMDMnLFxuICAgICAgYXBwbGljYXRpb25Db250ZXh0OiAnTWFya2V0aW5nU3VpdGUnLFxuICAgICAgZXhwZWN0ZWRSZXNwb25zZVR5cGU6ICdmYWxsYmFja19pbmZvJyxcbiAgICAgIGV4cGVjdGVkTWVzc2FnZUNvbnRhaW5zOiAnU3VnZ2VzdGVkIG5leHQgc3RlcDogaW52b2tlX3NraWxsJyxcbiAgICB9LFxuICBdO1xuXG4gIGxldCB0ZXN0c1Bhc3NlZCA9IDA7XG4gIGZvciAoY29uc3QgdGMgb2YgdGVzdENhc2VzKSB7XG4gICAgY29uc29sZS5sb2coYFxcblJ1bm5pbmc6ICR7dGMuZGVzY3JpcHRpb259YCk7XG5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHByb2Nlc3NHdWlkYW5jZVJlcXVlc3QoXG4gICAgICB0Yy5xdWVyeSxcbiAgICAgIHRjLnVzZXJJZCxcbiAgICAgIHRjLmFwcGxpY2F0aW9uQ29udGV4dFxuICAgICk7XG5cbiAgICBsZXQgcGFzcyA9IGZhbHNlO1xuICAgIHN3aXRjaCAodGMuZXhwZWN0ZWRSZXNwb25zZVR5cGUpIHtcbiAgICAgIGNhc2UgJ2NsYXJpZmljYXRpb24nOlxuICAgICAgICBwYXNzID1cbiAgICAgICAgICByZXNwb25zZS5tZXNzYWdlVG9Vc2VyLnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMoJ2NsYXJpZnknKSB8fFxuICAgICAgICAgIHJlc3BvbnNlLm1lc3NhZ2VUb1VzZXIudG9Mb3dlckNhc2UoKS5pbmNsdWRlcygnbW9yZSBpbmZvcm1hdGlvbicpIHx8XG4gICAgICAgICAgcmVzcG9uc2UubWVzc2FnZVRvVXNlci50b0xvd2VyQ2FzZSgpLmluY2x1ZGVzKCdyZXBocmFzZScpIHx8XG4gICAgICAgICAgcmVzcG9uc2UubWVzc2FnZVRvVXNlclxuICAgICAgICAgICAgLnRvTG93ZXJDYXNlKClcbiAgICAgICAgICAgIC5pbmNsdWRlcygnaW5jb25zaXN0ZW50IG9yIHVuY2xlYXInKTtcbiAgICAgICAgaWYgKHRjLmV4cGVjdGVkTWVzc2FnZUNvbnRhaW5zKSB7XG4gICAgICAgICAgY29uc3QgbWVzc2FnZXMgPSBBcnJheS5pc0FycmF5KHRjLmV4cGVjdGVkTWVzc2FnZUNvbnRhaW5zKVxuICAgICAgICAgICAgPyB0Yy5leHBlY3RlZE1lc3NhZ2VDb250YWluc1xuICAgICAgICAgICAgOiBbdGMuZXhwZWN0ZWRNZXNzYWdlQ29udGFpbnNdO1xuICAgICAgICAgIHBhc3MgPVxuICAgICAgICAgICAgcGFzcyAmJiBtZXNzYWdlcy5ldmVyeSgobSkgPT4gcmVzcG9uc2UubWVzc2FnZVRvVXNlci5pbmNsdWRlcyhtKSk7XG4gICAgICAgIH1cbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdndWlkYW5jZV9zdWNjZXNzJzpcbiAgICAgICAgcGFzcyA9XG4gICAgICAgICAgISFyZXNwb25zZS5ndWlkYW5jZVJlc3VsdCAmJlxuICAgICAgICAgIHJlc3BvbnNlLmd1aWRhbmNlUmVzdWx0Lmd1aWRhbmNlUHJvdmlkZWQubGVuZ3RoID4gMDtcbiAgICAgICAgaWYgKHBhc3MgJiYgdGMuZXhwZWN0ZWRNZXNzYWdlQ29udGFpbnMpIHtcbiAgICAgICAgICBjb25zdCBtZXNzYWdlcyA9IEFycmF5LmlzQXJyYXkodGMuZXhwZWN0ZWRNZXNzYWdlQ29udGFpbnMpXG4gICAgICAgICAgICA/IHRjLmV4cGVjdGVkTWVzc2FnZUNvbnRhaW5zXG4gICAgICAgICAgICA6IFt0Yy5leHBlY3RlZE1lc3NhZ2VDb250YWluc107XG4gICAgICAgICAgcGFzcyA9XG4gICAgICAgICAgICBwYXNzICYmIG1lc3NhZ2VzLmV2ZXJ5KChtKSA9PiByZXNwb25zZS5tZXNzYWdlVG9Vc2VyLmluY2x1ZGVzKG0pKTtcbiAgICAgICAgfVxuICAgICAgICBpZiAocGFzcyAmJiB0Yy5leHBlY3RlZEd1aWRhbmNlVGl0bGVzICYmIHJlc3BvbnNlLmd1aWRhbmNlUmVzdWx0KSB7XG4gICAgICAgICAgcGFzcyA9XG4gICAgICAgICAgICBwYXNzICYmXG4gICAgICAgICAgICB0Yy5leHBlY3RlZEd1aWRhbmNlVGl0bGVzLmV2ZXJ5KCh0aXRsZSkgPT5cbiAgICAgICAgICAgICAgcmVzcG9uc2UuZ3VpZGFuY2VSZXN1bHQ/Lmd1aWRhbmNlUHJvdmlkZWQuc29tZShcbiAgICAgICAgICAgICAgICAoZykgPT4gZy50aXRsZSA9PT0gdGl0bGVcbiAgICAgICAgICAgICAgKVxuICAgICAgICAgICAgKTtcbiAgICAgICAgfVxuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ2ZhbGxiYWNrX2luZm8nOiAvLyBGb3Igd2hlbiBOTFUgaXMgZ29vZCwgYnV0IHNraWxsIGlzbid0IHRoZSBvbmUgd2UncmUgdGVzdGluZyBkZWVwbHlcbiAgICAgICAgcGFzcyA9XG4gICAgICAgICAgIXJlc3BvbnNlLmd1aWRhbmNlUmVzdWx0IHx8XG4gICAgICAgICAgcmVzcG9uc2UuZ3VpZGFuY2VSZXN1bHQuZ3VpZGFuY2VQcm92aWRlZC5sZW5ndGggPT09IDA7XG4gICAgICAgIGlmICh0Yy5leHBlY3RlZE1lc3NhZ2VDb250YWlucykge1xuICAgICAgICAgIGNvbnN0IG1lc3NhZ2VzID0gQXJyYXkuaXNBcnJheSh0Yy5leHBlY3RlZE1lc3NhZ2VDb250YWlucylcbiAgICAgICAgICAgID8gdGMuZXhwZWN0ZWRNZXNzYWdlQ29udGFpbnNcbiAgICAgICAgICAgIDogW3RjLmV4cGVjdGVkTWVzc2FnZUNvbnRhaW5zXTtcbiAgICAgICAgICBwYXNzID1cbiAgICAgICAgICAgIHBhc3MgJiYgbWVzc2FnZXMuZXZlcnkoKG0pID0+IHJlc3BvbnNlLm1lc3NhZ2VUb1VzZXIuaW5jbHVkZXMobSkpO1xuICAgICAgICB9XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnZXJyb3InOlxuICAgICAgICBwYXNzID0gcmVzcG9uc2UubWVzc2FnZVRvVXNlci50b0xvd2VyQ2FzZSgpLmluY2x1ZGVzKCdlcnJvcicpO1xuICAgICAgICBicmVhaztcbiAgICB9XG5cbiAgICBpZiAocGFzcykge1xuICAgICAgdGVzdHNQYXNzZWQrKztcbiAgICAgIGNvbnNvbGUubG9nKGBQQVNTOiAke3RjLmRlc2NyaXB0aW9ufWApO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zb2xlLmVycm9yKGBGQUlMOiAke3RjLmRlc2NyaXB0aW9ufWApO1xuICAgICAgY29uc29sZS5sb2coJyAgRXhwZWN0ZWQgcmVzcG9uc2UgdHlwZTonLCB0Yy5leHBlY3RlZFJlc3BvbnNlVHlwZSk7XG4gICAgICBpZiAodGMuZXhwZWN0ZWRNZXNzYWdlQ29udGFpbnMpXG4gICAgICAgIGNvbnNvbGUubG9nKCcgIEV4cGVjdGVkIG1lc3NhZ2UgY29udGFpbnM6JywgdGMuZXhwZWN0ZWRNZXNzYWdlQ29udGFpbnMpO1xuICAgICAgY29uc29sZS5sb2coJyAgQWN0dWFsIG1lc3NhZ2VUb1VzZXI6JywgcmVzcG9uc2UubWVzc2FnZVRvVXNlcik7XG4gICAgICBpZiAodGMuZXhwZWN0ZWRSZXNwb25zZVR5cGUgPT09ICdndWlkYW5jZV9zdWNjZXNzJylcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgJyAgQWN0dWFsIGd1aWRhbmNlUmVzdWx0OicsXG4gICAgICAgICAgSlNPTi5zdHJpbmdpZnkocmVzcG9uc2UuZ3VpZGFuY2VSZXN1bHQsIG51bGwsIDIpLnN1YnN0cmluZygwLCAzMDApICtcbiAgICAgICAgICAgICcuLi4nXG4gICAgICAgICk7XG4gICAgfVxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJyAgTkxVIFByaW1hcnkgR29hbDonLFxuICAgICAgcmVzcG9uc2UuZW5yaWNoZWRJbnRlbnQ/LnByaW1hcnlHb2FsLFxuICAgICAgJyhDb25maWRlbmNlOicsXG4gICAgICByZXNwb25zZS5lbnJpY2hlZEludGVudD8ucHJpbWFyeUdvYWxDb25maWRlbmNlPy50b0ZpeGVkKDIpLFxuICAgICAgJyknXG4gICAgKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgICcgIE5MVSBTdWdnZXN0ZWQgQWN0aW9uOicsXG4gICAgICByZXNwb25zZS5lbnJpY2hlZEludGVudD8uc3VnZ2VzdGVkTmV4dEFjdGlvbj8uYWN0aW9uVHlwZSxcbiAgICAgICdSZWFzb246JyxcbiAgICAgIHJlc3BvbnNlLmVucmljaGVkSW50ZW50Py5zdWdnZXN0ZWROZXh0QWN0aW9uPy5yZWFzb25cbiAgICApO1xuICB9XG5cbiAgY29uc29sZS5sb2coYFxcbi0tLSBHdWlkYW5jZU9yY2hlc3RyYXRvciBUZXN0cyBDb21wbGV0ZSAtLS1gKTtcbiAgY29uc29sZS5sb2coYCR7dGVzdHNQYXNzZWR9LyR7dGVzdENhc2VzLmxlbmd0aH0gdGVzdCBjYXNlcyBwYXNzZWQuYCk7XG4gIGlmICh0ZXN0c1Bhc3NlZCA9PT0gdGVzdENhc2VzLmxlbmd0aCkge1xuICAgIGNvbnNvbGUubG9nKCdBbGwgdGVzdHMgcGFzc2VkIHN1Y2Nlc3NmdWxseSEnKTtcbiAgICByZXR1cm4gdHJ1ZTtcbiAgfSBlbHNlIHtcbiAgICBjb25zb2xlLmVycm9yKGAke3Rlc3RDYXNlcy5sZW5ndGggLSB0ZXN0c1Bhc3NlZH0gdGVzdChzKSBmYWlsZWQuYCk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG59XG5cbi8vIFRvIHJ1biB0ZXN0czpcbi8vIHJ1bkd1aWRhbmNlT3JjaGVzdHJhdG9yVGVzdHMoKTtcblxuY29uc29sZS5sb2coXG4gICdHdWlkYW5jZU9yY2hlc3RyYXRvciBsb2FkZWQuIENhbGwgcnVuR3VpZGFuY2VPcmNoZXN0cmF0b3JUZXN0cygpIHRvIHJ1biBpbnRlZ3JhdGlvbiB0ZXN0cy4nXG4pO1xuIl19