"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.VibeHackingAgent = void 0;
const nlu_types_1 = require("../nlu_agents/nlu_types");
class VibeHackingAgent {
    llmService;
    agentName = 'VibeHackingAgent';
    constructor(llmService) {
        this.llmService = llmService;
    }
    constructPrompt(input) {
        const systemMessage = `
You are the Vibe Hacking Agent. Your role is to perform red team testing on web applications.
Focus on:
1.  **Vulnerability Scanning**: Scan the target system for vulnerabilities.
2.  **Exploitation**: Attempt to exploit any vulnerabilities that are found.
3.  **Reporting**: Generate a report of the findings, with a description of the vulnerabilities, the steps taken to exploit them, and recommendations for remediation.

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "vulnerabilityReport": [{ "vulnerability": "The name of the vulnerability.", "severity": "Critical" | "High" | "Medium" | "Low", "description": "A description of the vulnerability.", "remediation": "Recommendations for remediating the vulnerability." }]
}

Ensure all specified fields are present in your JSON output. If no items apply for a list-based field (like "vulnerabilityReport"), return an empty array [].
Do not include any explanations, apologies, or conversational text outside the JSON structure. Your entire response must be the JSON object itself.

Consider the following context when forming your response:
User's query: "${input.userInput}"
User ID: ${input.userId || 'N/A'}
`;
        return {
            task: 'custom_vibe_hacking',
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
            temperature: nlu_types_1.DEFAULT_TEMPERATURE_ANALYTICAL,
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
            vulnerabilityReport: parsedResponse.vulnerabilityReport || [],
            rawLLMResponse: llmResponse.content,
        };
    }
}
exports.VibeHackingAgent = VibeHackingAgent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidmliZUhhY2tpbmdTa2lsbC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInZpYmVIYWNraW5nU2tpbGwudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsdURBT2lDO0FBR2pDLE1BQWEsZ0JBQWdCO0lBQ25CLFVBQVUsQ0FBa0I7SUFDNUIsU0FBUyxHQUFXLGtCQUFrQixDQUFDO0lBRS9DLFlBQVksVUFBMkI7UUFDckMsSUFBSSxDQUFDLFVBQVUsR0FBRyxVQUFVLENBQUM7SUFDL0IsQ0FBQztJQUVPLGVBQWUsQ0FBQyxLQUFvQjtRQUMxQyxNQUFNLGFBQWEsR0FBRzs7Ozs7Ozs7Ozs7Ozs7OztpQkFnQlQsS0FBSyxDQUFDLFNBQVM7V0FDckIsS0FBSyxDQUFDLE1BQU0sSUFBSSxLQUFLO0NBQy9CLENBQUM7UUFFRSxPQUFPO1lBQ0wsSUFBSSxFQUFFLHFCQUFxQjtZQUMzQixJQUFJLEVBQUU7Z0JBQ0osYUFBYSxFQUFFLGFBQWE7Z0JBQzVCLFVBQVUsRUFBRSxLQUFLLENBQUMsU0FBUzthQUM1QjtTQUNGLENBQUM7SUFDSixDQUFDO0lBRU0sS0FBSyxDQUFDLE9BQU8sQ0FDbEIsS0FBb0I7UUFFcEIsTUFBTSxnQkFBZ0IsR0FBRyxJQUFJLENBQUMsZUFBZSxDQUFDLEtBQUssQ0FBQyxDQUFDO1FBQ3JELE1BQU0sV0FBVyxHQUFHLElBQUksSUFBSSxDQUFDLFNBQVMscUJBQXFCLENBQUM7UUFFNUQsT0FBTyxDQUFDLEdBQUcsQ0FDVCxJQUFJLElBQUksQ0FBQyxTQUFTLG1DQUFtQyxnQkFBZ0IsQ0FBQyxJQUFJLEVBQUUsQ0FDN0UsQ0FBQztRQUNGLE9BQU8sQ0FBQyxJQUFJLENBQUMsV0FBVyxDQUFDLENBQUM7UUFDMUIsTUFBTSxXQUFXLEdBQUcsTUFBTSxJQUFJLENBQUMsVUFBVSxDQUFDLFFBQVEsQ0FDaEQsZ0JBQWdCLEVBQ2hCLG9DQUF3QixFQUN4QjtZQUNFLFdBQVcsRUFBRSwwQ0FBOEI7WUFDM0MsWUFBWSxFQUFFLElBQUk7U0FDbkIsQ0FDRixDQUFDO1FBQ0YsT0FBTyxDQUFDLE9BQU8sQ0FBQyxXQUFXLENBQUMsQ0FBQztRQUU3QixJQUFJLFdBQVcsQ0FBQyxLQUFLLEVBQUUsQ0FBQztZQUN0QixPQUFPLENBQUMsR0FBRyxDQUNULElBQUksSUFBSSxDQUFDLFNBQVMsc0JBQXNCLElBQUksQ0FBQyxTQUFTLENBQUMsV0FBVyxDQUFDLEtBQUssQ0FBQyxFQUFFLENBQzVFLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxDQUFDLFdBQVcsQ0FBQyxPQUFPLElBQUksQ0FBQyxXQUFXLENBQUMsT0FBTyxFQUFFLENBQUM7WUFDakQsT0FBTyxDQUFDLEtBQUssQ0FDWCxJQUFJLElBQUksQ0FBQyxTQUFTLG9EQUFvRCxXQUFXLENBQUMsS0FBSyxFQUFFLENBQzFGLENBQUM7WUFDRixPQUFPO2dCQUNMLGNBQWMsRUFBRSxXQUFXLENBQUMsT0FBTyxJQUFJLFVBQVUsV0FBVyxDQUFDLEtBQUssRUFBRTthQUNyRSxDQUFDO1FBQ0osQ0FBQztRQUVELE1BQU0sY0FBYyxHQUFHLElBQUEseUJBQWEsRUFDbEMsV0FBVyxDQUFDLE9BQU8sRUFDbkIsSUFBSSxDQUFDLFNBQVMsRUFDZCxnQkFBZ0IsQ0FBQyxJQUFJLENBQ3RCLENBQUM7UUFFRixJQUFJLENBQUMsY0FBYyxFQUFFLENBQUM7WUFDcEIsT0FBTyxDQUFDLEtBQUssQ0FDWCxJQUFJLElBQUksQ0FBQyxTQUFTLDBEQUEwRCxXQUFXLENBQUMsT0FBTyxDQUFDLFNBQVMsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLEtBQUssQ0FDdkgsQ0FBQztZQUNGLE9BQU87Z0JBQ0wsY0FBYyxFQUFFLFdBQVcsQ0FBQyxPQUFPO2FBQ3BDLENBQUM7UUFDSixDQUFDO1FBRUQsT0FBTztZQUNMLG1CQUFtQixFQUFFLGNBQWMsQ0FBQyxtQkFBbUIsSUFBSSxFQUFFO1lBQzdELGNBQWMsRUFBRSxXQUFXLENBQUMsT0FBTztTQUNwQyxDQUFDO0lBQ0osQ0FBQztDQUNGO0FBN0ZELDRDQTZGQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIFN1YkFnZW50SW5wdXQsXG4gIFZpYmVIYWNraW5nQWdlbnRSZXNwb25zZSxcbiAgQWdlbnRMTE1TZXJ2aWNlLFxuICBERUZBVUxUX01PREVMX0ZPUl9BR0VOVFMsXG4gIERFRkFVTFRfVEVNUEVSQVRVUkVfQU5BTFlUSUNBTCxcbiAgc2FmZVBhcnNlSlNPTixcbn0gZnJvbSAnLi4vbmx1X2FnZW50cy9ubHVfdHlwZXMnO1xuaW1wb3J0IHsgU3RydWN0dXJlZExMTVByb21wdCB9IGZyb20gJy4uL2xpYi9sbG1VdGlscyc7XG5cbmV4cG9ydCBjbGFzcyBWaWJlSGFja2luZ0FnZW50IHtcbiAgcHJpdmF0ZSBsbG1TZXJ2aWNlOiBBZ2VudExMTVNlcnZpY2U7XG4gIHByaXZhdGUgYWdlbnROYW1lOiBzdHJpbmcgPSAnVmliZUhhY2tpbmdBZ2VudCc7XG5cbiAgY29uc3RydWN0b3IobGxtU2VydmljZTogQWdlbnRMTE1TZXJ2aWNlKSB7XG4gICAgdGhpcy5sbG1TZXJ2aWNlID0gbGxtU2VydmljZTtcbiAgfVxuXG4gIHByaXZhdGUgY29uc3RydWN0UHJvbXB0KGlucHV0OiBTdWJBZ2VudElucHV0KTogU3RydWN0dXJlZExMTVByb21wdCB7XG4gICAgY29uc3Qgc3lzdGVtTWVzc2FnZSA9IGBcbllvdSBhcmUgdGhlIFZpYmUgSGFja2luZyBBZ2VudC4gWW91ciByb2xlIGlzIHRvIHBlcmZvcm0gcmVkIHRlYW0gdGVzdGluZyBvbiB3ZWIgYXBwbGljYXRpb25zLlxuRm9jdXMgb246XG4xLiAgKipWdWxuZXJhYmlsaXR5IFNjYW5uaW5nKio6IFNjYW4gdGhlIHRhcmdldCBzeXN0ZW0gZm9yIHZ1bG5lcmFiaWxpdGllcy5cbjIuICAqKkV4cGxvaXRhdGlvbioqOiBBdHRlbXB0IHRvIGV4cGxvaXQgYW55IHZ1bG5lcmFiaWxpdGllcyB0aGF0IGFyZSBmb3VuZC5cbjMuICAqKlJlcG9ydGluZyoqOiBHZW5lcmF0ZSBhIHJlcG9ydCBvZiB0aGUgZmluZGluZ3MsIHdpdGggYSBkZXNjcmlwdGlvbiBvZiB0aGUgdnVsbmVyYWJpbGl0aWVzLCB0aGUgc3RlcHMgdGFrZW4gdG8gZXhwbG9pdCB0aGVtLCBhbmQgcmVjb21tZW5kYXRpb25zIGZvciByZW1lZGlhdGlvbi5cblxuUmV0dXJuIHlvdXIgYW5hbHlzaXMgT05MWSBhcyBhIHZhbGlkIEpTT04gb2JqZWN0IHdpdGggdGhlIGZvbGxvd2luZyBzdHJ1Y3R1cmU6XG57XG4gIFwidnVsbmVyYWJpbGl0eVJlcG9ydFwiOiBbeyBcInZ1bG5lcmFiaWxpdHlcIjogXCJUaGUgbmFtZSBvZiB0aGUgdnVsbmVyYWJpbGl0eS5cIiwgXCJzZXZlcml0eVwiOiBcIkNyaXRpY2FsXCIgfCBcIkhpZ2hcIiB8IFwiTWVkaXVtXCIgfCBcIkxvd1wiLCBcImRlc2NyaXB0aW9uXCI6IFwiQSBkZXNjcmlwdGlvbiBvZiB0aGUgdnVsbmVyYWJpbGl0eS5cIiwgXCJyZW1lZGlhdGlvblwiOiBcIlJlY29tbWVuZGF0aW9ucyBmb3IgcmVtZWRpYXRpbmcgdGhlIHZ1bG5lcmFiaWxpdHkuXCIgfV1cbn1cblxuRW5zdXJlIGFsbCBzcGVjaWZpZWQgZmllbGRzIGFyZSBwcmVzZW50IGluIHlvdXIgSlNPTiBvdXRwdXQuIElmIG5vIGl0ZW1zIGFwcGx5IGZvciBhIGxpc3QtYmFzZWQgZmllbGQgKGxpa2UgXCJ2dWxuZXJhYmlsaXR5UmVwb3J0XCIpLCByZXR1cm4gYW4gZW1wdHkgYXJyYXkgW10uXG5EbyBub3QgaW5jbHVkZSBhbnkgZXhwbGFuYXRpb25zLCBhcG9sb2dpZXMsIG9yIGNvbnZlcnNhdGlvbmFsIHRleHQgb3V0c2lkZSB0aGUgSlNPTiBzdHJ1Y3R1cmUuIFlvdXIgZW50aXJlIHJlc3BvbnNlIG11c3QgYmUgdGhlIEpTT04gb2JqZWN0IGl0c2VsZi5cblxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBjb250ZXh0IHdoZW4gZm9ybWluZyB5b3VyIHJlc3BvbnNlOlxuVXNlcidzIHF1ZXJ5OiBcIiR7aW5wdXQudXNlcklucHV0fVwiXG5Vc2VyIElEOiAke2lucHV0LnVzZXJJZCB8fCAnTi9BJ31cbmA7XG5cbiAgICByZXR1cm4ge1xuICAgICAgdGFzazogJ2N1c3RvbV92aWJlX2hhY2tpbmcnLFxuICAgICAgZGF0YToge1xuICAgICAgICBzeXN0ZW1fcHJvbXB0OiBzeXN0ZW1NZXNzYWdlLFxuICAgICAgICB1c2VyX3F1ZXJ5OiBpbnB1dC51c2VySW5wdXQsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICBwdWJsaWMgYXN5bmMgYW5hbHl6ZShcbiAgICBpbnB1dDogU3ViQWdlbnRJbnB1dFxuICApOiBQcm9taXNlPFZpYmVIYWNraW5nQWdlbnRSZXNwb25zZT4ge1xuICAgIGNvbnN0IHN0cnVjdHVyZWRQcm9tcHQgPSB0aGlzLmNvbnN0cnVjdFByb21wdChpbnB1dCk7XG4gICAgY29uc3QgVElNRVJfTEFCRUwgPSBgWyR7dGhpcy5hZ2VudE5hbWV9XSBMTE0gQ2FsbCBEdXJhdGlvbmA7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbJHt0aGlzLmFnZW50TmFtZX1dIENhbGxpbmcgTExNIHNlcnZpY2UgZm9yIHRhc2s6ICR7c3RydWN0dXJlZFByb21wdC50YXNrfWBcbiAgICApO1xuICAgIGNvbnNvbGUudGltZShUSU1FUl9MQUJFTCk7XG4gICAgY29uc3QgbGxtUmVzcG9uc2UgPSBhd2FpdCB0aGlzLmxsbVNlcnZpY2UuZ2VuZXJhdGUoXG4gICAgICBzdHJ1Y3R1cmVkUHJvbXB0LFxuICAgICAgREVGQVVMVF9NT0RFTF9GT1JfQUdFTlRTLFxuICAgICAge1xuICAgICAgICB0ZW1wZXJhdHVyZTogREVGQVVMVF9URU1QRVJBVFVSRV9BTkFMWVRJQ0FMLFxuICAgICAgICBpc0pzb25PdXRwdXQ6IHRydWUsXG4gICAgICB9XG4gICAgKTtcbiAgICBjb25zb2xlLnRpbWVFbmQoVElNRVJfTEFCRUwpO1xuXG4gICAgaWYgKGxsbVJlc3BvbnNlLnVzYWdlKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gTExNIFRva2VuIFVzYWdlOiAke0pTT04uc3RyaW5naWZ5KGxsbVJlc3BvbnNlLnVzYWdlKX1gXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmICghbGxtUmVzcG9uc2Uuc3VjY2VzcyB8fCAhbGxtUmVzcG9uc2UuY29udGVudCkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gTExNIGNhbGwgZmFpbGVkIG9yIHJldHVybmVkIG5vIGNvbnRlbnQuIEVycm9yOiAke2xsbVJlc3BvbnNlLmVycm9yfWBcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICByYXdMTE1SZXNwb25zZTogbGxtUmVzcG9uc2UuY29udGVudCB8fCBgRXJyb3I6ICR7bGxtUmVzcG9uc2UuZXJyb3J9YCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgcGFyc2VkUmVzcG9uc2UgPSBzYWZlUGFyc2VKU09OPFBhcnRpYWw8VmliZUhhY2tpbmdBZ2VudFJlc3BvbnNlPj4oXG4gICAgICBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgICAgdGhpcy5hZ2VudE5hbWUsXG4gICAgICBzdHJ1Y3R1cmVkUHJvbXB0LnRhc2tcbiAgICApO1xuXG4gICAgaWYgKCFwYXJzZWRSZXNwb25zZSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gRmFpbGVkIHRvIHBhcnNlIEpTT04gcmVzcG9uc2UgZnJvbSBMTE0uIFJhdyBjb250ZW50OiAke2xsbVJlc3BvbnNlLmNvbnRlbnQuc3Vic3RyaW5nKDAsIDIwMCl9Li4uYFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIHJhd0xMTVJlc3BvbnNlOiBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICByZXR1cm4ge1xuICAgICAgdnVsbmVyYWJpbGl0eVJlcG9ydDogcGFyc2VkUmVzcG9uc2UudnVsbmVyYWJpbGl0eVJlcG9ydCB8fCBbXSxcbiAgICAgIHJhd0xMTVJlc3BvbnNlOiBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgIH07XG4gIH1cbn1cbiJdfQ==