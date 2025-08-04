"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AnalyticalAgent = void 0;
const nlu_types_1 = require("./nlu_types");
class AnalyticalAgent {
    llmService;
    agentName = 'AnalyticalAgent';
    constructor(llmService) {
        this.llmService = llmService;
    }
    constructPrompt(input) {
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
            },
        };
    }
    async analyze(input) {
        const structuredPrompt = this.constructPrompt(input);
        const P_ANALYTICAL_AGENT_TIMER_LABEL = `[${this.agentName}] LLM Call Duration`;
        console.log(`[${this.agentName}] Calling LLM service for task: ${structuredPrompt.task}`);
        console.time(P_ANALYTICAL_AGENT_TIMER_LABEL);
        const llmResponse = await this.llmService.generate(structuredPrompt, nlu_types_1.DEFAULT_MODEL_FOR_AGENTS, {
            temperature: nlu_types_1.DEFAULT_TEMPERATURE_ANALYTICAL,
            isJsonOutput: true, // Crucial for ensuring RealLLMService requests JSON mode
        });
        if (!llmResponse.success || !llmResponse.content) {
            console.error(`[${this.agentName}] LLM call failed or returned no content. Error: ${llmResponse.error}`);
            return {
                // Return a default/error response structure
                logicalConsistency: {
                    isConsistent: false,
                    reason: `LLM analysis failed: ${llmResponse.error || 'No content'}`,
                },
                rawLLMResponse: llmResponse.content || `Error: ${llmResponse.error}`,
            };
        }
        // Attempt to parse the JSON response from the LLM
        const parsedResponse = (0, nlu_types_1.safeParseJSON)(// Expecting a partial response that matches the structure
        llmResponse.content, this.agentName, structuredPrompt.task);
        if (!parsedResponse) {
            console.error(`[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`);
            return {
                // Return a default/error response structure if parsing fails
                logicalConsistency: {
                    isConsistent: false,
                    reason: 'Failed to parse LLM JSON response.',
                },
                rawLLMResponse: llmResponse.content,
            };
        }
        // Construct the full response, providing defaults for any missing fields
        // This also serves as a basic validation that the LLM is returning something usable.
        // More advanced schema validation could be added here (e.g., using Zod or AJV).
        const analyticalAgentResponse = {
            identifiedEntities: parsedResponse.identifiedEntities || [],
            explicitTasks: parsedResponse.explicitTasks || [],
            informationNeeded: parsedResponse.informationNeeded || [],
            logicalConsistency: parsedResponse.logicalConsistency || {
                isConsistent: true,
                reason: 'Consistency not specified by LLM.',
            },
            problemType: parsedResponse.problemType || 'unknown',
            rawLLMResponse: llmResponse.content, // Always include the raw response for debugging
        };
        return analyticalAgentResponse;
    }
}
exports.AnalyticalAgent = AnalyticalAgent;
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
console.log('AnalyticalAgent class loaded. To test, uncomment and run testAnalyticalAgent().');
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYW5hbHl0aWNhbF9hZ2VudC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFuYWx5dGljYWxfYWdlbnQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsMkNBT3FCO0FBR3JCLE1BQWEsZUFBZTtJQUNsQixVQUFVLENBQWtCO0lBQzVCLFNBQVMsR0FBVyxpQkFBaUIsQ0FBQztJQUU5QyxZQUFZLFVBQTJCO1FBQ3JDLElBQUksQ0FBQyxVQUFVLEdBQUcsVUFBVSxDQUFDO0lBQy9CLENBQUM7SUFFTyxlQUFlLENBQUMsS0FBb0I7UUFDMUMsTUFBTSxhQUFhLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O1VBdUJoQixLQUFLLENBQUMsTUFBTSxJQUFJLEtBQUs7Q0FDOUIsQ0FBQztRQUVFLE9BQU87WUFDTCxJQUFJLEVBQUUsNEJBQTRCLEVBQUUsNkRBQTZEO1lBQ2pHLElBQUksRUFBRTtnQkFDSixhQUFhLEVBQUUsYUFBYTtnQkFDNUIsVUFBVSxFQUFFLEtBQUssQ0FBQyxTQUFTO2FBQzVCO1NBQ0YsQ0FBQztJQUNKLENBQUM7SUFFTSxLQUFLLENBQUMsT0FBTyxDQUFDLEtBQW9CO1FBQ3ZDLE1BQU0sZ0JBQWdCLEdBQUcsSUFBSSxDQUFDLGVBQWUsQ0FBQyxLQUFLLENBQUMsQ0FBQztRQUNyRCxNQUFNLDhCQUE4QixHQUFHLElBQUksSUFBSSxDQUFDLFNBQVMscUJBQXFCLENBQUM7UUFFL0UsT0FBTyxDQUFDLEdBQUcsQ0FDVCxJQUFJLElBQUksQ0FBQyxTQUFTLG1DQUFtQyxnQkFBZ0IsQ0FBQyxJQUFJLEVBQUUsQ0FDN0UsQ0FBQztRQUNGLE9BQU8sQ0FBQyxJQUFJLENBQUMsOEJBQThCLENBQUMsQ0FBQztRQUM3QyxNQUFNLFdBQVcsR0FBRyxNQUFNLElBQUksQ0FBQyxVQUFVLENBQUMsUUFBUSxDQUNoRCxnQkFBZ0IsRUFDaEIsb0NBQXdCLEVBQ3hCO1lBQ0UsV0FBVyxFQUFFLDBDQUE4QjtZQUMzQyxZQUFZLEVBQUUsSUFBSSxFQUFFLHlEQUF5RDtTQUM5RSxDQUNGLENBQUM7UUFFRixJQUFJLENBQUMsV0FBVyxDQUFDLE9BQU8sSUFBSSxDQUFDLFdBQVcsQ0FBQyxPQUFPLEVBQUUsQ0FBQztZQUNqRCxPQUFPLENBQUMsS0FBSyxDQUNYLElBQUksSUFBSSxDQUFDLFNBQVMsb0RBQW9ELFdBQVcsQ0FBQyxLQUFLLEVBQUUsQ0FDMUYsQ0FBQztZQUNGLE9BQU87Z0JBQ0wsNENBQTRDO2dCQUM1QyxrQkFBa0IsRUFBRTtvQkFDbEIsWUFBWSxFQUFFLEtBQUs7b0JBQ25CLE1BQU0sRUFBRSx3QkFBd0IsV0FBVyxDQUFDLEtBQUssSUFBSSxZQUFZLEVBQUU7aUJBQ3BFO2dCQUNELGNBQWMsRUFBRSxXQUFXLENBQUMsT0FBTyxJQUFJLFVBQVUsV0FBVyxDQUFDLEtBQUssRUFBRTthQUNyRSxDQUFDO1FBQ0osQ0FBQztRQUVELGtEQUFrRDtRQUNsRCxNQUFNLGNBQWMsR0FBRyxJQUFBLHlCQUFhLEVBQW9DLDBEQUEwRDtRQUNoSSxXQUFXLENBQUMsT0FBTyxFQUNuQixJQUFJLENBQUMsU0FBUyxFQUNkLGdCQUFnQixDQUFDLElBQUksQ0FDdEIsQ0FBQztRQUVGLElBQUksQ0FBQyxjQUFjLEVBQUUsQ0FBQztZQUNwQixPQUFPLENBQUMsS0FBSyxDQUNYLElBQUksSUFBSSxDQUFDLFNBQVMsMERBQTBELFdBQVcsQ0FBQyxPQUFPLENBQUMsU0FBUyxDQUFDLENBQUMsRUFBRSxHQUFHLENBQUMsS0FBSyxDQUN2SCxDQUFDO1lBQ0YsT0FBTztnQkFDTCw2REFBNkQ7Z0JBQzdELGtCQUFrQixFQUFFO29CQUNsQixZQUFZLEVBQUUsS0FBSztvQkFDbkIsTUFBTSxFQUFFLG9DQUFvQztpQkFDN0M7Z0JBQ0QsY0FBYyxFQUFFLFdBQVcsQ0FBQyxPQUFPO2FBQ3BDLENBQUM7UUFDSixDQUFDO1FBRUQseUVBQXlFO1FBQ3pFLHFGQUFxRjtRQUNyRixnRkFBZ0Y7UUFDaEYsTUFBTSx1QkFBdUIsR0FBNEI7WUFDdkQsa0JBQWtCLEVBQUUsY0FBYyxDQUFDLGtCQUFrQixJQUFJLEVBQUU7WUFDM0QsYUFBYSxFQUFFLGNBQWMsQ0FBQyxhQUFhLElBQUksRUFBRTtZQUNqRCxpQkFBaUIsRUFBRSxjQUFjLENBQUMsaUJBQWlCLElBQUksRUFBRTtZQUN6RCxrQkFBa0IsRUFBRSxjQUFjLENBQUMsa0JBQWtCLElBQUk7Z0JBQ3ZELFlBQVksRUFBRSxJQUFJO2dCQUNsQixNQUFNLEVBQUUsbUNBQW1DO2FBQzVDO1lBQ0QsV0FBVyxFQUFFLGNBQWMsQ0FBQyxXQUFXLElBQUksU0FBUztZQUNwRCxjQUFjLEVBQUUsV0FBVyxDQUFDLE9BQU8sRUFBRSxnREFBZ0Q7U0FDdEYsQ0FBQztRQUVGLE9BQU8sdUJBQXVCLENBQUM7SUFDakMsQ0FBQztDQUNGO0FBakhELDBDQWlIQztBQUVELDJFQUEyRTtBQUMzRTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0VBaUNFO0FBRUYsT0FBTyxDQUFDLEdBQUcsQ0FDVCxpRkFBaUYsQ0FDbEYsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIFN1YkFnZW50SW5wdXQsXG4gIEFuYWx5dGljYWxBZ2VudFJlc3BvbnNlLFxuICBBZ2VudExMTVNlcnZpY2UsXG4gIERFRkFVTFRfTU9ERUxfRk9SX0FHRU5UUyxcbiAgREVGQVVMVF9URU1QRVJBVFVSRV9BTkFMWVRJQ0FMLFxuICBzYWZlUGFyc2VKU09OLFxufSBmcm9tICcuL25sdV90eXBlcyc7XG5pbXBvcnQgeyBTdHJ1Y3R1cmVkTExNUHJvbXB0LCBMTE1TZXJ2aWNlUmVzcG9uc2UgfSBmcm9tICcuLi9saWIvbGxtVXRpbHMnO1xuXG5leHBvcnQgY2xhc3MgQW5hbHl0aWNhbEFnZW50IHtcbiAgcHJpdmF0ZSBsbG1TZXJ2aWNlOiBBZ2VudExMTVNlcnZpY2U7XG4gIHByaXZhdGUgYWdlbnROYW1lOiBzdHJpbmcgPSAnQW5hbHl0aWNhbEFnZW50JztcblxuICBjb25zdHJ1Y3RvcihsbG1TZXJ2aWNlOiBBZ2VudExMTVNlcnZpY2UpIHtcbiAgICB0aGlzLmxsbVNlcnZpY2UgPSBsbG1TZXJ2aWNlO1xuICB9XG5cbiAgcHJpdmF0ZSBjb25zdHJ1Y3RQcm9tcHQoaW5wdXQ6IFN1YkFnZW50SW5wdXQpOiBTdHJ1Y3R1cmVkTExNUHJvbXB0IHtcbiAgICBjb25zdCBzeXN0ZW1NZXNzYWdlID0gYFxuWW91IGFyZSB0aGUgQW5hbHl0aWNhbCBJbnRlbGxpZ2VuY2UgQWdlbnQuIFlvdXIgcm9sZSBpcyB0byBtZXRpY3Vsb3VzbHkgYW5hbHl6ZSB0aGUgdXNlcidzIHF1ZXJ5IHRvIGlkZW50aWZ5IGl0cyBjb3JlIGNvbXBvbmVudHMuXG5Gb2N1cyBvbjpcbjEuICAqKkVudGl0aWVzKio6IEtleSBub3VucywgY29uY2VwdHMsIHByb2plY3QgbmFtZXMsIGRhdGVzLCBzcGVjaWZpYyBpdGVtcyBtZW50aW9uZWQuXG4yLiAgKipFeHBsaWNpdCBUYXNrcyoqOiBWZXJicyBhbmQgYWN0aW9ucyB0aGUgdXNlciBleHBsaWNpdGx5IHN0YXRlcyB0aGV5IHdhbnQgdG8gcGVyZm9ybS5cbjMuICAqKkluZm9ybWF0aW9uIE5lZWRlZCoqOiBXaGF0IHNwZWNpZmljIGluZm9ybWF0aW9uIGlzIHRoZSB1c2VyIHNlZWtpbmc/XG40LiAgKipMb2dpY2FsIENvbnNpc3RlbmN5Kio6IElzIHRoZSByZXF1ZXN0IGNsZWFyLCB1bmFtYmlndW91cywgYW5kIGxvZ2ljYWxseSBzb3VuZD8gSWRlbnRpZnkgYW55IGNvbnRyYWRpY3Rpb25zIG9yIHZhZ3VlbmVzcy5cbjUuICAqKlByb2JsZW0gVHlwZSoqOiBDbGFzc2lmeSB0aGUgZ2VuZXJhbCB0eXBlIG9mIHByb2JsZW0gKGUuZy4sIGluZm9ybWF0aW9uX3JldHJpZXZhbCwgdGFza19leGVjdXRpb24sIGRhdGFfYW5hbHlzaXMsIGNvbXBhcmlzb24sIHRyb3VibGVzaG9vdGluZywgYWR2YW5jZWRfcmVzZWFyY2gsIHNvY2lhbF9tZWRpYV9tYW5hZ2VtZW50LCBjb250ZW50X2NyZWF0aW9uLCBwZXJzb25hbGl6ZWRfc2hvcHBpbmcsIGxlZ2FsX2RvY3VtZW50X2FuYWx5c2lzLCByZWNydWl0bWVudF9yZWNvbW1lbmRhdGlvbiwgdmliZV9oYWNraW5nKS5cblxuUmV0dXJuIHlvdXIgYW5hbHlzaXMgT05MWSBhcyBhIHZhbGlkIEpTT04gb2JqZWN0IHdpdGggdGhlIGZvbGxvd2luZyBzdHJ1Y3R1cmU6XG57XG4gIFwiaWRlbnRpZmllZEVudGl0aWVzXCI6IFtcImVudGl0eTFcIiwgXCJlbnRpdHkyXCIsIC4uLl0sXG4gIFwiZXhwbGljaXRUYXNrc1wiOiBbXCJ0YXNrMSBkZXNjcmlwdGlvblwiLCBcInRhc2syIGRlc2NyaXB0aW9uXCIsIC4uLl0sXG4gIFwiaW5mb3JtYXRpb25OZWVkZWRcIjogW1wic3BlY2lmaWMgaW5mbzFcIiwgXCJzcGVjaWZpYyBpbmZvMlwiLCAuLi5dLFxuICBcImxvZ2ljYWxDb25zaXN0ZW5jeVwiOiB7XG4gICAgXCJpc0NvbnNpc3RlbnRcIjogYm9vbGVhbixcbiAgICBcInJlYXNvblwiOiBcInN0cmluZyAoaWYgbm90IGNvbnNpc3RlbnQsIGV4cGxhaW4gd2h5KVwiXG4gIH0sXG4gIFwicHJvYmxlbVR5cGVcIjogXCJ0eXBlX3N0cmluZ1wiXG59XG5cbkRvIG5vdCBpbmNsdWRlIGFueSBleHBsYW5hdGlvbnMgb3IgY29udmVyc2F0aW9uYWwgdGV4dCBvdXRzaWRlIHRoZSBKU09OIHN0cnVjdHVyZS5cblVzZXIncyBlbnZpcm9ubWVudCBjb250ZXh0IChpZiBwcm92aWRlZCwgdXNlIGl0IHRvIHJlZmluZSBlbnRpdHkvdGFzayBpZGVudGlmaWNhdGlvbik6XG5Vc2VySWQ6ICR7aW5wdXQudXNlcklkIHx8ICdOL0EnfVxuYDtcblxuICAgIHJldHVybiB7XG4gICAgICB0YXNrOiAnY3VzdG9tX2FuYWx5dGljYWxfYW5hbHlzaXMnLCAvLyBDdXN0b20gdGFzayB0eXBlIGZvciBMTE0gbG9nZ2luZy9kaWZmZXJlbnRpYXRpb24gaWYgbmVlZGVkXG4gICAgICBkYXRhOiB7XG4gICAgICAgIHN5c3RlbV9wcm9tcHQ6IHN5c3RlbU1lc3NhZ2UsXG4gICAgICAgIHVzZXJfcXVlcnk6IGlucHV0LnVzZXJJbnB1dCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIHB1YmxpYyBhc3luYyBhbmFseXplKGlucHV0OiBTdWJBZ2VudElucHV0KTogUHJvbWlzZTxBbmFseXRpY2FsQWdlbnRSZXNwb25zZT4ge1xuICAgIGNvbnN0IHN0cnVjdHVyZWRQcm9tcHQgPSB0aGlzLmNvbnN0cnVjdFByb21wdChpbnB1dCk7XG4gICAgY29uc3QgUF9BTkFMWVRJQ0FMX0FHRU5UX1RJTUVSX0xBQkVMID0gYFske3RoaXMuYWdlbnROYW1lfV0gTExNIENhbGwgRHVyYXRpb25gO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBgWyR7dGhpcy5hZ2VudE5hbWV9XSBDYWxsaW5nIExMTSBzZXJ2aWNlIGZvciB0YXNrOiAke3N0cnVjdHVyZWRQcm9tcHQudGFza31gXG4gICAgKTtcbiAgICBjb25zb2xlLnRpbWUoUF9BTkFMWVRJQ0FMX0FHRU5UX1RJTUVSX0xBQkVMKTtcbiAgICBjb25zdCBsbG1SZXNwb25zZSA9IGF3YWl0IHRoaXMubGxtU2VydmljZS5nZW5lcmF0ZShcbiAgICAgIHN0cnVjdHVyZWRQcm9tcHQsXG4gICAgICBERUZBVUxUX01PREVMX0ZPUl9BR0VOVFMsXG4gICAgICB7XG4gICAgICAgIHRlbXBlcmF0dXJlOiBERUZBVUxUX1RFTVBFUkFUVVJFX0FOQUxZVElDQUwsXG4gICAgICAgIGlzSnNvbk91dHB1dDogdHJ1ZSwgLy8gQ3J1Y2lhbCBmb3IgZW5zdXJpbmcgUmVhbExMTVNlcnZpY2UgcmVxdWVzdHMgSlNPTiBtb2RlXG4gICAgICB9XG4gICAgKTtcblxuICAgIGlmICghbGxtUmVzcG9uc2Uuc3VjY2VzcyB8fCAhbGxtUmVzcG9uc2UuY29udGVudCkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gTExNIGNhbGwgZmFpbGVkIG9yIHJldHVybmVkIG5vIGNvbnRlbnQuIEVycm9yOiAke2xsbVJlc3BvbnNlLmVycm9yfWBcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICAvLyBSZXR1cm4gYSBkZWZhdWx0L2Vycm9yIHJlc3BvbnNlIHN0cnVjdHVyZVxuICAgICAgICBsb2dpY2FsQ29uc2lzdGVuY3k6IHtcbiAgICAgICAgICBpc0NvbnNpc3RlbnQ6IGZhbHNlLFxuICAgICAgICAgIHJlYXNvbjogYExMTSBhbmFseXNpcyBmYWlsZWQ6ICR7bGxtUmVzcG9uc2UuZXJyb3IgfHwgJ05vIGNvbnRlbnQnfWAsXG4gICAgICAgIH0sXG4gICAgICAgIHJhd0xMTVJlc3BvbnNlOiBsbG1SZXNwb25zZS5jb250ZW50IHx8IGBFcnJvcjogJHtsbG1SZXNwb25zZS5lcnJvcn1gLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICAvLyBBdHRlbXB0IHRvIHBhcnNlIHRoZSBKU09OIHJlc3BvbnNlIGZyb20gdGhlIExMTVxuICAgIGNvbnN0IHBhcnNlZFJlc3BvbnNlID0gc2FmZVBhcnNlSlNPTjxQYXJ0aWFsPEFuYWx5dGljYWxBZ2VudFJlc3BvbnNlPj4oIC8vIEV4cGVjdGluZyBhIHBhcnRpYWwgcmVzcG9uc2UgdGhhdCBtYXRjaGVzIHRoZSBzdHJ1Y3R1cmVcbiAgICAgIGxsbVJlc3BvbnNlLmNvbnRlbnQsXG4gICAgICB0aGlzLmFnZW50TmFtZSxcbiAgICAgIHN0cnVjdHVyZWRQcm9tcHQudGFza1xuICAgICk7XG5cbiAgICBpZiAoIXBhcnNlZFJlc3BvbnNlKSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICBgWyR7dGhpcy5hZ2VudE5hbWV9XSBGYWlsZWQgdG8gcGFyc2UgSlNPTiByZXNwb25zZSBmcm9tIExMTS4gUmF3IGNvbnRlbnQ6ICR7bGxtUmVzcG9uc2UuY29udGVudC5zdWJzdHJpbmcoMCwgMjAwKX0uLi5gXG4gICAgICApO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgLy8gUmV0dXJuIGEgZGVmYXVsdC9lcnJvciByZXNwb25zZSBzdHJ1Y3R1cmUgaWYgcGFyc2luZyBmYWlsc1xuICAgICAgICBsb2dpY2FsQ29uc2lzdGVuY3k6IHtcbiAgICAgICAgICBpc0NvbnNpc3RlbnQ6IGZhbHNlLFxuICAgICAgICAgIHJlYXNvbjogJ0ZhaWxlZCB0byBwYXJzZSBMTE0gSlNPTiByZXNwb25zZS4nLFxuICAgICAgICB9LFxuICAgICAgICByYXdMTE1SZXNwb25zZTogbGxtUmVzcG9uc2UuY29udGVudCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgLy8gQ29uc3RydWN0IHRoZSBmdWxsIHJlc3BvbnNlLCBwcm92aWRpbmcgZGVmYXVsdHMgZm9yIGFueSBtaXNzaW5nIGZpZWxkc1xuICAgIC8vIFRoaXMgYWxzbyBzZXJ2ZXMgYXMgYSBiYXNpYyB2YWxpZGF0aW9uIHRoYXQgdGhlIExMTSBpcyByZXR1cm5pbmcgc29tZXRoaW5nIHVzYWJsZS5cbiAgICAvLyBNb3JlIGFkdmFuY2VkIHNjaGVtYSB2YWxpZGF0aW9uIGNvdWxkIGJlIGFkZGVkIGhlcmUgKGUuZy4sIHVzaW5nIFpvZCBvciBBSlYpLlxuICAgIGNvbnN0IGFuYWx5dGljYWxBZ2VudFJlc3BvbnNlOiBBbmFseXRpY2FsQWdlbnRSZXNwb25zZSA9IHtcbiAgICAgIGlkZW50aWZpZWRFbnRpdGllczogcGFyc2VkUmVzcG9uc2UuaWRlbnRpZmllZEVudGl0aWVzIHx8IFtdLFxuICAgICAgZXhwbGljaXRUYXNrczogcGFyc2VkUmVzcG9uc2UuZXhwbGljaXRUYXNrcyB8fCBbXSxcbiAgICAgIGluZm9ybWF0aW9uTmVlZGVkOiBwYXJzZWRSZXNwb25zZS5pbmZvcm1hdGlvbk5lZWRlZCB8fCBbXSxcbiAgICAgIGxvZ2ljYWxDb25zaXN0ZW5jeTogcGFyc2VkUmVzcG9uc2UubG9naWNhbENvbnNpc3RlbmN5IHx8IHtcbiAgICAgICAgaXNDb25zaXN0ZW50OiB0cnVlLFxuICAgICAgICByZWFzb246ICdDb25zaXN0ZW5jeSBub3Qgc3BlY2lmaWVkIGJ5IExMTS4nLFxuICAgICAgfSxcbiAgICAgIHByb2JsZW1UeXBlOiBwYXJzZWRSZXNwb25zZS5wcm9ibGVtVHlwZSB8fCAndW5rbm93bicsXG4gICAgICByYXdMTE1SZXNwb25zZTogbGxtUmVzcG9uc2UuY29udGVudCwgLy8gQWx3YXlzIGluY2x1ZGUgdGhlIHJhdyByZXNwb25zZSBmb3IgZGVidWdnaW5nXG4gICAgfTtcblxuICAgIHJldHVybiBhbmFseXRpY2FsQWdlbnRSZXNwb25zZTtcbiAgfVxufVxuXG4vLyBFeGFtcGxlIFVzYWdlIChmb3IgdGVzdGluZyBwdXJwb3Nlcywgd291bGQgYmUgcmVtb3ZlZCBvciBpbiBhIHRlc3QgZmlsZSlcbi8qXG5pbXBvcnQgeyBNb2NrTExNU2VydmljZSB9IGZyb20gJy4uL2xpYi9sbG1VdGlscyc7XG5cbmFzeW5jIGZ1bmN0aW9uIHRlc3RBbmFseXRpY2FsQWdlbnQoKSB7XG4gICAgY29uc3QgbW9ja0xMTSA9IG5ldyBNb2NrTExNU2VydmljZSgpOyAvLyBVc2luZyB0aGUgZ2VuZXJhbCBtb2NrIHNlcnZpY2VcbiAgICBjb25zdCBhZ2VudCA9IG5ldyBBbmFseXRpY2FsQWdlbnQobW9ja0xMTSk7XG5cbiAgICBjb25zdCBpbnB1dDE6IFN1YkFnZW50SW5wdXQgPSB7XG4gICAgICAgIHVzZXJJbnB1dDogXCJDYW4geW91IHRlbGwgbWUgYWJvdXQgdGhlIFEzIGJ1ZGdldCBmb3IgdGhlIG1hcmtldGluZyByZXBvcnQgYW5kIGhvdyB0byBtYWtlIGl0IG1vcmUgZWZmaWNpZW50LCBtYXliZSB1c2luZyB0aGF0IG5ldyBBSSB0aGluZz9cIixcbiAgICAgICAgdXNlcklkOiBcInRlc3RVc2VyMTIzXCJcbiAgICB9O1xuICAgIGNvbnNvbGUubG9nKFwiLS0tIEFuYWx5dGljYWwgVGVzdCAxIC0tLVwiKTtcbiAgICBjb25zdCByZXNwb25zZTEgPSBhd2FpdCBhZ2VudC5hbmFseXplKGlucHV0MSk7XG4gICAgY29uc29sZS5sb2coSlNPTi5zdHJpbmdpZnkocmVzcG9uc2UxLCBudWxsLCAyKSk7XG5cbiAgICBjb25zdCBpbnB1dDI6IFN1YkFnZW50SW5wdXQgPSB7XG4gICAgICAgIHVzZXJJbnB1dDogXCJIb3cgdG8gY3JlYXRlIHBpdm90IHRhYmxlIGluIFNwcmVhZHNoZWV0QXBwXCIsXG4gICAgICAgIHVzZXJJZDogXCJ0ZXN0VXNlcjQ1NlwiXG4gICAgfTtcbiAgICBjb25zb2xlLmxvZyhcIlxcXFxuLS0tIEFuYWx5dGljYWwgVGVzdCAyIC0tLVwiKTtcbiAgICBjb25zdCByZXNwb25zZTIgPSBhd2FpdCBhZ2VudC5hbmFseXplKGlucHV0Mik7XG4gICAgY29uc29sZS5sb2coSlNPTi5zdHJpbmdpZnkocmVzcG9uc2UyLCBudWxsLCAyKSk7XG5cbiAgICBjb25zdCBpbnB1dDM6IFN1YkFnZW50SW5wdXQgPSB7XG4gICAgICAgIHVzZXJJbnB1dDogXCJIZWxwIG1lLlwiLFxuICAgICAgICB1c2VySWQ6IFwidGVzdFVzZXI3ODlcIlxuICAgIH07XG4gICAgY29uc29sZS5sb2coXCJcXFxcbi0tLSBBbmFseXRpY2FsIFRlc3QgMyAoVmFndWUpIC0tLVwiKTtcbiAgICBjb25zdCByZXNwb25zZTMgPSBhd2FpdCBhZ2VudC5hbmFseXplKGlucHV0Myk7XG4gICAgY29uc29sZS5sb2coSlNPTi5zdHJpbmdpZnkocmVzcG9uc2UzLCBudWxsLCAyKSk7XG59XG5cbi8vIHRlc3RBbmFseXRpY2FsQWdlbnQoKTtcbiovXG5cbmNvbnNvbGUubG9nKFxuICAnQW5hbHl0aWNhbEFnZW50IGNsYXNzIGxvYWRlZC4gVG8gdGVzdCwgdW5jb21tZW50IGFuZCBydW4gdGVzdEFuYWx5dGljYWxBZ2VudCgpLidcbik7XG4iXX0=