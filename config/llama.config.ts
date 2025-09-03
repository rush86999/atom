// Llama.cpp Configuration for Atom NLU System
// This configuration manages local model settings and fallback strategies

export interface LlamaModelConfig {
  // Model identification
  modelId: string;
  modelName: string;
  modelSize: 'small' | 'medium' | 'large';

  // Model file configuration
  modelPath: string;
  downloadUrl: string;
  fileSize: number; // in bytes
  quantization: string; // e.g., 'Q4_K_M', 'IQ2_M', etc.

  // Performance settings
  contextSize: number;
  gpuLayers: number;
  threadCount: number;
  batchSize: number;

  // Quality settings
  temperature: number;
  topP: number;
  topK: number;
  typicalP: number;

  // Memory usage
  memoryUsage: number; // estimated MB
  vramUsage: number; // estimated MB for GPU
}

export interface LlamaServerConfig {
  // Server settings
  enabled: boolean;
  serverPort: number;
  host: string;
  apiEndpoint: string;

  // Startup behavior
  autoStart: boolean;
  autoDownload: boolean;
  startupTimeout: number; // ms

  // Health checks
  healthCheckInterval: number;
  maxRestartAttempts: number;
  restartDelay: number;
}

export interface LlamaFallbackConfig {
  // Fallback strategies
  enableFallback: boolean;
  fallbackStrategy: 'local-first' | 'cloud-first' | 'cost-optimized';

  // Complexity thresholds
  minComplexityForLocal: number;
  maxComplexityForLocal: number;

  // Performance thresholds
  maxResponseTime: number; // ms
  minConfidenceForLocal: number;

  // Cost considerations
  maxCostPerToken: number;
  preferredProviders: string[];
}

export interface LlamaCacheConfig {
  // Response caching
  enableCaching: boolean;
  cacheTTL: number; // ms
  maxCacheSize: number; // items
  cacheCleanupInterval: number;

  // Model caching
  cacheModels: boolean;
  modelCachePath: string;
}

export interface LlamaMonitoringConfig {
  // Metrics collection
  enableMetrics: boolean;
  metricsInterval: number;

  // Performance monitoring
  trackResponseTimes: boolean;
  trackTokenUsage: boolean;
  trackCosts: boolean;

  // Error tracking
  logErrors: boolean;
  errorThreshold: number;
}

export interface LlamaConfig {
  // Model configurations
  models: LlamaModelConfig[];
  defaultModel: string;

  // Server configuration
  server: LlamaServerConfig;

  // Fallback configuration
  fallback: LlamaFallbackConfig;

  // Caching configuration
  cache: LlamaCacheConfig;

  // Monitoring configuration
  monitoring: LlamaMonitoringConfig;

  // System paths
  basePath: string;
  modelsPath: string;
  binariesPath: string;
  tempPath: string;
}

