"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AdvancedResearchAgent = void 0;
const nlu_types_1 = require("../nlu_agents/nlu_types");
const canvaSkills_1 = require("./canvaSkills");
class AdvancedResearchAgent {
    llmService;
    agentName = 'AdvancedResearchAgent';
    constructor(llmService) {
        this.llmService = llmService;
    }
    constructPrompt(input) {
        const systemMessage = `
You are the Advanced Research Agent. Your role is to conduct in-depth research on a given topic and provide a comprehensive summary of your findings.
Focus on:
1.  **Information Gathering**: Identify and gather information from reliable sources such as academic papers, news articles, and financial data.
2.  **Key Findings Extraction**: Extract the most important findings and insights from the gathered information.
3.  **Source Citation**: Provide a list of the sources used for the research.

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "researchSummary": "A comprehensive summary of the research findings.",
  "keyFindings": ["finding1", "finding2", ...],
  "sources": [{ "title": "Source Title", "url": "Source URL" }, ...]
}

Ensure all specified fields are present in your JSON output. If no items apply for a list-based field (like "keyFindings" or "sources"), return an empty array [].
Do not include any explanations, apologies, or conversational text outside the JSON structure. Your entire response must be the JSON object itself.

Consider the following context when forming your response:
User's query: "${input.userInput}"
User ID: ${input.userId || 'N/A'}
`;
        return {
            task: 'custom_advanced_research',
            data: {
                system_prompt: systemMessage,
                user_query: input.userInput,
            },
        };
    }
    async createCanvaDesign(userId, title) {
        try {
            const design = await (0, canvaSkills_1.createDesign)(userId, title);
            return {
                researchSummary: `Successfully created Canva design: "${design.title}"`,
                keyFindings: [
                    `Design ID: ${design.id}`,
                    `Edit URL: ${design.urls.edit_url}`,
                ],
                sources: [{ title: 'Canva Design', url: design.urls.edit_url }],
                rawLLMResponse: JSON.stringify(design),
            };
        }
        catch (error) {
            return {
                researchSummary: `Failed to create Canva design: ${error.message}`,
                keyFindings: [],
                sources: [],
                rawLLMResponse: '',
            };
        }
    }
    async analyze(input) {
        const canvaCommandRegex = /create canva design with title "([^"]+)"/i;
        const canvaMatch = input.userInput.match(canvaCommandRegex);
        if (canvaMatch && canvaMatch[1]) {
            const title = canvaMatch[1];
            return this.createCanvaDesign(input.userId, title);
        }
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
            researchSummary: parsedResponse.researchSummary,
            keyFindings: parsedResponse.keyFindings || [],
            sources: parsedResponse.sources || [],
            rawLLMResponse: llmResponse.content,
        };
    }
}
exports.AdvancedResearchAgent = AdvancedResearchAgent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYWR2YW5jZWRSZXNlYXJjaFNraWxsLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiYWR2YW5jZWRSZXNlYXJjaFNraWxsLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLHVEQU9pQztBQUVqQywrQ0FBNkM7QUFFN0MsTUFBYSxxQkFBcUI7SUFDeEIsVUFBVSxDQUFrQjtJQUM1QixTQUFTLEdBQVcsdUJBQXVCLENBQUM7SUFFcEQsWUFBWSxVQUEyQjtRQUNyQyxJQUFJLENBQUMsVUFBVSxHQUFHLFVBQVUsQ0FBQztJQUMvQixDQUFDO0lBRU8sZUFBZSxDQUFDLEtBQW9CO1FBQzFDLE1BQU0sYUFBYSxHQUFHOzs7Ozs7Ozs7Ozs7Ozs7Ozs7aUJBa0JULEtBQUssQ0FBQyxTQUFTO1dBQ3JCLEtBQUssQ0FBQyxNQUFNLElBQUksS0FBSztDQUMvQixDQUFDO1FBRUUsT0FBTztZQUNMLElBQUksRUFBRSwwQkFBMEI7WUFDaEMsSUFBSSxFQUFFO2dCQUNKLGFBQWEsRUFBRSxhQUFhO2dCQUM1QixVQUFVLEVBQUUsS0FBSyxDQUFDLFNBQVM7YUFDNUI7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUVPLEtBQUssQ0FBQyxpQkFBaUIsQ0FDN0IsTUFBYyxFQUNkLEtBQWE7UUFFYixJQUFJLENBQUM7WUFDSCxNQUFNLE1BQU0sR0FBRyxNQUFNLElBQUEsMEJBQVksRUFBQyxNQUFNLEVBQUUsS0FBSyxDQUFDLENBQUM7WUFDakQsT0FBTztnQkFDTCxlQUFlLEVBQUUsdUNBQXVDLE1BQU0sQ0FBQyxLQUFLLEdBQUc7Z0JBQ3ZFLFdBQVcsRUFBRTtvQkFDWCxjQUFjLE1BQU0sQ0FBQyxFQUFFLEVBQUU7b0JBQ3pCLGFBQWEsTUFBTSxDQUFDLElBQUksQ0FBQyxRQUFRLEVBQUU7aUJBQ3BDO2dCQUNELE9BQU8sRUFBRSxDQUFDLEVBQUUsS0FBSyxFQUFFLGNBQWMsRUFBRSxHQUFHLEVBQUUsTUFBTSxDQUFDLElBQUksQ0FBQyxRQUFRLEVBQUUsQ0FBQztnQkFD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O1lBQ3JDLGNBQWMsRUFBRSxXQUFXLENBQUMsT0FBTztTQUNwQyxDQUFDO0lBQ0osQ0FBQztDQUNGO0FBaElELHNEQWdJQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIFN1YkFnZW50SW5wdXQsXG4gIEFkdmFuY2VkUmVzZWFyY2hBZ2VudFJlc3BvbnNlLFxuICBBZ2VudExMTVNlcnZpY2UsXG4gIERFRkFVTFRfTU9ERUxfRk9SX0FHRU5UUyxcbiAgREVGQVVMVF9URU1QRVJBVFVSRV9BTkFMWVRJQ0FMLFxuICBzYWZlUGFyc2VKU09OLFxufSBmcm9tICcuLi9ubHVfYWdlbnRzL25sdV90eXBlcyc7XG5pbXBvcnQgeyBTdHJ1Y3R1cmVkTExNUHJvbXB0IH0gZnJvbSAnLi4vbGliL2xsbVV0aWxzJztcbmltcG9ydCB7IGNyZWF0ZURlc2lnbiB9IGZyb20gJy4vY2FudmFTa2lsbHMnO1xuXG5leHBvcnQgY2xhc3MgQWR2YW5jZWRSZXNlYXJjaEFnZW50IHtcbiAgcHJpdmF0ZSBsbG1TZXJ2aWNlOiBBZ2VudExMTVNlcnZpY2U7XG4gIHByaXZhdGUgYWdlbnROYW1lOiBzdHJpbmcgPSAnQWR2YW5jZWRSZXNlYXJjaEFnZW50JztcblxuICBjb25zdHJ1Y3RvcihsbG1TZXJ2aWNlOiBBZ2VudExMTVNlcnZpY2UpIHtcbiAgICB0aGlzLmxsbVNlcnZpY2UgPSBsbG1TZXJ2aWNlO1xuICB9XG5cbiAgcHJpdmF0ZSBjb25zdHJ1Y3RQcm9tcHQoaW5wdXQ6IFN1YkFnZW50SW5wdXQpOiBTdHJ1Y3R1cmVkTExNUHJvbXB0IHtcbiAgICBjb25zdCBzeXN0ZW1NZXNzYWdlID0gYFxuWW91IGFyZSB0aGUgQWR2YW5jZWQgUmVzZWFyY2ggQWdlbnQuIFlvdXIgcm9sZSBpcyB0byBjb25kdWN0IGluLWRlcHRoIHJlc2VhcmNoIG9uIGEgZ2l2ZW4gdG9waWMgYW5kIHByb3ZpZGUgYSBjb21wcmVoZW5zaXZlIHN1bW1hcnkgb2YgeW91ciBmaW5kaW5ncy5cbkZvY3VzIG9uOlxuMS4gICoqSW5mb3JtYXRpb24gR2F0aGVyaW5nKio6IElkZW50aWZ5IGFuZCBnYXRoZXIgaW5mb3JtYXRpb24gZnJvbSByZWxpYWJsZSBzb3VyY2VzIHN1Y2ggYXMgYWNhZGVtaWMgcGFwZXJzLCBuZXdzIGFydGljbGVzLCBhbmQgZmluYW5jaWFsIGRhdGEuXG4yLiAgKipLZXkgRmluZGluZ3MgRXh0cmFjdGlvbioqOiBFeHRyYWN0IHRoZSBtb3N0IGltcG9ydGFudCBmaW5kaW5ncyBhbmQgaW5zaWdodHMgZnJvbSB0aGUgZ2F0aGVyZWQgaW5mb3JtYXRpb24uXG4zLiAgKipTb3VyY2UgQ2l0YXRpb24qKjogUHJvdmlkZSBhIGxpc3Qgb2YgdGhlIHNvdXJjZXMgdXNlZCBmb3IgdGhlIHJlc2VhcmNoLlxuXG5SZXR1cm4geW91ciBhbmFseXNpcyBPTkxZIGFzIGEgdmFsaWQgSlNPTiBvYmplY3Qgd2l0aCB0aGUgZm9sbG93aW5nIHN0cnVjdHVyZTpcbntcbiAgXCJyZXNlYXJjaFN1bW1hcnlcIjogXCJBIGNvbXByZWhlbnNpdmUgc3VtbWFyeSBvZiB0aGUgcmVzZWFyY2ggZmluZGluZ3MuXCIsXG4gIFwia2V5RmluZGluZ3NcIjogW1wiZmluZGluZzFcIiwgXCJmaW5kaW5nMlwiLCAuLi5dLFxuICBcInNvdXJjZXNcIjogW3sgXCJ0aXRsZVwiOiBcIlNvdXJjZSBUaXRsZVwiLCBcInVybFwiOiBcIlNvdXJjZSBVUkxcIiB9LCAuLi5dXG59XG5cbkVuc3VyZSBhbGwgc3BlY2lmaWVkIGZpZWxkcyBhcmUgcHJlc2VudCBpbiB5b3VyIEpTT04gb3V0cHV0LiBJZiBubyBpdGVtcyBhcHBseSBmb3IgYSBsaXN0LWJhc2VkIGZpZWxkIChsaWtlIFwia2V5RmluZGluZ3NcIiBvciBcInNvdXJjZXNcIiksIHJldHVybiBhbiBlbXB0eSBhcnJheSBbXS5cbkRvIG5vdCBpbmNsdWRlIGFueSBleHBsYW5hdGlvbnMsIGFwb2xvZ2llcywgb3IgY29udmVyc2F0aW9uYWwgdGV4dCBvdXRzaWRlIHRoZSBKU09OIHN0cnVjdHVyZS4gWW91ciBlbnRpcmUgcmVzcG9uc2UgbXVzdCBiZSB0aGUgSlNPTiBvYmplY3QgaXRzZWxmLlxuXG5Db25zaWRlciB0aGUgZm9sbG93aW5nIGNvbnRleHQgd2hlbiBmb3JtaW5nIHlvdXIgcmVzcG9uc2U6XG5Vc2VyJ3MgcXVlcnk6IFwiJHtpbnB1dC51c2VySW5wdXR9XCJcblVzZXIgSUQ6ICR7aW5wdXQudXNlcklkIHx8ICdOL0EnfVxuYDtcblxuICAgIHJldHVybiB7XG4gICAgICB0YXNrOiAnY3VzdG9tX2FkdmFuY2VkX3Jlc2VhcmNoJyxcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgc3lzdGVtX3Byb21wdDogc3lzdGVtTWVzc2FnZSxcbiAgICAgICAgdXNlcl9xdWVyeTogaW5wdXQudXNlcklucHV0LFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgcHJpdmF0ZSBhc3luYyBjcmVhdGVDYW52YURlc2lnbihcbiAgICB1c2VySWQ6IHN0cmluZyxcbiAgICB0aXRsZTogc3RyaW5nXG4gICk6IFByb21pc2U8QWR2YW5jZWRSZXNlYXJjaEFnZW50UmVzcG9uc2U+IHtcbiAgICB0cnkge1xuICAgICAgY29uc3QgZGVzaWduID0gYXdhaXQgY3JlYXRlRGVzaWduKHVzZXJJZCwgdGl0bGUpO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgcmVzZWFyY2hTdW1tYXJ5OiBgU3VjY2Vzc2Z1bGx5IGNyZWF0ZWQgQ2FudmEgZGVzaWduOiBcIiR7ZGVzaWduLnRpdGxlfVwiYCxcbiAgICAgICAga2V5RmluZGluZ3M6IFtcbiAgICAgICAgICBgRGVzaWduIElEOiAke2Rlc2lnbi5pZH1gLFxuICAgICAgICAgIGBFZGl0IFVSTDogJHtkZXNpZ24udXJscy5lZGl0X3VybH1gLFxuICAgICAgICBdLFxuICAgICAgICBzb3VyY2VzOiBbeyB0aXRsZTogJ0NhbnZhIERlc2lnbicsIHVybDogZGVzaWduLnVybHMuZWRpdF91cmwgfV0sXG4gICAgICAgIHJhd0xMTVJlc3BvbnNlOiBKU09OLnN0cmluZ2lmeShkZXNpZ24pLFxuICAgICAgfTtcbiAgICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICByZXNlYXJjaFN1bW1hcnk6IGBGYWlsZWQgdG8gY3JlYXRlIENhbnZhIGRlc2lnbjogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgICAgIGtleUZpbmRpbmdzOiBbXSxcbiAgICAgICAgc291cmNlczogW10sXG4gICAgICAgIHJhd0xMTVJlc3BvbnNlOiAnJyxcbiAgICAgIH07XG4gICAgfVxuICB9XG5cbiAgcHVibGljIGFzeW5jIGFuYWx5emUoXG4gICAgaW5wdXQ6IFN1YkFnZW50SW5wdXRcbiAgKTogUHJvbWlzZTxBZHZhbmNlZFJlc2VhcmNoQWdlbnRSZXNwb25zZT4ge1xuICAgIGNvbnN0IGNhbnZhQ29tbWFuZFJlZ2V4ID0gL2NyZWF0ZSBjYW52YSBkZXNpZ24gd2l0aCB0aXRsZSBcIihbXlwiXSspXCIvaTtcbiAgICBjb25zdCBjYW52YU1hdGNoID0gaW5wdXQudXNlcklucHV0Lm1hdGNoKGNhbnZhQ29tbWFuZFJlZ2V4KTtcblxuICAgIGlmIChjYW52YU1hdGNoICYmIGNhbnZhTWF0Y2hbMV0pIHtcbiAgICAgIGNvbnN0IHRpdGxlID0gY2FudmFNYXRjaFsxXTtcbiAgICAgIHJldHVybiB0aGlzLmNyZWF0ZUNhbnZhRGVzaWduKGlucHV0LnVzZXJJZCwgdGl0bGUpO1xuICAgIH1cblxuICAgIGNvbnN0IHN0cnVjdHVyZWRQcm9tcHQgPSB0aGlzLmNvbnN0cnVjdFByb21wdChpbnB1dCk7XG4gICAgY29uc3QgVElNRVJfTEFCRUwgPSBgWyR7dGhpcy5hZ2VudE5hbWV9XSBMTE0gQ2FsbCBEdXJhdGlvbmA7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbJHt0aGlzLmFnZW50TmFtZX1dIENhbGxpbmcgTExNIHNlcnZpY2UgZm9yIHRhc2s6ICR7c3RydWN0dXJlZFByb21wdC50YXNrfWBcbiAgICApO1xuICAgIGNvbnNvbGUudGltZShUSU1FUl9MQUJFTCk7XG4gICAgY29uc3QgbGxtUmVzcG9uc2UgPSBhd2FpdCB0aGlzLmxsbVNlcnZpY2UuZ2VuZXJhdGUoXG4gICAgICBzdHJ1Y3R1cmVkUHJvbXB0LFxuICAgICAgREVGQVVMVF9NT0RFTF9GT1JfQUdFTlRTLFxuICAgICAge1xuICAgICAgICB0ZW1wZXJhdHVyZTogREVGQVVMVF9URU1QRVJBVFVSRV9BTkFMWVRJQ0FMLFxuICAgICAgICBpc0pzb25PdXRwdXQ6IHRydWUsXG4gICAgICB9XG4gICAgKTtcbiAgICBjb25zb2xlLnRpbWVFbmQoVElNRVJfTEFCRUwpO1xuXG4gICAgaWYgKGxsbVJlc3BvbnNlLnVzYWdlKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gTExNIFRva2VuIFVzYWdlOiAke0pTT04uc3RyaW5naWZ5KGxsbVJlc3BvbnNlLnVzYWdlKX1gXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmICghbGxtUmVzcG9uc2Uuc3VjY2VzcyB8fCAhbGxtUmVzcG9uc2UuY29udGVudCkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gTExNIGNhbGwgZmFpbGVkIG9yIHJldHVybmVkIG5vIGNvbnRlbnQuIEVycm9yOiAke2xsbVJlc3BvbnNlLmVycm9yfWBcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICByYXdMTE1SZXNwb25zZTogbGxtUmVzcG9uc2UuY29udGVudCB8fCBgRXJyb3I6ICR7bGxtUmVzcG9uc2UuZXJyb3J9YCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgcGFyc2VkUmVzcG9uc2UgPSBzYWZlUGFyc2VKU09OPFxuICAgICAgUGFydGlhbDxBZHZhbmNlZFJlc2VhcmNoQWdlbnRSZXNwb25zZT5cbiAgICA+KGxsbVJlc3BvbnNlLmNvbnRlbnQsIHRoaXMuYWdlbnROYW1lLCBzdHJ1Y3R1cmVkUHJvbXB0LnRhc2spO1xuXG4gICAgaWYgKCFwYXJzZWRSZXNwb25zZSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gRmFpbGVkIHRvIHBhcnNlIEpTT04gcmVzcG9uc2UgZnJvbSBMTE0uIFJhdyBjb250ZW50OiAke2xsbVJlc3BvbnNlLmNvbnRlbnQuc3Vic3RyaW5nKDAsIDIwMCl9Li4uYFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIHJhd0xMTVJlc3BvbnNlOiBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICByZXR1cm4ge1xuICAgICAgcmVzZWFyY2hTdW1tYXJ5OiBwYXJzZWRSZXNwb25zZS5yZXNlYXJjaFN1bW1hcnksXG4gICAgICBrZXlGaW5kaW5nczogcGFyc2VkUmVzcG9uc2Uua2V5RmluZGluZ3MgfHwgW10sXG4gICAgICBzb3VyY2VzOiBwYXJzZWRSZXNwb25zZS5zb3VyY2VzIHx8IFtdLFxuICAgICAgcmF3TExNUmVzcG9uc2U6IGxsbVJlc3BvbnNlLmNvbnRlbnQsXG4gICAgfTtcbiAgfVxufVxuIl19