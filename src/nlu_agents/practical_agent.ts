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

Do not include any explanations or conversational text outside the JSON structure.
User's query: "${input.userInput}"
User ID: ${input.userId || 'N/A'}
Hypothetical available tools: ["Standard Office Suite", "Internal Wiki", "AI_Helper_Bot v1.2", "ProjectDB Access"]
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

        // --- MOCK LLM RESPONSE ---
        let mockLLMContent: string;
        if (input.userInput.toLowerCase().includes("efficient") && input.userInput.toLowerCase().includes("ai thing")) {
            mockLLMContent = JSON.stringify({
                contextualFactors: [
                    `User '${input.userId || 'unknown'}' is asking about report efficiency.`,
                    "Org has 'AI_Helper_Bot v1.2' available."
                ],
                feasibilityAssessment: {
                    rating: "Medium",
                    reason: "Depends on the capabilities of 'AI_Helper_Bot v1.2' and complexity of the report. Data access for the bot is key.",
                    dependencies: ["Access to Q3 marketing data sources", "AI_Helper_Bot v1.2 configured for reporting tasks"]
                },
                efficiencyTips: [
                    "Ensure data sources are clean and structured before feeding to AI.",
                    "Break down the report into smaller parts for the AI to process if it struggles with the whole.",
                    "Verify AI outputs for accuracy, especially initially."
                ],
                resourceImplications: {
                    timeEstimate: "Moderate",
                    toolsNeeded: ["Q3 marketing data sources", "AI_Helper_Bot v1.2", "Standard Office Suite (for final report)"]
                },
                commonSenseValidation: {
                    isValid: true,
                    reason: "Seeking efficiency using available AI tools is a reasonable request."
                }
            });
        } else if (input.userInput.toLowerCase().includes("pivot table")) {
            mockLLMContent = JSON.stringify({
                contextualFactors: ["User is asking a 'how-to' question about SpreadsheetApp."],
                feasibilityAssessment: {
                    rating: "High",
                    reason: "Creating pivot tables is a standard feature in spreadsheet software.",
                    dependencies: ["SpreadsheetApp installed", "Data available to pivot"]
                },
                efficiencyTips: ["Use named ranges for data sources for easier updates.", "Start with a clear question you want the pivot table to answer."],
                resourceImplications: {
                    timeEstimate: "Quick",
                    toolsNeeded: ["SpreadsheetApp"]
                },
                commonSenseValidation: {
                    isValid: true,
                    reason: "Common task for data analysis."
                }
            });
        } else {
            mockLLMContent = JSON.stringify({
                contextualFactors: ["User submitted a very short, non-specific query."],
                feasibilityAssessment: {
                    rating: "Unknown",
                    reason: "Cannot assess feasibility without a clear task or goal.",
                    dependencies: ["User to provide more details"]
                },
                efficiencyTips: ["Provide more details about what you need help with."],
                resourceImplications: {
                    timeEstimate: "Unknown",
                    toolsNeeded: []
                },
                commonSenseValidation": {
                    isValid: false,
                    reason: "Query 'Help me.' is too vague to be actionable without further context or clarification."
                }
            });
        }
        const mockResponse: LLMServiceResponse = {
            success: true,
            content: mockLLMContent,
            usage: { promptTokens: 110, completionTokens: 150, totalTokens: 260 }
        };
        // --- END MOCK LLM RESPONSE ---

        const parsedResponse = safeParseJSON<Partial<PracticalAgentResponse>>(
            mockResponse.content,
            this.agentName,
            structuredPrompt.task
        );

        if (!mockResponse.success || !parsedResponse) {
            console.error(`[${this.agentName}] LLM call failed or response parsing failed. Error: ${mockResponse.error}`);
            return { // Return a default/error response structure
                feasibilityAssessment: { rating: "Unknown", reason: "LLM analysis failed." },
                commonSenseValidation: { isValid: false, reason: "LLM analysis failed." },
                rawLLMResponse: mockResponse.content || "No content from LLM."
            };
        }

        return {
            contextualFactors: parsedResponse.contextualFactors || [],
            feasibilityAssessment: parsedResponse.feasibilityAssessment || { rating: "Unknown", reason: "N/A" },
            efficiencyTips: parsedResponse.efficiencyTips || [],
            resourceImplications: parsedResponse.resourceImplications || { timeEstimate: "Unknown" },
            commonSenseValidation: parsedResponse.commonSenseValidation || { isValid: true, reason: "N/A" },
            rawLLMResponse: mockResponse.content,
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
