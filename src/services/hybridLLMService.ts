import {
  LLMServiceInterface,
  StructuredLLMPrompt,
  LLMServiceResponse,
} from "../lib/llmUtils";
import { EventEmitter } from "events";
import axios from "axios";
import { spawn, exec } from "child_process";
import * as path from "path";
import * as fs from "fs";
import { promisify } from "util";

const execAsync = promisify(exec);

export interface LLMProviderConfig {
  name: string;
  apiKey: string;
  baseURL: string;
  defaultModel: string;
  costPerToken?: {
    input: number;
    output: number;
  };
  maxTokens: number;
  supports: string[];
  priority: number;
}

export interface LocalModelConfig {
  enabled: boolean;
  modelPath: string;
  serverPort: number;
  contextSize: number;
  gpuLayers: number;
  threadCount: number;
  maxPromptLength: number;
  confidenceThreshold: number;
}

export interface HybridLLMConfig {
  providers: LLMProviderConfig[];
  localModel: LocalModelConfig;
  defaultProvider: string;
  fallbackStrategy:
    | "local-first"
    | "api-first"
    | "cost-optimized"
    | "performance-optimized";
  timeout: number;
  maxRetries: number;
  enableCache: boolean;
  cacheTTL: number;
}

export interface LlamaCPPResponse {
  content: string;
  model: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  finish_reason: string;
}

export class HybridLLMService implements LLMServiceInterface {
  private config: HybridLLMConfig;
  private isLocalModelAvailable: boolean = false;
  private serverProcess: any = null;
  private cache: Map<
    string,
    { response: LLMServiceResponse; timestamp: number }
  > = new Map();
  private eventEmitter: EventEmitter = new EventEmitter();

  constructor(config: Partial<HybridLLMConfig> = {}) {
    this.config = {
      providers: config.providers || [],
      localModel: {
        enabled: config.localModel?.enabled ?? true,
        modelPath: config.localModel?.modelPath || "./models/llama.cpp",
        serverPort: config.localModel?.serverPort || 8080,
        contextSize: config.localModel?.contextSize || 4096,
        gpuLayers: config.localModel?.gpuLayers || 0,
        threadCount: config.localModel?.threadCount || 4,
        maxPromptLength: config.localModel?.maxPromptLength || 2048,
        confidenceThreshold: config.localModel?.confidenceThreshold || 0.6,
      },
      defaultProvider: config.defaultProvider || "openai",
      fallbackStrategy: config.fallbackStrategy || "local-first",
      timeout: config.timeout || 30000,
      maxRetries: config.maxRetries || 3,
      enableCache: config.enableCache ?? true,
      cacheTTL: config.cacheTTL || 300000, // 5 minutes
    };

    this.initializeLocalModel();
  }

  private async initializeLocalModel(): Promise<void> {
    if (!this.config.localModel.enabled) {
      console.log("Local model disabled in configuration");
      return;
    }

    try {
      // Check if llama.cpp is available
      this.isLocalModelAvailable = await this.checkLocalModelAvailability();
      console.log(
        `Local model ${this.isLocalModelAvailable ? "available" : "unavailable"}`,
      );

      if (this.isLocalModelAvailable) {
        await this.startLlamaServer();
      }
    } catch (error) {
      console.warn("Local model initialization failed:", error);
      this.isLocalModelAvailable = false;
    }
  }

  private async checkLocalModelAvailability(): Promise<boolean> {
    try {
      // Check if model file exists
      const modelPath = this.config.localModel.modelPath;
      if (!fs.existsSync(modelPath)) {
        console.log(`Model file not found at: ${modelPath}`);
        return false;
      }

      // Check if llama.cpp server binary exists or can be downloaded
      const llamaBinary = await this.getLlamaBinaryPath();
      if (!llamaBinary) {
        console.log("Llama.cpp binary not available");
        return false;
      }

      return true;
    } catch (error) {
      console.warn("Local model availability check failed:", error);
      return false;
    }
  }

  private async getLlamaBinaryPath(): Promise<string | null> {
    const platform = process.platform;
    const arch = process.arch;

    const binaryName =
      platform === "win32" ? "llama-server.exe" : "llama-server";
    const binaryPath = path.join(__dirname, "../../bin/llama.cpp", binaryName);

    if (fs.existsSync(binaryPath)) {
      return binaryPath;
    }

    // Try to download llama.cpp if not available
    try {
      await this.downloadLlamaCPP();
      return fs.existsSync(binaryPath) ? binaryPath : null;
    } catch (error) {
      console.warn("Failed to download llama.cpp:", error);
      return null;
    }
  }

