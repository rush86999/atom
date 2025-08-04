"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ContentCreationAgent = void 0;
const nlu_types_1 = require("../nlu_agents/nlu_types");
class ContentCreationAgent {
    llmService;
    agentName = 'ContentCreationAgent';
    constructor(llmService) {
        this.llmService = llmService;
    }
    constructPrompt(input) {
        const systemMessage = `
You are the Content Creation Agent. Your role is to help users create a wide range of content, such as blog posts, articles, presentations, and even code.
Focus on:
1.  **Content Generation**: Generate high-quality content based on the user's input.
2.  **Content Formatting**: Format the content appropriately for the specified content type.
3.  **Content Type Identification**: Identify the type of content the user wants to create.

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "generatedContent": "The generated content.",
  "contentType": "blog post" | "article" | "presentation" | "code"
}

Ensure all specified fields are present in your JSON output.
Do not include any explanations, apologies, or conversational text outside the JSON structure. Your entire response must be the JSON object itself.

Consider the following context when forming your response:
User's query: "${input.userInput}"
User ID: ${input.userId || 'N/A'}
`;
        return {
            task: 'custom_content_creation',
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
                contentType: 'code',
            };
        }
        const parsedResponse = (0, nlu_types_1.safeParseJSON)(llmResponse.content, this.agentName, structuredPrompt.task);
        if (!parsedResponse) {
            console.error(`[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`);
            return {
                rawLLMResponse: llmResponse.content,
                contentType: 'code',
            };
        }
        return {
            generatedContent: parsedResponse.generatedContent,
            contentType: parsedResponse.contentType,
            rawLLMResponse: llmResponse.content,
        };
    }
}
exports.ContentCreationAgent = ContentCreationAgent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY29udGVudENyZWF0aW9uU2tpbGwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjb250ZW50Q3JlYXRpb25Ta2lsbC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFBQSx1REFPaUM7QUFHakMsTUFBYSxvQkFBb0I7SUFDdkIsVUFBVSxDQUFrQjtJQUM1QixTQUFTLEdBQVcsc0JBQXNCLENBQUM7SUFFbkQsWUFBWSxVQUEyQjtRQUNyQyxJQUFJLENBQUMsVUFBVSxHQUFHLFVBQVUsQ0FBQztJQUMvQixDQUFDO0lBRU8sZUFBZSxDQUFDLEtBQW9CO1FBQzFDLE1BQU0sYUFBYSxHQUFHOzs7Ozs7Ozs7Ozs7Ozs7OztpQkFpQlQsS0FBSyxDQUFDLFNBQVM7V0FDckIsS0FBSyxDQUFDLE1BQU0sSUFBSSxLQUFLO0NBQy9CLENBQUM7UUFFRSxPQUFPO1lBQ0wsSUFBSSxFQUFFLHlCQUF5QjtZQUMvQixJQUFJLEVBQUU7Z0JBQ0osYUFBYSxFQUFFLGFBQWE7Z0JBQzVCLFVBQVUsRUFBRSxLQUFLLENBQUMsU0FBUzthQUM1QjtTQUNGLENBQUM7SUFDSixDQUFDO0lBRU0sS0FBSyxDQUFDLE9BQU8sQ0FDbEIsS0FBb0I7UUFFcEIsTUFBTSxnQkFBZ0IsR0FBRyxJQUFJLENBQUMsZUFBZSxDQUFDLEtBQUssQ0FBQyxDQUFDO1FBQ3JELE1BQU0sV0FBVyxHQUFHLElBQUksSUFBSSxDQUFDLFNBQVMscUJBQXFCLENBQUM7UUFFNUQsT0FBTyxDQUFDLEdBQUcsQ0FDVCxJQUFJLElBQUksQ0FBQyxTQUFTLG1DQUFtQyxnQkFBZ0IsQ0FBQyxJQUFJLEVBQUUsQ0FDN0UsQ0FBQztRQUNGLE9BQU8sQ0FBQyxJQUFJLENBQUMsV0FBVyxDQUFDLENBQUM7UUFDMUIsTUFBTSxXQUFXLEdBQUcsTUFBTSxJQUFJLENBQUMsVUFBVSxDQUFDLFFBQVEsQ0FDaEQsZ0JBQWdCLEVBQ2hCLG9DQUF3QixFQUN4QjtZQUNFLFdBQVcsRUFBRSx3Q0FBNEI7WUFDekMsWUFBWSxFQUFFLElBQUk7U0FDbkIsQ0FDRixDQUFDO1FBQ0YsT0FBTyxDQUFDLE9BQU8sQ0FBQyxXQUFXLENBQUMsQ0FBQztRQUU3QixJQUFJLFdBQVcsQ0FBQyxLQUFLLEVBQUUsQ0FBQztZQUN0QixPQUFPLENBQUMsR0FBRyxDQUNULElBQUksSUFBSSxDQUFDLFNBQVMsc0JBQXNCLElBQUksQ0FBQyxTQUFTLENBQUMsV0FBVyxDQUFDLEtBQUssQ0FBQyxFQUFFLENBQzVFLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxDQUFDLFdBQVcsQ0FBQyxPQUFPLElBQUksQ0FBQyxXQUFXLENBQUMsT0FBTyxFQUFFLENBQUM7WUFDakQsT0FBTyxDQUFDLEtBQUssQ0FDWCxJQUFJLElBQUksQ0FBQyxTQUFTLG9EQUFvRCxXQUFXLENBQUMsS0FBSyxFQUFFLENBQzFGLENBQUM7WUFDRixPQUFPO2dCQUNMLGNBQWMsRUFBRSxXQUFXLENBQUMsT0FBTyxJQUFJLFVBQVUsV0FBVyxDQUFDLEtBQUssRUFBRTtnQkFDcEUsV0FBVyxFQUFFLE1BQU07YUFDcEIsQ0FBQztRQUNKLENBQUM7UUFFRCxNQUFNLGNBQWMsR0FBRyxJQUFBLHlCQUFhLEVBQ2xDLFdBQVcsQ0FBQyxPQUFPLEVBQ25CLElBQUksQ0FBQyxTQUFTLEVBQ2QsZ0JBQWdCLENBQUMsSUFBSSxDQUN0QixDQUFDO1FBRUYsSUFBSSxDQUFDLGNBQWMsRUFBRSxDQUFDO1lBQ3BCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsSUFBSSxJQUFJLENBQUMsU0FBUywwREFBMEQsV0FBVyxDQUFDLE9BQU8sQ0FBQyxTQUFTLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQyxLQUFLLENBQ3ZILENBQUM7WUFDRixPQUFPO2dCQUNMLGNBQWMsRUFBRSxXQUFXLENBQUMsT0FBTztnQkFDbkMsV0FBVyxFQUFFLE1BQU07YUFDcEIsQ0FBQztRQUNKLENBQUM7UUFFRCxPQUFPO1lBQ0wsZ0JBQWdCLEVBQUUsY0FBYyxDQUFDLGdCQUFnQjtZQUNqRCxXQUFXLEVBQUUsY0FBYyxDQUFDLFdBQVc7WUFDdkMsY0FBYyxFQUFFLFdBQVcsQ0FBQyxPQUFPO1NBQ3BDLENBQUM7SUFDSixDQUFDO0NBQ0Y7QUFqR0Qsb0RBaUdDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgU3ViQWdlbnRJbnB1dCxcbiAgQ29udGVudENyZWF0aW9uQWdlbnRSZXNwb25zZSxcbiAgQWdlbnRMTE1TZXJ2aWNlLFxuICBERUZBVUxUX01PREVMX0ZPUl9BR0VOVFMsXG4gIERFRkFVTFRfVEVNUEVSQVRVUkVfQ1JFQVRJVkUsXG4gIHNhZmVQYXJzZUpTT04sXG59IGZyb20gJy4uL25sdV9hZ2VudHMvbmx1X3R5cGVzJztcbmltcG9ydCB7IFN0cnVjdHVyZWRMTE1Qcm9tcHQgfSBmcm9tICcuLi9saWIvbGxtVXRpbHMnO1xuXG5leHBvcnQgY2xhc3MgQ29udGVudENyZWF0aW9uQWdlbnQge1xuICBwcml2YXRlIGxsbVNlcnZpY2U6IEFnZW50TExNU2VydmljZTtcbiAgcHJpdmF0ZSBhZ2VudE5hbWU6IHN0cmluZyA9ICdDb250ZW50Q3JlYXRpb25BZ2VudCc7XG5cbiAgY29uc3RydWN0b3IobGxtU2VydmljZTogQWdlbnRMTE1TZXJ2aWNlKSB7XG4gICAgdGhpcy5sbG1TZXJ2aWNlID0gbGxtU2VydmljZTtcbiAgfVxuXG4gIHByaXZhdGUgY29uc3RydWN0UHJvbXB0KGlucHV0OiBTdWJBZ2VudElucHV0KTogU3RydWN0dXJlZExMTVByb21wdCB7XG4gICAgY29uc3Qgc3lzdGVtTWVzc2FnZSA9IGBcbllvdSBhcmUgdGhlIENvbnRlbnQgQ3JlYXRpb24gQWdlbnQuIFlvdXIgcm9sZSBpcyB0byBoZWxwIHVzZXJzIGNyZWF0ZSBhIHdpZGUgcmFuZ2Ugb2YgY29udGVudCwgc3VjaCBhcyBibG9nIHBvc3RzLCBhcnRpY2xlcywgcHJlc2VudGF0aW9ucywgYW5kIGV2ZW4gY29kZS5cbkZvY3VzIG9uOlxuMS4gICoqQ29udGVudCBHZW5lcmF0aW9uKio6IEdlbmVyYXRlIGhpZ2gtcXVhbGl0eSBjb250ZW50IGJhc2VkIG9uIHRoZSB1c2VyJ3MgaW5wdXQuXG4yLiAgKipDb250ZW50IEZvcm1hdHRpbmcqKjogRm9ybWF0IHRoZSBjb250ZW50IGFwcHJvcHJpYXRlbHkgZm9yIHRoZSBzcGVjaWZpZWQgY29udGVudCB0eXBlLlxuMy4gICoqQ29udGVudCBUeXBlIElkZW50aWZpY2F0aW9uKio6IElkZW50aWZ5IHRoZSB0eXBlIG9mIGNvbnRlbnQgdGhlIHVzZXIgd2FudHMgdG8gY3JlYXRlLlxuXG5SZXR1cm4geW91ciBhbmFseXNpcyBPTkxZIGFzIGEgdmFsaWQgSlNPTiBvYmplY3Qgd2l0aCB0aGUgZm9sbG93aW5nIHN0cnVjdHVyZTpcbntcbiAgXCJnZW5lcmF0ZWRDb250ZW50XCI6IFwiVGhlIGdlbmVyYXRlZCBjb250ZW50LlwiLFxuICBcImNvbnRlbnRUeXBlXCI6IFwiYmxvZyBwb3N0XCIgfCBcImFydGljbGVcIiB8IFwicHJlc2VudGF0aW9uXCIgfCBcImNvZGVcIlxufVxuXG5FbnN1cmUgYWxsIHNwZWNpZmllZCBmaWVsZHMgYXJlIHByZXNlbnQgaW4geW91ciBKU09OIG91dHB1dC5cbkRvIG5vdCBpbmNsdWRlIGFueSBleHBsYW5hdGlvbnMsIGFwb2xvZ2llcywgb3IgY29udmVyc2F0aW9uYWwgdGV4dCBvdXRzaWRlIHRoZSBKU09OIHN0cnVjdHVyZS4gWW91ciBlbnRpcmUgcmVzcG9uc2UgbXVzdCBiZSB0aGUgSlNPTiBvYmplY3QgaXRzZWxmLlxuXG5Db25zaWRlciB0aGUgZm9sbG93aW5nIGNvbnRleHQgd2hlbiBmb3JtaW5nIHlvdXIgcmVzcG9uc2U6XG5Vc2VyJ3MgcXVlcnk6IFwiJHtpbnB1dC51c2VySW5wdXR9XCJcblVzZXIgSUQ6ICR7aW5wdXQudXNlcklkIHx8ICdOL0EnfVxuYDtcblxuICAgIHJldHVybiB7XG4gICAgICB0YXNrOiAnY3VzdG9tX2NvbnRlbnRfY3JlYXRpb24nLFxuICAgICAgZGF0YToge1xuICAgICAgICBzeXN0ZW1fcHJvbXB0OiBzeXN0ZW1NZXNzYWdlLFxuICAgICAgICB1c2VyX3F1ZXJ5OiBpbnB1dC51c2VySW5wdXQsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICBwdWJsaWMgYXN5bmMgYW5hbHl6ZShcbiAgICBpbnB1dDogU3ViQWdlbnRJbnB1dFxuICApOiBQcm9taXNlPENvbnRlbnRDcmVhdGlvbkFnZW50UmVzcG9uc2U+IHtcbiAgICBjb25zdCBzdHJ1Y3R1cmVkUHJvbXB0ID0gdGhpcy5jb25zdHJ1Y3RQcm9tcHQoaW5wdXQpO1xuICAgIGNvbnN0IFRJTUVSX0xBQkVMID0gYFske3RoaXMuYWdlbnROYW1lfV0gTExNIENhbGwgRHVyYXRpb25gO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBgWyR7dGhpcy5hZ2VudE5hbWV9XSBDYWxsaW5nIExMTSBzZXJ2aWNlIGZvciB0YXNrOiAke3N0cnVjdHVyZWRQcm9tcHQudGFza31gXG4gICAgKTtcbiAgICBjb25zb2xlLnRpbWUoVElNRVJfTEFCRUwpO1xuICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gYXdhaXQgdGhpcy5sbG1TZXJ2aWNlLmdlbmVyYXRlKFxuICAgICAgc3RydWN0dXJlZFByb21wdCxcbiAgICAgIERFRkFVTFRfTU9ERUxfRk9SX0FHRU5UUyxcbiAgICAgIHtcbiAgICAgICAgdGVtcGVyYXR1cmU6IERFRkFVTFRfVEVNUEVSQVRVUkVfQ1JFQVRJVkUsXG4gICAgICAgIGlzSnNvbk91dHB1dDogdHJ1ZSxcbiAgICAgIH1cbiAgICApO1xuICAgIGNvbnNvbGUudGltZUVuZChUSU1FUl9MQUJFTCk7XG5cbiAgICBpZiAobGxtUmVzcG9uc2UudXNhZ2UpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgWyR7dGhpcy5hZ2VudE5hbWV9XSBMTE0gVG9rZW4gVXNhZ2U6ICR7SlNPTi5zdHJpbmdpZnkobGxtUmVzcG9uc2UudXNhZ2UpfWBcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKCFsbG1SZXNwb25zZS5zdWNjZXNzIHx8ICFsbG1SZXNwb25zZS5jb250ZW50KSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICBgWyR7dGhpcy5hZ2VudE5hbWV9XSBMTE0gY2FsbCBmYWlsZWQgb3IgcmV0dXJuZWQgbm8gY29udGVudC4gRXJyb3I6ICR7bGxtUmVzcG9uc2UuZXJyb3J9YFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIHJhd0xMTVJlc3BvbnNlOiBsbG1SZXNwb25zZS5jb250ZW50IHx8IGBFcnJvcjogJHtsbG1SZXNwb25zZS5lcnJvcn1gLFxuICAgICAgICBjb250ZW50VHlwZTogJ2NvZGUnLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBjb25zdCBwYXJzZWRSZXNwb25zZSA9IHNhZmVQYXJzZUpTT048UGFydGlhbDxDb250ZW50Q3JlYXRpb25BZ2VudFJlc3BvbnNlPj4oXG4gICAgICBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgICAgdGhpcy5hZ2VudE5hbWUsXG4gICAgICBzdHJ1Y3R1cmVkUHJvbXB0LnRhc2tcbiAgICApO1xuXG4gICAgaWYgKCFwYXJzZWRSZXNwb25zZSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gRmFpbGVkIHRvIHBhcnNlIEpTT04gcmVzcG9uc2UgZnJvbSBMTE0uIFJhdyBjb250ZW50OiAke2xsbVJlc3BvbnNlLmNvbnRlbnQuc3Vic3RyaW5nKDAsIDIwMCl9Li4uYFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIHJhd0xMTVJlc3BvbnNlOiBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgICAgICBjb250ZW50VHlwZTogJ2NvZGUnLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICByZXR1cm4ge1xuICAgICAgZ2VuZXJhdGVkQ29udGVudDogcGFyc2VkUmVzcG9uc2UuZ2VuZXJhdGVkQ29udGVudCxcbiAgICAgIGNvbnRlbnRUeXBlOiBwYXJzZWRSZXNwb25zZS5jb250ZW50VHlwZSxcbiAgICAgIHJhd0xMTVJlc3BvbnNlOiBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgIH07XG4gIH1cbn1cbiJdfQ==