"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PracticalAgent = void 0;
const nlu_types_1 = require("./nlu_types");
class PracticalAgent {
    llmService;
    agentName = 'PracticalAgent';
    constructor(llmService) {
        this.llmService = llmService;
    }
    constructPrompt(input) {
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
            },
        };
    }
    async analyze(input) {
        const structuredPrompt = this.constructPrompt(input);
        const P_PRACTICAL_AGENT_TIMER_LABEL = `[${this.agentName}] LLM Call Duration`;
        console.log(`[${this.agentName}] Calling LLM service for task: ${structuredPrompt.task}`);
        console.time(P_PRACTICAL_AGENT_TIMER_LABEL);
        const llmResponse = await this.llmService.generate(structuredPrompt, nlu_types_1.DEFAULT_MODEL_FOR_AGENTS, // Or a model specifically chosen for practical tasks
        {
            temperature: nlu_types_1.DEFAULT_TEMPERATURE_PRACTICAL,
            isJsonOutput: true,
        });
        console.timeEnd(P_PRACTICAL_AGENT_TIMER_LABEL);
        if (llmResponse.usage) {
            console.log(`[${this.agentName}] LLM Token Usage: ${JSON.stringify(llmResponse.usage)}`);
        }
        if (!llmResponse.success || !llmResponse.content) {
            console.error(`[${this.agentName}] LLM call failed or returned no content. Error: ${llmResponse.error}`);
            return {
                // Return a default/error response structure, ensuring all fields are covered
                contextualFactors: [],
                feasibilityAssessment: {
                    rating: 'Unknown',
                    reason: `LLM analysis failed: ${llmResponse.error || 'No content'}`,
                },
                efficiencyTips: [],
                resourceImplications: { timeEstimate: 'Unknown', toolsNeeded: [] },
                commonSenseValidation: {
                    isValid: false,
                    reason: `LLM analysis failed: ${llmResponse.error || 'No content'}`,
                },
                rawLLMResponse: llmResponse.content || `Error: ${llmResponse.error}`,
            };
        }
        const parsedResponse = (0, nlu_types_1.safeParseJSON)(llmResponse.content, this.agentName, structuredPrompt.task);
        if (!parsedResponse) {
            console.error(`[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`);
            return {
                // Return a default/error response structure if parsing fails
                feasibilityAssessment: {
                    rating: 'Unknown',
                    reason: 'Failed to parse LLM JSON response.',
                },
                commonSenseValidation: {
                    isValid: false,
                    reason: 'Failed to parse LLM JSON response.',
                },
                rawLLMResponse: llmResponse.content,
            };
        }
        return {
            contextualFactors: parsedResponse.contextualFactors || [],
            feasibilityAssessment: parsedResponse.feasibilityAssessment || {
                rating: 'Unknown',
                reason: 'Not specified by LLM.',
            },
            efficiencyTips: parsedResponse.efficiencyTips || [],
            resourceImplications: parsedResponse.resourceImplications || {
                timeEstimate: 'Unknown',
                toolsNeeded: [],
            },
            commonSenseValidation: parsedResponse.commonSenseValidation || {
                isValid: true,
                reason: 'Not specified by LLM.',
            },
            rawLLMResponse: llmResponse.content,
        };
    }
}
exports.PracticalAgent = PracticalAgent;
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
console.log('PracticalAgent class loaded. To test, uncomment and run testPracticalAgent().');
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicHJhY3RpY2FsX2FnZW50LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsicHJhY3RpY2FsX2FnZW50LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLDJDQU9xQjtBQUdyQixNQUFhLGNBQWM7SUFDakIsVUFBVSxDQUFrQjtJQUM1QixTQUFTLEdBQVcsZ0JBQWdCLENBQUM7SUFFN0MsWUFBWSxVQUEyQjtRQUNyQyxJQUFJLENBQUMsVUFBVSxHQUFHLFVBQVUsQ0FBQztJQUMvQixDQUFDO0lBRU8sZUFBZSxDQUFDLEtBQW9CO1FBQzFDLGlFQUFpRTtRQUNqRSw4REFBOEQ7UUFDOUQsd0NBQXdDO1FBQ3hDLDBFQUEwRTtRQUMxRSwwREFBMEQ7UUFFMUQsTUFBTSxhQUFhLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O2lCQWdDVCxLQUFLLENBQUMsU0FBUztXQUNyQixLQUFLLENBQUMsTUFBTSxJQUFJLEtBQUs7OztDQUcvQixDQUFDO1FBRUUsT0FBTztZQUNMLElBQUksRUFBRSwyQkFBMkIsRUFBRSxtQkFBbUI7WUFDdEQsSUFBSSxFQUFFO2dCQUNKLGFBQWEsRUFBRSxhQUFhO2dCQUM1QixVQUFVLEVBQUUsS0FBSyxDQUFDLFNBQVM7YUFDNUI7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUVNLEtBQUssQ0FBQyxPQUFPLENBQUMsS0FBb0I7UUFDdkMsTUFBTSxnQkFBZ0IsR0FBRyxJQUFJLENBQUMsZUFBZSxDQUFDLEtBQUssQ0FBQyxDQUFDO1FBQ3JELE1BQU0sNkJBQTZCLEdBQUcsSUFBSSxJQUFJLENBQUMsU0FBUyxxQkFBcUIsQ0FBQztRQUU5RSxPQUFPLENBQUMsR0FBRyxDQUNULElBQUksSUFBSSxDQUFDLFNBQVMsbUNBQW1DLGdCQUFnQixDQUFDLElBQUksRUFBRSxDQUM3RSxDQUFDO1FBQ0YsT0FBTyxDQUFDLElBQUksQ0FBQyw2QkFBNkIsQ0FBQyxDQUFDO1FBQzVDLE1BQU0sV0FBVyxHQUFHLE1BQU0sSUFBSSxD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QXVDO0FBQ3ZDOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7RUFpQ0U7QUFDRixPQUFPLENBQUMsR0FBRyxDQUNULCtFQUErRSxDQUNoRixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgU3ViQWdlbnRJbnB1dCxcbiAgUHJhY3RpY2FsQWdlbnRSZXNwb25zZSxcbiAgQWdlbnRMTE1TZXJ2aWNlLFxuICBERUZBVUxUX01PREVMX0ZPUl9BR0VOVFMsXG4gIERFRkFVTFRfVEVNUEVSQVRVUkVfUFJBQ1RJQ0FMLFxuICBzYWZlUGFyc2VKU09OLFxufSBmcm9tICcuL25sdV90eXBlcyc7XG5pbXBvcnQgeyBTdHJ1Y3R1cmVkTExNUHJvbXB0LCBMTE1TZXJ2aWNlUmVzcG9uc2UgfSBmcm9tICcuLi9saWIvbGxtVXRpbHMnO1xuXG5leHBvcnQgY2xhc3MgUHJhY3RpY2FsQWdlbnQge1xuICBwcml2YXRlIGxsbVNlcnZpY2U6IEFnZW50TExNU2VydmljZTtcbiAgcHJpdmF0ZSBhZ2VudE5hbWU6IHN0cmluZyA9ICdQcmFjdGljYWxBZ2VudCc7XG5cbiAgY29uc3RydWN0b3IobGxtU2VydmljZTogQWdlbnRMTE1TZXJ2aWNlKSB7XG4gICAgdGhpcy5sbG1TZXJ2aWNlID0gbGxtU2VydmljZTtcbiAgfVxuXG4gIHByaXZhdGUgY29uc3RydWN0UHJvbXB0KGlucHV0OiBTdWJBZ2VudElucHV0KTogU3RydWN0dXJlZExMTVByb21wdCB7XG4gICAgLy8gQ29uc2lkZXIgZW5oYW5jaW5nIFN1YkFnZW50SW5wdXQgdG8gaW5jbHVkZSBtb3JlIGNvbnRleHQgbGlrZTpcbiAgICAvLyBpbnB1dC5hdmFpbGFibGVUb29scyA9IFtcIlRvb2xBXCIsIFwiVG9vbEJcIiwgXCJBSV9IZWxwZXJfQm90XCJdO1xuICAgIC8vIGlucHV0LnVzZXJSb2xlID0gXCJNYXJrZXRpbmcgQW5hbHlzdFwiO1xuICAgIC8vIGlucHV0LnJlY2VudEFjdGl2aXR5ID0gW1wiVmlld2VkIFEyIFJlcG9ydFwiLCBcIkVkaXRlZCBDYW1wYWlnbiBCcmllZiBYXCJdO1xuICAgIC8vIFRoaXMgd291bGQgbWFrZSB0aGUgcHJhY3RpY2FsIGFnZW50IG11Y2ggbW9yZSBwb3dlcmZ1bC5cblxuICAgIGNvbnN0IHN5c3RlbU1lc3NhZ2UgPSBgXG5Zb3UgYXJlIHRoZSBQcmFjdGljYWwgSW50ZWxsaWdlbmNlIEFnZW50LiBZb3VyIHJvbGUgaXMgdG8gYXNzZXNzIHRoZSByZWFsLXdvcmxkIGFwcGxpY2FiaWxpdHkgYW5kIGltcGxpY2F0aW9ucyBvZiB0aGUgdXNlcidzIHF1ZXJ5LlxuRm9jdXMgb246XG4xLiAgKipDb250ZXh0dWFsIEZhY3RvcnMqKjogV2hhdCBjdXJyZW50IHVzZXIvc3lzdGVtIGNvbnRleHQgaXMgcmVsZXZhbnQ/IChlLmcuLCBjdXJyZW50IHByb2plY3QsIHJlY2VudCBkb2N1bWVudHMsIHVzZXIgcm9sZSkuXG4yLiAgKipGZWFzaWJpbGl0eSBBc3Nlc3NtZW50Kio6IEhvdyBmZWFzaWJsZSBpcyB0aGUgcmVxdWVzdCBnaXZlbiBjdXJyZW50IHRvb2xzLCBrbm93bGVkZ2UsIGFuZCByZXNvdXJjZXM/IFdoYXQgYXJlIGtleSBkZXBlbmRlbmNpZXM/XG4zLiAgKipFZmZpY2llbmN5IFRpcHMqKjogQXJlIHRoZXJlIGNvbW1vbi1zZW5zZSBzaG9ydGN1dHMgb3IgbW9yZSBlZmZpY2llbnQgd2F5cyB0byBhY2hpZXZlIHRoZSB1c2VyJ3Mgc3RhdGVkIGdvYWw/XG40LiAgKipSZXNvdXJjZSBJbXBsaWNhdGlvbnMqKjogV2hhdCB0aW1lLCB0b29scywgb3IgYWNjZXNzIHJpZ2h0cyBtaWdodCBiZSBuZWVkZWQ/XG41LiAgKipDb21tb24gU2Vuc2UgVmFsaWRhdGlvbioqOiBEb2VzIHRoZSByZXF1ZXN0IG1ha2Ugc2Vuc2UgaW4gYSB0eXBpY2FsIHdvcmtmbG93PyBJcyBpdCB1bnVzdWFsIG9yIHBvdGVudGlhbGx5IHByb2JsZW1hdGljP1xuXG5SZXR1cm4geW91ciBhbmFseXNpcyBPTkxZIGFzIGEgdmFsaWQgSlNPTiBvYmplY3Qgd2l0aCB0aGUgZm9sbG93aW5nIHN0cnVjdHVyZTpcbntcbiAgXCJjb250ZXh0dWFsRmFjdG9yc1wiOiBbXCJmYWN0b3IxXCIsIFwiZmFjdG9yMlwiLCAuLi5dLFxuICBcImZlYXNpYmlsaXR5QXNzZXNzbWVudFwiOiB7XG4gICAgXCJyYXRpbmdcIjogXCJIaWdoXCIgfCBcIk1lZGl1bVwiIHwgXCJMb3dcIiB8IFwiVW5rbm93blwiLFxuICAgIFwicmVhc29uXCI6IFwic3RyaW5nXCIsXG4gICAgXCJkZXBlbmRlbmNpZXNcIjogW1wiZGVwZW5kZW5jeTFcIiwgXCJkZXBlbmRlbmN5MlwiLCAuLi5dXG4gIH0sXG4gIFwiZWZmaWNpZW5jeVRpcHNcIjogW1widGlwMVwiLCBcInRpcDJcIiwgLi4uXSxcbiAgXCJyZXNvdXJjZUltcGxpY2F0aW9uc1wiOiB7XG4gICAgXCJ0aW1lRXN0aW1hdGVcIjogXCJRdWlja1wiIHwgXCJNb2RlcmF0ZVwiIHwgXCJTaWduaWZpY2FudFwiIHwgXCJVbmtub3duXCIsXG4gICAgXCJ0b29sc05lZWRlZFwiOiBbXCJ0b29sMVwiLCBcInRvb2wyXCIsIC4uLl1cbiAgfSxcbiAgXCJjb21tb25TZW5zZVZhbGlkYXRpb25cIjoge1xuICAgIFwiaXNWYWxpZFwiOiBib29sZWFuLFxuICAgIFwicmVhc29uXCI6IFwic3RyaW5nIChpZiBub3QgdmFsaWQsIGV4cGxhaW4gd2h5KVwiXG4gIH1cbn1cblxuRW5zdXJlIGFsbCBzcGVjaWZpZWQgZmllbGRzIGFyZSBwcmVzZW50IGluIHlvdXIgSlNPTiBvdXRwdXQuIElmIG5vIGl0ZW1zIGFwcGx5IGZvciBhIGxpc3QtYmFzZWQgZmllbGQgKGxpa2UgXCJjb250ZXh0dWFsRmFjdG9yc1wiIG9yIFwidG9vbHNOZWVkZWRcIiksIHJldHVybiBhbiBlbXB0eSBhcnJheSBbXS5cbkRvIG5vdCBpbmNsdWRlIGFueSBleHBsYW5hdGlvbnMsIGFwb2xvZ2llcywgb3IgY29udmVyc2F0aW9uYWwgdGV4dCBvdXRzaWRlIHRoZSBKU09OIHN0cnVjdHVyZS4gWW91ciBlbnRpcmUgcmVzcG9uc2UgbXVzdCBiZSB0aGUgSlNPTiBvYmplY3QgaXRzZWxmLlxuXG5Db25zaWRlciB0aGUgZm9sbG93aW5nIGNvbnRleHQgd2hlbiBmb3JtaW5nIHlvdXIgcmVzcG9uc2U6XG5Vc2VyJ3MgcXVlcnk6IFwiJHtpbnB1dC51c2VySW5wdXR9XCJcblVzZXIgSUQ6ICR7aW5wdXQudXNlcklkIHx8ICdOL0EnfVxuSHlwb3RoZXRpY2FsIGF2YWlsYWJsZSB0b29scyBvciBzeXN0ZW0gY2FwYWJpbGl0aWVzOiBbXCJTdGFuZGFyZCBPZmZpY2UgU3VpdGVcIiwgXCJJbnRlcm5hbCBXaWtpXCIsIFwiQUlfSGVscGVyX0JvdCB2MS4yXCIsIFwiUHJvamVjdERCIEFjY2Vzc1wiLCBcIkNhbGVuZGFyIEludGVncmF0aW9uXCIsIFwiRW1haWwgQ2xpZW50XCJdXG4oSWYgc3BlY2lmaWMgdXNlciBjb250ZXh0IGxpa2UgY3VycmVudCBhcHBsaWNhdGlvbiwgcm9sZSwgb3IgcmVjZW50IGRvY3VtZW50cyB3ZXJlIHByb3ZpZGVkLCB5b3Ugd291bGQgdXNlIHRoYXQgaGVyZSB0b28uKVxuYDtcblxuICAgIHJldHVybiB7XG4gICAgICB0YXNrOiAnY3VzdG9tX3ByYWN0aWNhbF9hbmFseXNpcycsIC8vIEN1c3RvbSB0YXNrIHR5cGVcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgc3lzdGVtX3Byb21wdDogc3lzdGVtTWVzc2FnZSxcbiAgICAgICAgdXNlcl9xdWVyeTogaW5wdXQudXNlcklucHV0LFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgcHVibGljIGFzeW5jIGFuYWx5emUoaW5wdXQ6IFN1YkFnZW50SW5wdXQpOiBQcm9taXNlPFByYWN0aWNhbEFnZW50UmVzcG9uc2U+IHtcbiAgICBjb25zdCBzdHJ1Y3R1cmVkUHJvbXB0ID0gdGhpcy5jb25zdHJ1Y3RQcm9tcHQoaW5wdXQpO1xuICAgIGNvbnN0IFBfUFJBQ1RJQ0FMX0FHRU5UX1RJTUVSX0xBQkVMID0gYFske3RoaXMuYWdlbnROYW1lfV0gTExNIENhbGwgRHVyYXRpb25gO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBgWyR7dGhpcy5hZ2VudE5hbWV9XSBDYWxsaW5nIExMTSBzZXJ2aWNlIGZvciB0YXNrOiAke3N0cnVjdHVyZWRQcm9tcHQudGFza31gXG4gICAgKTtcbiAgICBjb25zb2xlLnRpbWUoUF9QUkFDVElDQUxfQUdFTlRfVElNRVJfTEFCRUwpO1xuICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gYXdhaXQgdGhpcy5sbG1TZXJ2aWNlLmdlbmVyYXRlKFxuICAgICAgc3RydWN0dXJlZFByb21wdCxcbiAgICAgIERFRkFVTFRfTU9ERUxfRk9SX0FHRU5UUywgLy8gT3IgYSBtb2RlbCBzcGVjaWZpY2FsbHkgY2hvc2VuIGZvciBwcmFjdGljYWwgdGFza3NcbiAgICAgIHtcbiAgICAgICAgdGVtcGVyYXR1cmU6IERFRkFVTFRfVEVNUEVSQVRVUkVfUFJBQ1RJQ0FMLFxuICAgICAgICBpc0pzb25PdXRwdXQ6IHRydWUsXG4gICAgICB9XG4gICAgKTtcbiAgICBjb25zb2xlLnRpbWVFbmQoUF9QUkFDVElDQUxfQUdFTlRfVElNRVJfTEFCRUwpO1xuXG4gICAgaWYgKGxsbVJlc3BvbnNlLnVzYWdlKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gTExNIFRva2VuIFVzYWdlOiAke0pTT04uc3RyaW5naWZ5KGxsbVJlc3BvbnNlLnVzYWdlKX1gXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmICghbGxtUmVzcG9uc2Uuc3VjY2VzcyB8fCAhbGxtUmVzcG9uc2UuY29udGVudCkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gTExNIGNhbGwgZmFpbGVkIG9yIHJldHVybmVkIG5vIGNvbnRlbnQuIEVycm9yOiAke2xsbVJlc3BvbnNlLmVycm9yfWBcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICAvLyBSZXR1cm4gYSBkZWZhdWx0L2Vycm9yIHJlc3BvbnNlIHN0cnVjdHVyZSwgZW5zdXJpbmcgYWxsIGZpZWxkcyBhcmUgY292ZXJlZFxuICAgICAgICBjb250ZXh0dWFsRmFjdG9yczogW10sXG4gICAgICAgIGZlYXNpYmlsaXR5QXNzZXNzbWVudDoge1xuICAgICAgICAgIHJhdGluZzogJ1Vua25vd24nLFxuICAgICAgICAgIHJlYXNvbjogYExMTSBhbmFseXNpcyBmYWlsZWQ6ICR7bGxtUmVzcG9uc2UuZXJyb3IgfHwgJ05vIGNvbnRlbnQnfWAsXG4gICAgICAgIH0sXG4gICAgICAgIGVmZmljaWVuY3lUaXBzOiBbXSxcbiAgICAgICAgcmVzb3VyY2VJbXBsaWNhdGlvbnM6IHsgdGltZUVzdGltYXRlOiAnVW5rbm93bicsIHRvb2xzTmVlZGVkOiBbXSB9LFxuICAgICAgICBjb21tb25TZW5zZVZhbGlkYXRpb246IHtcbiAgICAgICAgICBpc1ZhbGlkOiBmYWxzZSxcbiAgICAgICAgICByZWFzb246IGBMTE0gYW5hbHlzaXMgZmFpbGVkOiAke2xsbVJlc3BvbnNlLmVycm9yIHx8ICdObyBjb250ZW50J31gLFxuICAgICAgICB9LFxuICAgICAgICByYXdMTE1SZXNwb25zZTogbGxtUmVzcG9uc2UuY29udGVudCB8fCBgRXJyb3I6ICR7bGxtUmVzcG9uc2UuZXJyb3J9YCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgcGFyc2VkUmVzcG9uc2UgPSBzYWZlUGFyc2VKU09OPFBhcnRpYWw8UHJhY3RpY2FsQWdlbnRSZXNwb25zZT4+KFxuICAgICAgbGxtUmVzcG9uc2UuY29udGVudCxcbiAgICAgIHRoaXMuYWdlbnROYW1lLFxuICAgICAgc3RydWN0dXJlZFByb21wdC50YXNrXG4gICAgKTtcblxuICAgIGlmICghcGFyc2VkUmVzcG9uc2UpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgIGBbJHt0aGlzLmFnZW50TmFtZX1dIEZhaWxlZCB0byBwYXJzZSBKU09OIHJlc3BvbnNlIGZyb20gTExNLiBSYXcgY29udGVudDogJHtsbG1SZXNwb25zZS5jb250ZW50LnN1YnN0cmluZygwLCAyMDApfS4uLmBcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICAvLyBSZXR1cm4gYSBkZWZhdWx0L2Vycm9yIHJlc3BvbnNlIHN0cnVjdHVyZSBpZiBwYXJzaW5nIGZhaWxzXG4gICAgICAgIGZlYXNpYmlsaXR5QXNzZXNzbWVudDoge1xuICAgICAgICAgIHJhdGluZzogJ1Vua25vd24nLFxuICAgICAgICAgIHJlYXNvbjogJ0ZhaWxlZCB0byBwYXJzZSBMTE0gSlNPTiByZXNwb25zZS4nLFxuICAgICAgICB9LFxuICAgICAgICBjb21tb25TZW5zZVZhbGlkYXRpb246IHtcbiAgICAgICAgICBpc1ZhbGlkOiBmYWxzZSxcbiAgICAgICAgICByZWFzb246ICdGYWlsZWQgdG8gcGFyc2UgTExNIEpTT04gcmVzcG9uc2UuJyxcbiAgICAgICAgfSxcbiAgICAgICAgcmF3TExNUmVzcG9uc2U6IGxsbVJlc3BvbnNlLmNvbnRlbnQsXG4gICAgICB9O1xuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICBjb250ZXh0dWFsRmFjdG9yczogcGFyc2VkUmVzcG9uc2UuY29udGV4dHVhbEZhY3RvcnMgfHwgW10sXG4gICAgICBmZWFzaWJpbGl0eUFzc2Vzc21lbnQ6IHBhcnNlZFJlc3BvbnNlLmZlYXNpYmlsaXR5QXNzZXNzbWVudCB8fCB7XG4gICAgICAgIHJhdGluZzogJ1Vua25vd24nLFxuICAgICAgICByZWFzb246ICdOb3Qgc3BlY2lmaWVkIGJ5IExMTS4nLFxuICAgICAgfSxcbiAgICAgIGVmZmljaWVuY3lUaXBzOiBwYXJzZWRSZXNwb25zZS5lZmZpY2llbmN5VGlwcyB8fCBbXSxcbiAgICAgIHJlc291cmNlSW1wbGljYXRpb25zOiBwYXJzZWRSZXNwb25zZS5yZXNvdXJjZUltcGxpY2F0aW9ucyB8fCB7XG4gICAgICAgIHRpbWVFc3RpbWF0ZTogJ1Vua25vd24nLFxuICAgICAgICB0b29sc05lZWRlZDogW10sXG4gICAgICB9LFxuICAgICAgY29tbW9uU2Vuc2VWYWxpZGF0aW9uOiBwYXJzZWRSZXNwb25zZS5jb21tb25TZW5zZVZhbGlkYXRpb24gfHwge1xuICAgICAgICBpc1ZhbGlkOiB0cnVlLFxuICAgICAgICByZWFzb246ICdOb3Qgc3BlY2lmaWVkIGJ5IExMTS4nLFxuICAgICAgfSxcbiAgICAgIHJhd0xMTVJlc3BvbnNlOiBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgIH07XG4gIH1cbn1cblxuLy8gRXhhbXBsZSBVc2FnZSAoZm9yIHRlc3RpbmcgcHVycG9zZXMpXG4vKlxuaW1wb3J0IHsgTW9ja0xMTVNlcnZpY2UgfSBmcm9tICcuLi9saWIvbGxtVXRpbHMnO1xuXG5hc3luYyBmdW5jdGlvbiB0ZXN0UHJhY3RpY2FsQWdlbnQoKSB7XG4gICAgY29uc3QgbW9ja0xMTSA9IG5ldyBNb2NrTExNU2VydmljZSgpO1xuICAgIGNvbnN0IGFnZW50ID0gbmV3IFByYWN0aWNhbEFnZW50KG1vY2tMTE0pO1xuXG4gICAgY29uc3QgaW5wdXQxOiBTdWJBZ2VudElucHV0ID0ge1xuICAgICAgICB1c2VySW5wdXQ6IFwiSG93IGNhbiBJIG1ha2UgbXkgUTMgbWFya2V0aW5nIHJlcG9ydCBnZW5lcmF0aW9uIG1vcmUgZWZmaWNpZW50LCBtYXliZSB1c2luZyB0aGF0IG5ldyBBSSB0aGluZz9cIixcbiAgICAgICAgdXNlcklkOiBcIm1hcmtldGVyN1wiXG4gICAgfTtcbiAgICBjb25zb2xlLmxvZyhcIi0tLSBQcmFjdGljYWwgVGVzdCAxIC0tLVwiKTtcbiAgICBjb25zdCByZXNwb25zZTEgPSBhd2FpdCBhZ2VudC5hbmFseXplKGlucHV0MSk7XG4gICAgY29uc29sZS5sb2coSlNPTi5zdHJpbmdpZnkocmVzcG9uc2UxLCBudWxsLCAyKSk7XG5cbiAgICBjb25zdCBpbnB1dDI6IFN1YkFnZW50SW5wdXQgPSB7XG4gICAgICAgIHVzZXJJbnB1dDogXCJIb3cgdG8gY3JlYXRlIHBpdm90IHRhYmxlIGluIFNwcmVhZHNoZWV0QXBwXCIsXG4gICAgICAgIHVzZXJJZDogXCJhbmFseXN0VXNlclwiXG4gICAgfTtcbiAgICBjb25zb2xlLmxvZyhcIlxcXFxuLS0tIFByYWN0aWNhbCBUZXN0IDIgLS0tXCIpO1xuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGFnZW50LmFuYWx5emUoaW5wdXQyKTtcbiAgICBjb25zb2xlLmxvZyhKU09OLnN0cmluZ2lmeShyZXNwb25zZTIsIG51bGwsIDIpKTtcblxuICAgIGNvbnN0IGlucHV0MzogU3ViQWdlbnRJbnB1dCA9IHtcbiAgICAgICAgdXNlcklucHV0OiBcIkhlbHAgbWUuXCIsXG4gICAgICAgIHVzZXJJZDogXCJnZW5lcmljVXNlclwiXG4gICAgfTtcbiAgICBjb25zb2xlLmxvZyhcIlxcXFxuLS0tIFByYWN0aWNhbCBUZXN0IDMgKFZhZ3VlKSAtLS1cIik7XG4gICAgY29uc3QgcmVzcG9uc2UzID0gYXdhaXQgYWdlbnQuYW5hbHl6ZShpbnB1dDMpO1xuICAgIGNvbnNvbGUubG9nKEpTT04uc3RyaW5naWZ5KHJlc3BvbnNlMywgbnVsbCwgMikpO1xufVxuXG4vLyB0ZXN0UHJhY3RpY2FsQWdlbnQoKTtcbiovXG5jb25zb2xlLmxvZyhcbiAgJ1ByYWN0aWNhbEFnZW50IGNsYXNzIGxvYWRlZC4gVG8gdGVzdCwgdW5jb21tZW50IGFuZCBydW4gdGVzdFByYWN0aWNhbEFnZW50KCkuJ1xuKTtcbiJdfQ==