  private async downloadLlamaCPP(): Promise<void> {
    const platform = process.platform;
    const arch = process.arch;
    const binDir = path.join(__dirname, "../../bin/llama.cpp");

    if (!fs.existsSync(binDir)) {
      fs.mkdirSync(binDir, { recursive: true });
    }

    const urls: Record<string, string> = {
      "win32-x64":
        "https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-win-avx2-x64.zip",
      "darwin-arm64":
        "https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-macos-arm64.zip",
      "darwin-x64":
        "https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-macos-x64.zip",
      "linux-x64":
        "https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-ubuntu-x64.zip",
    };

    const downloadUrl = urls[`${platform}-${arch}`];
    if (!downloadUrl) {
      throw new Error(`Unsupported platform: ${platform}-${arch}`);
    }

    console.log(`Downloading llama.cpp from: ${downloadUrl}`);
    // Implementation would download and extract the binary
    // This is a placeholder - actual implementation would use axios and unzipper
  }

  private async startLlamaServer(): Promise<void> {
    try {
      const binaryPath = await this.getLlamaBinaryPath();
      if (!binaryPath) {
        throw new Error("Llama.cpp binary not available");
      }

      const modelPath = this.config.localModel.modelPath;
      const args = [
        "--model",
        modelPath,
        "--port",
        this.config.localModel.serverPort.toString(),
        "--ctx-size",
        this.config.localModel.contextSize.toString(),
        "--n-gpu-layers",
        this.config.localModel.gpuLayers.toString(),
        "--threads",
        this.config.localModel.threadCount.toString(),
        "--log-disable",
      ];

      this.serverProcess = spawn(binaryPath, args);

      this.serverProcess.stdout.on("data", (data: Buffer) => {
        console.log(`Llama.cpp: ${data.toString()}`);
      });

      this.serverProcess.stderr.on("data", (data: Buffer) => {
        console.error(`Llama.cpp error: ${data.toString()}`);
      });

      this.serverProcess.on("close", (code: number) => {
        console.log(`Llama.cpp server process exited with code ${code}`);
        this.isLocalModelAvailable = false;
      });

      // Wait for server to start
      await new Promise((resolve) => setTimeout(resolve, 2000));
      console.log("Llama.cpp server started successfully");
    } catch (error) {
      console.error("Failed to start llama.cpp server:", error);
      this.isLocalModelAvailable = false;
    }
  }

