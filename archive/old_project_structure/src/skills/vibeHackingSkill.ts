import {
  SubAgentInput,
  VibeHackingAgentResponse,
  AgentLLMService,
  DEFAULT_MODEL_FOR_AGENTS,
  DEFAULT_TEMPERATURE_ANALYTICAL,
  safeParseJSON,
} from '../nlu_agents/nlu_types';
import { StructuredLLMPrompt } from '../lib/llmUtils';

export class VibeHackingAgent {
  private llmService: AgentLLMService;
  private agentName: string = 'VibeHackingAgent';

  constructor(llmService: AgentLLMService) {
    this.llmService = llmService;
  }

  private constructPrompt(input: SubAgentInput): StructuredLLMPrompt {
    const systemMessage = `
You are the Vibe Hacking Agent. Your role is to perform red team testing on web applications.
Focus on:
1.  **Vulnerability Scanning**: Scan the target system for vulnerabilities.
2.  **Exploitation**: Attempt to exploit any vulnerabilities that are found.
3.  **Reporting**: Generate a report of the findings, with a description of the vulnerabilities, the steps taken to exploit them, and recommendations for remediation.

Return your analysis ONLY as a valid JSON object with the following structure:
{
  "vulnerabilityReport": [{ "vulnerability": "The name of the vulnerability.", "severity": "Critical" | "High" | "Medium" | "Low", "description": "A description of the vulnerability.", "remediation": "Recommendations for remediating the vulnerability." }]
}

Ensure all specified fields are present in your JSON output. If no items apply for a list-based field (like "vulnerabilityReport"), return an empty array [].
Do not include any explanations, apologies, or conversational text outside the JSON structure. Your entire response must be the JSON object itself.

Consider the following context when forming your response:
User's query: "${input.userInput}"
User ID: ${input.userId || 'N/A'}
`;

    return {
      task: 'custom_vibe_hacking',
      data: {
        system_prompt: systemMessage,
        user_query: input.userInput,
      },
    };
  }

  public async analyze(
    input: SubAgentInput
  ): Promise<VibeHackingAgentResponse> {
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

    const parsedResponse = safeParseJSON<Partial<VibeHackingAgentResponse>>(
      llmResponse.content,
      this.agentName,
      structuredPrompt.task
    );

    if (!parsedResponse) {
      console.error(
        `[${this.agentName}] Failed to parse JSON response from LLM. Raw content: ${llmResponse.content.substring(0, 200)}...`
      );
      return {
        rawLLMResponse: llmResponse.content,
      };
    }

    return {
      vulnerabilityReport: parsedResponse.vulnerabilityReport || [],
      rawLLMResponse: llmResponse.content,
    };
  }
}
