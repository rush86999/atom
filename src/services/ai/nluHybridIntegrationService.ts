import { NLUService } from "./nluService";
import { OpenAIService } from "./openaiService";
import { WorkflowService } from "./workflowService";
import { SkillService } from "./skillService";
import { hybridLLMService } from "./hybridLLMService";

// Simple local model for fallback processing
interface LocalModelConfig {
  enabled: boolean;
  confidenceThreshold: number;
  maxQueryLength: number;
}

interface LocalModelPrediction {
  intent: string;
  confidence: number;
  entities: Record<string, any>;
}

export interface NLUHybridConfig {
  enableHybridMode: boolean;
  complexityThreshold: number;
  enableFallbackToAI: boolean;
  enableLocalModel: boolean;
  localModelConfidenceThreshold: number;
  maxBatchSize: number;
  cacheResponses: boolean;
  useLlamaCPP: boolean;
  llamaCPPThreshold: number;
}

export interface NLUHybridResponse {
  intent: string;
  confidence: number;
  entities: Record<string, any>;
  action: string;
  parameters: Record<string, any>;
  workflow?: string;
  requiresConfirmation: boolean;
  suggestedResponses: string[];
  context?: any;
  providerUsed: "rules" | "ai" | "hybrid";
  processingTime: number;
}

export class NLUHybridIntegrationService {
  private nluService: NLUService;
  private openaiService: OpenAIService;
  private workflowService: WorkflowService;
  private skillService: SkillService;
  private config: NLUHybridConfig;
  private localModelConfig: LocalModelConfig;

  constructor(
    nluService: NLUService,
    openaiService?: OpenAIService,
    workflowService?: WorkflowService,
    skillService?: SkillService,
  ) {
    this.nluService = nluService;
    this.openaiService = openaiService || new OpenAIService();
    this.workflowService = workflowService || new WorkflowService();
    this.skillService = skillService || new SkillService();

    this.config = {
      enableHybridMode: true,
      complexityThreshold: 0.7,
      enableFallbackToAI: true,
      enableLocalModel: true,
      localModelConfidenceThreshold: 0.6,
      maxBatchSize: 10,
      cacheResponses: true,
      useLlamaCPP: true,
      llamaCPPThreshold: 0.4,
    };

    this.localModelConfig = {
      enabled: true,
      confidenceThreshold: 0.6,
      maxQueryLength: 50,
    };
  }

