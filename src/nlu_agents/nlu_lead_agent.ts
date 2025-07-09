import {
    SubAgentInput,
    AnalyticalAgentResponse,
    CreativeAgentResponse,
    PracticalAgentResponse,
    EnrichedIntent,
    AgentLLMService, // For sub-agents and potentially lead agent's own LLM calls
    DEFAULT_MODEL_LEAD_SYNTHESIS,
    DEFAULT_TEMPERATURE_LEAD_SYNTHESIS,
    safeParseJSON
} from './nlu_types';
import { AnalyticalAgent } from './analytical_agent';
import { CreativeAgent } from './creative_agent';
import { PracticalAgent } from './practical_agent';
import { StructuredLLMPrompt, LLMServiceResponse } from '../lib/llmUtils'; // For lead agent's own LLM calls

export class NLULeadAgent {
    private analyticalAgent: AnalyticalAgent;
    private creativeAgent: CreativeAgent;
    private practicalAgent: PracticalAgent;
    private llmService: AgentLLMService; // For synthesis LLM call if used
    private agentName: string = "NLULeadAgent";

    constructor(
        analyticalAgent: AnalyticalAgent,
        creativeAgent: CreativeAgent,
        practicalAgent: PracticalAgent,
        llmService: AgentLLMService // LLM Service for the lead agent itself (e.g., for synthesis)
    ) {
        this.analyticalAgent = analyticalAgent;
        this.creativeAgent = creativeAgent;
        this.practicalAgent = practicalAgent;
        this.llmService = llmService;
    }

