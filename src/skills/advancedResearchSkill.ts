import {
  SubAgentInput,
  AdvancedResearchAgentResponse,
  AgentLLMService,
  DEFAULT_MODEL_FOR_AGENTS,
  DEFAULT_TEMPERATURE_ANALYTICAL,
  safeParseJSON,
} from '../nlu_agents/nlu_types';
import { StructuredLLMPrompt } from '../lib/llmUtils';
import { createDesign } from './canvaSkills';

export class AdvancedResearchAgent {
  private llmService: AgentLLMService;
  private agentName: string = 'AdvancedResearchAgent';

  constructor(llmService: AgentLLMService) {
    this.llmService = llmService;
  }

  private constructPrompt(input: SubAgentInput): StructuredLLMPrompt {
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

  private async createCanvaDesign(
    userId: string,
    title: string
  ): Promise<AdvancedResearchAgentResponse> {
    try {
      const design = await createDesign(userId, title);
      return {
        researchSummary: `Successfully created Canva design: "${design.title}"`,
        keyFindings: [
          `Design ID: ${design.id}`,
          `Edit URL: ${design.urls.edit_url}`,
        ],
        sources: [{ title: 'Canva Design', url: design.urls.edit_url }],
        rawLLMResponse: JSON.stringify(design),
      };
    } catch (error: any) {
      return {
        researchSummary: `Failed to create Canva design: ${error.message}`,
        keyFindings: [],
        sources: [],
        rawLLMResponse: '',
      };
    }
  }

  public async analyze(
    input: SubAgentInput
  ): Promise<AdvancedResearchAgentResponse> {
    const canvaCommandRegex = /create canva design with title "([^"]+)"/i;
    const canvaMatch = input.userInput.match(canvaCommandRegex);

    if (canvaMatch && canvaMatch[1]) {
      const title = canvaMatch[1];
      return this.createCanvaDesign(input.userId, title);
    }

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
        temperature: DEFAULT_TEMPERATURE_ANALYTICAL,
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
      return {
        rawLLMResponse: llmResponse.content || `Error: ${llmResponse.error}`,
      };
    }

    const parsedResponse = safeParseJSON<
      Partial<AdvancedResearchAgentResponse>
    >(llmResponse.content, this.agentName, structuredPrompt.task);

    if (!parsedResponse) {
      console.error(
        `[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`
      );
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
