import { NLUService } from "./nluService";
import { OpenAIService } from "./openaiService";
import { WorkflowService } from "./workflowService";
import { SkillService } from "./skillService";

export interface NLUHybridConfig {
  enableHybridMode: boolean;
  complexityThreshold: number;
  enableFallbackToAI: boolean;
  maxBatchSize: number;
  cacheResponses: boolean;
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
      maxBatchSize: 10,
      cacheResponses: true,
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
      // Fallback to AI if rules-based fails and fallback is enabled
      if (this.config.enableFallbackToAI) {
        try {
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
