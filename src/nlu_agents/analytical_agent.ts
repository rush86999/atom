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
5.  **Problem Type**: Classify the general type of problem (e.g., information_retrieval, task_execution, data_analysis, comparison, troubleshooting).

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

        // For actual LLM call, would be something like:
        // const llmResponse = await this.llmService.generate(structuredPrompt, DEFAULT_MODEL_FOR_AGENTS, { temperature: DEFAULT_TEMPERATURE_ANALYTICAL });

        // --- MOCK LLM RESPONSE ---
        // Simulating LLM call using MockLLMService or a direct mock for now
        let mockLLMContent: string;
        if (input.userInput.toLowerCase().includes("budget") && input.userInput.toLowerCase().includes("q3")) {
            mockLLMContent = JSON.stringify({
                identifiedEntities: ["Q3 budget", "marketing report"],
                explicitTasks: ["make report generation efficient", "use new AI thing"],
                informationNeeded: ["details about 'new AI thing'", "current report generation process"],
                logicalConsistency: {
                    isConsistent: true,
                    reason: "Request is clear."
                },
                problemType: "process_optimization"
            });
        } else if (input.userInput.toLowerCase().includes("how to create pivot table")) {
            mockLLMContent = JSON.stringify({
                identifiedEntities: ["pivot table", "SpreadsheetApp"],
                explicitTasks: ["create pivot table"],
                informationNeeded: ["steps to create pivot table in SpreadsheetApp"],
                logicalConsistency: {
                    isConsistent: true,
                    reason: "Request is specific and clear."
                },
                problemType: "how-to_guidance"
            });
        } else {
            mockLLMContent = JSON.stringify({
                identifiedEntities: ["user query"],
                explicitTasks: ["understand query"],
                informationNeeded: ["clarification of intent"],
                logicalConsistency: {
                    isConsistent: false,
                    reason: "Query is too vague or generic for detailed analysis."
                },
                problemType: "general_query"
            });
        }
        const mockResponse: LLMServiceResponse = {
            success: true,
            content: mockLLMContent,
            usage: { promptTokens: 100, completionTokens: 50, totalTokens: 150 }
        };
        // --- END MOCK LLM RESPONSE ---

        const parsedResponse = safeParseJSON<Partial<AnalyticalAgentResponse>>(
            mockResponse.content,
            this.agentName,
            structuredPrompt.task
        );

        if (!mockResponse.success || !parsedResponse) {
            console.error(`[${this.agentName}] LLM call failed or response parsing failed. Error: ${mockResponse.error}`);
            return { // Return a default/error response structure
                logicalConsistency: { isConsistent: false, reason: "LLM analysis failed." },
                rawLLMResponse: mockResponse.content || "No content from LLM."
            };
        }

        return {
            identifiedEntities: parsedResponse.identifiedEntities || [],
            explicitTasks: parsedResponse.explicitTasks || [],
            informationNeeded: parsedResponse.informationNeeded || [],
            logicalConsistency: parsedResponse.logicalConsistency || { isConsistent: true, reason: "N/A" },
            problemType: parsedResponse.problemType || "unknown",
            rawLLMResponse: mockResponse.content,
        };
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
