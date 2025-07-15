import { NLULeadAgent } from '../nlu_agents/nlu_lead_agent';
import { AnalyticalAgent } from '../nlu_agents/analytical_agent';
import { CreativeAgent } from '../nlu_agents/creative_agent';
import { PracticalAgent } from '../nlu_agents/practical_agent';
import { SubAgentInput, EnrichedIntent, DEFAULT_MODEL_FOR_AGENTS } from '../nlu_agents/nlu_types';

import { LearningAndGuidanceSkill, LearningAndGuidanceInput, LearningAndGuidanceResult } from '../skills/learningAndGuidanceSkill';
import { MockLLMService, RealLLMService } from '../lib/llmUtils'; // Import RealLLMService

// --- Initialization (typically done once, e.g., on server start) ---

// For services that still use mocks or for fallback
const mockLLM = new MockLLMService();

// Initialize RealLLMService for the AnalyticalAgent
// IMPORTANT: In a real app, "YOUR_API_KEY_PLACEHOLDER" would come from a secure source like process.env.LLM_API_KEY
// Since the key is a placeholder, RealLLMService will internally use its simulated successful response.
const realLLMServiceForAnalytical = new RealLLMService(
    process.env.LLM_API_KEY || "YOUR_API_KEY_PLACEHOLDER", // Prioritize env variable if available
    DEFAULT_MODEL_FOR_AGENTS, // Defined in nlu_types, e.g., "mixtral-8x7b-32768"
    // Specify baseURL if not OpenAI default, e.g., for Groq: 'https://api.groq.com/openai/v1'
);

const analyticalAgent = new AnalyticalAgent(realLLMServiceForAnalytical); // AnalyticalAgent uses RealLLMService

// Initialize RealLLMService for the CreativeAgent
const realLLMServiceForCreative = new RealLLMService(
    process.env.LLM_API_KEY || "YOUR_API_KEY_PLACEHOLDER",
    DEFAULT_MODEL_FOR_AGENTS
);
const creativeAgent = new CreativeAgent(realLLMServiceForCreative); // CreativeAgent now uses RealLLMService

// Initialize RealLLMService for the PracticalAgent
const realLLMServiceForPractical = new RealLLMService(
    process.env.LLM_API_KEY || "YOUR_API_KEY_PLACEHOLDER",
    DEFAULT_MODEL_FOR_AGENTS
);
const practicalAgent = new PracticalAgent(realLLMServiceForPractical); // PracticalAgent now uses RealLLMService

// NLULeadAgent can also use the real service if its LLM-based synthesis is to be tested with a real LLM.
// For now, let's assume its synthesis might also use a more general/mocked service or its rule-based approach.
// If NLULeadAgent's LLM synthesis were the focus, it too would get an instance of RealLLMService.
// To test the LLM-based synthesis path with RealLLMService's simulation, NLULeadAgent needs a RealLLMService.
// We can reuse one of the existing instances, e.g., realLLMServiceForAnalytical, as they are configured similarly.
const nluLeadAgent = new NLULeadAgent(
    analyticalAgent,
    creativeAgent,
    practicalAgent,
    realLLMServiceForAnalytical // NLULeadAgent now uses RealLLMService for its own LLM calls (i.e., synthesis)
);

