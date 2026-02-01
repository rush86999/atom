import { EventEmitter } from "events";
import axios from "axios";
import { spawn } from "child_process";
import path from "path";
import fs from "fs";
import { v4 as uuidv4 } from "uuid";

interface LLMCallTask {
  id: string;
  type:
    | "simple_intent"
    | "complex_planning"
    | "creative_generation"
    | "detailed_analysis"
    | "translation"
    | "validation";
  prompt: string;
  priority: "low" | "medium" | "high";
  context?: Record<string, any>;
  callback?: (response: string) => void;
}

interface LLMProvider {
  name: string;
  type: "local" | "cloud";
  modelSize: string;
  costPerToken?: number;
  maxTokens: number;
  supports: string[];
}

interface LlamaContext {
  path: string;
  model: string;
  contextSize: number;
  gpuLayers: number;
}

interface HybridLLMResponse {
  content: string;
  provider: string;
  modelUsed: string;
  tokensUsed: number;
  processingTime: number;
  cost: number;
  confidence: number;
}

interface ComplexityScorer {
  textLength: number;
  creativityRequired: boolean;
  domainExpertiseRequired: boolean;
  calculationNeeded: boolean;
  smallBizContext: boolean;
}

export class HybridLLMRouter extends EventEmitter {
  private providers: Map<string, LLMProvider> = new Map();
  private localLlama: LlamaContext | null = null;
  private activeTasks: Map<string, LLMCallTask> = new Map();
  private metrics: Map<string, any> = new Map();
  private costTracker = { total: 0, breakdown: new Map() };
  private config = {
    cacheMutex: new Map(),
    enableLoRA: false,
    temperature: 0.7,
    top_p: 0.9,
    typical_p: 1.0,
    presence_penalty: 0.0,
    frequency_penalty: 0.0,
  };
  private thresholds = {
    simple: 0.3,
    creative: 0.7,
    complex: 0.9,
  };

  constructor() {
    super();
    this.initializeProviders();
    this.setupLlamaCPP();
  }

  private initializeProviders() {
    // Local llama.cpp models for specific tasks
    this.providers.set("llama-local-8b", {
      name: "Llama-3B-8B-Small-Biz",
      type: "local",
      modelSize: "8B",
      maxTokens: 4096,
      supports: [
        "intent_detection",
        "simple_routing",
        "basic_automation",
        "small_biz_workflows",
      ],
    });

    this.providers.set("llama-local-full", {
      name: "Llama-SmallBiz-V2-13B",
      type: "local",
      modelSize: "13B",
      maxTokens: 8192,
      supports: ["planning", "analysis", "complex_workflows"],
    });

    // Cloud providers for advanced tasks
    this.providers.set("gpt-4", {
      name: "OpenAI GPT-4",
      type: "cloud",
      modelSize: "Large",
      costPerToken: 0.001,
      maxTokens: 8192,
      supports: ["creative", "planning", "analysis", "complex_reasoning"],
    });

    this.providers.set("claude-opus", {
      name: "Claude-3-Opus",
      type: "cloud",
      modelSize: "Large",
      costPerToken: 0.0008,
      maxTokens: 200000,
      supports: ["creative", "analysis", "document_processing", "long_context"],
    });

    this.providers.set("gemini-pro", {
      name: "Gemini-1.5-Pro",
      type: "cloud",
      modelSize: "Large",
      costPerToken: 0.0005,
      maxTokens: 1000000,
      supports: ["multimodal", "creative", "analysis", "planning"],
    });

    this.providers.set("moonshot-v1", {
      name: "MoonShot AI",
      type: "cloud",
      modelSize: "Large",
      costPerToken: 0.012,
      maxTokens: 128000,
      supports: ["analysis", "creative", "long_context", "planning"],
    });

    this.providers.set("openrouter-llama", {
      name: "OpenRouter Llama-2-70B",
      type: "cloud",
      modelSize: "70B",
      costPerToken: 0.0007,
      maxTokens: 4096,
      supports: ["analysis", "creative", "planning"],
    });
  }

  private setupLlamaCPP() {
    const llamaPath = process.env.LLAMA_CPP_PATH || "/opt/llama.cpp";
    const modelPath = process.env.LLAMA_MODEL_PATH || "./models";

    this.localLlama = {
      path: llamaPath,
      model: path.join(modelPath, "llama-3.2-8b-instruct.s.gguf"),
      contextSize: 4096,
      gpuLayers: 28, // Use GPU for speed
    };
  }

  private calculateComplexity(
    text: string,
    context?: Record<string, any>,
  ): number {
    const scorer: ComplexityScorer = {
      textLength: text.length,
      creativityRequired:
        text.includes("creative") ||
        text.includes("imagine") ||
        text.includes("generate"),
      domainExpertiseRequired: context?.domain !== undefined,
      calculationNeeded:
        text.includes("calculate") ||
        text.includes("analyze") ||
        text.includes("compare"),
      smallBizContext: context?.businessContext === true,
    };

    let score = 0;
    score += Math.min(scorer.textLength / 1000, 1) * 0.2;
    score += scorer.creativityRequired ? 0.3 : 0;
    score += scorer.domainExpertiseRequired ? 0.2 : 0;
    score += scorer.calculationNeeded ? 0.2 : 0;
    score += scorer.smallBizContext ? 0.1 : 0;

    return Math.min(score, 1);
  }

