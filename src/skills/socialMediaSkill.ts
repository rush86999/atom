import {
    SubAgentInput,
    SocialMediaAgentResponse,
    AgentLLMService,
    DEFAULT_MODEL_FOR_AGENTS,
    DEFAULT_TEMPERATURE_CREATIVE,
    safeParseJSON
} from '../nlu_agents/nlu_types';
import { StructuredLLMPrompt } from '../lib/llmUtils';

export class SocialMediaAgent {
    private llmService: AgentLLMService;
    private agentName: string = "SocialMediaAgent";

    constructor(llmService: AgentLLMService) {
        this.llmService = llmService;
    }

    private constructPrompt(input: SubAgentInput): StructuredLLMPrompt {
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
            }
        };
    }

    public async analyze(input: SubAgentInput): Promise<SocialMediaAgentResponse> {
        const structuredPrompt = this.constructPrompt(input);
        const TIMER_LABEL = `[${this.agentName}] LLM Call Duration`;

        console.log(`[${this.agentName}] Calling LLM service for task: ${structuredPrompt.task}`);
        console.time(TIMER_LABEL);
        const llmResponse = await this.llmService.generate(
            structuredPrompt,
            DEFAULT_MODEL_FOR_AGENTS,
            {
                temperature: DEFAULT_TEMPERATURE_CREATIVE,
                isJsonOutput: true
            }
        );
        console.timeEnd(TIMER_LABEL);

        if (llmResponse.usage) {
            console.log(`[${this.agentName}] LLM Token Usage: ${JSON.stringify(llmResponse.usage)}`);
        }

        if (!llmResponse.success || !llmResponse.content) {
            console.error(`[${this.agentName}] LLM call failed or returned no content. Error: ${llmResponse.error}`);
            return {
                rawLLMResponse: llmResponse.content || `Error: ${llmResponse.error}`
            };
        }

        const parsedResponse = safeParseJSON<Partial<SocialMediaAgentResponse>>(
            llmResponse.content,
            this.agentName,
            structuredPrompt.task
        );

        if (!parsedResponse) {
            console.error(`[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`);
            return {
                rawLLMResponse: llmResponse.content
            };
        }

        return {
            scheduledPosts: parsedResponse.scheduledPosts || [],
            engagementSummary: parsedResponse.engagementSummary,
            rawLLMResponse: llmResponse.content,
        };
    }
}
