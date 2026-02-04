import { EventEmitter } from "events";
import axios from "axios";
import { spawn } from "child_process";
import path from "path";
import { v4 as uuidv4 } from "uuid";

interface LLMProvider {
  name: string;
  type:
    | "local"
    | "openai"
    | "openrouter"
    | "gemini"
    | "claude"
    | "moonshot"
    | "custom";
  endpoint: string;
  apiKey?: string;
  models: string[];
  costPerToken?: {
    input: number;
    output: number;
  };
  maxTokens: number;
  supports: string[]; // Types of tasks this provider handles
  rateLimits?: {
    requestsPerMinute?: number;
    tokensPerMinute?: number;
  };
}

interface LLMRequest {
  id: string;
  prompt: string;
  type:
    | "simple"
    | "creative"
    | "complex_planning"
    | "analysis"
    | "translation"
    | "generation";
  context?: Record<string, any>;
  endpoint?: string;
  model?: string;
  maxTokens?: number;
  temperature?: number;
}

interface LLMResponse {
  content: string;
  tokens: {
    input: number;
    output: number;
  };
  provider: string;
  model: string;
  cost: number;
  processingTime: number;
  cached?: boolean;
}

interface ComplexityScorer {
  textLength: number;
  requiresReasoning: boolean;
  creativityNeeded: boolean;
  domainSpecific: boolean;
  timeSensitivity: number;
}

export class UniversalLLMProvider extends EventEmitter {
  private providers: Map<string, LLMProvider> = new Map();
  private activeRequests: Map<string, LLMRequest> = new Map();
  private costTracker = { total: 0, byProvider: new Map() };
  private fallbackChain: string[] = [];
  private localModels: Map<string, any> = new Map();
  private cache = new Map<string, LLMResponse>();

  private config = {
    defaultTemperature: 0.7,
    maxRetries: 3,
    cacheTTL: 300000, // 5 minutes
    enableCostTracking: true,
  };

  constructor() {
    super();
    this.initializeProviders();
    this.setupLlamaCPP();
  }

  private initializeProviders() {
    // OpenAI Providers
    this.providers.set("openai-gpt4", {
      name: "OpenAI GPT-4",
      type: "openai",
      endpoint: "https://api.openai.com/v1/chat/completions",
      models: [
        "gpt-4-0125-preview",
        "gpt-4-1106-preview",
        "gpt-4",
        "gpt-4-turbo",
      ],
      costPerToken: { input: 0.03, output: 0.06 },
      maxTokens: 8192,
      supports: [
        "complex_planning",
        "creative",
        "analysis",
        "translation",
        "generation",
      ],
    });

    this.providers.set("openai-gpt3", {
      name: "OpenAI GPT-3.5",
      type: "openai",
      endpoint: "https://api.openai.com/v1/chat/completions",
      models: ["gpt-3.5-turbo-0125", "gpt-3.5-turbo-1106"],
      costPerToken: { input: 0.0015, output: 0.002 },
      maxTokens: 4096,
      supports: ["simple", "translation", "generation"],
    });

    // OpenRouter (Universal access)
    this.providers.set("openrouter-llama", {
      name: "OpenRouter Llama-2-70B",
      type: "openrouter",
      endpoint: "https://openrouter.ai/api/v1/chat/completions",
      models: [
        "meta-llama/llama-2-70b-chat",
        "mistralai/mistral-7b-instruct",
        "anthropic/claude-3-sonnet",
        "google/palm-2-chat-bison",
      ],
      costPerToken: { input: 0.0007, output: 0.0013 },
      maxTokens: 4096,
      supports: ["analysis", "creative", "planning"],
    });

    // Google Gemini
    this.providers.set("gemini-pro", {
      name: "Google Gemini Pro",
      type: "gemini",
      endpoint:
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
      models: ["gemini-pro", "gemini-pro-vision"],
      costPerToken: { input: 0.0005, output: 0.0015 },
      maxTokens: 32768,
      supports: ["creative", "analysis", "multimodal", "generation"],
    });

    // Anthropic Claude
    this.providers.set("claude-opus", {
      name: "Claude 3 Opus",
      type: "claude",
      endpoint: "https://api.anthropic.com/v1/messages",
      models: [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
      ],
      costPerToken: { input: 0.015, output: 0.075 },
      maxTokens: 4096,
      supports: ["complex_planning", "analysis", "creative", "reasoning"],
    });

    // MoonShot AI
    this.providers.set("moonshot-v1", {
      name: "MoonShot AI",
      type: "moonshot",
      endpoint: "https://api.moonshot.cn/v1/chat/completions",
      models: ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
      costPerToken: { input: 0.012, output: 0.012 },
      maxTokens: 128000,
      supports: ["analysis", "creative", "long_context", "planning"],
    });

    // Local llama.cpp models
    this.providers.set("llama-local-8b", {
      name: "Llama 3 8B Local",
      type: "local",
      endpoint: "http://localhost:8080/completion",
      models: ["llama-3-8b-instruct"],
      maxTokens: 4096,
      supports: ["simple", "translation", "basic_analysis"],
    });

    this.providers.set("llama-local-70b", {
      name: "Llama 3 70B Local",
      type: "local",
      endpoint: "http://localhost:8080/completion",
      models: ["llama-3-70b-instruct"],
      maxTokens: 8192,
      supports: ["analysis", "creative", "planning"],
    });

    // Set fallback chain
    this.fallbackChain = [
      "openai-gpt4",
      "claude-opus",
      "openrouter-llama",
      "gemini-pro",
      "moonshot-v1",
      "llama-local-70b",
      "llama-local-8b",
      "openai-gpt3",
    ];
  }

