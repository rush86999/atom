<file_path>
atom/src/llm/universalLLMProvider.ts
</file_path>

import { EventEmitter } from 'events';
import axios from 'axios';
import { spawn } from 'child_process';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';

interface LLMProvider {
  name: string;
  type: 'local' | 'openai' | 'openrouter' | 'gemini' | 'claude' | 'moonshot' | 'custom';
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
  type: 'simple' | 'creative' | 'complex_planning' | 'analysis' | 'translation' | 'generation';
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
    enableCostTracking: true
  };

  constructor() {
    super();
    this.initializeProviders();
    this.setupLlamaCPP();
  }

  private initializeProviders() {
    // OpenAI Providers
    this.providers.set('openai-gpt4', {
      name: 'OpenAI GPT-4',
      type: 'openai',
      endpoint: 'https://api.openai.com/v1/chat/completions',
      models: ['gpt-4-0125-preview', 'gpt-4-1106-preview', 'gpt-4', 'gpt-4-turbo'],
      costPerToken: { input: 0.03, output: 0.06 },
      maxTokens: 8192,
      supports: ['complex_planning', 'creative', 'analysis', 'translation', 'generation']
    });

    this.providers.set('openai-gpt3', {
      name: 'OpenAI GPT-3.5',
      type: 'openai',
      endpoint: 'https://api.openai.com/v1/chat/completions',
      models: ['gpt-3.5-turbo-0125', 'gpt-3.5-turbo-1106'],
      costPerToken: { input: 0.0015, output: 0.002 },
      maxTokens: 4096,
      supports: ['simple', 'translation', 'generation']
    });

    // OpenRouter (Universal access)
    this.providers.set('openrouter-llama', {
      name: 'OpenRouter Llama-2-70B',
      type: 'openrouter',
      endpoint: 'https://openrouter.ai/api/v1/chat/completions',
      models: [
        'meta-llama/llama-2-70b-chat',
        'mistralai/mistral-7b-instruct',
        'anthropic/claude-3-sonnet',
        'google/palm-2-chat-bison'
      ],
      costPerToken: { input: 0.0007, output: 0.0013 },
      maxTokens: 4096,
      supports: ['analysis', 'creative', 'planning']
    });

    // Google Gemini
    this.providers.set('gemini-pro', {
      name: 'Google Gemini Pro',
      type: 'gemini',
      endpoint: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent',
      models: ['gemini-pro', 'gemini-pro-vision'],
      costPerToken: { input: 0.0005, output: 0.0015 },
      maxTokens: 32768,
