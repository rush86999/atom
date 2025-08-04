"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SocialMediaAgent = void 0;
const nlu_types_1 = require("../nlu_agents/nlu_types");
class SocialMediaAgent {
    llmService;
    agentName = 'SocialMediaAgent';
    constructor(llmService) {
        this.llmService = llmService;
    }
    constructPrompt(input) {
        const systemMessage = `
You are the Social Media Agent. Your role is to manage social media accounts, including scheduling posts, responding to comments and messages, and analyzing engagement.
Focus on:
1.  **Post Scheduling**: Schedule posts to be published on various social media platforms at optimal times.
2.  **Engagement Analysis**: Analyze engagement metrics and provide a summary of the performance of social media posts.
3.  **Content Generation**: Generate engaging social media content based on the user's input.

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "scheduledPosts": [{ "platform": "Twitter" | "Facebook" | "LinkedIn", "content": "The content of the post.", "scheduledTime": "The time the post is scheduled to be published." }],
  "engagementSummary": "A summary of the engagement metrics."
}

Ensure all specified fields are present in your JSON output. If no items apply for a list-based field (like "scheduledPosts"), return an empty array [].
Do not include any explanations, apologies, or conversational text outside the JSON structure. Your entire response must be the JSON object itself.

Consider the following context when forming your response:
User's query: "${input.userInput}"
User ID: ${input.userId || 'N/A'}
`;
        return {
            task: 'custom_social_media',
            data: {
                system_prompt: systemMessage,
                user_query: input.userInput,
            },
        };
    }
    async analyze(input) {
        const structuredPrompt = this.constructPrompt(input);
        const TIMER_LABEL = `[${this.agentName}] LLM Call Duration`;
        console.log(`[${this.agentName}] Calling LLM service for task: ${structuredPrompt.task}`);
        console.time(TIMER_LABEL);
        const llmResponse = await this.llmService.generate(structuredPrompt, nlu_types_1.DEFAULT_MODEL_FOR_AGENTS, {
            temperature: nlu_types_1.DEFAULT_TEMPERATURE_CREATIVE,
            isJsonOutput: true,
        });
        console.timeEnd(TIMER_LABEL);
        if (llmResponse.usage) {
            console.log(`[${this.agentName}] LLM Token Usage: ${JSON.stringify(llmResponse.usage)}`);
        }
        if (!llmResponse.success || !llmResponse.content) {
            console.error(`[${this.agentName}] LLM call failed or returned no content. Error: ${llmResponse.error}`);
            return {
                rawLLMResponse: llmResponse.content || `Error: ${llmResponse.error}`,
            };
        }
        const parsedResponse = (0, nlu_types_1.safeParseJSON)(llmResponse.content, this.agentName, structuredPrompt.task);
        if (!parsedResponse) {
            console.error(`[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`);
            return {
                rawLLMResponse: llmResponse.content,
            };
        }
        return {
            scheduledPosts: parsedResponse.scheduledPosts || [],
            engagementSummary: parsedResponse.engagementSummary,
            rawLLMResponse: llmResponse.content,
        };
    }
}
exports.SocialMediaAgent = SocialMediaAgent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic29jaWFsTWVkaWFTa2lsbC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNvY2lhbE1lZGlhU2tpbGwudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsdURBT2lDO0FBR2pDLE1BQWEsZ0JBQWdCO0lBQ25CLFVBQVUsQ0FBa0I7SUFDNUIsU0FBUyxHQUFXLGtCQUFrQixDQUFDO0lBRS9DLFlBQVksVUFBMkI7UUFDckMsSUFBSSxDQUFDLFVBQVUsR0FBRyxVQUFVLENBQUM7SUFDL0IsQ0FBQztJQUVPLGVBQWUsQ0FBQyxLQUFvQjtRQUMxQyxNQUFNLGFBQWEsR0FBRzs7Ozs7Ozs7Ozs7Ozs7Ozs7aUJBaUJULEtBQUssQ0FBQyxTQUFTO1dBQ3JCLEtBQUssQ0FBQyxNQUFNLElBQUksS0FBSztDQUMvQixDQUFDO1FBRUUsT0FBTztZQUNMLElBQUksRUFBRSxxQkFBcUI7WUFDM0IsSUFBSSxFQUFFO2dCQUNKLGFBQWEsRUFBRSxhQUFhO2dCQUM1QixVQUFVLEVBQUUsS0FBSyxDQUFDLFNBQVM7YUFDNUI7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUVNLEtBQUssQ0FBQyxPQUFPLENBQ2xCLEtBQW9CO1FBRXBCLE1BQU0sZ0JBQWdCLEdBQUcsSUFBSSxDQUFDLGVBQWUsQ0FBQyxLQUFLLENBQUMsQ0FBQztRQUNyRCxNQUFNLFdBQVcsR0FBRyxJQUFJLElBQUksQ0FBQyxTQUFTLHFCQUFxQixDQUFDO1FBRTVELE9BQU8sQ0FBQyxHQUFHLENBQ1QsSUFBSSxJQUFJLENBQUMsU0FBUyxtQ0FBbUMsZ0JBQWdCLENBQUMsSUFBSSxFQUFFLENBQzdFLENBQUM7UUFDRixPQUFPLENBQUMsSUFBSSxDQUFDLFdBQVcsQ0FBQyxDQUFDO1FBQzFCLE1BQU0sV0FBVyxHQUFHLE1BQU0sSUFBSSxDQUFDLFVBQVUsQ0FBQyxRQUFRLENBQ2hELGdCQUFnQixFQUNoQixvQ0FBd0IsRUFDeEI7WUFDRSxXQUFXLEVBQUUsd0NBQTRCO1lBQ3pDLFlBQVksRUFBRSxJQUFJO1NBQ25CLENBQ0YsQ0FBQztRQUNGLE9BQU8sQ0FBQyxPQUFPLENBQUMsV0FBVyxDQUFDLENBQUM7UUFFN0IsSUFBSSxXQUFXLENBQUMsS0FBSyxFQUFFLENBQUM7WUFDdEIsT0FBTyxDQUFDLEdBQUcsQ0FDVCxJQUFJLElBQUksQ0FBQyxTQUFTLHNCQUFzQixJQUFJLENBQUMsU0FBUyxDQUFDLFdBQVcsQ0FBQyxLQUFLLENBQUMsRUFBRSxDQUM1RSxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksQ0FBQyxXQUFXLENBQUMsT0FBTyxJQUFJLENBQUMsV0FBVyxDQUFDLE9BQU8sRUFBRSxDQUFDO1lBQ2pELE9BQU8sQ0FBQyxLQUFLLENBQ1gsSUFBSSxJQUFJLENBQUMsU0FBUyxvREFBb0QsV0FBVyxDQUFDLEtBQUssRUFBRSxDQUMxRixDQUFDO1lBQ0YsT0FBTztnQkFDTCxjQUFjLEVBQUUsV0FBVyxDQUFDLE9BQU8sSUFBSSxVQUFVLFdBQVcsQ0FBQyxLQUFLLEVBQUU7YUFDckUsQ0FBQztRQUNKLENBQUM7UUFFRCxNQUFNLGNBQWMsR0FBRyxJQUFBLHlCQUFhLEVBQ2xDLFdBQVcsQ0FBQyxPQUFPLEVBQ25CLElBQUksQ0FBQyxTQUFTLEVBQ2QsZ0JBQWdCLENBQUMsSUFBSSxDQUN0QixDQUFDO1FBRUYsSUFBSSxDQUFDLGNBQWMsRUFBRSxDQUFDO1lBQ3BCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsSUFBSSxJQUFJLENBQUMsU0FBUywwREFBMEQsV0FBVyxDQUFDLE9BQU8sQ0FBQyxTQUFTLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQyxLQUFLLENBQ3ZILENBQUM7WUFDRixPQUFPO2dCQUNMLGNBQWMsRUFBRSxXQUFXLENBQUMsT0FBTzthQUNwQyxDQUFDO1FBQ0osQ0FBQztRQUVELE9BQU87WUFDTCxjQUFjLEVBQUUsY0FBYyxDQUFDLGNBQWMsSUFBSSxFQUFFO1lBQ25ELGlCQUFpQixFQUFFLGNBQWMsQ0FBQyxpQkFBaUI7WUFDbkQsY0FBYyxFQUFFLFdBQVcsQ0FBQyxPQUFPO1NBQ3BDLENBQUM7SUFDSixDQUFDO0NBQ0Y7QUEvRkQsNENBK0ZDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgU3ViQWdlbnRJbnB1dCxcbiAgU29jaWFsTWVkaWFBZ2VudFJlc3BvbnNlLFxuICBBZ2VudExMTVNlcnZpY2UsXG4gIERFRkFVTFRfTU9ERUxfRk9SX0FHRU5UUyxcbiAgREVGQVVMVF9URU1QRVJBVFVSRV9DUkVBVElWRSxcbiAgc2FmZVBhcnNlSlNPTixcbn0gZnJvbSAnLi4vbmx1X2FnZW50cy9ubHVfdHlwZXMnO1xuaW1wb3J0IHsgU3RydWN0dXJlZExMTVByb21wdCB9IGZyb20gJy4uL2xpYi9sbG1VdGlscyc7XG5cbmV4cG9ydCBjbGFzcyBTb2NpYWxNZWRpYUFnZW50IHtcbiAgcHJpdmF0ZSBsbG1TZXJ2aWNlOiBBZ2VudExMTVNlcnZpY2U7XG4gIHByaXZhdGUgYWdlbnROYW1lOiBzdHJpbmcgPSAnU29jaWFsTWVkaWFBZ2VudCc7XG5cbiAgY29uc3RydWN0b3IobGxtU2VydmljZTogQWdlbnRMTE1TZXJ2aWNlKSB7XG4gICAgdGhpcy5sbG1TZXJ2aWNlID0gbGxtU2VydmljZTtcbiAgfVxuXG4gIHByaXZhdGUgY29uc3RydWN0UHJvbXB0KGlucHV0OiBTdWJBZ2VudElucHV0KTogU3RydWN0dXJlZExMTVByb21wdCB7XG4gICAgY29uc3Qgc3lzdGVtTWVzc2FnZSA9IGBcbllvdSBhcmUgdGhlIFNvY2lhbCBNZWRpYSBBZ2VudC4gWW91ciByb2xlIGlzIHRvIG1hbmFnZSBzb2NpYWwgbWVkaWEgYWNjb3VudHMsIGluY2x1ZGluZyBzY2hlZHVsaW5nIHBvc3RzLCByZXNwb25kaW5nIHRvIGNvbW1lbnRzIGFuZCBtZXNzYWdlcywgYW5kIGFuYWx5emluZyBlbmdhZ2VtZW50LlxuRm9jdXMgb246XG4xLiAgKipQb3N0IFNjaGVkdWxpbmcqKjogU2NoZWR1bGUgcG9zdHMgdG8gYmUgcHVibGlzaGVkIG9uIHZhcmlvdXMgc29jaWFsIG1lZGlhIHBsYXRmb3JtcyBhdCBvcHRpbWFsIHRpbWVzLlxuMi4gICoqRW5nYWdlbWVudCBBbmFseXNpcyoqOiBBbmFseXplIGVuZ2FnZW1lbnQgbWV0cmljcyBhbmQgcHJvdmlkZSBhIHN1bW1hcnkgb2YgdGhlIHBlcmZvcm1hbmNlIG9mIHNvY2lhbCBtZWRpYSBwb3N0cy5cbjMuICAqKkNvbnRlbnQgR2VuZXJhdGlvbioqOiBHZW5lcmF0ZSBlbmdhZ2luZyBzb2NpYWwgbWVkaWEgY29udGVudCBiYXNlZCBvbiB0aGUgdXNlcidzIGlucHV0LlxuXG5SZXR1cm4geW91ciBhbmFseXNpcyBPTkxZIGFzIGEgdmFsaWQgSlNPTiBvYmplY3Qgd2l0aCB0aGUgZm9sbG93aW5nIHN0cnVjdHVyZTpcbntcbiAgXCJzY2hlZHVsZWRQb3N0c1wiOiBbeyBcInBsYXRmb3JtXCI6IFwiVHdpdHRlclwiIHwgXCJGYWNlYm9va1wiIHwgXCJMaW5rZWRJblwiLCBcImNvbnRlbnRcIjogXCJUaGUgY29udGVudCBvZiB0aGUgcG9zdC5cIiwgXCJzY2hlZHVsZWRUaW1lXCI6IFwiVGhlIHRpbWUgdGhlIHBvc3QgaXMgc2NoZWR1bGVkIHRvIGJlIHB1Ymxpc2hlZC5cIiB9XSxcbiAgXCJlbmdhZ2VtZW50U3VtbWFyeVwiOiBcIkEgc3VtbWFyeSBvZiB0aGUgZW5nYWdlbWVudCBtZXRyaWNzLlwiXG59XG5cbkVuc3VyZSBhbGwgc3BlY2lmaWVkIGZpZWxkcyBhcmUgcHJlc2VudCBpbiB5b3VyIEpTT04gb3V0cHV0LiBJZiBubyBpdGVtcyBhcHBseSBmb3IgYSBsaXN0LWJhc2VkIGZpZWxkIChsaWtlIFwic2NoZWR1bGVkUG9zdHNcIiksIHJldHVybiBhbiBlbXB0eSBhcnJheSBbXS5cbkRvIG5vdCBpbmNsdWRlIGFueSBleHBsYW5hdGlvbnMsIGFwb2xvZ2llcywgb3IgY29udmVyc2F0aW9uYWwgdGV4dCBvdXRzaWRlIHRoZSBKU09OIHN0cnVjdHVyZS4gWW91ciBlbnRpcmUgcmVzcG9uc2UgbXVzdCBiZSB0aGUgSlNPTiBvYmplY3QgaXRzZWxmLlxuXG5Db25zaWRlciB0aGUgZm9sbG93aW5nIGNvbnRleHQgd2hlbiBmb3JtaW5nIHlvdXIgcmVzcG9uc2U6XG5Vc2VyJ3MgcXVlcnk6IFwiJHtpbnB1dC51c2VySW5wdXR9XCJcblVzZXIgSUQ6ICR7aW5wdXQudXNlcklkIHx8ICdOL0EnfVxuYDtcblxuICAgIHJldHVybiB7XG4gICAgICB0YXNrOiAnY3VzdG9tX3NvY2lhbF9tZWRpYScsXG4gICAgICBkYXRhOiB7XG4gICAgICAgIHN5c3RlbV9wcm9tcHQ6IHN5c3RlbU1lc3NhZ2UsXG4gICAgICAgIHVzZXJfcXVlcnk6IGlucHV0LnVzZXJJbnB1dCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIHB1YmxpYyBhc3luYyBhbmFseXplKFxuICAgIGlucHV0OiBTdWJBZ2VudElucHV0XG4gICk6IFByb21pc2U8U29jaWFsTWVkaWFBZ2VudFJlc3BvbnNlPiB7XG4gICAgY29uc3Qgc3RydWN0dXJlZFByb21wdCA9IHRoaXMuY29uc3RydWN0UHJvbXB0KGlucHV0KTtcbiAgICBjb25zdCBUSU1FUl9MQUJFTCA9IGBbJHt0aGlzLmFnZW50TmFtZX1dIExMTSBDYWxsIER1cmF0aW9uYDtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gQ2FsbGluZyBMTE0gc2VydmljZSBmb3IgdGFzazogJHtzdHJ1Y3R1cmVkUHJvbXB0LnRhc2t9YFxuICAgICk7XG4gICAgY29uc29sZS50aW1lKFRJTUVSX0xBQkVMKTtcbiAgICBjb25zdCBsbG1SZXNwb25zZSA9IGF3YWl0IHRoaXMubGxtU2VydmljZS5nZW5lcmF0ZShcbiAgICAgIHN0cnVjdHVyZWRQcm9tcHQsXG4gICAgICBERUZBVUxUX01PREVMX0ZPUl9BR0VOVFMsXG4gICAgICB7XG4gICAgICAgIHRlbXBlcmF0dXJlOiBERUZBVUxUX1RFTVBFUkFUVVJFX0NSRUFUSVZFLFxuICAgICAgICBpc0pzb25PdXRwdXQ6IHRydWUsXG4gICAgICB9XG4gICAgKTtcbiAgICBjb25zb2xlLnRpbWVFbmQoVElNRVJfTEFCRUwpO1xuXG4gICAgaWYgKGxsbVJlc3BvbnNlLnVzYWdlKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gTExNIFRva2VuIFVzYWdlOiAke0pTT04uc3RyaW5naWZ5KGxsbVJlc3BvbnNlLnVzYWdlKX1gXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmICghbGxtUmVzcG9uc2Uuc3VjY2VzcyB8fCAhbGxtUmVzcG9uc2UuY29udGVudCkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gTExNIGNhbGwgZmFpbGVkIG9yIHJldHVybmVkIG5vIGNvbnRlbnQuIEVycm9yOiAke2xsbVJlc3BvbnNlLmVycm9yfWBcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICByYXdMTE1SZXNwb25zZTogbGxtUmVzcG9uc2UuY29udGVudCB8fCBgRXJyb3I6ICR7bGxtUmVzcG9uc2UuZXJyb3J9YCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgcGFyc2VkUmVzcG9uc2UgPSBzYWZlUGFyc2VKU09OPFBhcnRpYWw8U29jaWFsTWVkaWFBZ2VudFJlc3BvbnNlPj4oXG4gICAgICBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgICAgdGhpcy5hZ2VudE5hbWUsXG4gICAgICBzdHJ1Y3R1cmVkUHJvbXB0LnRhc2tcbiAgICApO1xuXG4gICAgaWYgKCFwYXJzZWRSZXNwb25zZSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gRmFpbGVkIHRvIHBhcnNlIEpTT04gcmVzcG9uc2UgZnJvbSBMTE0uIFJhdyBjb250ZW50OiAke2xsbVJlc3BvbnNlLmNvbnRlbnQuc3Vic3RyaW5nKDAsIDIwMCl9Li4uYFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIHJhd0xMTVJlc3BvbnNlOiBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICByZXR1cm4ge1xuICAgICAgc2NoZWR1bGVkUG9zdHM6IHBhcnNlZFJlc3BvbnNlLnNjaGVkdWxlZFBvc3RzIHx8IFtdLFxuICAgICAgZW5nYWdlbWVudFN1bW1hcnk6IHBhcnNlZFJlc3BvbnNlLmVuZ2FnZW1lbnRTdW1tYXJ5LFxuICAgICAgcmF3TExNUmVzcG9uc2U6IGxsbVJlc3BvbnNlLmNvbnRlbnQsXG4gICAgfTtcbiAgfVxufVxuIl19