  private selectProvider(taskType: string, complexity: number): LLMProvider {
    const supportedProviders = Array.from(this.providers.values()).filter(
      (provider) => provider.supports.includes(taskType),
    );

    if (supportedProviders.length === 0) {
      throw new Error(`No providers support task type: ${taskType}`);
    }

    // For simple tasks, prefer local models
    if (complexity < this.thresholds.simple) {
      const localProvider = supportedProviders.find((p) => p.type === "local");
      if (localProvider) return localProvider;
    }

    // For creative tasks, prefer cloud providers
    if (complexity > this.thresholds.creative) {
      const cloudProvider = supportedProviders.find(
        (p) => p.type === "cloud" && p.supports.includes("creative"),
      );
      if (cloudProvider) return cloudProvider;
    }

    // For complex tasks, prefer the most capable provider
    if (complexity > this.thresholds.complex) {
      return (
        supportedProviders.find((p) => p.modelSize === "Large") ||
        supportedProviders[0]
      );
    }

    // Default to first supported provider
    return supportedProviders[0];
  }

  private async callLocalLlama(
    prompt: string,
    maxTokens: number,
  ): Promise<string> {
    if (!this.localLlama) {
      throw new Error("Local llama.cpp not configured");
    }

    try {
      const response = await axios.post("http://localhost:8080/completion", {
        prompt,
        n_predict: maxTokens,
        temperature: this.config.temperature,
        top_p: this.config.top_p,
      });

      return response.data.content;
    } catch (error) {
      throw new Error(`Local llama.cpp call failed: ${error.message}`);
    }
  }

  private async callCloudProvider(
    provider: LLMProvider,
    prompt: string,
    maxTokens: number,
  ): Promise<string> {
    const apiKey =
      process.env[`${provider.name.toUpperCase().replace(/-/g, "_")}_API_KEY`];

    if (!apiKey) {
      throw new Error(`API key not found for ${provider.name}`);
    }

    try {
      let endpoint = provider.name.toLowerCase().includes("openai")
        ? "https://api.openai.com/v1/chat/completions"
        : provider.name.toLowerCase().includes("claude")
          ? "https://api.anthropic.com/v1/messages"
          : provider.name.toLowerCase().includes("gemini")
            ? "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
            : provider.name.toLowerCase().includes("moonshot")
              ? "https://api.moonshot.cn/v1/chat/completions"
              : "https://openrouter.ai/api/v1/chat/completions";

      const response = await axios.post(
        endpoint,
        {
          model: provider.name.toLowerCase().includes("gpt")
            ? "gpt-4"
            : provider.name.toLowerCase().includes("claude")
              ? "claude-3-opus-20240229"
              : provider.name.toLowerCase().includes("gemini")
                ? "gemini-pro"
                : provider.name.toLowerCase().includes("moonshot")
                  ? "moonshot-v1-8k"
                  : "meta-llama/llama-2-70b-chat",
          messages: [{ role: "user", content: prompt }],
          max_tokens: maxTokens,
          temperature: this.config.temperature,
        },
        {
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
        },
      );

      return response.data.choices[0].message.content;
    } catch (error) {
      throw new Error(`Cloud provider call failed: ${error.message}`);
    }
  }

  async routeRequest(task: LLMCallTask): Promise<HybridLLMResponse> {
    const taskId = uuidv4();
    this.activeTasks.set(taskId, task);

    const startTime = Date.now();
    const complexity = this.calculateComplexity(task.prompt, task.context);
    const provider = this.selectProvider(task.type, complexity);

    try {
      let content: string;
      let tokensUsed: number;
      let cost = 0;

      if (provider.type === "local") {
        content = await this.callLocalLlama(task.prompt, provider.maxTokens);
        tokensUsed = Math.ceil(content.length / 4); // Approximate token count
      } else {
        content = await this.callCloudProvider(
          provider,
          task.prompt,
          provider.maxTokens,
        );
        tokensUsed = Math.ceil(content.length / 4);
        cost = tokensUsed * (provider.costPerToken || 0);
      }

      const processingTime = Date.now() - startTime;
      const confidence = Math.min(0.95, 1 - complexity * 0.2); // Higher complexity = lower confidence

      const response: HybridLLMResponse = {
        content,
        provider: provider.name,
        modelUsed: provider.modelSize,
        tokensUsed,
        processingTime,
        cost,
        confidence,
      };

      // Update cost tracking
      this.costTracker.total += cost;
      const providerCost = this.costTracker.breakdown.get(provider.name) || 0;
      this.costTracker.breakdown.set(provider.name, providerCost + cost);

      // Update metrics
      this.metrics.set(taskId, {
        type: task.type,
        provider: provider.name,
        complexity,
        processingTime,
        tokensUsed,
        cost,
      });

      this.emit("request_completed", { taskId, response });

      if (task.callback) {
        task.callback(content);
      }

      return response;
    } catch (error) {
      this.emit("request_failed", { taskId, error: error.message });
      throw error;
    } finally {
      this.activeTasks.delete(taskId);
    }
  }

  async batchRoute(tasks: LLMCallTask[]): Promise<HybridLLMResponse[]> {
    return Promise.all(tasks.map((task) => this.routeRequest(task)));
  }

  getMetrics(): Map<string, any> {
    return this.metrics;
  }

  getCostTracking(): { total: number; breakdown: Map<string, number> } {
    return this.costTracker;
  }

  resetMetrics(): void {
    this.metrics.clear();
    this.costTracker.total = 0;
    this.costTracker.breakdown.clear();
  }

  addProvider(providerId: string, provider: LLMProvider): void {
    this.providers.set(providerId, provider);
  }

  removeProvider(providerId: string): void {
    this.providers.delete(providerId);
  }

  listProviders(): LLMProvider[] {
    return Array.from(this.providers.values());
  }

  getActiveTasks(): number {
    return this.activeTasks.size;
  }
}

// Export singleton instance
export const hybridLLMRouter = new HybridLLMRouter();