    // Initial rule-based synthesis. Can be replaced/augmented with an LLM call.
    private synthesizeResponses(
        input: SubAgentInput,
        analytical: AnalyticalAgentResponse | null,
        creative: CreativeAgentResponse | null,
        practical: PracticalAgentResponse | null
    ): Partial<EnrichedIntent> {
        const synthesisLog: string[] = ["Starting rule-based synthesis."];
        let primaryGoal: string | undefined = undefined;
        let primaryGoalConfidence: number = 0.0;
        let identifiedTasks: string[] = [];
        let extractedParameters: Record<string, any> = {};
        let suggestedNextAction: EnrichedIntent['suggestedNextAction'] = {
            actionType: 'unable_to_determine',
            reason: "Default fallback"
        };

        if (analytical) {
            synthesisLog.push("Processing Analytical Agent response.");
            if (analytical.explicitTasks && analytical.explicitTasks.length > 0) {
                identifiedTasks = [...analytical.explicitTasks];
                primaryGoal = analytical.explicitTasks[0]; // Simplistic: first task is primary goal
                primaryGoalConfidence = (analytical.logicalConsistency?.isConsistent) ? 0.7 : 0.4;
                synthesisLog.push(`Derived primary goal '${primaryGoal}' from analytical tasks with confidence ${primaryGoalConfidence}.`);
            } else if (analytical.problemType) {
                 primaryGoal = `Address problem type: ${analytical.problemType}`;
                 primaryGoalConfidence = (analytical.logicalConsistency?.isConsistent) ? 0.6 : 0.3;
                 synthesisLog.push(`Derived primary goal '${primaryGoal}' from problem type with confidence ${primaryGoalConfidence}.`);
            }

            if (analytical.identifiedEntities && analytical.identifiedEntities.length > 0) {
                // Basic parameter extraction: if entities look like key-value pairs or known concepts
                analytical.identifiedEntities.forEach(entity => {
                    if (entity.toLowerCase().includes("q3")) extractedParameters["quarter"] = "Q3";
                    if (entity.toLowerCase().includes("marketing")) extractedParameters["department"] = "marketing";
                    if (entity.toLowerCase().includes("report")) extractedParameters["documentType"] = "report";
                });
                if(Object.keys(extractedParameters).length > 0) {
                    synthesisLog.push(`Extracted parameters: ${JSON.stringify(extractedParameters)}`);
                }
            }
        } else {
            synthesisLog.push("Analytical response was null.");
            primaryGoalConfidence = 0.1;
        }

        if (practical?.feasibilityAssessment?.rating === "Low") {
            synthesisLog.push("Practical Agent rated feasibility as Low.");
            suggestedNextAction = {
                actionType: 'clarify_query',
                clarificationQuestion: `The request seems difficult to achieve due to: ${practical.feasibilityAssessment.reason}. Can you provide more details or simplify the request?`,
                reason: "Low feasibility."
            };
            primaryGoalConfidence = Math.min(primaryGoalConfidence, 0.3);
        } else if (practical?.commonSenseValidation?.isValid === false) {
            synthesisLog.push("Practical Agent found common sense validation failed.");
            suggestedNextAction = {
                actionType: 'clarify_query',
                clarificationQuestion: `There's a concern with the request: ${practical.commonSenseValidation.reason}. Could you clarify your intent?`,
                reason: "Common sense validation failed."
            };
            primaryGoalConfidence = Math.min(primaryGoalConfidence, 0.3);
        } else if (analytical?.logicalConsistency?.isConsistent === false) {
            synthesisLog.push("Analytical Agent found logical inconsistency.");
             suggestedNextAction = {
                actionType: 'clarify_query',
                clarificationQuestion: `The request seems inconsistent or unclear: ${analytical.logicalConsistency.reason}. Can you rephrase or provide more details?`,
                reason: "Logical inconsistency."
            };
            primaryGoalConfidence = Math.min(primaryGoalConfidence, 0.4);
        } else if (creative?.ambiguityFlags && creative.ambiguityFlags.length > 0) {
            synthesisLog.push("Creative Agent flagged ambiguities.");
            const firstAmbiguity = creative.ambiguityFlags[0];
            suggestedNextAction = {
                actionType: 'clarify_query',
                clarificationQuestion: `The term '${firstAmbiguity.term}' is a bit ambiguous (${firstAmbiguity.reason}). Can you be more specific?`,
                reason: `Ambiguity detected: ${firstAmbiguity.term}`
            };
             primaryGoalConfidence = Math.min(primaryGoalConfidence, 0.5);
        } else if (primaryGoal && primaryGoalConfidence > 0.65) {
            // Default action if goal is reasonably clear and no major issues
            synthesisLog.push("Primary goal seems clear, suggesting skill invocation or direct action.");
            if (primaryGoal.toLowerCase().includes("report") && primaryGoal.toLowerCase().includes("efficient")) {
                 suggestedNextAction = { actionType: 'invoke_skill', skillId: 'WorkflowAutomationSuggesterSkill', reason: "High confidence goal related to report efficiency." };
            } else if (primaryGoal.toLowerCase().includes("pivot table")) {
                 suggestedNextAction = { actionType: 'invoke_skill', skillId: 'LearningAndGuidanceSkill', reason: "User asking for 'how-to' on pivot tables." };
            } else {
                 suggestedNextAction = { actionType: 'perform_direct_action', directActionDetails: { goal: primaryGoal, params: extractedParameters }, reason: "Generic high confidence goal."};
            }
        } else if (!primaryGoal) {
            synthesisLog.push("No primary goal could be determined.");
            suggestedNextAction = {
                actionType: 'clarify_query',
                clarificationQuestion: "I'm not sure I understand what you're trying to achieve. Can you please rephrase your request?",
                reason: "No primary goal identified."
            };
        }


        // If confidence is still very low after all checks, default to clarification
        if (primaryGoalConfidence < 0.35 && suggestedNextAction.actionType !== 'clarify_query') {
             synthesisLog.push(`Confidence ${primaryGoalConfidence} is too low, overriding to clarification.`);
             suggestedNextAction = {
                actionType: 'clarify_query',
                clarificationQuestion: "I'm having a bit of trouble understanding your request fully. Could you please provide more details or rephrase it?",
                reason: "Overall low confidence in understanding."
            };
        }


        synthesisLog.push("Rule-based synthesis complete.");
        return {
            primaryGoal,
            primaryGoalConfidence,
            identifiedTasks,
            extractedParameters,
            suggestedNextAction,
            alternativeInterpretations: creative?.alternativeGoals,
            potentialAmbiguities: creative?.ambiguityFlags,
            practicalConsiderations: {
                feasibility: practical?.feasibilityAssessment,
                efficiencyTips: practical?.efficiencyTips,
            },
            synthesisLog
        };
    }

