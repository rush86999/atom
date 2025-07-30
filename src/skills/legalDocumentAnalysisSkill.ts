import {
    SubAgentInput,
    LegalDocumentAnalysisAgentResponse,
    AgentLLMService,
    DEFAULT_MODEL_FOR_AGENTS,
    DEFAULT_TEMPERATURE_ANALYTICAL,
    safeParseJSON
} from '../nlu_agents/nlu_types';
import { StructuredLLMPrompt } from '../lib/llmUtils';

export class LegalDocumentAnalysisAgent {
    private llmService: AgentLLMService;
    private agentName: string = "LegalDocumentAnalysisAgent";

    constructor(llmService: AgentLLMService) {
        this.llmService = llmService;
    }

    private constructPrompt(input: SubAgentInput): StructuredLLMPrompt {
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
            }
        };
    }

    public async analyze(input: SubAgentInput): Promise<LegalDocumentAnalysisAgentResponse> {
        const structuredPrompt = this.constructPrompt(input);
        const TIMER_LABEL = `[${this.agentName}] LLM Call Duration`;

        console.log(`[${this.agentName}] Calling LLM service for task: ${structuredPrompt.task}`);
        console.time(TIMER_LABEL);
        const llmResponse = await this.llmService.generate(
            structuredPrompt,
            DEFAULT_MODEL_FOR_AGENTS,
            {
                temperature: DEFAULT_TEMPERATURE_ANALYTICAL,
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

        const parsedResponse = safeParseJSON<Partial<LegalDocumentAnalysisAgentResponse>>(
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
            riskAnalysis: parsedResponse.riskAnalysis || [],
            summary: parsedResponse.summary,
            rawLLMResponse: llmResponse.content,
        };
    }
}