  private async callLocalLlama(
    prompt: string,
    maxTokens: number,
    temperature: number = 0.7,
  ): Promise<LlamaCPPResponse> {
    const url = `http://localhost:${this.config.localModel.serverPort}/completion`;

    try {
      const response = await axios.post(
        url,
        {
          prompt,
          n_predict: maxTokens,
          temperature,
          top_p: 0.9,
          typical_p: 1.0,
          presence_penalty: 0.0,
          frequency_penalty: 0.0,
        },
        {
          timeout: this.config.timeout,
        },
      );

      return response.data;
    } catch (error) {
      throw new Error(
        `Local llama.cpp call failed: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  private async callOpenAI(
    provider: LLMProviderConfig,
    prompt: string,
    maxTokens: number,
    temperature: number = 0.7,
  ): Promise<LLMServiceResponse> {
    try {
      const response = await axios.post(
        `${provider.baseURL}/chat/completions`,
        {
          model: provider.defaultModel,
          messages: [{ role: "user", content: prompt }],
          max_tokens: maxTokens,
          temperature,
        },
        {
          headers: {
            Authorization: `Bearer ${provider.apiKey}`,
            "Content-Type": "application/json",
          },
          timeout: this.config.timeout,
        },
      );

      const content = response.data.choices[0].message.content;
      const tokens = {
        input:
          response.data.usage?.prompt_tokens || Math.ceil(prompt.length / 4),
        output:
          response.data.usage?.completion_tokens ||
          Math.ceil(content.length / 4),
      };

      const cost =
        tokens.input * (provider.costPerToken?.input || 0) +
        tokens.output * (provider.costPerToken?.output || 0);

      return {
        success: true,
        content,
        usage: {
          promptTokens: tokens.input,
          completionTokens: tokens.output,
          totalTokens: tokens.input + tokens.output,
        },
      };
    } catch (error) {
      throw new Error(
        `OpenAI API call failed: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  private calculateMessageComplexity(message: string): number {
    const words = message.split(/\s+/).filter((word) => word.length > 0);
    const lengthComplexity = Math.min(message.length / 100, 1.0);
    const wordCountComplexity = Math.min(words.length / 10, 1.0);

    const hasComplexPatterns =
      /(\b\d+\b|\b\w{10,}\b|@|\#|\$|\%|\^|\&|\*|\(|\)|\-|\+|\=)/.test(message);
    const patternComplexity = hasComplexPatterns ? 0.3 : 0;

    return Math.min(
      lengthComplexity * 0.4 + wordCountComplexity * 0.4 + patternComplexity,
      1.0,
    );
  }

  private shouldUseLocalModel(prompt: string): boolean {
    if (!this.isLocalModelAvailable || !this.config.localModel.enabled) {
      return false;
    }

    const complexity = this.calculateMessageComplexity(prompt);
    return (
      complexity < this.config.localModel.confidenceThreshold &&
      prompt.length <= this.config.localModel.maxPromptLength
    );
  }

  private getCacheKey(prompt: string, model: string): string {
    return `${model}:${prompt.substring(0, 100)}`;
  }

  async generate(
    prompt: StructuredLLMPrompt,
    model: string,
    options?: {
      temperature?: number;
      maxTokens?: number;
      isJsonOutput?: boolean;
      provider?: string;
    },
  ): Promise<LLMServiceResponse> {
    const providerName = options?.provider || this.config.defaultProvider;
    const temperature = options?.temperature || 0.7;
    const maxTokens = options?.maxTokens || 2048;
    const promptText =
      typeof prompt === "string" ? prompt : JSON.stringify(prompt);

    // Check cache first
    const cacheKey = this.getCacheKey(promptText, model);
    if (this.config.enableCache) {
      const cached = this.cache.get(cacheKey);
      if (cached && Date.now() - cached.timestamp < this.config.cacheTTL) {
        return cached.response;
      }
    }

    let retries = 0;
    let lastError: Error | null = null;

    while (retries < this.config.maxRetries) {
      try {
        let response: LLMServiceResponse;

        // Determine which provider to use based on strategy
        if (
          this.shouldUseLocalModel(promptText) &&
          this.config.fallbackStrategy === "local-first"
        ) {
          // Use local llama.cpp
          const llamaResponse = await this.callLocalLlama(
            promptText,
            maxTokens,
            temperature,
          );
          response = {
            success: true,
            content: llamaResponse.content,
            usage: {
              promptTokens: llamaResponse.usage.prompt_tokens,
              completionTokens: llamaResponse.usage.completion_tokens,
              totalTokens: llamaResponse.usage.total_tokens,
            },
          };
        } else {
          // Use cloud provider
          const provider = this.config.providers.find(
            (p) => p.name === providerName,
          );
          if (!provider) {
            throw new Error(`Provider ${providerName} not found`);
          }

          if (provider.name.toLowerCase().includes("openai")) {
            response = await this.callOpenAI(
              provider,
              promptText,
              maxTokens,
              temperature,
            );
          } else {
            // Generic API call for other providers
            response = await this.callGenericAPI(
              provider,
              promptText,
              maxTokens,
              temperature,
            );
          }
        }

        // Cache the response
        if (this.config.enableCache) {
          this.cache.set(cacheKey, {
            response,
            timestamp: Date.now(),
          });
        }

        return response;
      } catch (error) {
        lastError = error as Error;
        retries++;

        if (retries < this.config.maxRetries) {
          // Exponential backoff
          await new Promise((resolve) =>
            setTimeout(resolve, 1000 * Math.pow(2, retries)),
          );
        }
      }
    }

    throw new Error(
      `All retries failed: ${lastError?.message || "Unknown error"}`,
    );
  }

  private async callGenericAPI(
    provider: LLMProviderConfig,
    prompt: string,
    maxTokens: number,
    temperature: number,
  ): Promise<LLMServiceResponse> {
    // Generic implementation for other API providers
    // This would be extended for specific providers like Anthropic, Gemini, etc.
    try {
      const response = await axios.post(
        provider.baseURL,
        {
          model: provider.defaultModel,
          messages: [{ role: "user", content: prompt }],
          max_tokens: maxTokens,
          temperature,
        },
        {
          headers: {
            Authorization: `Bearer ${provider.apiKey}`,
            "Content-Type": "application/json",
          },
          timeout: this.config.timeout,
        },
      );

      const content =
        response.data.choices?.[0]?.message?.content ||
        response.data.candidates?.[0]?.content?.parts?.[0]?.text ||
        response.data.content;

      const tokens = {
        input:
          response.data.usage?.prompt_tokens || Math.ceil(prompt.length / 4),
        output:
          response.data.usage?.completion_tokens ||
          Math.ceil(content.length / 4),
      };

      const cost =
        tokens.input * (provider.costPerToken?.input || 0) +
        tokens.output * (provider.costPerToken?.output || 0);

      return {
        success: true,
        content,
        usage: {
          promptTokens: tokens.input,
          completionTokens: tokens.output,
          totalTokens: tokens.input + tokens.output,
        },
      };
    } catch (error) {
      throw new Error(
        `${provider.name} API call failed: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  async stop(): Promise<void> {
    if (this.serverProcess) {
      this.serverProcess.kill();
      this.serverProcess = null;
    }
    this.isLocalModelAvailable = false;
  }

  getStatus(): { localModelAvailable: boolean; cacheSize: number } {
    return {
      localModelAvailable: this.isLocalModelAvailable,
      cacheSize: this.cache.size,
    };
  }

  clearCache(): void {
    this.cache.clear();
  }

  on(
    event: "localModelStatusChange",
    listener: (available: boolean) => void,
  ): void;
  on(event: "cacheHit", listener: (key: string) => void): void;
  on(event: string, listener: (...args: any[]) => void): void {
    this.eventEmitter.on(event, listener);
  }

  off(event: string, listener: (...args: any[]) => void): void {
    this.eventEmitter.off(event, listener);
  }
}

// Export default instance
export const hybridLLMService = new HybridLLMService();
