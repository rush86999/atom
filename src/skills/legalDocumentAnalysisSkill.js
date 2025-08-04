"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.LegalDocumentAnalysisAgent = void 0;
const nlu_types_1 = require("../nlu_agents/nlu_types");
class LegalDocumentAnalysisAgent {
    llmService;
    agentName = 'LegalDocumentAnalysisAgent';
    constructor(llmService) {
        this.llmService = llmService;
    }
    constructPrompt(input) {
        const systemMessage = `
You are the Legal Document Analysis Agent. Your role is to analyze legal documents and provide insights.
Focus on:
1.  **Risk Analysis**: Identify and analyze potential risks in legal documents.
2.  **Clause Identification**: Identify and extract key clauses from legal documents.
3.  **Sentiment Analysis**: Analyze the sentiment of legal documents.

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "riskAnalysis": [{ "clause": "The clause that contains the risk.", "riskLevel": "High" | "Medium" | "Low", "explanation": "An explanation of the risk." }],
  "summary": "A summary of the legal document."
}

Ensure all specified fields are present in your JSON output. If no items apply for a list-based field (like "riskAnalysis"), return an empty array [].
Do not include any explanations, apologies, or conversational text outside the JSON structure. Your entire response must be the JSON object itself.

Consider the following context when forming your response:
User's query: "${input.userInput}"
User ID: ${input.userId || 'N/A'}
`;
        return {
            task: 'custom_legal_document_analysis',
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
            riskAnalysis: parsedResponse.riskAnalysis || [],
            summary: parsedResponse.summary,
            rawLLMResponse: llmResponse.content,
        };
    }
}
exports.LegalDocumentAnalysisAgent = LegalDocumentAnalysisAgent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGVnYWxEb2N1bWVudEFuYWx5c2lzU2tpbGwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsZWdhbERvY3VtZW50QW5hbHlzaXNTa2lsbC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFBQSx1REFPaUM7QUFHakMsTUFBYSwwQkFBMEI7SUFDN0IsVUFBVSxDQUFrQjtJQUM1QixTQUFTLEdBQVcsNEJBQTRCLENBQUM7SUFFekQsWUFBWSxVQUEyQjtRQUNyQyxJQUFJLENBQUMsVUFBVSxHQUFHLFVBQVUsQ0FBQztJQUMvQixDQUFDO0lBRU8sZUFBZSxDQUFDLEtBQW9CO1FBQzFDLE1BQU0sYUFBYSxHQUFHOzs7Ozs7Ozs7Ozs7Ozs7OztpQkFpQlQsS0FBSyxDQUFDLFNBQVM7V0FDckIsS0FBSyxDQUFDLE1BQU0sSUFBSSxLQUFLO0NBQy9CLENBQUM7UUFFRSxPQUFPO1lBQ0wsSUFBSSxFQUFFLGdDQUFnQztZQUN0QyxJQUFJLEVBQUU7Z0JBQ0osYUFBYSxFQUFFLGFBQWE7Z0JBQzVCLFVBQVUsRUFBRSxLQUFLLENBQUMsU0FBUzthQUM1QjtTQUNGLENBQUM7SUFDSixDQUFDO0lBRU0sS0FBSyxDQUFDLE9BQU8sQ0FDbEIsS0FBb0I7UUFFcEIsTUFBTSxnQkFBZ0IsR0FBRyxJQUFJLENBQUMsZUFBZSxDQUFDLEtBQUssQ0FBQyxDQUFDO1FBQ3JELE1BQU0sV0FBVyxHQUFHLElBQUksSUFBSSxDQUFDLFNBQVMscUJBQXFCLENBQUM7UUFFNUQsT0FBTyxDQUFDLEdBQUcsQ0FDVCxJQUFJLElBQUksQ0FBQyxTQUFTLG1DQUFtQyxnQkFBZ0IsQ0FBQyxJQUFJLEVBQUUsQ0FDN0UsQ0FBQztRQUNGLE9BQU8sQ0FBQyxJQUFJLENBQUMsV0FBVyxDQUFDLENBQUM7UUFDMUIsTUFBTSxXQUFXLEdBQUcsTUFBTSxJQUFJLENBQUMsVUFBVSxDQUFDLFFBQVEsQ0FDaEQsZ0JBQWdCLEVBQ2hCLG9DQUF3QixFQUN4QjtZQUNFLFdBQVcsRUFBRSwwQ0FBOEI7WUFDM0MsWUFBWSxFQUFFLElBQUk7U0FDbkIsQ0FDRixDQUFDO1FBQ0YsT0FBTyxDQUFDLE9BQU8sQ0FBQyxXQUFXLENBQUMsQ0FBQztRQUU3QixJQUFJLFdBQVcsQ0FBQyxLQUFLLEVBQUUsQ0FBQztZQUN0QixPQUFPLENBQUMsR0FBRyxDQUNULElBQUksSUFBSSxDQUFDLFNBQVMsc0JBQXNCLElBQUksQ0FBQyxTQUFTLENBQUMsV0FBVyxDQUFDLEtBQUssQ0FBQyxFQUFFLENBQzVFLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxDQUFDLFdBQVcsQ0FBQyxPQUFPLElBQUksQ0FBQyxXQUFXLENBQUMsT0FBTyxFQUFFLENBQUM7WUFDakQsT0FBTyxDQUFDLEtBQUssQ0FDWCxJQUFJLElBQUksQ0FBQyxTQUFTLG9EQUFvRCxXQUFXLENBQUMsS0FBSyxFQUFFLENBQzFGLENBQUM7WUFDRixPQUFPO2dCQUNMLGNBQWMsRUFBRSxXQUFXLENBQUMsT0FBTyxJQUFJLFVBQVUsV0FBVyxDQUFDLEtBQUssRUFBRTthQUNyRSxDQUFDO1FBQ0osQ0FBQztRQUVELE1BQU0sY0FBYyxHQUFHLElBQUEseUJBQWEsRUFFbEMsV0FBVyxDQUFDLE9BQU8sRUFBRSxJQUFJLENBQUMsU0FBUyxFQUFFLGdCQUFnQixDQUFDLElBQUksQ0FBQyxDQUFDO1FBRTlELElBQUksQ0FBQyxjQUFjLEVBQUUsQ0FBQztZQUNwQixPQUFPLENBQUMsS0FBSyxDQUNYLElBQUksSUFBSSxDQUFDLFNBQVMsMERBQTBELFdBQVcsQ0FBQyxPQUFPLENBQUMsU0FBUyxDQUFDLENBQUMsRUFBRSxHQUFHLENBQUMsS0FBSyxDQUN2SCxDQUFDO1lBQ0YsT0FBTztnQkFDTCxjQUFjLEVBQUUsV0FBVyxDQUFDLE9BQU87YUFDcEMsQ0FBQztRQUNKLENBQUM7UUFFRCxPQUFPO1lBQ0wsWUFBWSxFQUFFLGNBQWMsQ0FBQyxZQUFZLElBQUksRUFBRTtZQUMvQyxPQUFPLEVBQUUsY0FBYyxDQUFDLE9BQU87WUFDL0IsY0FBYyxFQUFFLFdBQVcsQ0FBQyxPQUFPO1NBQ3BDLENBQUM7SUFDSixDQUFDO0NBQ0Y7QUE3RkQsZ0VBNkZDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgU3ViQWdlbnRJbnB1dCxcbiAgTGVnYWxEb2N1bWVudEFuYWx5c2lzQWdlbnRSZXNwb25zZSxcbiAgQWdlbnRMTE1TZXJ2aWNlLFxuICBERUZBVUxUX01PREVMX0ZPUl9BR0VOVFMsXG4gIERFRkFVTFRfVEVNUEVSQVRVUkVfQU5BTFlUSUNBTCxcbiAgc2FmZVBhcnNlSlNPTixcbn0gZnJvbSAnLi4vbmx1X2FnZW50cy9ubHVfdHlwZXMnO1xuaW1wb3J0IHsgU3RydWN0dXJlZExMTVByb21wdCB9IGZyb20gJy4uL2xpYi9sbG1VdGlscyc7XG5cbmV4cG9ydCBjbGFzcyBMZWdhbERvY3VtZW50QW5hbHlzaXNBZ2VudCB7XG4gIHByaXZhdGUgbGxtU2VydmljZTogQWdlbnRMTE1TZXJ2aWNlO1xuICBwcml2YXRlIGFnZW50TmFtZTogc3RyaW5nID0gJ0xlZ2FsRG9jdW1lbnRBbmFseXNpc0FnZW50JztcblxuICBjb25zdHJ1Y3RvcihsbG1TZXJ2aWNlOiBBZ2VudExMTVNlcnZpY2UpIHtcbiAgICB0aGlzLmxsbVNlcnZpY2UgPSBsbG1TZXJ2aWNlO1xuICB9XG5cbiAgcHJpdmF0ZSBjb25zdHJ1Y3RQcm9tcHQoaW5wdXQ6IFN1YkFnZW50SW5wdXQpOiBTdHJ1Y3R1cmVkTExNUHJvbXB0IHtcbiAgICBjb25zdCBzeXN0ZW1NZXNzYWdlID0gYFxuWW91IGFyZSB0aGUgTGVnYWwgRG9jdW1lbnQgQW5hbHlzaXMgQWdlbnQuIFlvdXIgcm9sZSBpcyB0byBhbmFseXplIGxlZ2FsIGRvY3VtZW50cyBhbmQgcHJvdmlkZSBpbnNpZ2h0cy5cbkZvY3VzIG9uOlxuMS4gICoqUmlzayBBbmFseXNpcyoqOiBJZGVudGlmeSBhbmQgYW5hbHl6ZSBwb3RlbnRpYWwgcmlza3MgaW4gbGVnYWwgZG9jdW1lbnRzLlxuMi4gICoqQ2xhdXNlIElkZW50aWZpY2F0aW9uKio6IElkZW50aWZ5IGFuZCBleHRyYWN0IGtleSBjbGF1c2VzIGZyb20gbGVnYWwgZG9jdW1lbnRzLlxuMy4gICoqU2VudGltZW50IEFuYWx5c2lzKio6IEFuYWx5emUgdGhlIHNlbnRpbWVudCBvZiBsZWdhbCBkb2N1bWVudHMuXG5cblJldHVybiB5b3VyIGFuYWx5c2lzIE9OTFkgYXMgYSB2YWxpZCBKU09OIG9iamVjdCB3aXRoIHRoZSBmb2xsb3dpbmcgc3RydWN0dXJlOlxue1xuICBcInJpc2tBbmFseXNpc1wiOiBbeyBcImNsYXVzZVwiOiBcIlRoZSBjbGF1c2UgdGhhdCBjb250YWlucyB0aGUgcmlzay5cIiwgXCJyaXNrTGV2ZWxcIjogXCJIaWdoXCIgfCBcIk1lZGl1bVwiIHwgXCJMb3dcIiwgXCJleHBsYW5hdGlvblwiOiBcIkFuIGV4cGxhbmF0aW9uIG9mIHRoZSByaXNrLlwiIH1dLFxuICBcInN1bW1hcnlcIjogXCJBIHN1bW1hcnkgb2YgdGhlIGxlZ2FsIGRvY3VtZW50LlwiXG59XG5cbkVuc3VyZSBhbGwgc3BlY2lmaWVkIGZpZWxkcyBhcmUgcHJlc2VudCBpbiB5b3VyIEpTT04gb3V0cHV0LiBJZiBubyBpdGVtcyBhcHBseSBmb3IgYSBsaXN0LWJhc2VkIGZpZWxkIChsaWtlIFwicmlza0FuYWx5c2lzXCIpLCByZXR1cm4gYW4gZW1wdHkgYXJyYXkgW10uXG5EbyBub3QgaW5jbHVkZSBhbnkgZXhwbGFuYXRpb25zLCBhcG9sb2dpZXMsIG9yIGNvbnZlcnNhdGlvbmFsIHRleHQgb3V0c2lkZSB0aGUgSlNPTiBzdHJ1Y3R1cmUuIFlvdXIgZW50aXJlIHJlc3BvbnNlIG11c3QgYmUgdGhlIEpTT04gb2JqZWN0IGl0c2VsZi5cblxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBjb250ZXh0IHdoZW4gZm9ybWluZyB5b3VyIHJlc3BvbnNlOlxuVXNlcidzIHF1ZXJ5OiBcIiR7aW5wdXQudXNlcklucHV0fVwiXG5Vc2VyIElEOiAke2lucHV0LnVzZXJJZCB8fCAnTi9BJ31cbmA7XG5cbiAgICByZXR1cm4ge1xuICAgICAgdGFzazogJ2N1c3RvbV9sZWdhbF9kb2N1bWVudF9hbmFseXNpcycsXG4gICAgICBkYXRhOiB7XG4gICAgICAgIHN5c3RlbV9wcm9tcHQ6IHN5c3RlbU1lc3NhZ2UsXG4gICAgICAgIHVzZXJfcXVlcnk6IGlucHV0LnVzZXJJbnB1dCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIHB1YmxpYyBhc3luYyBhbmFseXplKFxuICAgIGlucHV0OiBTdWJBZ2VudElucHV0XG4gICk6IFByb21pc2U8TGVnYWxEb2N1bWVudEFuYWx5c2lzQWdlbnRSZXNwb25zZT4ge1xuICAgIGNvbnN0IHN0cnVjdHVyZWRQcm9tcHQgPSB0aGlzLmNvbnN0cnVjdFByb21wdChpbnB1dCk7XG4gICAgY29uc3QgVElNRVJfTEFCRUwgPSBgWyR7dGhpcy5hZ2VudE5hbWV9XSBMTE0gQ2FsbCBEdXJhdGlvbmA7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbJHt0aGlzLmFnZW50TmFtZX1dIENhbGxpbmcgTExNIHNlcnZpY2UgZm9yIHRhc2s6ICR7c3RydWN0dXJlZFByb21wdC50YXNrfWBcbiAgICApO1xuICAgIGNvbnNvbGUudGltZShUSU1FUl9MQUJFTCk7XG4gICAgY29uc3QgbGxtUmVzcG9uc2UgPSBhd2FpdCB0aGlzLmxsbVNlcnZpY2UuZ2VuZXJhdGUoXG4gICAgICBzdHJ1Y3R1cmVkUHJvbXB0LFxuICAgICAgREVGQVVMVF9NT0RFTF9GT1JfQUdFTlRTLFxuICAgICAge1xuICAgICAgICB0ZW1wZXJhdHVyZTogREVGQVVMVF9URU1QRVJBVFVSRV9BTkFMWVRJQ0FMLFxuICAgICAgICBpc0pzb25PdXRwdXQ6IHRydWUsXG4gICAgICB9XG4gICAgKTtcbiAgICBjb25zb2xlLnRpbWVFbmQoVElNRVJfTEFCRUwpO1xuXG4gICAgaWYgKGxsbVJlc3BvbnNlLnVzYWdlKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gTExNIFRva2VuIFVzYWdlOiAke0pTT04uc3RyaW5naWZ5KGxsbVJlc3BvbnNlLnVzYWdlKX1gXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmICghbGxtUmVzcG9uc2Uuc3VjY2VzcyB8fCAhbGxtUmVzcG9uc2UuY29udGVudCkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gTExNIGNhbGwgZmFpbGVkIG9yIHJldHVybmVkIG5vIGNvbnRlbnQuIEVycm9yOiAke2xsbVJlc3BvbnNlLmVycm9yfWBcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICByYXdMTE1SZXNwb25zZTogbGxtUmVzcG9uc2UuY29udGVudCB8fCBgRXJyb3I6ICR7bGxtUmVzcG9uc2UuZXJyb3J9YCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgcGFyc2VkUmVzcG9uc2UgPSBzYWZlUGFyc2VKU09OPFxuICAgICAgUGFydGlhbDxMZWdhbERvY3VtZW50QW5hbHlzaXNBZ2VudFJlc3BvbnNlPlxuICAgID4obGxtUmVzcG9uc2UuY29udGVudCwgdGhpcy5hZ2VudE5hbWUsIHN0cnVjdHVyZWRQcm9tcHQudGFzayk7XG5cbiAgICBpZiAoIXBhcnNlZFJlc3BvbnNlKSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICBgWyR7dGhpcy5hZ2VudE5hbWV9XSBGYWlsZWQgdG8gcGFyc2UgSlNPTiByZXNwb25zZSBmcm9tIExMTS4gUmF3IGNvbnRlbnQ6ICR7bGxtUmVzcG9uc2UuY29udGVudC5zdWJzdHJpbmcoMCwgMjAwKX0uLi5gXG4gICAgICApO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgcmF3TExNUmVzcG9uc2U6IGxsbVJlc3BvbnNlLmNvbnRlbnQsXG4gICAgICB9O1xuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICByaXNrQW5hbHlzaXM6IHBhcnNlZFJlc3BvbnNlLnJpc2tBbmFseXNpcyB8fCBbXSxcbiAgICAgIHN1bW1hcnk6IHBhcnNlZFJlc3BvbnNlLnN1bW1hcnksXG4gICAgICByYXdMTE1SZXNwb25zZTogbGxtUmVzcG9uc2UuY29udGVudCxcbiAgICB9O1xuICB9XG59XG4iXX0=