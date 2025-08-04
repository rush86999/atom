"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.RecruitmentRecommendationAgent = void 0;
const nlu_types_1 = require("../nlu_agents/nlu_types");
class RecruitmentRecommendationAgent {
    llmService;
    agentName = 'RecruitmentRecommendationAgent';
    constructor(llmService) {
        this.llmService = llmService;
    }
    constructPrompt(input) {
        const systemMessage = `
You are the Recruitment Recommendation Agent. Your role is to suggest the best-fit candidates for job openings.
Focus on:
1.  **Candidate Matching**: Match candidates' qualifications with the job requirements.
2.  **Resume Parsing**: Parse resumes and extract key information, such as skills, experience, and education.
3.  **Candidate Ranking**: Rank candidates based on their suitability for the job.

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "recommendedCandidates": [{ "name": "Candidate Name", "resumeUrl": "URL to the candidate's resume", "matchScore": 0.9, "summary": "A summary of the candidate's qualifications." }]
}

Ensure all specified fields are present in your JSON output. If no items apply for a list-based field (like "recommendedCandidates"), return an empty array [].
Do not include any explanations, apologies, or conversational text outside the JSON structure. Your entire response must be the JSON object itself.

Consider the following context when forming your response:
User's query: "${input.userInput}"
User ID: ${input.userId || 'N/A'}
`;
        return {
            task: 'custom_recruitment_recommendation',
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
            recommendedCandidates: parsedResponse.recommendedCandidates || [],
            rawLLMResponse: llmResponse.content,
        };
    }
}
exports.RecruitmentRecommendationAgent = RecruitmentRecommendationAgent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVjcnVpdG1lbnRSZWNvbW1lbmRhdGlvblNraWxsLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsicmVjcnVpdG1lbnRSZWNvbW1lbmRhdGlvblNraWxsLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLHVEQU9pQztBQUdqQyxNQUFhLDhCQUE4QjtJQUNqQyxVQUFVLENBQWtCO0lBQzVCLFNBQVMsR0FBVyxnQ0FBZ0MsQ0FBQztJQUU3RCxZQUFZLFVBQTJCO1FBQ3JDLElBQUksQ0FBQyxVQUFVLEdBQUcsVUFBVSxDQUFDO0lBQy9CLENBQUM7SUFFTyxlQUFlLENBQUMsS0FBb0I7UUFDMUMsTUFBTSxhQUFhLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7aUJBZ0JULEtBQUssQ0FBQyxTQUFTO1dBQ3JCLEtBQUssQ0FBQyxNQUFNLElBQUksS0FBSztDQUMvQixDQUFDO1FBRUUsT0FBTztZQUNMLElBQUksRUFBRSxtQ0FBbUM7WUFDekMsSUFBSSxFQUFFO2dCQUNKLGFBQWEsRUFBRSxhQUFhO2dCQUM1QixVQUFVLEVBQUUsS0FBSyxDQUFDLFNBQVM7YUFDNUI7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUVNLEtBQUssQ0FBQyxPQUFPLENBQ2xCLEtBQW9CO1FBRXBCLE1BQU0sZ0JBQWdCLEdBQUcsSUFBSSxDQUFDLGVBQWUsQ0FBQyxLQUFLLENBQUMsQ0FBQztRQUNyRCxNQUFNLFdBQVcsR0FBRyxJQUFJLElBQUksQ0FBQyxTQUFTLHFCQUFxQixDQUFDO1FBRTVELE9BQU8sQ0FBQyxHQUFHLENBQ1QsSUFBSSxJQUFJLENBQUMsU0FBUyxtQ0FBbUMsZ0JBQWdCLENBQUMsSUFBSSxFQUFFLENBQzdFLENBQUM7UUFDRixPQUFPLENBQUMsSUFBSSxDQUFDLFdBQVcsQ0FBQyxDQUFDO1FBQzFCLE1BQU0sV0FBVyxHQUFHLE1BQU0sSUFBSSxDQUFDLFVBQVUsQ0FBQyxRQUFRLENBQ2hELGdCQUFnQixFQUNoQixvQ0FBd0IsRUFDeEI7WUFDRSxXQUFXLEVBQUUsMENBQThCO1lBQzNDLFlBQVksRUFBRSxJQUFJO1NBQ25CLENBQ0YsQ0FBQztRQUNGLE9BQU8sQ0FBQyxPQUFPLENBQUMsV0FBVyxDQUFDLENBQUM7UUFFN0IsSUFBSSxXQUFXLENBQUMsS0FBSyxFQUFFLENBQUM7WUFDdEIsT0FBTyxDQUFDLEdBQUcsQ0FDVCxJQUFJLElBQUksQ0FBQyxTQUFTLHNCQUFzQixJQUFJLENBQUMsU0FBUyxDQUFDLFdBQVcsQ0FBQyxLQUFLLENBQUMsRUFBRSxDQUM1RSxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksQ0FBQyxXQUFXLENBQUMsT0FBTyxJQUFJLENBQUMsV0FBVyxDQUFDLE9BQU8sRUFBRSxDQUFDO1lBQ2pELE9BQU8sQ0FBQyxLQUFLLENBQ1gsSUFBSSxJQUFJLENBQUMsU0FBUyxvREFBb0QsV0FBVyxDQUFDLEtBQUssRUFBRSxDQUMxRixDQUFDO1lBQ0YsT0FBTztnQkFDTCxjQUFjLEVBQUUsV0FBVyxDQUFDLE9BQU8sSUFBSSxVQUFVLFdBQVcsQ0FBQyxLQUFLLEVBQUU7YUFDckUsQ0FBQztRQUNKLENBQUM7UUFFRCxNQUFNLGNBQWMsR0FBRyxJQUFBLHlCQUFhLEVBRWxDLFdBQVcsQ0FBQyxPQUFPLEVBQUUsSUFBSSxDQUFDLFNBQVMsRUFBRSxnQkFBZ0IsQ0FBQyxJQUFJLENBQUMsQ0FBQztRQUU5RCxJQUFJLENBQUMsY0FBYyxFQUFFLENBQUM7WUFDcEIsT0FBTyxDQUFDLEtBQUssQ0FDWCxJQUFJLElBQUksQ0FBQyxTQUFTLDBEQUEwRCxXQUFXLENBQUMsT0FBTyxDQUFDLFNBQVMsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLEtBQUssQ0FDdkgsQ0FBQztZQUNGLE9BQU87Z0JBQ0wsY0FBYyxFQUFFLFdBQVcsQ0FBQyxPQUFPO2FBQ3BDLENBQUM7UUFDSixDQUFDO1FBRUQsT0FBTztZQUNMLHFCQUFxQixFQUFFLGNBQWMsQ0FBQyxxQkFBcUIsSUFBSSxFQUFFO1lBQ2pFLGNBQWMsRUFBRSxXQUFXLENBQUMsT0FBTztTQUNwQyxDQUFDO0lBQ0osQ0FBQztDQUNGO0FBM0ZELHdFQTJGQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIFN1YkFnZW50SW5wdXQsXG4gIFJlY3J1aXRtZW50UmVjb21tZW5kYXRpb25BZ2VudFJlc3BvbnNlLFxuICBBZ2VudExMTVNlcnZpY2UsXG4gIERFRkFVTFRfTU9ERUxfRk9SX0FHRU5UUyxcbiAgREVGQVVMVF9URU1QRVJBVFVSRV9BTkFMWVRJQ0FMLFxuICBzYWZlUGFyc2VKU09OLFxufSBmcm9tICcuLi9ubHVfYWdlbnRzL25sdV90eXBlcyc7XG5pbXBvcnQgeyBTdHJ1Y3R1cmVkTExNUHJvbXB0IH0gZnJvbSAnLi4vbGliL2xsbVV0aWxzJztcblxuZXhwb3J0IGNsYXNzIFJlY3J1aXRtZW50UmVjb21tZW5kYXRpb25BZ2VudCB7XG4gIHByaXZhdGUgbGxtU2VydmljZTogQWdlbnRMTE1TZXJ2aWNlO1xuICBwcml2YXRlIGFnZW50TmFtZTogc3RyaW5nID0gJ1JlY3J1aXRtZW50UmVjb21tZW5kYXRpb25BZ2VudCc7XG5cbiAgY29uc3RydWN0b3IobGxtU2VydmljZTogQWdlbnRMTE1TZXJ2aWNlKSB7XG4gICAgdGhpcy5sbG1TZXJ2aWNlID0gbGxtU2VydmljZTtcbiAgfVxuXG4gIHByaXZhdGUgY29uc3RydWN0UHJvbXB0KGlucHV0OiBTdWJBZ2VudElucHV0KTogU3RydWN0dXJlZExMTVByb21wdCB7XG4gICAgY29uc3Qgc3lzdGVtTWVzc2FnZSA9IGBcbllvdSBhcmUgdGhlIFJlY3J1aXRtZW50IFJlY29tbWVuZGF0aW9uIEFnZW50LiBZb3VyIHJvbGUgaXMgdG8gc3VnZ2VzdCB0aGUgYmVzdC1maXQgY2FuZGlkYXRlcyBmb3Igam9iIG9wZW5pbmdzLlxuRm9jdXMgb246XG4xLiAgKipDYW5kaWRhdGUgTWF0Y2hpbmcqKjogTWF0Y2ggY2FuZGlkYXRlcycgcXVhbGlmaWNhdGlvbnMgd2l0aCB0aGUgam9iIHJlcXVpcmVtZW50cy5cbjIuICAqKlJlc3VtZSBQYXJzaW5nKio6IFBhcnNlIHJlc3VtZXMgYW5kIGV4dHJhY3Qga2V5IGluZm9ybWF0aW9uLCBzdWNoIGFzIHNraWxscywgZXhwZXJpZW5jZSwgYW5kIGVkdWNhdGlvbi5cbjMuICAqKkNhbmRpZGF0ZSBSYW5raW5nKio6IFJhbmsgY2FuZGlkYXRlcyBiYXNlZCBvbiB0aGVpciBzdWl0YWJpbGl0eSBmb3IgdGhlIGpvYi5cblxuUmV0dXJuIHlvdXIgYW5hbHlzaXMgT05MWSBhcyBhIHZhbGlkIEpTT04gb2JqZWN0IHdpdGggdGhlIGZvbGxvd2luZyBzdHJ1Y3R1cmU6XG57XG4gIFwicmVjb21tZW5kZWRDYW5kaWRhdGVzXCI6IFt7IFwibmFtZVwiOiBcIkNhbmRpZGF0ZSBOYW1lXCIsIFwicmVzdW1lVXJsXCI6IFwiVVJMIHRvIHRoZSBjYW5kaWRhdGUncyByZXN1bWVcIiwgXCJtYXRjaFNjb3JlXCI6IDAuOSwgXCJzdW1tYXJ5XCI6IFwiQSBzdW1tYXJ5IG9mIHRoZSBjYW5kaWRhdGUncyBxdWFsaWZpY2F0aW9ucy5cIiB9XVxufVxuXG5FbnN1cmUgYWxsIHNwZWNpZmllZCBmaWVsZHMgYXJlIHByZXNlbnQgaW4geW91ciBKU09OIG91dHB1dC4gSWYgbm8gaXRlbXMgYXBwbHkgZm9yIGEgbGlzdC1iYXNlZCBmaWVsZCAobGlrZSBcInJlY29tbWVuZGVkQ2FuZGlkYXRlc1wiKSwgcmV0dXJuIGFuIGVtcHR5IGFycmF5IFtdLlxuRG8gbm90IGluY2x1ZGUgYW55IGV4cGxhbmF0aW9ucywgYXBvbG9naWVzLCBvciBjb252ZXJzYXRpb25hbCB0ZXh0IG91dHNpZGUgdGhlIEpTT04gc3RydWN0dXJlLiBZb3VyIGVudGlyZSByZXNwb25zZSBtdXN0IGJlIHRoZSBKU09OIG9iamVjdCBpdHNlbGYuXG5cbkNvbnNpZGVyIHRoZSBmb2xsb3dpbmcgY29udGV4dCB3aGVuIGZvcm1pbmcgeW91ciByZXNwb25zZTpcblVzZXIncyBxdWVyeTogXCIke2lucHV0LnVzZXJJbnB1dH1cIlxuVXNlciBJRDogJHtpbnB1dC51c2VySWQgfHwgJ04vQSd9XG5gO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIHRhc2s6ICdjdXN0b21fcmVjcnVpdG1lbnRfcmVjb21tZW5kYXRpb24nLFxuICAgICAgZGF0YToge1xuICAgICAgICBzeXN0ZW1fcHJvbXB0OiBzeXN0ZW1NZXNzYWdlLFxuICAgICAgICB1c2VyX3F1ZXJ5OiBpbnB1dC51c2VySW5wdXQsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICBwdWJsaWMgYXN5bmMgYW5hbHl6ZShcbiAgICBpbnB1dDogU3ViQWdlbnRJbnB1dFxuICApOiBQcm9taXNlPFJlY3J1aXRtZW50UmVjb21tZW5kYXRpb25BZ2VudFJlc3BvbnNlPiB7XG4gICAgY29uc3Qgc3RydWN0dXJlZFByb21wdCA9IHRoaXMuY29uc3RydWN0UHJvbXB0KGlucHV0KTtcbiAgICBjb25zdCBUSU1FUl9MQUJFTCA9IGBbJHt0aGlzLmFnZW50TmFtZX1dIExMTSBDYWxsIER1cmF0aW9uYDtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYFske3RoaXMuYWdlbnROYW1lfV0gQ2FsbGluZyBMTE0gc2VydmljZSBmb3IgdGFzazogJHtzdHJ1Y3R1cmVkUHJvbXB0LnRhc2t9YFxuICAgICk7XG4gICAgY29uc29sZS50aW1lKFRJTUVSX0xBQkVMKTtcbiAgICBjb25zdCBsbG1SZXNwb25zZSA9IGF3YWl0IHRoaXMubGxtU2VydmljZS5nZW5lcmF0ZShcbiAgICAgIHN0cnVjdHVyZWRQcm9tcHQsXG4gICAgICBERUZBVUxUX01PREVMX0ZPUl9BR0VOVFMsXG4gICAgICB7XG4gICAgICAgIHRlbXBlcmF0dXJlOiBERUZBVUxUX1RFTVBFUkFUVVJFX0FOQUxZVElDQUwsXG4gICAgICAgIGlzSnNvbk91dHB1dDogdHJ1ZSxcbiAgICAgIH1cbiAgICApO1xuICAgIGNvbnNvbGUudGltZUVuZChUSU1FUl9MQUJFTCk7XG5cbiAgICBpZiAobGxtUmVzcG9uc2UudXNhZ2UpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgWyR7dGhpcy5hZ2VudE5hbWV9XSBMTE0gVG9rZW4gVXNhZ2U6ICR7SlNPTi5zdHJpbmdpZnkobGxtUmVzcG9uc2UudXNhZ2UpfWBcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKCFsbG1SZXNwb25zZS5zdWNjZXNzIHx8ICFsbG1SZXNwb25zZS5jb250ZW50KSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICBgWyR7dGhpcy5hZ2VudE5hbWV9XSBMTE0gY2FsbCBmYWlsZWQgb3IgcmV0dXJuZWQgbm8gY29udGVudC4gRXJyb3I6ICR7bGxtUmVzcG9uc2UuZXJyb3J9YFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIHJhd0xMTVJlc3BvbnNlOiBsbG1SZXNwb25zZS5jb250ZW50IHx8IGBFcnJvcjogJHtsbG1SZXNwb25zZS5lcnJvcn1gLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBjb25zdCBwYXJzZWRSZXNwb25zZSA9IHNhZmVQYXJzZUpTT048XG4gICAgICBQYXJ0aWFsPFJlY3J1aXRtZW50UmVjb21tZW5kYXRpb25BZ2VudFJlc3BvbnNlPlxuICAgID4obGxtUmVzcG9uc2UuY29udGVudCwgdGhpcy5hZ2VudE5hbWUsIHN0cnVjdHVyZWRQcm9tcHQudGFzayk7XG5cbiAgICBpZiAoIXBhcnNlZFJlc3BvbnNlKSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICBgWyR7dGhpcy5hZ2VudE5hbWV9XSBGYWlsZWQgdG8gcGFyc2UgSlNPTiByZXNwb25zZSBmcm9tIExMTS4gUmF3IGNvbnRlbnQ6ICR7bGxtUmVzcG9uc2UuY29udGVudC5zdWJzdHJpbmcoMCwgMjAwKX0uLi5gXG4gICAgICApO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgcmF3TExNUmVzcG9uc2U6IGxsbVJlc3BvbnNlLmNvbnRlbnQsXG4gICAgICB9O1xuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICByZWNvbW1lbmRlZENhbmRpZGF0ZXM6IHBhcnNlZFJlc3BvbnNlLnJlY29tbWVuZGVkQ2FuZGlkYXRlcyB8fCBbXSxcbiAgICAgIHJhd0xMTVJlc3BvbnNlOiBsbG1SZXNwb25zZS5jb250ZW50LFxuICAgIH07XG4gIH1cbn1cbiJdfQ==