  private setupLlamaCPP() {
    // This would setup local llama.cpp server if available
    // For now, we assume it's running on localhost:8080
    console.log("Llama.cpp setup: assuming server running on localhost:8080");
  }

  private calculateComplexity(
    prompt: string,
    context?: Record<string, any>,
  ): number {
    const scorer: ComplexityScorer = {
      textLength: prompt.length,
      requiresReasoning:
        prompt.includes("why") ||
        prompt.includes("how") ||
        prompt.includes("analyze"),
      creativityNeeded:
        prompt.includes("creative") ||
        prompt.includes("imagine") ||
        prompt.includes("generate"),
      domainSpecific: context?.domain !== undefined,
      timeSensitivity: context?.urgent ? 0.9 : 0.1,
    };

    let score = 0;
    score += Math.min(scorer.textLength / 1000, 1) * 0.2;
    score += scorer.requiresReasoning ? 0.3 : 0;
    score += scorer.creativityNeeded ? 0.2 : 0;
    score += scorer.domainSpecific ? 0.2 : 0;
    score += scorer.timeSensitivity * 0.1;

    return Math.min(score, 1);
  }

  private selectProvider(requestType: string, complexity: number): LLMProvider {
    // Find providers that support this request type
    const supportedProviders = Array.from(this.providers.values()).filter(
      (provider) => provider.supports.includes(requestType),
    );

    if (supportedProviders.length === 0) {
      throw new Error(`No providers support request type: ${requestType}`);
    }

    // Sort by capability (local last, cloud first for complex tasks)
    supportedProviders.sort((a, b) => {
      if (a.type === "local" && b.type !== "local") return 1;
      if (a.type !== "local" && b.type === "local") return -1;
      return 0;
    });

    // For complex tasks, prefer more capable models
    if (complexity > 0.7) {
      return (
        supportedProviders.find((p) =>
          p.models.some((m) => m.includes("gpt-4") || m.includes("opus")),
        ) || supportedProviders[0]
      );
    }

    // For simple tasks, prefer cheaper/local options
    if (complexity < 0.3) {
      return (
        supportedProviders.find((p) => p.type === "local") ||
        supportedProviders.find((p) =>
          p.models.some((m) => m.includes("gpt-3.5")),
        ) ||
        supportedProviders[0]
      );
    }

    return supportedProviders[0];
  }

  private async callOpenAI(
    provider: LLMProvider,
    request: LLMRequest,
  ): Promise<LLMResponse> {
    const model = request.model || provider.models[0];
    const apiKey = provider.apiKey || process.env.OPENAI_API_KEY;

    if (!apiKey) {
      throw new Error("OpenAI API key not found");
    }

    const startTime = Date.now();

    try {
      const response = await axios.post(
        provider.endpoint,
        {
          model,
          messages: [{ role: "user", content: request.prompt }],
          max_tokens: request.maxTokens || provider.maxTokens,
          temperature: request.temperature || this.config.defaultTemperature,
        },
        {
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
        },
      );

      const content = response.data.choices[0].message.content;
      const tokens = {
        input:
          response.data.usage?.prompt_tokens ||
          Math.ceil(request.prompt.length / 4),
        output:
          response.data.usage?.completion_tokens ||
          Math.ceil(content.length / 4),
      };

      const cost =
        tokens.input * (provider.costPerToken?.input || 0) +
        tokens.output * (provider.costPerToken?.output || 0);

      return {
        content,
        tokens,
        provider: provider.name,
        model,
        cost,
        processingTime: Date.now() - startTime,
      };
    } catch (error) {
      throw new Error(`OpenAI API call failed: ${error.message}`);
    }
  }