// Instance of the existing skill, can still use MockLLMService for its internal LLM calls
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
    applicationContext?: string,
    useLLMSynthesisForNLU: boolean = false
): Promise<OrchestratorResponse> {

    console.log(`[GuidanceOrchestrator] Received query: "${originalQuery}" from user: ${userId}`);

    const subAgentInput: SubAgentInput = {
        userInput: originalQuery,
        userId: userId,
        // In a real scenario, more context could be added here:
        // currentApplication: applicationContext,
        // userProfile: await fetchUserProfile(userId), // e.g.
    };

    // 1. Get Enriched Intent from NLULeadAgent
    const enrichedIntent = await nluLeadAgent.analyzeIntent(subAgentInput, useLLMSynthesisForNLU);
    console.log(`[GuidanceOrchestrator] NLULeadAgent suggested action: ${enrichedIntent.suggestedNextAction?.actionType}`);
    console.log(`[GuidanceOrchestrator] NLULeadAgent primary goal: ${enrichedIntent.primaryGoal} (Confidence: ${enrichedIntent.primaryGoalConfidence?.toFixed(2)})`);


    // 2. Decide next step based on EnrichedIntent
    if (enrichedIntent.suggestedNextAction?.actionType === 'clarify_query') {
        return {
            messageToUser: enrichedIntent.suggestedNextAction.clarificationQuestion || "I need more information to help you. Could you please rephrase?",
            enrichedIntent: enrichedIntent
        };
    }

    if (enrichedIntent.suggestedNextAction?.actionType === 'invoke_skill' &&
        (enrichedIntent.suggestedNextAction.skillId === 'LearningAndGuidanceSkill' || !enrichedIntent.suggestedNextAction.skillId)) { // Fallback if no specific skillId but goal seems guidance related

        console.log("[GuidanceOrchestrator] Invoking LearningAndGuidanceSkill.");

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
        if (enrichedIntent.primaryGoal?.toLowerCase().includes("tutorial") || enrichedIntent.identifiedTasks?.some(t => t.includes("tutorial"))) {
            skillInput.guidanceTypeHint = 'find_tutorial';
        } else if (enrichedIntent.primaryGoal?.toLowerCase().includes("explain") || enrichedIntent.primaryGoal?.toLowerCase().includes("explanation")) {
            skillInput.guidanceTypeHint = 'general_explanation';
        }
        // etc. for other types based on primaryGoal or identifiedTasks

        try {
            const guidanceResult = await learningAndGuidanceSkill.execute(skillInput);
            // Ideally, the message to user would be constructed based on guidanceResult
            let friendlyMessage = `Here's what I found for "${originalQuery}":\n`;
            if (guidanceResult.guidanceProvided.length > 0) {
                guidanceResult.guidanceProvided.forEach(g => {
                    friendlyMessage += `\nTitle: ${g.title}\n`;
                    if (g.contentSnippet) friendlyMessage += `Snippet: ${g.contentSnippet.substring(0,100)}...\n`;
                    if (g.steps) friendlyMessage += `${g.steps.length} steps found.\n`;
                });
            } else {
                friendlyMessage = `I couldn't find specific guidance for "${originalQuery}", but I'll keep learning!`;
            }
             if (guidanceResult.followUpSuggestions && guidanceResult.followUpSuggestions.length > 0) {
                friendlyMessage += `\n\nFollow-up suggestions: ${guidanceResult.followUpSuggestions.join(', ')}`;
            }

            return {
                messageToUser: friendlyMessage,
                guidanceResult: guidanceResult,
                enrichedIntent: enrichedIntent
            };
        } catch (error: any) {
            console.error("[GuidanceOrchestrator] Error executing LearningAndGuidanceSkill:", error);
            return {
                messageToUser: `Sorry, I encountered an error while trying to get guidance for "${originalQuery}". Error: ${error.message}`,
                enrichedIntent: enrichedIntent
            };
        }
    }

    // Fallback for other action types or if the skill doesn't match
    let fallbackMessage = `I've analyzed your query: "${originalQuery}".\n`;
    fallbackMessage += `Goal: ${enrichedIntent.primaryGoal || 'Not clearly identified'}.\n`;
    if(enrichedIntent.suggestedNextAction?.actionType && enrichedIntent.suggestedNextAction?.actionType !== 'unable_to_determine') {
         fallbackMessage += `Suggested next step: ${enrichedIntent.suggestedNextAction.actionType}`;
         if(enrichedIntent.suggestedNextAction.reason) fallbackMessage += ` (${enrichedIntent.suggestedNextAction.reason})`;
    } else {
        fallbackMessage += "I'm not sure how to proceed with this specific request yet.";
    }


    return {
        messageToUser: fallbackMessage,
        enrichedIntent: enrichedIntent
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
    expectedResponseType: 'clarification' | 'guidance_success' | 'fallback_info' | 'error';
    expectedMessageContains?: string | string[]; // Substring(s) expected in the messageToUser
    expectedGuidanceTitles?: string[]; // if guidance_success, check for these titles
}

async function runGuidanceOrchestratorTests() {
    console.log("\\n--- Starting GuidanceOrchestrator Tests ---");
    const testCases: TestCase[] = [
        {
            description: "Test 1: Vague query, expecting clarification (Rule-based NLU)",
            query: "Help me fix stuff.",
            userId: "user-test-001",
            expectedResponseType: 'clarification',
            expectedMessageContains: "clarify your intent" // From NLULeadAgent's rule-based synthesis for vague queries
        },
        {
            description: "Test 2: Specific 'how-to' query, expecting guidance success (Rule-based NLU)",
            query: "How do I create a pivot table in SpreadsheetApp?",
            userId: "user-test-002",
            applicationContext: "SpreadsheetApp",
            expectedResponseType: 'guidance_success',
            expectedMessageContains: "Here's what I found",
            expectedGuidanceTitles: ["How to Create Pivot Tables in SpreadsheetApp"]
        },
        {
            description: "Test 3: Complex query, rule-based NLU, expecting skill invocation",
            query: "my marketing report for Q3 is hard to do, how can AI make it efficient?",
            userId: "user-test-003",
            applicationContext: "MarketingSuite",
            expectedResponseType: 'fallback_info', // Because our mock skill doesn't handle "WorkflowAutomationSuggesterSkill" yet
            expectedMessageContains: ["Goal: make report generation efficient", "Suggested next step: invoke_skill (WorkflowAutomationSuggesterSkill)"]
        },
        {
            description: "Test 4: Complex query, (mocked) LLM-based NLU, expecting different skill",
            query: "my marketing report for Q3 is hard to do, how can AI make it efficient?",
            userId: "user-test-004",
            applicationContext: "MarketingSuite",
            useLLMSynthesis: true, // This activates LLM-based synthesis in NLULeadAgent
            expectedResponseType: 'fallback_info',
            // This now reflects the output from RealLLMService's simulation for 'custom_lead_agent_synthesis'
            expectedMessageContains: [
                "Goal: Simulated: Schedule meeting about Project Alpha",
                "Suggested next step: invoke_skill (CalendarSkill)"
            ]
        },
        {
            description: "Test 5: Query that analytical agent deems inconsistent",
            // For this, we need to ensure the NLULeadAgent's rule-based synthesis correctly prioritizes clarification
            // The mock analytical agent returns inconsistency for generic queries by default.
            query: "This statement is false and also not false.", // A bit contrived for mock
            userId: "user-test-005",
            expectedResponseType: 'clarification',
            expectedMessageContains: "inconsistent or unclear"
        }
    ];

    let testsPassed = 0;
    for (const tc of testCases) {
        console.log(`\nRunning: ${tc.description}`);
        // Temporarily modify sub-agent mocks if needed for specific test cases (as done in NLULeadAgent example)
        if (tc.query.includes("This statement is false")) {
             analyticalAgent.analyze = async (input: SubAgentInput) => ({
                identifiedEntities: [], explicitTasks: [], informationNeeded: [],
                logicalConsistency: { isConsistent: false, reason: "Query contains a logical paradox." },
                problemType: "paradox_check", rawLLMResponse: "{}"
            });
        } else {
            // Restore default mock behavior for analytical agent (important if changed by a previous test)
            // This is a bit hacky; proper test setup/teardown would handle this better.
            const defaultAnalyticalAgent = new AnalyticalAgent(mockLLM);
            analyticalAgent.analyze = defaultAnalyticalAgent.analyze.bind(defaultAnalyticalAgent);
        }


        const response = await processGuidanceRequest(
            tc.query,
            tc.userId,
            tc.applicationContext,
            tc.useLLMSynthesis
        );

        let pass = false;
        switch (tc.expectedResponseType) {
            case 'clarification':
                pass = response.messageToUser.toLowerCase().includes("clarify") ||
                       response.messageToUser.toLowerCase().includes("more information") ||
                       response.messageToUser.toLowerCase().includes("rephrase") ||
                       response.messageToUser.toLowerCase().includes("inconsistent or unclear");
                if (tc.expectedMessageContains) {
                     const messages = Array.isArray(tc.expectedMessageContains) ? tc.expectedMessageContains : [tc.expectedMessageContains];
                     pass = pass && messages.every(m => response.messageToUser.includes(m));
                }
                break;
            case 'guidance_success':
                pass = !!response.guidanceResult && response.guidanceResult.guidanceProvided.length > 0;
                 if (pass && tc.expectedMessageContains) {
                     const messages = Array.isArray(tc.expectedMessageContains) ? tc.expectedMessageContains : [tc.expectedMessageContains];
                     pass = pass && messages.every(m => response.messageToUser.includes(m));
                 }
                if (pass && tc.expectedGuidanceTitles && response.guidanceResult) {
                    pass = pass && tc.expectedGuidanceTitles.every(title =>
                        response.guidanceResult?.guidanceProvided.some(g => g.title === title)
                    );
                }
                break;
            case 'fallback_info': // For when NLU is good, but skill isn't the one we're testing deeply
                 pass = !response.guidanceResult || response.guidanceResult.guidanceProvided.length === 0;
                 if (tc.expectedMessageContains) {
                     const messages = Array.isArray(tc.expectedMessageContains) ? tc.expectedMessageContains : [tc.expectedMessageContains];
                     pass = pass && messages.every(m => response.messageToUser.includes(m));
                 }
                break;
            case 'error':
                pass = response.messageToUser.toLowerCase().includes("error");
                break;
        }

        if (pass) {
            testsPassed++;
            console.log(`PASS: ${tc.description}`);
        } else {
            console.error(`FAIL: ${tc.description}`);
            console.log("  Expected response type:", tc.expectedResponseType);
            if(tc.expectedMessageContains) console.log("  Expected message contains:", tc.expectedMessageContains);
            console.log("  Actual messageToUser:", response.messageToUser);
            if(tc.expectedResponseType === 'guidance_success') console.log("  Actual guidanceResult:", JSON.stringify(response.guidanceResult, null, 2).substring(0, 300) + "...");
        }
         console.log("  NLU Primary Goal:", response.enrichedIntent?.primaryGoal, "(Confidence:", response.enrichedIntent?.primaryGoalConfidence?.toFixed(2), ")");
         console.log("  NLU Suggested Action:", response.enrichedIntent?.suggestedNextAction?.actionType, "Reason:", response.enrichedIntent?.suggestedNextAction?.reason);

    }

    console.log(`\n--- GuidanceOrchestrator Tests Complete ---`);
    console.log(`${testsPassed}/${testCases.length} test cases passed.`);
    if (testsPassed === testCases.length) {
        console.log("All tests passed successfully!");
        return true;
    } else {
        console.error(`${testCases.length - testsPassed} test(s) failed.`);
        return false;
    }
}

// To run tests:
// runGuidanceOrchestratorTests();

console.log("GuidanceOrchestrator loaded. Call runGuidanceOrchestratorTests() to run integration tests.");