    // LLM-based synthesis (conceptual, can be implemented later)
    private async synthesizeResponsesWithLLM(
        input: SubAgentInput,
        analytical: AnalyticalAgentResponse | null,
        creative: CreativeAgentResponse | null,
        practical: PracticalAgentResponse | null
    ): Promise<Partial<EnrichedIntent>> {
        const synthesisLog: string[] = ["Starting LLM-based synthesis."];
        const systemMessage = `
You are the NLU Lead Agent's Synthesizer. Your task is to consolidate the analyses from three sub-agents (Analytical, Creative, Practical) into a single, actionable EnrichedIntent object.
User's original query: "${input.userInput}"

Analytical Agent's findings:
${JSON.stringify(analytical, null, 2)}

Creative Agent's findings:
${JSON.stringify(creative, null, 2)}

Practical Agent's findings:
${JSON.stringify(practical, null, 2)}

Based on all the above, determine the most likely primary goal, extract key parameters, and suggest the best next action.
The next action can be:
- 'invoke_skill': If a specific skill/tool should handle it (provide skillId).
- 'clarify_query': If more information is needed from the user (provide clarificationQuestion).
- 'perform_direct_action': If the request is simple and can be handled directly (provide details).
- 'no_action_needed': If the query doesn't require action (e.g., a greeting).
- 'unable_to_determine': If the intent is still too unclear.

Return ONLY a valid JSON object for the EnrichedIntent structure, focusing on:
primaryGoal, primaryGoalConfidence (0.0-1.0), extractedParameters, identifiedTasks, suggestedNextAction.
Example suggestedNextAction: { "actionType": "invoke_skill", "skillId": "some_skill", "reason": "Reasoning here" }
`;
        const structuredPrompt: StructuredLLMPrompt = {
            task: 'custom_lead_agent_synthesis',
            data: { system_prompt: systemMessage, user_query: "" } // user_query is part of system_prompt here
        };

        const llmResponse = await this.llmService.generate(structuredPrompt, DEFAULT_MODEL_LEAD_SYNTHESIS, { temperature: DEFAULT_TEMPERATURE_LEAD_SYNTHESIS });

        if (!llmResponse.success || !llmResponse.content) {
            synthesisLog.push("LLM synthesis call failed or returned no content.");
            console.error(`[${this.agentName}] LLM Synthesis call failed: ${llmResponse.error}`);
            // Fallback to rule-based or return error state
            const ruleBasedFallback = this.synthesizeResponses(input, analytical, creative, practical);
            ruleBasedFallback.synthesisLog?.unshift("LLM Synthesis failed, falling back to rule-based.");
            return ruleBasedFallback;
        }
        synthesisLog.push("LLM synthesis call successful.");

        const parsedLLMSynthesis = safeParseJSON<Partial<EnrichedIntent>>(llmResponse.content, this.agentName, "LLMSynthesis");
        if (!parsedLLMSynthesis) {
             synthesisLog.push("Failed to parse LLM synthesis response.");
             const ruleBasedFallback = this.synthesizeResponses(input, analytical, creative, practical);
             ruleBasedFallback.synthesisLog?.unshift("LLM Synthesis parsing failed, falling back to rule-based.");
            return ruleBasedFallback;
        }

        parsedLLMSynthesis.synthesisLog = synthesisLog;
        return parsedLLMSynthesis;
    }


