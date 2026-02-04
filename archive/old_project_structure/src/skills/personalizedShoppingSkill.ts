import {
    SubAgentInput,
    PersonalizedShoppingAgentResponse,
    AgentLLMService,
    DEFAULT_MODEL_FOR_AGENTS,
    DEFAULT_TEMPERATURE_CREATIVE,
    safeParseJSON
} from '../nlu_agents/nlu_types';
import { StructuredLLMPrompt } from '../lib/llmUtils';

export class PersonalizedShoppingAgent {
    private llmService: AgentLLMService;
    private agentName: string = "PersonalizedShoppingAgent";

    constructor(llmService: AgentLLMService) {
        this.llmService = llmService;
    }

    private constructPrompt(input: SubAgentInput): StructuredLLMPrompt {
        const systemMessage = `
You are the Personalized Shopping Agent. Your role is to provide a personalized shopping experience by learning about the user's preferences and purchase history, and then recommending products that they are likely to be interested in.
Focus on:
1.  **Preference Learning**: Learn about the user's preferences from their purchase history and other available data.
2.  **Product Recommendation**: Recommend products that the user is likely to be interested in, based on their preferences.
3.  **Product Search**: Search for products on e-commerce websites that meet the user's criteria.

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "productRecommendations": [{ "productName": "Product Name", "price": 100, "url": "Product URL", "reasoning": "Why the product is recommended." }]
}

Ensure all specified fields are present in your JSON output. If no items apply for a list-based field (like "productRecommendations"), return an empty array [].
Do not include any explanations, apologies, or conversational text outside the JSON structure. Your entire response must be the JSON object itself.

Consider the following context when forming your response:
User's query: "${input.userInput}"
User ID: ${input.userId || 'N/A'}
`;

        return {
            task: 'custom_personalized_shopping',
            data: {
                system_prompt: systemMessage,
                user_query: input.userInput,
            }
        };
    }

    public async analyze(input: SubAgentInput): Promise<PersonalizedShoppingAgentResponse> {
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

        const parsedResponse = safeParseJSON<Partial<PersonalizedShoppingAgentResponse>>(
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
            productRecommendations: parsedResponse.productRecommendations || [],
            rawLLMResponse: llmResponse.content,
        };
    }
}
