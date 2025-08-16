import {
  SubAgentInput,
  SubAgentResponse,
  AgentLLMService,
  DEFAULT_MODEL_FOR_AGENTS,
  DEFAULT_TEMPERATURE_CREATIVE,
  safeParseJSON,
} from './nlu_types';
import { StructuredLLMPrompt } from '../lib/llmUtils';
import { runSocialMediaAutoPost } from '../orchestration/autonomousSystemOrchestrator';

interface SocialMediaAgentResponse extends SubAgentResponse {
  action: 'post';
  text: string;
}

export class SocialMediaAgent {
  private llmService: AgentLLMService;
  private agentName: string = 'SocialMediaAgent';

  constructor(llmService: AgentLLMService) {
    this.llmService = llmService;
  }

  private constructPrompt(input: SubAgentInput): StructuredLLMPrompt {
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

  public async analyzeAndAct(
    input: SubAgentInput
  ): Promise<void> {
    const structuredPrompt = this.constructPrompt(input);
    const TIMER_LABEL = `[${this.agentName}] LLM Call Duration`;

    console.log(
      `[${this.agentName}] Calling LLM service for task: ${structuredPrompt.task}`
    );
    console.time(TIMER_LABEL);
    const llmResponse = await this.llmService.generate(
      structuredPrompt,
      DEFAULT_MODEL_FOR_AGENTS,
      {
        temperature: DEFAULT_TEMPERATURE_CREATIVE,
        isJsonOutput: true,
      }
    );
    console.timeEnd(TIMER_LABEL);

    if (llmResponse.usage) {
      console.log(
        `[${this.agentName}] LLM Token Usage: ${JSON.stringify(llmResponse.usage)}`
      );
    }

    if (!llmResponse.success || !llmResponse.content) {
      console.error(
        `[${this.agentName}] LLM call failed or returned no content. Error: ${llmResponse.error}`
      );
      return;
    }

    const parsedResponse = safeParseJSON<Partial<SocialMediaAgentResponse>>(
      llmResponse.content,
      this.agentName,
      structuredPrompt.task
    );

    if (parsedResponse && parsedResponse.action === 'post' && parsedResponse.text) {
        if (input.userId) {
            await runSocialMediaAutoPost(input.userId, parsedResponse.text);
        } else {
            console.error("User ID is not available, cannot post to social media.");
        }
    }
  }
}
