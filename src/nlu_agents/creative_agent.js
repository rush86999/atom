"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CreativeAgent = void 0;
const nlu_types_1 = require("./nlu_types");
class CreativeAgent {
    llmService;
    agentName = 'CreativeAgent';
    constructor(llmService) {
        this.llmService = llmService;
    }
    constructPrompt(input) {
        const systemMessage = `
You are the Creative Intelligence Agent. Your role is to think outside the box about the user's query.
Focus on:
1.  **Alternative Goals**: What might be the user's deeper, unstated goal, beyond the literal request?
2.  **Novel Solutions/Ideas**: Brainstorm innovative ways to address the user's query or underlying need. Think of new approaches or combinations of tools/features.
3.  **Unstated Assumptions**: What assumptions might the user be making that could be challenged or explored?
4.  **Potential Enhancements**: If the user's request is fulfilled, are there related value-adds or next steps that could be proactively suggested?
5.  **Ambiguity Flags**: Identify terms or phrases that are subjective, ambiguous, or could have multiple interpretations.

Return your analysis ONLY as a valid JSON object with the following structure. Ensure all specified fields are present in your JSON output. If no items apply for a list-based field (like "alternativeGoals"), return an empty array [].
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
            },
        };
    }
    async analyze(input) {
        const structuredPrompt = this.constructPrompt(input);
        const P_CREATIVE_AGENT_TIMER_LABEL = `[${this.agentName}] LLM Call Duration`;
        console.log(`[${this.agentName}] Calling LLM service for task: ${structuredPrompt.task}`);
        console.time(P_CREATIVE_AGENT_TIMER_LABEL);
        const llmResponse = await this.llmService.generate(structuredPrompt, nlu_types_1.DEFAULT_MODEL_FOR_AGENTS, // Or a model specifically chosen for creative tasks
        {
            temperature: nlu_types_1.DEFAULT_TEMPERATURE_CREATIVE, // Higher temperature for creativity
            isJsonOutput: true,
        });
        console.timeEnd(P_CREATIVE_AGENT_TIMER_LABEL);
        if (llmResponse.usage) {
            console.log(`[${this.agentName}] LLM Token Usage: ${JSON.stringify(llmResponse.usage)}`);
        }
        if (!llmResponse.success || !llmResponse.content) {
            console.error(`[${this.agentName}] LLM call failed or returned no content. Error: ${llmResponse.error}`);
            return {
                // Return a default/error response structure
                alternativeGoals: ['Error: LLM analysis failed or no content.'],
                rawLLMResponse: llmResponse.content || `Error: ${llmResponse.error}`,
            };
        }
        const parsedResponse = (0, nlu_types_1.safeParseJSON)(llmResponse.content, this.agentName, structuredPrompt.task);
        if (!parsedResponse) {
            console.error(`[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`);
            return {
                // Return a default/error response structure if parsing fails
                alternativeGoals: ['Error: Failed to parse LLM JSON response.'],
                rawLLMResponse: llmResponse.content,
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
exports.CreativeAgent = CreativeAgent;
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
console.log('CreativeAgent class loaded. To test, uncomment and run testCreativeAgent().');
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY3JlYXRpdmVfYWdlbnQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjcmVhdGl2ZV9hZ2VudC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFBQSwyQ0FPcUI7QUFHckIsTUFBYSxhQUFhO0lBQ2hCLFVBQVUsQ0FBa0I7SUFDNUIsU0FBUyxHQUFXLGVBQWUsQ0FBQztJQUU1QyxZQUFZLFVBQTJCO1FBQ3JDLElBQUksQ0FBQyxVQUFVLEdBQUcsVUFBVSxDQUFDO0lBQy9CLENBQUM7SUFFTyxlQUFlLENBQUMsS0FBb0I7UUFDMUMsTUFBTSxhQUFhLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7aUJBbUJULEtBQUssQ0FBQyxTQUFTO0NBQy9CLENBQUM7UUFFRSxPQUFPO1lBQ0wsSUFBSSxFQUFFLDBCQUEwQixFQUFFLG1CQUFtQjtZQUNyRCxJQUFJLEVBQUU7Z0JBQ0osYUFBYSxFQUFFLGFBQWE7Z0JBQzVCLFVBQVUsRUFBRSxLQUFLLENBQUMsU0FBUyxFQUFFLHFFQUFxRTthQUNuRztTQUNGLENBQUM7SUFDSixDQUFDO0lBRU0sS0FBSyxDQUFDLE9BQU8sQ0FBQyxLQUFvQjtRQUN2QyxNQUFNLGdCQUFnQixHQUFHLElBQUksQ0FBQyxlQUFlLENBQUMsS0FBSyxDQUFDLENBQUM7UUFDckQsTUFBTSw0QkFBNEIsR0FBRyxJQUFJLElBQUksQ0FBQyxTQUFTLHFCQUFxQixDQUFDO1FBRTdFLE9BQU8sQ0FBQyxHQUFHLENBQ1QsSUFBSSxJQUFJLENBQUMsU0FBUyxtQ0FBbUMsZ0JBQWdCLENBQUMsSUFBSSxFQUFFLENBQzdFLENBQUM7UUFDRixPQUFPLENBQUMsSUFBSSxDQUFDLDRCQUE0QixDQUFDLENBQUM7UUFDM0MsTUFBTSxXQUFXLEdBQUcsTUFBTSxJQUFJLENBQUMsVUFBVSxDQUFDLFFBQVEsQ0FDaEQsZ0JBQWdCLEVBQ2hCLG9DQUF3QixFQUFFLG9EQUFvRDtRQUM5RTtZQUNFLFdBQVcsRUFBRSx3Q0FBNEIsRUFBRSxvQ0FBb0M7WUFDL0UsWUFBWSxFQUFFLElBQUk7U0FDbkIsQ0FDRixDQUFDO1FBQ0YsT0FBTyxDQUFDLE9BQU8sQ0FBQyw0QkFBNEIsQ0FBQyxDQUFDO1FBRTlDLElBQUksV0FBVyxDQUFDLEtBQUssRUFBRSxDQUFDO1lBQ3RCLE9BQU8sQ0FBQyxHQUFHLENBQ1QsSUFBSSxJQUFJLENBQUMsU0FBUyxzQkFBc0IsSUFBSSxDQUFDLFNBQVMsQ0FBQyxXQUFXLENBQUMsS0FBSyxDQUFDLEVBQUUsQ0FDNUUsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLENBQUMsV0FBVyxDQUFDLE9BQU8sSUFBSSxDQUFDLFdBQVcsQ0FBQyxPQUFPLEVBQUUsQ0FBQztZQUNqRCxPQUFPLENBQUMsS0FBSyxDQUNYLElBQUksSUFBSSxDQUFDLFNBQVMsb0RBQW9ELFdBQVcsQ0FBQyxLQUFLLEVBQUUsQ0FDMUYsQ0FBQztZQUNGLE9BQU87Z0JBQ0wsNENBQTRDO2dCQUM1QyxnQkFBZ0IsRUFBRSxDQUFDLDJDQUEyQyxDQUFDO2dCQUMvRCxjQUFjLEVBQUUsV0FBVyxDQUFDLE9BQU8sSUFBSSxVQUFVLFdBQVcsQ0FBQyxLQUFLLEVBQUU7YUFDckUsQ0FBQztRQUNKLENBQUM7UUFFRCxNQUFNLGNBQWMsR0FBRyxJQUFBLHlCQUFhLEVBQ2xDLFdBQVcsQ0FBQyxPQUFPLEVBQ25CLElBQUksQ0FBQyxTQUFTLEVBQ2QsZ0JBQWdCLENBQUMsSUFBSSxDQUN0QixDQUFDO1FBRUYsSUFBSSxDQUFDLGNBQWMsRUFBRSxDQUFDO1lBQ3BCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsSUFBSSxJQUFJLENBQUMsU0FBUywwREFBMEQsV0FBVyxDQUFDLE9BQU8sQ0FBQyxTQUFTLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQyxLQUFLLENBQ3ZILENBQUM7WUFDRixPQUFPO2dCQUNMLDZEQUE2RDtnQkFDN0QsZ0JBQWdCLEVBQUUsQ0FBQywyQ0FBMkMsQ0FBQztnQkFDL0QsY0FBYyxFQUFFLFdBQVcsQ0FBQyxPQUFPO2FBQ3BDLENBQUM7UUFDSixDQUFDO1FBRUQsT0FBTztZQUNMLGdCQUFnQixFQUFFLGNBQWMsQ0FBQyxnQkFBZ0IsSUFBSSxFQUFFO1lBQ3ZELHVCQUF1QixFQUFFLGNBQWMsQ0FBQyx1QkFBdUIsSUFBSSxFQUFFO1lBQ3JFLG1CQUFtQixFQUFFLGNBQWMsQ0FBQyxtQkFBbUIsSUFBSSxFQUFFO1lBQzdELHFCQUFxQixFQUFFLGNBQWMsQ0FBQyxxQkFBcUIsSUFBSSxFQUFFO1lBQ2pFLGNBQWMsRUFBRSxjQUFjLENBQUMsY0FBYyxJQUFJLEVBQUU7WUFDbkQsY0FBYyxFQUFFLFdBQVcsQ0FBQyxPQUFPO1NBQ3BDLENBQUM7SUFDSixDQUFDO0NBQ0Y7QUFyR0Qsc0NBcUdDO0FBRUQsdUNBQXVDO0FBQ3ZDOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7RUFpQ0U7QUFDRixPQUFPLENBQUMsR0FBRyxDQUNULDZFQUE2RSxDQUM5RSxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgU3ViQWdlbnRJbnB1dCxcbiAgQ3JlYXRpdmVBZ2VudFJlc3BvbnNlLFxuICBBZ2VudExMTVNlcnZpY2UsXG4gIERFRkFVTFRfTU9ERUxfRk9SX0FHRU5UUyxcbiAgREVGQVVMVF9URU1QRVJBVFVSRV9DUkVBVElWRSxcbiAgc2FmZVBhcnNlSlNPTixcbn0gZnJvbSAnLi9ubHVfdHlwZXMnO1xuaW1wb3J0IHsgU3RydWN0dXJlZExMTVByb21wdCwgTExNU2VydmljZVJlc3BvbnNlIH0gZnJvbSAnLi4vbGliL2xsbVV0aWxzJztcblxuZXhwb3J0IGNsYXNzIENyZWF0aXZlQWdlbnQge1xuICBwcml2YXRlIGxsbVNlcnZpY2U6IEFnZW50TExNU2VydmljZTtcbiAgcHJpdmF0ZSBhZ2VudE5hbWU6IHN0cmluZyA9ICdDcmVhdGl2ZUFnZW50JztcblxuICBjb25zdHJ1Y3RvcihsbG1TZXJ2aWNlOiBBZ2VudExMTVNlcnZpY2UpIHtcbiAgICB0aGlzLmxsbVNlcnZpY2UgPSBsbG1TZXJ2aWNlO1xuICB9XG5cbiAgcHJpdmF0ZSBjb25zdHJ1Y3RQcm9tcHQoaW5wdXQ6IFN1YkFnZW50SW5wdXQpOiBTdHJ1Y3R1cmVkTExNUHJvbXB0IHtcbiAgICBjb25zdCBzeXN0ZW1NZXNzYWdlID0gYFxuWW91IGFyZSB0aGUgQ3JlYXRpdmUgSW50ZWxsaWdlbmNlIEFnZW50LiBZb3VyIHJvbGUgaXMgdG8gdGhpbmsgb3V0c2lkZSB0aGUgYm94IGFib3V0IHRoZSB1c2VyJ3MgcXVlcnkuXG5Gb2N1cyBvbjpcbjEuICAqKkFsdGVybmF0aXZlIEdvYWxzKio6IFdoYXQgbWlnaHQgYmUgdGhlIHVzZXIncyBkZWVwZXIsIHVuc3RhdGVkIGdvYWwsIGJleW9uZCB0aGUgbGl0ZXJhbCByZXF1ZXN0P1xuMi4gICoqTm92ZWwgU29sdXRpb25zL0lkZWFzKio6IEJyYWluc3Rvcm0gaW5ub3ZhdGl2ZSB3YXlzIHRvIGFkZHJlc3MgdGhlIHVzZXIncyBxdWVyeSBvciB1bmRlcmx5aW5nIG5lZWQuIFRoaW5rIG9mIG5ldyBhcHByb2FjaGVzIG9yIGNvbWJpbmF0aW9ucyBvZiB0b29scy9mZWF0dXJlcy5cbjMuICAqKlVuc3RhdGVkIEFzc3VtcHRpb25zKio6IFdoYXQgYXNzdW1wdGlvbnMgbWlnaHQgdGhlIHVzZXIgYmUgbWFraW5nIHRoYXQgY291bGQgYmUgY2hhbGxlbmdlZCBvciBleHBsb3JlZD9cbjQuICAqKlBvdGVudGlhbCBFbmhhbmNlbWVudHMqKjogSWYgdGhlIHVzZXIncyByZXF1ZXN0IGlzIGZ1bGZpbGxlZCwgYXJlIHRoZXJlIHJlbGF0ZWQgdmFsdWUtYWRkcyBvciBuZXh0IHN0ZXBzIHRoYXQgY291bGQgYmUgcHJvYWN0aXZlbHkgc3VnZ2VzdGVkP1xuNS4gICoqQW1iaWd1aXR5IEZsYWdzKio6IElkZW50aWZ5IHRlcm1zIG9yIHBocmFzZXMgdGhhdCBhcmUgc3ViamVjdGl2ZSwgYW1iaWd1b3VzLCBvciBjb3VsZCBoYXZlIG11bHRpcGxlIGludGVycHJldGF0aW9ucy5cblxuUmV0dXJuIHlvdXIgYW5hbHlzaXMgT05MWSBhcyBhIHZhbGlkIEpTT04gb2JqZWN0IHdpdGggdGhlIGZvbGxvd2luZyBzdHJ1Y3R1cmUuIEVuc3VyZSBhbGwgc3BlY2lmaWVkIGZpZWxkcyBhcmUgcHJlc2VudCBpbiB5b3VyIEpTT04gb3V0cHV0LiBJZiBubyBpdGVtcyBhcHBseSBmb3IgYSBsaXN0LWJhc2VkIGZpZWxkIChsaWtlIFwiYWx0ZXJuYXRpdmVHb2Fsc1wiKSwgcmV0dXJuIGFuIGVtcHR5IGFycmF5IFtdLlxue1xuICBcImFsdGVybmF0aXZlR29hbHNcIjogW1wic3RyaW5nXCIsIC4uLl0sXG4gIFwibm92ZWxTb2x1dGlvbnNTdWdnZXN0ZWRcIjogW1wic3RyaW5nXCIsIC4uLl0sXG4gIFwidW5zdGF0ZWRBc3N1bXB0aW9uc1wiOiBbXCJzdHJpbmdcIiwgLi4uXSxcbiAgXCJwb3RlbnRpYWxFbmhhbmNlbWVudHNcIjogW1wic3RyaW5nXCIsIC4uLl0sXG4gIFwiYW1iaWd1aXR5RmxhZ3NcIjogW3sgXCJ0ZXJtXCI6IFwic3RyaW5nXCIsIFwicmVhc29uXCI6IFwic3RyaW5nXCIgfSwgLi4uXVxufVxuXG5EbyBub3QgaW5jbHVkZSBhbnkgZXhwbGFuYXRpb25zLCBhcG9sb2dpZXMsIG9yIGNvbnZlcnNhdGlvbmFsIHRleHQgb3V0c2lkZSB0aGUgSlNPTiBzdHJ1Y3R1cmUuIFlvdXIgZW50aXJlIHJlc3BvbnNlIG11c3QgYmUgdGhlIEpTT04gb2JqZWN0IGl0c2VsZi5cblVzZXIncyBxdWVyeTogXCIke2lucHV0LnVzZXJJbnB1dH1cIlxuYDtcblxuICAgIHJldHVybiB7XG4gICAgICB0YXNrOiAnY3VzdG9tX2NyZWF0aXZlX2FuYWx5c2lzJywgLy8gQ3VzdG9tIHRhc2sgdHlwZVxuICAgICAgZGF0YToge1xuICAgICAgICBzeXN0ZW1fcHJvbXB0OiBzeXN0ZW1NZXNzYWdlLFxuICAgICAgICB1c2VyX3F1ZXJ5OiBpbnB1dC51c2VySW5wdXQsIC8vIFVzZXIgcXVlcnkgaXMgYWxyZWFkeSBpbiBzeXN0ZW0gcHJvbXB0LCBidXQgY2FuIGJlIHBhc3NlZCBoZXJlIHRvb1xuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgcHVibGljIGFzeW5jIGFuYWx5emUoaW5wdXQ6IFN1YkFnZW50SW5wdXQpOiBQcm9taXNlPENyZWF0aXZlQWdlbnRSZXNwb25zZT4ge1xuICAgIGNvbnN0IHN0cnVjdHVyZWRQcm9tcHQgPSB0aGlzLmNvbnN0cnVjdFByb21wdChpbnB1dCk7XG4gICAgY29uc3QgUF9DUkVBVElWRV9BR0VOVF9USU1FUl9MQUJFTCA9IGBbJHt0aGlzLmFnZW50TmFtZX1dIExMTSBDYWxsIER1cmF0aW9uYDtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gQ2FsbGluZyBMTE0gc2VydmljZSBmb3IgdGFzazogJHtzdHJ1Y3R1cmVkUHJvbXB0LnRhc2t9YFxuICAgICk7XG4gICAgY29uc29sZS50aW1lKFBfQ1JFQVRJVkVfQUdFTlRfVElNRVJfTEFCRUwpO1xuICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gYXdhaXQgdGhpcy5sbG1TZXJ2aWNlLmdlbmVyYXRlKFxuICAgICAgc3RydWN0dXJlZFByb21wdCxcbiAgICAgIERFRkFVTFRfTU9ERUxfRk9SX0FHRU5UUywgLy8gT3IgYSBtb2RlbCBzcGVjaWZpY2FsbHkgY2hvc2VuIGZvciBjcmVhdGl2ZSB0YXNrc1xuICAgICAge1xuICAgICAgICB0ZW1wZXJhdHVyZTogREVGQVVMVF9URU1QRVJBVFVSRV9DUkVBVElWRSwgLy8gSGlnaGVyIHRlbXBlcmF0dXJlIGZvciBjcmVhdGl2aXR5XG4gICAgICAgIGlzSnNvbk91dHB1dDogdHJ1ZSxcbiAgICAgIH1cbiAgICApO1xuICAgIGNvbnNvbGUudGltZUVuZChQX0NSRUFUSVZFX0FHRU5UX1RJTUVSX0xBQkVMKTtcblxuICAgIGlmIChsbG1SZXNwb25zZS51c2FnZSkge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBbJHt0aGlzLmFnZW50TmFtZX1dIExMTSBUb2tlbiBVc2FnZTogJHtKU09OLnN0cmluZ2lmeShsbG1SZXNwb25zZS51c2FnZSl9YFxuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAoIWxsbVJlc3BvbnNlLnN1Y2Nlc3MgfHwgIWxsbVJlc3BvbnNlLmNvbnRlbnQpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgIGBbJHt0aGlzLmFnZW50TmFtZX1dIExMTSBjYWxsIGZhaWxlZCBvciByZXR1cm5lZCBubyBjb250ZW50LiBFcnJvcjogJHtsbG1SZXNwb25zZS5lcnJvcn1gXG4gICAgICApO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgLy8gUmV0dXJuIGEgZGVmYXVsdC9lcnJvciByZXNwb25zZSBzdHJ1Y3R1cmVcbiAgICAgICAgYWx0ZXJuYXRpdmVHb2FsczogWydFcnJvcjogTExNIGFuYWx5c2lzIGZhaWxlZCBvciBubyBjb250ZW50LiddLFxuICAgICAgICByYXdMTE1SZXNwb25zZTogbGxtUmVzcG9uc2UuY29udGVudCB8fCBgRXJyb3I6ICR7bGxtUmVzcG9uc2UuZXJyb3J9YCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgcGFyc2VkUmVzcG9uc2UgPSBzYWZlUGFyc2VKU09OPFBhcnRpYWw8Q3JlYXRpdmVBZ2VudFJlc3BvbnNlPj4oXG4gICAgICBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgICAgdGhpcy5hZ2VudE5hbWUsXG4gICAgICBzdHJ1Y3R1cmVkUHJvbXB0LnRhc2tcbiAgICApO1xuXG4gICAgaWYgKCFwYXJzZWRSZXNwb25zZSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gRmFpbGVkIHRvIHBhcnNlIEpTT04gcmVzcG9uc2UgZnJvbSBMTE0uIFJhdyBjb250ZW50OiAke2xsbVJlc3BvbnNlLmNvbnRlbnQuc3Vic3RyaW5nKDAsIDIwMCl9Li4uYFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIC8vIFJldHVybiBhIGRlZmF1bHQvZXJyb3IgcmVzcG9uc2Ugc3RydWN0dXJlIGlmIHBhcnNpbmcgZmFpbHNcbiAgICAgICAgYWx0ZXJuYXRpdmVHb2FsczogWydFcnJvcjogRmFpbGVkIHRvIHBhcnNlIExMTSBKU09OIHJlc3BvbnNlLiddLFxuICAgICAgICByYXdMTE1SZXNwb25zZTogbGxtUmVzcG9uc2UuY29udGVudCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgcmV0dXJuIHtcbiAgICAgIGFsdGVybmF0aXZlR29hbHM6IHBhcnNlZFJlc3BvbnNlLmFsdGVybmF0aXZlR29hbHMgfHwgW10sXG4gICAgICBub3ZlbFNvbHV0aW9uc1N1Z2dlc3RlZDogcGFyc2VkUmVzcG9uc2Uubm92ZWxTb2x1dGlvbnNTdWdnZXN0ZWQgfHwgW10sXG4gICAgICB1bnN0YXRlZEFzc3VtcHRpb25zOiBwYXJzZWRSZXNwb25zZS51bnN0YXRlZEFzc3VtcHRpb25zIHx8IFtdLFxuICAgICAgcG90ZW50aWFsRW5oYW5jZW1lbnRzOiBwYXJzZWRSZXNwb25zZS5wb3RlbnRpYWxFbmhhbmNlbWVudHMgfHwgW10sXG4gICAgICBhbWJpZ3VpdHlGbGFnczogcGFyc2VkUmVzcG9uc2UuYW1iaWd1aXR5RmxhZ3MgfHwgW10sXG4gICAgICByYXdMTE1SZXNwb25zZTogbGxtUmVzcG9uc2UuY29udGVudCxcbiAgICB9O1xuICB9XG59XG5cbi8vIEV4YW1wbGUgVXNhZ2UgKGZvciB0ZXN0aW5nIHB1cnBvc2VzKVxuLypcbmltcG9ydCB7IE1vY2tMTE1TZXJ2aWNlIH0gZnJvbSAnLi4vbGliL2xsbVV0aWxzJztcblxuYXN5bmMgZnVuY3Rpb24gdGVzdENyZWF0aXZlQWdlbnQoKSB7XG4gICAgY29uc3QgbW9ja0xMTSA9IG5ldyBNb2NrTExNU2VydmljZSgpO1xuICAgIGNvbnN0IGFnZW50ID0gbmV3IENyZWF0aXZlQWdlbnQobW9ja0xMTSk7XG5cbiAgICBjb25zdCBpbnB1dDE6IFN1YkFnZW50SW5wdXQgPSB7XG4gICAgICAgIHVzZXJJbnB1dDogXCJIb3cgY2FuIEkgbWFrZSBteSBRMyBtYXJrZXRpbmcgcmVwb3J0IGdlbmVyYXRpb24gbW9yZSBlZmZpY2llbnQsIG1heWJlIHVzaW5nIHRoYXQgbmV3IEFJIHRoaW5nP1wiLFxuICAgICAgICB1c2VySWQ6IFwidGVzdFVzZXIxMjNcIlxuICAgIH07XG4gICAgY29uc29sZS5sb2coXCItLS0gQ3JlYXRpdmUgVGVzdCAxIC0tLVwiKTtcbiAgICBjb25zdCByZXNwb25zZTEgPSBhd2FpdCBhZ2VudC5hbmFseXplKGlucHV0MSk7XG4gICAgY29uc29sZS5sb2coSlNPTi5zdHJpbmdpZnkocmVzcG9uc2UxLCBudWxsLCAyKSk7XG5cbiAgICBjb25zdCBpbnB1dDI6IFN1YkFnZW50SW5wdXQgPSB7XG4gICAgICAgIHVzZXJJbnB1dDogXCJIb3cgdG8gY3JlYXRlIHBpdm90IHRhYmxlP1wiLFxuICAgICAgICB1c2VySWQ6IFwidGVzdFVzZXI0NTZcIlxuICAgIH07XG4gICAgY29uc29sZS5sb2coXCJcXFxcbi0tLSBDcmVhdGl2ZSBUZXN0IDIgLS0tXCIpO1xuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGFnZW50LmFuYWx5emUoaW5wdXQyKTtcbiAgICBjb25zb2xlLmxvZyhKU09OLnN0cmluZ2lmeShyZXNwb25zZTIsIG51bGwsIDIpKTtcblxuICAgIGNvbnN0IGlucHV0MzogU3ViQWdlbnRJbnB1dCA9IHtcbiAgICAgICAgdXNlcklucHV0OiBcIkhlbHAgbWUuXCIsXG4gICAgICAgIHVzZXJJZDogXCJ0ZXN0VXNlcjc4OVwiXG4gICAgfTtcbiAgICBjb25zb2xlLmxvZyhcIlxcXFxuLS0tIENyZWF0aXZlIFRlc3QgMyAoVmFndWUpIC0tLVwiKTtcbiAgICBjb25zdCByZXNwb25zZTMgPSBhd2FpdCBhZ2VudC5hbmFseXplKGlucHV0Myk7XG4gICAgY29uc29sZS5sb2coSlNPTi5zdHJpbmdpZnkocmVzcG9uc2UzLCBudWxsLCAyKSk7XG59XG5cbi8vIHRlc3RDcmVhdGl2ZUFnZW50KCk7XG4qL1xuY29uc29sZS5sb2coXG4gICdDcmVhdGl2ZUFnZW50IGNsYXNzIGxvYWRlZC4gVG8gdGVzdCwgdW5jb21tZW50IGFuZCBydW4gdGVzdENyZWF0aXZlQWdlbnQoKS4nXG4pO1xuIl19