    public async analyzeIntent(input: SubAgentInput, useLLMSynthesis: boolean = false): Promise<EnrichedIntent> {
        const P_LEAD_SUB_AGENTS_TIMER_LABEL = `[${this.agentName}] All Sub-Agents Processing Duration`;
        const P_LEAD_SYNTHESIS_TIMER_LABEL = `[${this.agentName}] Synthesis Duration`;
        let totalInputTokens = 0;
        let totalCompletionTokens = 0;
        let totalTokens = 0;

        console.time(P_LEAD_SUB_AGENTS_TIMER_LABEL);
        const [analyticalResponse, creativeResponse, practicalResponse] = await Promise.all([
            this.analyticalAgent.analyze(input).catch(e => { console.error("AnalyticalAgent failed:", e); return null; }),
            this.creativeAgent.analyze(input).catch(e => { console.error("CreativeAgent failed:", e); return null; }), // Assuming Creative/Practical also log their own times/tokens
            this.practicalAgent.analyze(input).catch(e => { console.error("PracticalAgent failed:", e); return null; })
        ]);
        console.timeEnd(P_LEAD_SUB_AGENTS_TIMER_LABEL);

        // Aggregate token usage from sub-agents
        [analyticalResponse, creativeResponse, practicalResponse].forEach(response => {
            if (response?.rawLLMResponse) { // Check if it was a successful call that would have usage
                // In a real scenario, usage would be on llmResponse object from the service
                // For now, we are accessing it from the AnalyticalAgent's structure as an example
                // This part needs to be harmonized if Creative/Practical agents also return usage via RealLLMService
                // Let's assume for now only analyticalResponse has detailed usage from RealLLMService
                if (response === analyticalResponse && (response as any).usage) { // Bit of a hack for current structure
                     const usage = (response as any).usage as { promptTokens: number, completionTokens: number, totalTokens: number};
                     totalInputTokens += usage.promptTokens || 0;
                     totalCompletionTokens += usage.completionTokens || 0;
                     totalTokens += usage.totalTokens || 0;
                } else if (response?.rawLLMResponse?.includes("simulated successful LLM JSON response")) {
                    // Crude simulation for other agents if they were also using RealLLMService's simulated path
                    totalInputTokens += 100; totalCompletionTokens += 100; totalTokens += 200; // Placeholder
                }
            }
        });
        if (totalTokens > 0) {
            console.log(`[${this.agentName}] Aggregated Sub-Agent Token Usage: Input=${totalInputTokens}, Completion=${totalCompletionTokens}, Total=${totalTokens}`);
        }


        console.time(P_LEAD_SYNTHESIS_TIMER_LABEL);
        let synthesisResult: Partial<EnrichedIntent>;

        if (useLLMSynthesis) {
            // This part is using the MOCK service for now for the synthesis LLM call
            // To make it real, the NLULeadAgent needs a real LLM service passed to its constructor
            // And the OpenAIGroqService_Stub in llmUtils.ts needs to be un-stubbed.
            synthesisLog.push("Attempting LLM-based synthesis (currently mocked).");
            const mockLLMSynthesisResponse: LLMServiceResponse = { // Simulate what the LLM would return for synthesis
                success: true,
                content: JSON.stringify({
                    primaryGoal: analyticalResponse?.explicitTasks?.[0] || "Synthesized goal via mock LLM",
                    primaryGoalConfidence: 0.75,
                    extractedParameters: { detail: "Synthesized by mock LLM" },
                    identifiedTasks: analyticalResponse?.explicitTasks || [],
                    suggestedNextAction: { actionType: 'invoke_skill', skillId: 'MockSkillViaLLMSynthesis', reason: 'Mock LLM synthesis decided this.'},
                })
            };
            const parsedMockLLMSynthesis = safeParseJSON<Partial<EnrichedIntent>>(mockLLMSynthesisResponse.content, this.agentName, "MockLLMSynthesis");
            synthesisResult = parsedMockLLMSynthesis || {}; // Ensure it's not null
            if (!synthesisResult.synthesisLog) synthesisResult.synthesisLog = [];
            synthesisResult.synthesisLog.unshift("Using (mocked) LLM-based synthesis result.");

        } else {
            synthesisResult = this.synthesizeResponses(input, analyticalResponse, creativeResponse, practicalResponse);
        }


        return {
            originalQuery: input.userInput,
            userId: input.userId,
            primaryGoal: synthesisResult.primaryGoal,
            primaryGoalConfidence: synthesisResult.primaryGoalConfidence,
            extractedParameters: synthesisResult.extractedParameters,
            identifiedTasks: synthesisResult.identifiedTasks,
            suggestedNextAction: synthesisResult.suggestedNextAction,
            alternativeInterpretations: synthesisResult.alternativeInterpretations || creativeResponse?.alternativeGoals,
            potentialAmbiguities: synthesisResult.potentialAmbiguities || creativeResponse?.ambiguityFlags,
            practicalConsiderations: synthesisResult.practicalConsiderations || {
                feasibility: practicalResponse?.feasibilityAssessment,
                efficiencyTips: practicalResponse?.efficiencyTips,
            },
            rawSubAgentResponses: {
                analytical: analyticalResponse,
                creative: creativeResponse,
                practical: practicalResponse,
            },
            synthesisLog: synthesisResult.synthesisLog || ["Synthesis log not initialized."],
        };
    }
}

