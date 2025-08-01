import {
    SubAgentInput,
    AnalyticalAgentResponse,
    CreativeAgentResponse,
    PracticalAgentResponse,
    TaxAgentResponse,
    EnrichedIntent,
    AgentLLMService,
    DEFAULT_MODEL_LEAD_SYNTHESIS,
    DEFAULT_TEMPERATURE_LEAD_SYNTHESIS,
    safeParseJSON
} from './nlu_types';
import { StructuredLLMPrompt } from '../lib/llmUtils';

export class SynthesizingAgent {
    private llmService: AgentLLMService;
    private agentName: string = "SynthesizingAgent";

    constructor(llmService: AgentLLMService) {
        this.llmService = llmService;
    }

    private constructPrompt(
        input: SubAgentInput,
        analytical: AnalyticalAgentResponse | null,
        creative: CreativeAgentResponse | null,
        practical: PracticalAgentResponse | null,
        socialMedia: any,
        contentCreation: any,
        personalizedShopping: any,
        recruitmentRecommendation: any,
        vibeHacking: any,
        tax: TaxAgentResponse | null,
        marketingAutomation: any
    ): StructuredLLMPrompt {
        const systemMessage = `
You are the Synthesizing Agent. Your task is to consolidate the analyses from three sub-agents (Analytical, Creative, Practical) into a single, actionable EnrichedIntent object.
User's original query: "${input.userInput}"

Analytical Agent's findings:
${JSON.stringify(analytical, null, 2)}

Creative Agent's findings:
${JSON.stringify(creative, null, 2)}

Practical Agent's findings:
${JSON.stringify(practical, null, 2)}

Social Media Agent's findings:
${JSON.stringify(socialMedia, null, 2)}

Content Creation Agent's findings:
${JSON.stringify(contentCreation, null, 2)}

Personalized Shopping Agent's findings:
${JSON.stringify(personalizedShopping, null, 2)}

Recruitment Recommendation Agent's findings:
${JSON.stringify(recruitmentRecommendation, null, 2)}

Vibe Hacking Agent's findings:
${JSON.stringify(vibeHacking, null, 2)}

Tax Agent's findings:
${JSON.stringify(tax, null, 2)}

Marketing Automation Agent's findings:
${JSON.stringify(marketingAutomation, null, 2)}

Based on all the above, determine the most likely primary goal, extract key parameters, and suggest the best next action.
The next action can be:
- 'invoke_skill': If a specific skill/tool should handle it (provide skillId).
- 'clarify_query': If more information is needed from the user (provide clarificationQuestion).
- 'perform_direct_action': If the request is simple and can be handled directly (provide details).
- 'no_action_needed': If the query doesn't require action (e.g., a greeting).
- 'unable_to_determine': If the intent is still too unclear.

Return ONLY a valid JSON object with the exact following structure. Ensure all fields are present.
{
  "primaryGoal": "string (A concise statement of the user's most likely primary intention, e.g., 'schedule a meeting with Jane about Project X')",
  "primaryGoalConfidence": "number (A score from 0.0 to 1.0 indicating your confidence in the primaryGoal. High confidence (0.8-1.0) means the goal is clear and actionable. Medium (0.5-0.7) may need minor clarification or has some ambiguity. Low (<0.5) means the goal is very unclear.)",
  "identifiedTasks": ["string", ... (List of specific sub-tasks derived primarily from Analytical Agent, if any, that contribute to the primaryGoal. Empty array if none.)],
  "extractedParameters": { /* key: value pairs, e.g., {"topic": "Project X", "attendee": "Jane"} */ },
  "suggestedNextAction": {
    "actionType": "'invoke_skill' | 'clarify_query' | 'perform_direct_action' | 'no_action_needed' | 'unable_to_determine'",
    "skillId": "string (If actionType is 'invoke_skill', the ID of the skill to call, e.g., 'LearningAndGuidanceSkill', 'EmailTriageSkill', 'DataAnalystSkill'. Can be null if not applicable.)",
    "clarificationQuestion": "string (If actionType is 'clarify_query', a specific question to ask the user. Can be null if not applicable.)",
    "directActionDetails": { /* object (If actionType is 'perform_direct_action', details for the action. Can be null if not applicable.) */ },
    "reason": "string (A brief explanation for why this next action is suggested, considering the sub-agent inputs.)"
  }
}

Decision-Making Guidelines:
- If Analytical Agent identifies clear, consistent tasks and Practical Agent deems them feasible, the \`primaryGoal\` should reflect these tasks, and \`suggestedNextAction.actionType\` should likely be 'invoke_skill' or 'perform_direct_action'. Confidence should be high.
- If the Analytical Agent identifies the problem type as 'data_analysis', the \`primaryGoal\` should reflect this, and \`suggestedNextAction.actionType\` should likely be 'invoke_skill' with a relevant data skill.
- If the Analytical Agent identifies the problem type as 'advanced_research', 'social_media_management', 'content_creation', 'personalized_shopping', 'legal_document_analysis', 'recruitment_recommendation', or 'vibe_hacking', the \`primaryGoal\` should reflect this, and \`suggestedNextAction.actionType\` should likely be 'invoke_skill' with the corresponding skillId (e.g., 'advancedResearch', 'socialMedia', 'contentCreation', 'personalizedShopping', 'legalDocumentAnalysis', 'recruitmentRecommendation', 'vibeHacking').
- If Creative Agent raises significant ambiguities or Practical Agent indicates low feasibility or failed common sense validation, \`suggestedNextAction.actionType\` should likely be 'clarify_query'. Confidence in \`primaryGoal\` might be lower. The \`clarificationQuestion\` should try to address the core issue.
- If the overall intent is very unclear even after sub-agent analysis, use 'unable_to_determine' and provide a reason.
- \`primaryGoalConfidence\` should reflect the overall clarity and actionability. For example, if a clarification is needed due to ambiguity, confidence might be medium. If feasibility is low, confidence might also be medium/low even if the task is clear.

Do NOT include any other fields from the full EnrichedIntent structure (like originalQuery, userId, rawSubAgentResponses, alternativeInterpretations, etc.) in your JSON output. These will be added by the calling system.
Do not include any explanations, apologies, or conversational text outside this JSON object. Your entire response must be the JSON object itself.
`;
        return {
            task: 'custom_synthesis',
            data: { system_prompt: systemMessage, user_query: "" }
        };
    }

