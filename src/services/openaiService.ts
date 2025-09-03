import { OpenAI } from "openai";

export interface OpenAIServiceConfig {
  apiKey: string;
  model?: string;
  temperature?: number;
  maxTokens?: number;
}

export interface AIMessageAnalysis {
  intent: string;
  confidence: number;
  entities: Record<string, any>;
  action: string;
  parameters: Record<string, any>;
  workflow?: string;
  requiresConfirmation: boolean;
  suggestedResponses: string[];
  context?: any;
}

export class OpenAIService {
  private client: OpenAI;
  private config: OpenAIServiceConfig;

  constructor(config?: Partial<OpenAIServiceConfig>) {
    this.config = {
      apiKey: process.env.OPENAI_API_KEY || "",
      model: "gpt-3.5-turbo",
      temperature: 0.7,
      maxTokens: 1000,
      ...config,
    };

    if (!this.config.apiKey) {
      throw new Error("OpenAI API key is required");
    }

    this.client = new OpenAI({
      apiKey: this.config.apiKey,
    });
  }

  async analyzeMessage(
    message: string,
    options?: { task?: string; context?: any },
  ): Promise<AIMessageAnalysis> {
    try {
      const systemPrompt = this.getSystemPrompt(options?.task);
      const userPrompt = this.formatUserMessage(message, options?.context);

      const response = await this.client.chat.completions.create({
        model: this.config.model!,
        temperature: this.config.temperature,
        max_tokens: this.config.maxTokens,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        response_format: { type: "json_object" },
      });

      const content = response.choices[0]?.message?.content;
      if (!content) {
        throw new Error("No response content from OpenAI");
      }

      return this.parseAIResponse(content);
    } catch (error) {
      console.error("OpenAI analysis failed:", error);
      throw new Error(
        `AI analysis failed: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  async generateText(
    prompt: string,
    options?: { temperature?: number; maxTokens?: number },
  ): Promise<string> {
    try {
      const response = await this.client.chat.completions.create({
        model: this.config.model!,
        temperature: options?.temperature ?? this.config.temperature,
        max_tokens: options?.maxTokens ?? this.config.maxTokens,
        messages: [{ role: "user", content: prompt }],
      });

      return response.choices[0]?.message?.content || "";
    } catch (error) {
      console.error("OpenAI text generation failed:", error);
      throw new Error(
        `Text generation failed: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  async generateResponse(message: string, context?: any): Promise<string> {
    try {
      const systemPrompt = `You are a helpful AI assistant. Provide clear, concise, and helpful responses.`;

      const response = await this.client.chat.completions.create({
        model: this.config.model!,
        temperature: 0.8,
        max_tokens: 500,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: message },
          ...(context
            ? [
                {
                  role: "system",
                  content: `Context: ${JSON.stringify(context)}`,
                },
              ]
            : []),
        ],
      });

      return (
        response.choices[0]?.message?.content ||
        "I apologize, but I cannot generate a response at this time."
      );
    } catch (error) {
      console.error("OpenAI response generation failed:", error);
      return "I apologize, but I encountered an error while generating a response.";
    }
  }

  updateConfig(newConfig: Partial<OpenAIServiceConfig>): void {
    this.config = { ...this.config, ...newConfig };

    // Recreate client with new config
    this.client = new OpenAI({
      apiKey: this.config.apiKey,
    });
  }

  getConfig(): OpenAIServiceConfig {
    return { ...this.config };
  }

  private getSystemPrompt(task?: string): string {
    const basePrompt = `You are an advanced NLU (Natural Language Understanding) system.
    Analyze the user's message and extract the following information in JSON format:
    - intent: the main purpose or goal of the message
    - confidence: a confidence score between 0.0 and 1.0
    - entities: key-value pairs of extracted information
    - action: what action should be taken (respond, execute_skill, execute_workflow, etc.)
    - parameters: parameters needed for the action
    - workflow: optional workflow name if applicable
    - requiresConfirmation: boolean indicating if confirmation is needed
    - suggestedResponses: array of possible response suggestions
    - context: any additional context information

    Return only valid JSON with these exact field names.`;

    switch (task) {
      case "nlu_analysis":
        return basePrompt;
      case "sentiment_analysis":
        return `${basePrompt} Focus on sentiment analysis and emotional tone.`;
      case "entity_extraction":
        return `${basePrompt} Focus on extracting named entities and detailed information.`;
      default:
        return basePrompt;
    }
  }

  private formatUserMessage(message: string, context?: any): string {
    if (context) {
      return `Message: ${message}\n\nContext: ${JSON.stringify(context)}\n\nPlease analyze this message and context.`;
    }
    return `Message: ${message}\n\nPlease analyze this message.`;
  }

  private parseAIResponse(content: string): AIMessageAnalysis {
    try {
      const parsed = JSON.parse(content);

      // Validate and provide defaults for required fields
      return {
        intent: parsed.intent || "unknown",
        confidence:
          typeof parsed.confidence === "number"
            ? Math.max(0, Math.min(1, parsed.confidence))
            : 0.7,
        entities: parsed.entities || {},
        action: parsed.action || "respond",
        parameters: parsed.parameters || {},
        workflow: parsed.workflow,
        requiresConfirmation: Boolean(parsed.requiresConfirmation),
        suggestedResponses: Array.isArray(parsed.suggestedResponses)
          ? parsed.suggestedResponses
          : ["I need more information to help you with that."],
        context: parsed.context,
      };
    } catch (error) {
      console.error("Failed to parse AI response:", error, "Content:", content);
      throw new Error("Invalid response format from AI service");
    }
  }
}

// Default export for convenience
export default OpenAIService;
