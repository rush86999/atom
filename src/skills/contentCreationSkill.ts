import {
    SubAgentInput,
    ContentCreationAgentResponse,
    AgentLLMService,
    DEFAULT_MODEL_FOR_AGENTS,
    DEFAULT_TEMPERATURE_CREATIVE,
    safeParseJSON
} from '../nlu_agents/nlu_types';
import { StructuredLLMPrompt } from '../lib/llmUtils';

export class ContentCreationAgent {
    private llmService: AgentLLMService;
    private agentName: string = "ContentCreationAgent";

    constructor(llmService: AgentLLMService) {
        this.llmService = llmService;
    }

    private constructPrompt(input: SubAgentInput): StructuredLLMPrompt {
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
            }
        };
    }

    public async analyze(input: SubAgentInput): Promise<ContentCreationAgentResponse> {
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
                rawLLMResponse: llmResponse.content || `Error: ${llmResponse.error}`,
                contentType: "code"
            };
        }

        const parsedResponse = safeParseJSON<Partial<ContentCreationAgentResponse>>(
            llmResponse.content,
            this.agentName,
            structuredPrompt.task
        );

        if (!parsedResponse) {
            console.error(`[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`);
            return {
                rawLLMResponse: llmResponse.content,
                contentType: "code"
            };
        }

        return {
            generatedContent: parsedResponse.generatedContent,
            contentType: parsedResponse.contentType,
            rawLLMResponse: llmResponse.content,
        };
    }
}