  private async callLocalLlama(
    provider: LLMProvider,
    request: LLMRequest,
  ): Promise<LLMResponse> {
    const startTime = Date.now();

    try {
      const response = await axios.post(provider.endpoint, {
        prompt: request.prompt,
        n_predict: request.maxTokens || provider.maxTokens,
        temperature: request.temperature || this.config.defaultTemperature,
      });

      const content = response.data.content;
      const tokens = {
        input: Math.ceil(request.prompt.length / 4),
        output: Math.ceil(content.length / 4),
      };

      return {
        content,
        tokens,
        provider: provider.name,
        model: provider.models[0],
        cost: 0, // Local models have no cost
        processingTime: Date.now() - startTime,
      };
    } catch (error) {
      throw new Error(`Local llama.cpp call failed: ${error.message}`);
    }
  }

  private async callGenericAPI(
    provider: LLMProvider,
    request: LLMRequest,
  ): Promise<LLMResponse> {
    const model = request.model || provider.models[0];
    const apiKey =
      provider.apiKey || process.env[`${provider.type.toUpperCase()}_API_KEY`];

    if (!apiKey) {
      throw new Error(`${provider.type} API key not found`);
    }

    const startTime = Date.now();

    try {
      const response = await axios.post(
        provider.endpoint,
        {
          model,
          messages: [{ role: "user", content: request.prompt }],
          max_tokens: request.maxTokens || provider.maxTokens,
          temperature: request.temperature || this.config.defaultTemperature,
        },
        {
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
        },
      );

      const content =
        response.data.choices?.[0]?.message?.content ||
        response.data.candidates?.[0]?.content?.parts?.[0]?.text ||
        response.data.content;

      const tokens = {
        input:
          response.data.usage?.prompt_tokens ||
          Math.ceil(request.prompt.length / 4),
        output:
          response.data.usage?.completion_tokens ||
          Math.ceil(content.length / 4),
      };

      const cost =
        tokens.input * (provider.costPerToken?.input || 0) +
        tokens.output * (provider.costPerToken?.output || 0);

      return {
        content,
        tokens,
        provider: provider.name,
        model,
        cost,
        processingTime: Date.now() - startTime,
      };
    } catch (error) {
      throw new Error(`${provider.type} API call failed: ${error.message}`);
    }
  }

  async processRequest(request: LLMRequest): Promise<LLMResponse> {
    const requestId = uuidv4();
    this.activeRequests.set(requestId, request);

    try {
      // Check cache first
      const cacheKey = `${request.type}:${request.prompt.substring(0, 100)}`;
      const cachedResponse = this.cache.get(cacheKey);

      if (
        cachedResponse &&
        Date.now() - cachedResponse.processingTime < this.config.cacheTTL
      ) {
        this.emit("cache-hit", { requestId, cacheKey });
        return { ...cachedResponse, cached: true };
      }

      const complexity = this.calculateComplexity(
        request.prompt,
        request.context,
      );
      let selectedProvider = this.selectProvider(request.type, complexity);

      // Try providers in fallback chain
      for (const providerId of this.fallbackChain) {
        const provider = this.providers.get(providerId);
        if (provider && provider.supports.includes(request.type)) {
          selectedProvider = provider;
          break;
        }
      }

      let response: LLMResponse;

      switch (selectedProvider.type) {
        case "openai":
          response = await this.callOpenAI(selectedProvider, request);
          break;
        case "local":
          response = await this.callLocalLlama(selectedProvider, request);
          break;
        default:
          response = await this.callGenericAPI(selectedProvider, request);
          break;
      }

      // Update cost tracking
      if (this.config.enableCostTracking) {
        this.costTracker.total += response.cost;
        const providerCost =
          this.costTracker.byProvider.get(selectedProvider.name) || 0;
        this.costTracker.byProvider.set(
          selectedProvider.name,
          providerCost + response.cost,
        );
      }

      // Cache the response
      this.cache.set(cacheKey, response);

      this.emit("request-complete", {
        requestId,
        response,
        provider: selectedProvider.name,
      });
      return response;
    } catch (error) {
      this.emit("request-failed", { requestId, error: error.message });
      throw error;
    } finally {
      this.activeRequests.delete(requestId);
    }
  }

  async batchProcess(requests: LLMRequest[]): Promise<LLMResponse[]> {
    return Promise.all(requests.map((req) => this.processRequest(req)));
  }

  getCostStats(): { total: number; byProvider: Map<string, number> } {
    return this.costTracker;
  }

  clearCache(): void {
    this.cache.clear();
  }

  addProvider(providerId: string, provider: LLMProvider): void {
    this.providers.set(providerId, provider);
  }

  removeProvider(providerId: string): void {
    this.providers.delete(providerId);
  }

  getProvider(providerId: string): LLMProvider | undefined {
    return this.providers.get(providerId);
  }

  listProviders(): LLMProvider[] {
    return Array.from(this.providers.values());
  }

  setFallbackChain(chain: string[]): void {
    this.fallbackChain = chain;
  }

  getActiveRequests(): number {
    return this.activeRequests.size;
  }
}

// Export singleton instance
export const universalLLMProvider = new UniversalLLMProvider();
