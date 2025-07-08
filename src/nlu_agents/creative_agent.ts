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

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "alternativeGoals": ["goal1", "goal2", ...],
  "novelSolutionsSuggested": ["solution1", "solution2", ...],
  "unstatedAssumptions": ["assumption1", "assumption2", ...],
  "potentialEnhancements": ["enhancement1", "enhancement2", ...],
  "ambiguityFlags": [{ "term": "ambiguous_term", "reason": "why_it_is_ambiguous" }, ...]
}

Do not include any explanations or conversational text outside the JSON structure.
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

        // --- MOCK LLM RESPONSE ---
        let mockLLMContent: string;
        if (input.userInput.toLowerCase().includes("efficient") && input.userInput.toLowerCase().includes("ai thing")) {
            mockLLMContent = JSON.stringify({
                alternativeGoals: [
                    "User wants to fully automate the Q3 marketing report generation.",
                    "User is looking for ways to reduce manual data entry for reports.",
                    "User wants to understand what the 'new AI thing' can do for their reporting tasks."
                ],
                novelSolutionsSuggested: [
                    "Integrate 'AI thing' to auto-summarize source documents for the report.",
                    "Develop a template that 'AI thing' can populate directly.",
                    "Use 'AI thing' to identify key insights or anomalies in the Q3 data to highlight in the report."
                ],
                unstatedAssumptions: [
                    "User assumes 'new AI thing' is the best or only solution for efficiency.",
                    "User assumes the current report structure is optimal."
                ],
                potentialEnhancements: [
                    "Set up a recurring task for the 'AI thing' to pre-process report data monthly.",
                    "Offer a brief training on how to best leverage the 'AI thing' for reporting."
                ],
                ambiguityFlags: [
                    { "term": "efficient", "reason": "Efficiency can mean faster, cheaper, or less manual effort. Clarification might be needed on primary goal." },
                    { "term": "new AI thing", "reason": "This is vague. Which specific AI tool is the user referring to?" }
                ]
            });
        } else if (input.userInput.toLowerCase().includes("pivot table")) {
             mockLLMContent = JSON.stringify({
                alternativeGoals: ["User wants to analyze data effectively", "User wants to present summarized data"],
                novelSolutionsSuggested: ["Suggest using automated chart generation based on pivot table data", "Introduce slicers for interactive filtering"],
                unstatedAssumptions: ["User knows what data to put in rows/columns/values"],
                potentialEnhancements: ["Offer to save pivot table configuration as a template"],
                ambiguityFlags: []
            });
        } else {
            mockLLMContent = JSON.stringify({
                alternativeGoals: ["User may need help with a completely different, unstated problem."],
                novelSolutionsSuggested: ["Suggest a general help document or a way to explore available tools."],
                unstatedAssumptions: [],
                potentialEnhancements: [],
                ambiguityFlags: [{ "term": "Help me", "reason": "Extremely vague, could mean anything." }]
            });
        }
        const mockResponse: LLMServiceResponse = {
            success: true,
            content: mockLLMContent,
            usage: { promptTokens: 120, completionTokens: 180, totalTokens: 300 }
        };
        // --- END MOCK LLM RESPONSE ---

        const parsedResponse = safeParseJSON<Partial<CreativeAgentResponse>>(
            mockResponse.content,
            this.agentName,
            structuredPrompt.task
        );

        if (!mockResponse.success || !parsedResponse) {
            console.error(`[${this.agentName}] LLM call failed or response parsing failed. Error: ${mockResponse.error}`);
            return { rawLLMResponse: mockResponse.content || "No content from LLM." };
        }

        return {
            alternativeGoals: parsedResponse.alternativeGoals || [],
            novelSolutionsSuggested: parsedResponse.novelSolutionsSuggested || [],
            unstatedAssumptions: parsedResponse.unstatedAssumptions || [],
            potentialEnhancements: parsedResponse.potentialEnhancements || [],
            ambiguityFlags: parsedResponse.ambiguityFlags || [],
            rawLLMResponse: mockResponse.content,
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
