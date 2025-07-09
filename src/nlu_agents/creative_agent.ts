import {
    SubAgentInput,
    CreativeAgentResponse,
    AgentLLMService,
    DEFAULT_MODEL_FOR_AGENTS,
    DEFAULT_TEMPERATURE_CREATIVE,
    safeParseJSON
} from './nlu_types';
import { StructuredLLMPrompt, LLMServiceResponse } from '../lib/llmUtils';

export class CreativeAgent {
    private llmService: AgentLLMService;
    private agentName: string = "CreativeAgent";

    constructor(llmService: AgentLLMService) {
        this.llmService = llmService;
    }

    private constructPrompt(input: SubAgentInput): StructuredLLMPrompt {
        const systemMessage = `
You are the Creative Intelligence Agent. Your role is to think outside the box about the user's query.
Focus on:
1.  **Alternative Goals**: What might be the user's deeper, unstated goal, beyond the literal request?
2.  **Novel Solutions/Ideas**: Brainstorm innovative ways to address the user's query or underlying need. Think of new approaches or combinations of tools/features.
3.  **Unstated Assumptions**: What assumptions might the user be making that could be challenged or explored?
4.  **Potential Enhancements**: If the user's request is fulfilled, are there related value-adds or next steps that could be proactively suggested?
5.  **Ambiguity Flags**: Identify terms or phrases that are subjective, ambiguous, or could have multiple interpretations.

Return your analysis ONLY as a valid JSON object with the following structure. Ensure all specified fields are present in your JSON output. If no items apply for a list-based field (like "alternativeGoals"), return an empty array `[]` for that field.
{
  "alternativeGoals": ["string", ...],
  "novelSolutionsSuggested": ["string", ...],
  "unstatedAssumptions": ["string", ...],
  "potentialEnhancements": ["string", ...],
  "ambiguityFlags": [{ "term": "string", "reason": "string" }, ...]
}

Do not include any explanations, apologies, or conversational text outside the JSON structure. Your entire response must be the JSON object itself.
User's query: "${input.userInput}"
`;

        return {
            task: 'custom_creative_analysis', // Custom task type
            data: {
                system_prompt: systemMessage,
                user_query: input.userInput, // User query is already in system prompt, but can be passed here too
            }
        };
    }

    public async analyze(input: SubAgentInput): Promise<CreativeAgentResponse> {
        const structuredPrompt = this.constructPrompt(input);
        const P_CREATIVE_AGENT_TIMER_LABEL = `[${this.agentName}] LLM Call Duration`;

        console.log(`[${this.agentName}] Calling LLM service for task: ${structuredPrompt.task}`);
        console.time(P_CREATIVE_AGENT_TIMER_LABEL);
        const llmResponse = await this.llmService.generate(
            structuredPrompt,
            DEFAULT_MODEL_FOR_AGENTS, // Or a model specifically chosen for creative tasks
            {
                temperature: DEFAULT_TEMPERATURE_CREATIVE, // Higher temperature for creativity
                isJsonOutput: true
            }
        );
        console.timeEnd(P_CREATIVE_AGENT_TIMER_LABEL);

        if (llmResponse.usage) {
            console.log(`[${this.agentName}] LLM Token Usage: ${JSON.stringify(llmResponse.usage)}`);
        }

        if (!llmResponse.success || !llmResponse.content) {
            console.error(`[${this.agentName}] LLM call failed or returned no content. Error: ${llmResponse.error}`);
            return { // Return a default/error response structure
                alternativeGoals: ["Error: LLM analysis failed or no content."],
                rawLLMResponse: llmResponse.content || `Error: ${llmResponse.error}`
            };
        }

        const parsedResponse = safeParseJSON<Partial<CreativeAgentResponse>>(
            llmResponse.content,
            this.agentName,
            structuredPrompt.task
        );

        if (!parsedResponse) {
            console.error(`[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`);
            return { // Return a default/error response structure if parsing fails
                alternativeGoals: ["Error: Failed to parse LLM JSON response."],
                rawLLMResponse: llmResponse.content
            };
        }

        return {
            alternativeGoals: parsedResponse.alternativeGoals || [],
            novelSolutionsSuggested: parsedResponse.novelSolutionsSuggested || [],
            unstatedAssumptions: parsedResponse.unstatedAssumptions || [],
            potentialEnhancements: parsedResponse.potentialEnhancements || [],
            ambiguityFlags: parsedResponse.ambiguityFlags || [],
            rawLLMResponse: llmResponse.content,
        };
    }
}

// Example Usage (for testing purposes)
/*
import { MockLLMService } from '../lib/llmUtils';

async function testCreativeAgent() {
    const mockLLM = new MockLLMService();
    const agent = new CreativeAgent(mockLLM);

    const input1: SubAgentInput = {
        userInput: "How can I make my Q3 marketing report generation more efficient, maybe using that new AI thing?",
        userId: "testUser123"
    };
    console.log("--- Creative Test 1 ---");
    const response1 = await agent.analyze(input1);
    console.log(JSON.stringify(response1, null, 2));

    const input2: SubAgentInput = {
        userInput: "How to create pivot table?",
        userId: "testUser456"
    };
    console.log("\\n--- Creative Test 2 ---");
    const response2 = await agent.analyze(input2);
    console.log(JSON.stringify(response2, null, 2));

    const input3: SubAgentInput = {
        userInput: "Help me.",
        userId: "testUser789"
    };
    console.log("\\n--- Creative Test 3 (Vague) ---");
    const response3 = await agent.analyze(input3);
    console.log(JSON.stringify(response3, null, 2));
}

// testCreativeAgent();
*/
console.log("CreativeAgent class loaded. To test, uncomment and run testCreativeAgent().");
