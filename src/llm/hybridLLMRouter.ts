<file_path>
atom/src/llm/hybridLLMRouter.ts
</file_path>

import { EventEmitter } from 'events';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import { v4 as uuidv4 } from 'uuid';

interface LLMCallTask {
  id: string;
  type: 'simple_intent' | 'complex_planning' | 'creative_generation' | 'detailed_analysis' | 'translation' | 'validation';
  prompt: string;
  priority: 'low' | 'medium' | 'high';
  context?: Record<string, any>;
  callback?: (response: string) => void;
}

interface LLMProvider {
  name: string;
  type: 'local' | 'cloud';
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
    frequency_penalty: 0.0
  };
  private thresholds = {
    simple: 0.3,
    creative: 0.7,
    complex: 0.9
  };

  constructor() {
    super();
    this.initializeProviders();
    this.setupLlamaCPP();
  }

  private initializeProviders() {
    // Local llama.cpp models for specific tasks
    this.providers.set('llama-local-8b', {
      name: 'Llama-3B-8B-Small-Biz',
      type: 'local',
      modelSize: '8B',
      maxTokens: 4096,
      supports: ['intent_detection', 'simple_routing', 'basic_automation', 'small_biz_workflows']
    });

    this.providers.set('llama-local-full', {
      name: 'Llama-SmallBiz-V2-13B',
      type: 'local',
      modelSize: '13B',
      maxTokens: 8192,
      supports: ['planning', 'analysis', 'complex_workflows']
    });

    // Cloud providers for advanced tasks
    this.providers.set('gpt-4', {
      name: 'OpenAI GPT-4',
      type: 'cloud',
      modelSize: 'Large',
      costPerToken: 0.001,
      maxTokens: 8192,
      supports: ['creative', 'planning', 'analysis', 'complex_reasoning']
    });

    this.providers.set('claude-opus', {
      name: 'Claude-3-Opus',
      type: 'cloud',
      modelSize: 'Large',
      costPerToken: 0.0008,
      maxTokens: 200000,
      supports: ['creative', 'analysis', 'document_processing', 'long_context']
    });

    this.providers.set('gemini-pro', {
      name: 'Gemini-1.5-Pro',
      type: 'cloud',
      modelSize: 'Large',
      costPerToken: 0.0005,
      maxTokens: 1000000,
      supports: ['multimodal', 'creative', 'analysis', 'planning']
    });
  }

  private setupLlamaCPP() {
    const llamaPath = process.env.LLAMA_CPP_PATH || '/opt/llama.cpp';
    const modelPath = process.env.LLAMA_MODEL_PATH || './models';

    this.localLlama = {
      path: llamaPath,
      model: path.join(modelPath, 'llama-3.2-8b-instruct.s.gguf'),
      contextSize: 4096,
      gpuLayers: 28 // Use GPU for speed
    };
  }

  /**
   * Intelligently route LLM requests based on complexity and business context