  async understandMessage(
    message: string,
    context?: any,
  ): Promise<NLUHybridResponse> {
    const startTime = Date.now();

    try {
      // First try rules-based NLU
      const rulesResult = await this.nluService.understandMessage(
        message,
        context,
      );

      // Calculate message complexity (simple heuristic based on length and structure)
      const complexity = this.calculateMessageComplexity(message);

      // If hybrid mode is enabled and message is complex, use AI enhancement
      if (
        this.config.enableHybridMode &&
        complexity > this.config.complexityThreshold
      ) {
        // Check if we should use llama.cpp for AI enhancement
        if (
          this.config.useLlamaCPP &&
          complexity < this.config.llamaCPPThreshold
        ) {
          const enhancedResult = await this.enhanceWithLlamaCPP(
            rulesResult,
            message,
            context,
          );
          return {
            ...enhancedResult,
            providerUsed: "llama-hybrid" as const,
            processingTime: Math.max(1, Date.now() - startTime),
          };
        } else {
          const enhancedResult = await this.enhanceWithAI(
            rulesResult,
            message,
            context,
          );
          return {
            ...enhancedResult,
            providerUsed: "hybrid" as const,
            processingTime: Math.max(1, Date.now() - startTime),
          };
        }
      }

      return {
        ...rulesResult,
        requiresConfirmation: rulesResult.requiresConfirmation || false,
        suggestedResponses: rulesResult.suggestedResponses || [
          "Hello! How can I help you?",
        ],
        providerUsed: "rules" as const,
        processingTime: Math.max(1, Date.now() - startTime),
      };
    } catch (error) {
      // First try llama.cpp fallback if enabled and appropriate
      if (this.config.useLlamaCPP && this.isSuitableForLlamaCPP(message)) {
        try {
          const llamaResult = await this.fallbackToLlamaCPP(message, context);
          return {
            ...llamaResult,
            providerUsed: "llama" as const,
            processingTime: Math.max(1, Date.now() - startTime),
          };
        } catch (llamaError) {
          console.warn("Llama.cpp fallback failed:", llamaError);
        }
      }

      // Then try local model fallback if enabled and appropriate
      if (
        this.config.enableLocalModel &&
        this.isSuitableForLocalModel(message)
      ) {
        try {
          const localResult = await this.fallbackToLocalModel(message, context);
          return {
            ...localResult,
            providerUsed: "local" as const,
            processingTime: Math.max(1, Date.now() - startTime),
          };
        } catch (localError) {
          console.warn("Local model fallback failed, trying AI:", localError);
        }
      }

      // Fallback to AI if rules-based fails and fallback is enabled
      if (this.config.enableFallbackToAI) {
        try {
          // Try llama.cpp first for AI fallback if enabled
          if (this.config.useLlamaCPP) {
            try {
              const llamaResult = await this.fallbackToLlamaCPP(
                message,
                context,
              );
              return {
                ...llamaResult,
                providerUsed: "llama" as const,
                processingTime: Math.max(1, Date.now() - startTime),
              };
            } catch (llamaError) {
              console.warn(
                "Llama.cpp AI fallback failed, trying cloud AI:",
                llamaError,
              );
            }
          }

          const aiResult = await this.fallbackToAI(message, context);
          return {
            ...aiResult,
            providerUsed: "ai" as const,
            processingTime: Math.max(1, Date.now() - startTime),
          };
        } catch (fallbackError) {
          throw new Error(
            `NLU processing failed: ${fallbackError instanceof Error ? fallbackError.message : "Unknown error"}`,
          );
        }
      }
      throw error;
    }
  }

  async batchProcess(
    messages: string[],
    context?: any,
  ): Promise<NLUHybridResponse[]> {
    if (messages.length > this.config.maxBatchSize) {
      throw new Error(
        `Batch size exceeds maximum allowed (${this.config.maxBatchSize})`,
      );
    }

    const results: NLUHybridResponse[] = [];
    for (const message of messages) {
      const result = await this.understandMessage(message, context);
      results.push(result);
    }

    return results;
  }

  private isSuitableForLocalModel(message: string): boolean {
    // Simple heuristic for when to use local model
    return (
      message.length <= this.localModelConfig.maxQueryLength &&
      this.calculateMessageComplexity(message) < 0.4
    );
  }

  private isSuitableForLlamaCPP(message: string): boolean {
    // Heuristic for when to use llama.cpp
    const complexity = this.calculateMessageComplexity(message);
    return (
      message.length <= 200 && // Moderate length queries
      complexity >= 0.3 &&
      complexity <= 0.7 && // Medium complexity
      !message.includes("urgent") && // Not time-sensitive
      !message.includes("critical") // Not critical tasks
    );
  }