// Example Usage (for testing purposes)
/*
import { MockLLMService } from '../lib/llmUtils';

async function testNLULeadAgent() {
    const mockLLM = new MockLLMService(); // Used by sub-agents and lead agent for synthesis (if LLM synthesis is real)

    const analyticalAgent = new AnalyticalAgent(mockLLM);
    const creativeAgent = new CreativeAgent(mockLLM);
    const practicalAgent = new PracticalAgent(mockLLM);

    const leadAgent = new NLULeadAgent(analyticalAgent, creativeAgent, practicalAgent, mockLLM);

    const input1: SubAgentInput = {
        userInput: "How can I make my Q3 marketing report generation more efficient, maybe using that new AI thing?",
        userId: "marketer7"
    };
    console.log("--- Lead Agent Test 1 (Rule-based Synthesis) ---");
    let enrichedIntent1 = await leadAgent.analyzeIntent(input1);
    console.log(JSON.stringify(enrichedIntent1, null, 2));

    console.log("\\n--- Lead Agent Test 1 (Mock LLM-based Synthesis) ---");
    enrichedIntent1 = await leadAgent.analyzeIntent(input1, true); // Requesting LLM synthesis (mocked)
    console.log(JSON.stringify(enrichedIntent1, null, 2));


    const input2: SubAgentInput = {
        userInput: "How to create pivot table in SpreadsheetApp",
        userId: "analystUser"
    };
    console.log("\\n--- Lead Agent Test 2 (Rule-based) ---");
    const enrichedIntent2 = await leadAgent.analyzeIntent(input2);
    console.log(JSON.stringify(enrichedIntent2, null, 2));

    const input3: SubAgentInput = {
        userInput: "This is totally unfeasible and makes no sense!", // Query designed to fail practical/analytical checks
        userId: "skepticUser"
    };
    // Mocking sub-agent responses for this specific test case to show rule-based logic
    analyticalAgent.analyze = async (input: SubAgentInput) => ({ // Override mock for this test
        identifiedEntities: ["this"], explicitTasks: [], informationNeeded: [],
        logicalConsistency: { isConsistent: false, reason: "Query is an opinion, not a task." },
        problemType: "complaint", rawLLMResponse: "{}"
    });
    practicalAgent.analyze = async (input: SubAgentInput) => ({ // Override mock for this test
        feasibilityAssessment: { rating: "Low", reason: "User states it's unfeasible." },
        commonSenseValidation: { isValid: false, reason: "User states it makes no sense." },
        rawLLMResponse: "{}"
    });

    console.log("\\n--- Lead Agent Test 3 (Rule-based, expected clarification) ---");
    const enrichedIntent3 = await leadAgent.analyzeIntent(input3);
    console.log(JSON.stringify(enrichedIntent3, null, 2));
}

// testNLULeadAgent();
*/
console.log("NLULeadAgent class loaded. To test, uncomment and run testNLULeadAgent().");
