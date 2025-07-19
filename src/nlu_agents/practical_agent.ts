import {
    SubAgentInput,
    PracticalAgentResponse,
    AgentLLMService,
    DEFAULT_MODEL_FOR_AGENTS,
    DEFAULT_TEMPERATURE_PRACTICAL,
    safeParseJSON
} from './nlu_types';
import { StructuredLLMPrompt, LLMServiceResponse } from '../lib/llmUtils';

export class PracticalAgent {
    private llmService: AgentLLMService;
    private agentName: string = "PracticalAgent";

    constructor(llmService: AgentLLMService) {
        this.llmService = llmService;
    }

    private constructPrompt(input: SubAgentInput): StructuredLLMPrompt {
        // Consider enhancing SubAgentInput to include more context like:
        // input.availableTools = ["ToolA", "ToolB", "AI_Helper_Bot"];
        // input.userRole = "Marketing Analyst";
        // input.recentActivity = ["Viewed Q2 Report", "Edited Campaign Brief X"];
        // This would make the practical agent much more powerful.

        const systemMessage = `
You are the Practical Intelligence Agent. Your role is to assess the real-world applicability and implications of the user's query.
Focus on:
1.  **Contextual Factors**: What current user/system context is relevant? (e.g., current project, recent documents, user role).
2.  **Feasibility Assessment**: How feasible is the request given current tools, knowledge, and resources? What are key dependencies?
3.  **Efficiency Tips**: Are there common-sense shortcuts or more efficient ways to achieve the user's stated goal?
4.  **Resource Implications**: What time, tools, or access rights might be needed?
5.  **Common Sense Validation**: Does the request make sense in a typical workflow? Is it unusual or potentially problematic?

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "contextualFactors": ["factor1", "factor2", ...],
  "feasibilityAssessment": {
    "rating": "High" | "Medium" | "Low" | "Unknown",
    "reason": "string",
    "dependencies": ["dependency1", "dependency2", ...]
  },
  "efficiencyTips": ["tip1", "tip2", ...],
  "resourceImplications": {
    "timeEstimate": "Quick" | "Moderate" | "Significant" | "Unknown",
    "toolsNeeded": ["tool1", "tool2", ...]
  },
  "commonSenseValidation": {
    "isValid": boolean,
    "reason": "string (if not valid, explain why)"
  }
}

Ensure all specified fields are present in your JSON output. If no items apply for a list-based field (like "contextualFactors" or "toolsNeeded"), return an empty array [].
Do not include any explanations, apologies, or conversational text outside the JSON structure. Your entire response must be the JSON object itself.

Consider the following context when forming your response:
User's query: "${input.userInput}"
User ID: ${input.userId || 'N/A'}
Hypothetical available tools or system capabilities: ["Standard Office Suite", "Internal Wiki", "AI_Helper_Bot v1.2", "ProjectDB Access", "Calendar Integration", "Email Client"]
(If specific user context like current application, role, or recent documents were provided, you would use that here too.)
`;

        return {
            task: 'custom_practical_analysis', // Custom task type
            data: {
                system_prompt: systemMessage,
                user_query: input.userInput,
            }
        };
    }

    public async analyze(input: SubAgentInput): Promise<PracticalAgentResponse> {
        const structuredPrompt = this.constructPrompt(input);
        const P_PRACTICAL_AGENT_TIMER_LABEL = `[${this.agentName}] LLM Call Duration`;

        console.log(`[${this.agentName}] Calling LLM service for task: ${structuredPrompt.task}`);
        console.time(P_PRACTICAL_AGENT_TIMER_LABEL);
        const llmResponse = await this.llmService.generate(
            structuredPrompt,
            DEFAULT_MODEL_FOR_AGENTS, // Or a model specifically chosen for practical tasks
            {
                temperature: DEFAULT_TEMPERATURE_PRACTICAL,
                isJsonOutput: true
            }
        );
        console.timeEnd(P_PRACTICAL_AGENT_TIMER_LABEL);

        if (llmResponse.usage) {
            console.log(`[${this.agentName}] LLM Token Usage: ${JSON.stringify(llmResponse.usage)}`);
        }

        if (!llmResponse.success || !llmResponse.content) {
            console.error(`[${this.agentName}] LLM call failed or returned no content. Error: ${llmResponse.error}`);
            return { // Return a default/error response structure, ensuring all fields are covered
                contextualFactors: [],
                feasibilityAssessment: { rating: "Unknown", reason: `LLM analysis failed: ${llmResponse.error || 'No content'}` },
                efficiencyTips: [],
                resourceImplications: { timeEstimate: "Unknown", toolsNeeded: [] },
                commonSenseValidation: { isValid: false, reason: `LLM analysis failed: ${llmResponse.error || 'No content'}` },
                rawLLMResponse: llmResponse.content || `Error: ${llmResponse.error}`
            };
        }

        const parsedResponse = safeParseJSON<Partial<PracticalAgentResponse>>(
            llmResponse.content,
            this.agentName,
            structuredPrompt.task
        );

        if (!parsedResponse) {
            console.error(`[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`);
            return { // Return a default/error response structure if parsing fails
                feasibilityAssessment: { rating: "Unknown", reason: "Failed to parse LLM JSON response." },
                commonSenseValidation: { isValid: false, reason: "Failed to parse LLM JSON response." },
                rawLLMResponse: llmResponse.content
            };
        }

        return {
            contextualFactors: parsedResponse.contextualFactors || [],
            feasibilityAssessment: parsedResponse.feasibilityAssessment || { rating: "Unknown", reason: "Not specified by LLM." },
            efficiencyTips: parsedResponse.efficiencyTips || [],
            resourceImplications: parsedResponse.resourceImplications || { timeEstimate: "Unknown", toolsNeeded: [] },
            commonSenseValidation: parsedResponse.commonSenseValidation || { isValid: true, reason: "Not specified by LLM." },
            rawLLMResponse: llmResponse.content,
        };
    }
}

// Example Usage (for testing purposes)
/*
import { MockLLMService } from '../lib/llmUtils';

async function testPracticalAgent() {
    const mockLLM = new MockLLMService();
    const agent = new PracticalAgent(mockLLM);

    const input1: SubAgentInput = {
        userInput: "How can I make my Q3 marketing report generation more efficient, maybe using that new AI thing?",
        userId: "marketer7"
    };
    console.log("--- Practical Test 1 ---");
    const response1 = await agent.analyze(input1);
    console.log(JSON.stringify(response1, null, 2));

    const input2: SubAgentInput = {
        userInput: "How to create pivot table in SpreadsheetApp",
        userId: "analystUser"
    };
    console.log("\\n--- Practical Test 2 ---");
    const response2 = await agent.analyze(input2);
    console.log(JSON.stringify(response2, null, 2));

    const input3: SubAgentInput = {
        userInput: "Help me.",
        userId: "genericUser"
    };
    console.log("\\n--- Practical Test 3 (Vague) ---");
    const response3 = await agent.analyze(input3);
    console.log(JSON.stringify(response3, null, 2));
}

// testPracticalAgent();
*/
console.log("PracticalAgent class loaded. To test, uncomment and run testPracticalAgent().");