// Default configuration
export const defaultLlamaConfig: LlamaConfig = {
  models: [
    {
      modelId: 'llama-3-8b-instruct',
      modelName: 'Llama 3 8B Instruct',
      modelSize: 'small',
      modelPath: './models/llama.cpp/llama-3-8b-instruct.Q4_K_M.gguf',
      downloadUrl: 'https://huggingface.co/bartowski/Llama-3-8B-Instruct-GGUF/resolve/main/Llama-3-8B-Instruct-Q4_K_M.gguf',
      fileSize: 4740000000, // ~4.74GB
      quantization: 'Q4_K_M',
      contextSize: 4096,
      gpuLayers: 28,
      threadCount: 4,
      batchSize: 512,
      temperature: 0.7,
      topP: 0.9,
      topK: 40,
      typicalP: 1.0,
      memoryUsage: 6000,
      vramUsage: 4000,
    },
    {
      modelId: 'llama-3-70b-instruct',
      modelName: 'Llama 3 70B Instruct',
      modelSize: 'large',
      modelPath: './models/llama.cpp/llama-3-70b-instruct.IQ2_M.gguf',
      downloadUrl: 'https://huggingface.co/bartowski/Llama-3-70B-Instruct-GGUF/resolve/main/Llama-3-70B-Instruct-IQ2_M.gguf',
      fileSize: 38900000000, // ~38.9GB
      quantization: 'IQ2_M',
      contextSize: 8192,
      gpuLayers: 83,
      threadCount: 8,
      batchSize: 1024,
      temperature: 0.7,
      topP: 0.9,
      topK: 40,
      typicalP: 1.0,
      memoryUsage: 45000,
      vramUsage: 35000,
    },
    {
      modelId: 'mistral-7b-instruct',
      modelName: 'Mistral 7B Instruct',
      modelSize: 'small',
      modelPath: './models/llama.cpp/mistral-7b-instruct-v0.2.Q4_K_M.gguf',
      downloadUrl: 'https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf',
      fileSize: 4260000000, // ~4.26GB
      quantization: 'Q4_K_M',
      contextSize: 32768,
      gpuLayers: 35,
      threadCount: 4,
      batchSize: 512,
      temperature: 0.7,
      topP: 0.9,
      topK: 40,
      typicalP: 1.0,
      memoryUsage: 5500,
      vramUsage: 3500,
    }
  ],

  defaultModel: 'llama-3-8b-instruct',

  server: {
    enabled: true,
    serverPort: 8080,
    host: 'localhost',
    apiEndpoint: '/completion',
    autoStart: true,
    autoDownload: true,
    startupTimeout: 30000,
    healthCheckInterval: 30000,
    maxRestartAttempts: 3,
    restartDelay: 5000,
  },

  fallback: {
    enableFallback: true,
    fallbackStrategy: 'local-first',
    minComplexityForLocal: 0.3,
    maxComplexityForLocal: 0.7,
    maxResponseTime: 10000,
    minConfidenceForLocal: 0.6,
    maxCostPerToken: 0.0001,
    preferredProviders: ['openai', 'anthropic', 'google'],
  },

  cache: {
    enableCaching: true,
    cacheTTL: 300000, // 5 minutes
    maxCacheSize: 1000,
    cacheCleanupInterval: 60000,
    cacheModels: true,
    modelCachePath: './cache/models',
  },

  monitoring: {
    enableMetrics: true,
    metricsInterval: 60000,
    trackResponseTimes: true,
    trackTokenUsage: true,
    trackCosts: true,
    logErrors: true,
    errorThreshold: 0.1, // 10% error rate
  },

  basePath: './llama.cpp',
  modelsPath: './models/llama.cpp',
  binariesPath: './bin/llama.cpp',
  tempPath: './temp/llama.cpp',
};

// Utility functions
export const getModelConfig = (modelId: string): LlamaModelConfig | undefined => {
  return defaultLlamaConfig.models.find(model => model.modelId === modelId);
};

export const getDefaultModelConfig = (): LlamaModelConfig => {
  const model = getModelConfig(defaultLlamaConfig.defaultModel);
  if (!model) {
    throw new Error(`Default model ${defaultLlamaConfig.defaultModel} not found in configuration`);
  }
  return model;
};

export const isModelAvailable = (modelId: string): boolean => {
  const model = getModelConfig(modelId);
  return !!model;
};

export const getSupportedModels = (): string[] => {
  return defaultLlamaConfig.models.map(model => model.modelId);
};

// Environment-based configuration
export const getEnvironmentConfig = (): LlamaConfig => {
  const config = { ...defaultLlamaConfig };

  // Override with environment variables
  if (process.env.LLAMA_SERVER_PORT) {
    config.server.serverPort = parseInt(process.env.LLAMA_SERVER_PORT);
  }

  if (process.env.LLAMA_MODEL_PATH) {
    config.modelsPath = process.env.LLAMA_MODEL_PATH;
  }

  if (process.env.LLAMA_ENABLED) {
    config.server.enabled = process.env.LLAMA_ENABLED.toLowerCase() === 'true';
  }

  if (process.env.LLAMA_AUTO_START) {
    config.server.autoStart = process.env.LLAMA_AUTO_START.toLowerCase() === 'true';
  }

  return config;
};

export default defaultLlamaConfig;
