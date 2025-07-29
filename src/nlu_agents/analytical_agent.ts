import {
    SubAgentInput,
    AnalyticalAgentResponse,
    AgentLLMService,
    DEFAULT_MODEL_FOR_AGENTS,
    DEFAULT_TEMPERATURE_ANALYTICAL,
    safeParseJSON
} from './nlu_types';
import { StructuredLLMPrompt, LLMServiceResponse } from '../lib/llmUtils';

export class AnalyticalAgent {
    private llmService: AgentLLMService;
    private agentName: string = "AnalyticalAgent";

    constructor(llmService: AgentLLMService) {
        this.llmService = llmService;
    }

    private constructPrompt(input: SubAgentInput): StructuredLLMPrompt {
        const systemMessage = `
You are the Analytical Intelligence Agent. Your role is to meticulously analyze the user's query to identify its core components.
Focus on:
1.  **Entities**: Key nouns, concepts, project names, dates, specific items mentioned.
2.  **Explicit Tasks**: Verbs and actions the user explicitly states they want to perform.
3.  **Information Needed**: What specific information is the user seeking?
4.  **Logical Consistency**: Is the request clear, unambiguous, and logically sound? Identify any contradictions or vagueness.
5.  **Problem Type**: Classify the general type of problem (e.g., information_retrieval, task_execution, data_analysis, comparison, troubleshooting, advanced_research, social_media_management, content_creation, personalized_shopping, legal_document_analysis, recruitment_recommendation, vibe_hacking).

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "identifiedEntities": ["entity1", "entity2", ...],
  "explicitTasks": ["task1 description", "task2 description", ...],
  "informationNeeded": ["specific info1", "specific info2", ...],
  "logicalConsistency": {
    "isConsistent": boolean,
    "reason": "string (if not consistent, explain why)"
  },
  "problemType": "type_string"
}

Do not include any explanations or conversational text outside the JSON structure.
User's environment context (if provided, use it to refine entity/task identification):
UserId: ${input.userId || 'N/A'}
`;

        return {
            task: 'custom_analytical_analysis', // Custom task type for LLM logging/differentiation if needed
            data: {
                system_prompt: systemMessage,
                user_query: input.userInput,
            }
        };
    }

    public async analyze(input: SubAgentInput): Promise<AnalyticalAgentResponse> {
        const structuredPrompt = this.constructPrompt(input);
        const P_ANALYTICAL_AGENT_TIMER_LABEL = `[${this.agentName}] LLM Call Duration`;

        console.log(`[${this.agentName}] Calling LLM service for task: ${structuredPrompt.task}`);
        console.time(P_ANALYTICAL_AGENT_TIMER_LABEL);
        const llmResponse = await this.llmService.generate(
            structuredPrompt,
            DEFAULT_MODEL_FOR_AGENTS,
            {
                temperature: DEFAULT_TEMPERATURE_ANALYTICAL,
                isJsonOutput: true // Crucial for ensuring RealLLMService requests JSON mode
            }
        );

        if (!llmResponse.success || !llmResponse.content) {
            console.error(`[${this.agentName}] LLM call failed or returned no content. Error: ${llmResponse.error}`);
            return { // Return a default/error response structure
                logicalConsistency: { isConsistent: false, reason: `LLM analysis failed: ${llmResponse.error || 'No content'}` },
                rawLLMResponse: llmResponse.content || `Error: ${llmResponse.error}`
            };
        }

        // Attempt to parse the JSON response from the LLM
        const parsedResponse = safeParseJSON<Partial<AnalyticalAgentResponse>>( // Expecting a partial response that matches the structure
            llmResponse.content,
            this.agentName,
            structuredPrompt.task
        );

        if (!parsedResponse) {
            console.error(`[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`);
            return { // Return a default/error response structure if parsing fails
                logicalConsistency: { isConsistent: false, reason: "Failed to parse LLM JSON response." },
                rawLLMResponse: llmResponse.content
            };
        }

        // Construct the full response, providing defaults for any missing fields
        // This also serves as a basic validation that the LLM is returning something usable.
        // More advanced schema validation could be added here (e.g., using Zod or AJV).
        const analyticalAgentResponse: AnalyticalAgentResponse = {
            identifiedEntities: parsedResponse.identifiedEntities || [],
            explicitTasks: parsedResponse.explicitTasks || [],
            informationNeeded: parsedResponse.informationNeeded || [],
            logicalConsistency: parsedResponse.logicalConsistency || { isConsistent: true, reason: "Consistency not specified by LLM." },
            problemType: parsedResponse.problemType || "unknown",
            rawLLMResponse: llmResponse.content, // Always include the raw response for debugging
        };

        if (analyticalAgentResponse.problemType === 'data_analysis') {
            const dataAnalystResponse = await this.dataAnalystAgent.analyze(input);
            analyticalAgentResponse.dataAnalystResponse = dataAnalystResponse;
        }

        return analyticalAgentResponse;
    }
}

// Example Usage (for testing purposes, would be removed or in a test file)
/*
import { MockLLMService } from '../lib/llmUtils';

async function testAnalyticalAgent() {
    const mockLLM = new MockLLMService(); // Using the general mock service
    const agent = new AnalyticalAgent(mockLLM);

    const input1: SubAgentInput = {
        userInput: "Can you tell me about the Q3 budget for the marketing report and how to make it more efficient, maybe using that new AI thing?",
        userId: "testUser123"
    };
    console.log("--- Analytical Test 1 ---");
    const response1 = await agent.analyze(input1);
    console.log(JSON.stringify(response1, null, 2));

    const input2: SubAgentInput = {
        userInput: "How to create pivot table in SpreadsheetApp",
        userId: "testUser456"
    };
    console.log("\\n--- Analytical Test 2 ---");
    const response2 = await agent.analyze(input2);
    console.log(JSON.stringify(response2, null, 2));

    const input3: SubAgentInput = {
        userInput: "Help me.",
        userId: "testUser789"
    };
    console.log("\\n--- Analytical Test 3 (Vague) ---");
    const response3 = await agent.analyze(input3);
    console.log(JSON.stringify(response3, null, 2));
}

// testAnalyticalAgent();
*/

console.log("AnalyticalAgent class loaded. To test, uncomment and run testAnalyticalAgent().");