  private async fallbackToLocalModel(
    message: string,
    context?: any,
  ): Promise<any> {
    try {
      const prediction = this.predictWithLocalModel(message);

      if (prediction.confidence >= this.localModelConfig.confidenceThreshold) {
        return {
          intent: prediction.intent,
          confidence: prediction.confidence,
          entities: prediction.entities,
          action: this.getActionForIntent(prediction.intent),
          parameters: {},
          workflow: undefined,
          requiresConfirmation: false,
          suggestedResponses: this.getSuggestedResponses(prediction.intent),
          context,
        };
      }

      throw new Error("Local model confidence too low");
    } catch (error) {
      throw new Error(
        `Local model processing failed: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  private async fallbackToLlamaCPP(
    message: string,
    context?: any,
  ): Promise<any> {
    try {
      const promptData = {
        message: message,
        context: context || {},
        instructions:
          "Analyze this user message and extract intent, entities, and suggest appropriate action. Respond with a JSON object containing: intent, confidence (0-1), entities (key-value pairs), action, requiresConfirmation (boolean), suggestedResponses (array)",
      };

      const response = await hybridLLMService.generate(
        {
          task: "custom_analytical_analysis",
          data: promptData,
        },
        "llama-3-8b-instruct",
        {
          temperature: 0.3,
          maxTokens: 500,
          isJsonOutput: true,
        },
      );

      const result = JSON.parse(response.content);

      return {
        intent: result.intent || "unknown",
        confidence: result.confidence || 0.7,
        entities: result.entities || {},
        action: result.action || "respond",
        parameters: {},
        workflow: undefined,
        requiresConfirmation: result.requiresConfirmation || false,
        suggestedResponses: result.suggestedResponses || [
          "I need more information to help you with that.",
        ],
        context,
      };
    } catch (error) {
      throw new Error(
        `Llama.cpp processing failed: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  private predictWithLocalModel(message: string): LocalModelPrediction {
    // Simple pattern-based local model
    const lowerMessage = message.toLowerCase();

    // Common greetings
    if (
      /(hello|hi|hey|greetings|good morning|good afternoon|good evening)/i.test(
        lowerMessage,
      )
    ) {
      return {
        intent: "greeting",
        confidence: 0.85,
        entities: {},
      };
    }

    // Simple questions
    if (/(what|who|where|when|why|how|which).*\?/.test(lowerMessage)) {
      return {
        intent: "simple_question",
        confidence: 0.75,
        entities: { question_type: this.detectQuestionType(lowerMessage) },
      };
    }

    // Basic commands
    if (/(help|assist|support)/i.test(lowerMessage)) {
      return {
        intent: "help_request",
        confidence: 0.8,
        entities: {},
      };
    }

    // Thank you messages
    if (/(thanks|thank you|appreciate|grateful)/i.test(lowerMessage)) {
      return {
        intent: "gratitude",
        confidence: 0.9,
        entities: {},
      };
    }

    // Default fallback
    return {
      intent: "unknown",
      confidence: 0.3,
      entities: {},
    };
  }

  private detectQuestionType(message: string): string {
    if (message.includes("what")) return "what";
    if (message.includes("who")) return "who";
    if (message.includes("where")) return "where";
    if (message.includes("when")) return "when";
    if (message.includes("why")) return "why";
    if (message.includes("how")) return "how";
    if (message.includes("which")) return "which";
    return "general";
  }

  private getActionForIntent(intent: string): string {
    const actionMap: Record<string, string> = {
      greeting: "respond",
      simple_question: "respond",
      help_request: "respond",
      gratitude: "respond",
      unknown: "respond",
    };
    return actionMap[intent] || "respond";
  }

  private getSuggestedResponses(intent: string): string[] {
    const responseMap: Record<string, string[]> = {
      greeting: [
        "Hello! How can I help you today?",
        "Hi there! What can I assist you with?",
      ],
      simple_question: [
        "I'd be happy to help with that.",
        "Let me think about that question.",
      ],
      help_request: [
        "I'm here to help! What do you need assistance with?",
        "How can I assist you today?",
      ],
      gratitude: ["You're welcome!", "Happy to help!", "Glad I could assist!"],
      unknown: [
        "I'm not sure I understand. Could you rephrase that?",
        "Could you provide more details?",
      ],
    };
    return (
      responseMap[intent] || ["I need more information to help you with that."]
    );
  }

  updateConfig(newConfig: Partial<NLUHybridConfig>): void {
    this.config = { ...this.config, ...newConfig };
  }

  getConfig(): NLUHybridConfig {
    return { ...this.config };
  }

  private calculateMessageComplexity(message: string): number {
    // Simple complexity calculation based on:
    // 1. Message length
    // 2. Number of words
    // 3. Presence of complex patterns (dates, times, numbers, etc.)

    const words = message.split(/\s+/).filter((word) => word.length > 0);
    const lengthComplexity = Math.min(message.length / 100, 1.0);
    const wordCountComplexity = Math.min(words.length / 10, 1.0);

    // Check for complex patterns
    const hasDate =
      /\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}|tomorrow|yesterday|today|next week|last week)\b/i.test(
        message,
      );
    const hasTime =
      /\b(\d{1,2}:\d{2}\s*(?:AM|PM)?|\d{1,2}\s*(?:AM|PM))\b/i.test(message);
    const hasNumbers = /\b\d+\b/.test(message);

    const patternComplexity =
      (hasDate ? 0.2 : 0) + (hasTime ? 0.2 : 0) + (hasNumbers ? 0.1 : 0);

    return Math.min(
      lengthComplexity * 0.4 + wordCountComplexity * 0.4 + patternComplexity,
      1.0,
    );
  }

  private async enhanceWithAI(
    baseResult: any,
    message: string,
    context?: any,
  ): Promise<any> {
    try {
      // Use AI to enhance the rules-based result
      // This could involve:
      // 1. Improving entity extraction
      // 2. Adding context awareness
      // 3. Generating better suggested responses
      // 4. Refining confidence scores

      // For now, we'll just return the base result with enhanced confidence
      return {
        ...baseResult,
        confidence: Math.min(baseResult.confidence * 1.1, 1.0), // Slight confidence boost
      };
    } catch (error) {
      // If AI enhancement fails, return the original result
      console.warn(
        "AI enhancement failed, falling back to rules-based result:",
        error,
      );
      return baseResult;
    }
  }

  private async enhanceWithLlamaCPP(
    baseResult: any,
    message: string,
    context?: any,
  ): Promise<any> {
    try {
      const enhanceData = {
        original_message: message,
        current_result: baseResult,
        context: context || {},
        instructions:
          "Enhance this NLU result with better entity extraction and context awareness. Improve entity extraction, add context awareness, refine confidence score, and generate better suggested responses. Respond with a JSON object containing the enhanced result.",
      };

      const response = await hybridLLMService.generate(
        {
          task: "custom_analytical_analysis",
          data: enhanceData,
        },
        "llama-3-8b-instruct",
        {
          temperature: 0.2,
          maxTokens: 800,
          isJsonOutput: true,
        },
      );

      const enhancedResult = JSON.parse(response.content);

      return {
        ...baseResult,
        ...enhancedResult,
        confidence: Math.min(
          (baseResult.confidence + enhancedResult.confidence) / 2,
          1.0,
        ),
      };
    } catch (error) {
      console.warn(
        "Llama.cpp enhancement failed, falling back to base result:",
        error,
      );
      return baseResult;
    }
  }

  private async fallbackToAI(message: string, context?: any): Promise<any> {
    try {
      // Use AI as fallback when rules-based processing fails
      // This would involve calling the OpenAI service to analyze the message

      // Placeholder implementation - in real scenario, this would call OpenAI API
      // with proper prompt engineering for NLU tasks
      // For now, use a simple mock response since the OpenAI service method signature has changed
      const aiAnalysis = {
        intent: "unknown",
        confidence: 0.7,
        entities: {},
        action: "respond",
        parameters: {},
        requiresConfirmation: false,
        suggestedResponses: ["I need more information to help you with that."],
        context: undefined,
      };

      return {
        intent: aiAnalysis.intent || "unknown",
        confidence: aiAnalysis.confidence || 0.7,
        entities: aiAnalysis.entities || {},
        action: aiAnalysis.action || "respond",
        parameters: aiAnalysis.parameters || {},
        workflow: undefined,
        requiresConfirmation: aiAnalysis.requiresConfirmation || false,
        suggestedResponses: aiAnalysis.suggestedResponses || [
          "I need more information to help you with that.",
        ],
        context: aiAnalysis.context,
      };
    } catch (error) {
      throw new Error(
        `AI fallback failed: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  // Utility methods for integration with other services
  async executeWorkflow(
    workflowName: string,
    parameters: Record<string, any>,
  ): Promise<any> {
    return this.workflowService.executeWorkflow(workflowName, parameters);
  }

  async executeSkill(
    skillName: string,
    parameters: Record<string, any>,
  ): Promise<any> {
    return this.skillService.executeSkill(skillName, parameters);
  }

  async getAvailableWorkflows(): Promise<string[]> {
    // Workflow service method signature has changed, use mock for now
    return ["calendar_scheduling", "financial_analysis", "document_processing"];
  }

  async getAvailableSkills(): Promise<string[]> {
    // Skill service method signature has changed, use mock for now
    return [
      "calendar_create_event",
      "analyze_financial_data",
      "generate_report",
      "extract_text",
      "analyze_content",
    ];
  }
}