    public async synthesize(
        input: SubAgentInput,
        analytical: AnalyticalAgentResponse | null,
        creative: CreativeAgentResponse | null,
        practical: PracticalAgentResponse | null,
        socialMedia: any,
        contentCreation: any,
        personalizedShopping: any,
        recruitmentRecommendation: any,
        vibeHacking: any,
        tax: TaxAgentResponse | null,
        marketingAutomation: any
    ): Promise<Partial<EnrichedIntent>> {
        const structuredPrompt = this.constructPrompt(input, analytical, creative, practical, socialMedia, contentCreation, personalizedShopping, recruitmentRecommendation, vibeHacking, tax, marketingAutomation);
        const P_SYNTHESIZING_AGENT_TIMER_LABEL = `[${this.agentName}] LLM Call Duration`;

        console.log(`[${this.agentName}] Calling LLM service for task: ${structuredPrompt.task}`);
        console.time(P_SYNTHESIZING_AGENT_TIMER_LABEL);
        const llmResponse = await this.llmService.generate(
            structuredPrompt,
            DEFAULT_MODEL_LEAD_SYNTHESIS,
            {
                temperature: DEFAULT_TEMPERATURE_LEAD_SYNTHESIS,
                isJsonOutput: true
            }
        );
        console.timeEnd(P_SYNTHESIZING_AGENT_TIMER_LABEL);

        if (llmResponse.usage) {
            console.log(`[${this.agentName}] LLM Token Usage: ${JSON.stringify(llmResponse.usage)}`);
        }

        if (!llmResponse.success || !llmResponse.content) {
            console.error(`[${this.agentName}] LLM call failed or returned no content. Error: ${llmResponse.error}`);
            return {
                suggestedNextAction: {
                    actionType: 'unable_to_determine',
                    reason: `LLM synthesis failed: ${llmResponse.error || 'No content'}`
                }
            };
        }

        const parsedResponse = safeParseJSON<Partial<EnrichedIntent>>(
            llmResponse.content,
            this.agentName,
            structuredPrompt.task
        );

        if (!parsedResponse) {
            console.error(`[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`);
            return {
                suggestedNextAction: {
                    actionType: 'unable_to_determine',
                    reason: "Failed to parse LLM JSON response."
                }
            };
        }

        return parsedResponse;
    }
}
