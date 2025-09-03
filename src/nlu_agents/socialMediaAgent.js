"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SocialMediaAgent = void 0;
const nlu_types_1 = require("./nlu_types");
const autonomousSystemOrchestrator_1 = require("../orchestration/autonomousSystemOrchestrator");
class SocialMediaAgent {
    constructor(llmService) {
        this.agentName = 'SocialMediaAgent';
        this.llmService = llmService;
    }
    constructPrompt(input) {
        const systemMessage = `
You are the Social Media Agent. Your role is to help users manage their social media accounts.
Focus on:
1.  **Action Identification**: Identify if the user wants to post to social media.
2.  **Content Extraction**: Extract the content to be posted.

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "action": "post",
  "text": "The content to be posted."
}

If the user's intent is not to post to social media, return an empty JSON object: {}

Ensure all specified fields are present in your JSON output.
Do not include any explanations, apologies, or conversational text outside the JSON structure. Your entire response must be the JSON object itself.

Consider the following context when forming your response:
User's query: "${input.userInput}"
User ID: ${input.userId || 'N/A'}
`;
        return {
            task: 'social_media_management',
            data: {
                system_prompt: systemMessage,
                user_query: input.userInput,
            },
        };
    }
    async analyzeAndAct(input) {
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
            return;
        }
        const parsedResponse = (0, nlu_types_1.safeParseJSON)(llmResponse.content, this.agentName, structuredPrompt.task);
        if (parsedResponse && parsedResponse.action === 'post' && parsedResponse.text) {
            if (input.userId) {
                await (0, autonomousSystemOrchestrator_1.runSocialMediaAutoPost)(input.userId, parsedResponse.text);
            }
            else {
                console.error("User ID is not available, cannot post to social media.");
            }
        }
    }
}
exports.SocialMediaAgent = SocialMediaAgent;
//# sourceMappingURL=socialMediaAgent.js.map