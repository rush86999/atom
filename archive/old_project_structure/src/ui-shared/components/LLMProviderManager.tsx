<file_path>
atom/src/ui-shared/components/LLMProviderManager.tsx
</file_path>

import React, { useState, useEffect } from 'react';
import { Settings, Key, Zap, Shield, CheckCircle, AlertTriangle } from 'lucide-react';
import { LLMProviderManager } from '../../llm/universalLLMProvider';

interface LLMProvider {
  id: string;
  name: string;
  icon: string;
  description: string;
  apiEndpoint: string;
  models: string[];
  costPerToken?: { input: number; output: number };
  features: string[];
  keyPlaceholder: string;
}

const LLM_PROVIDERS: LLMProvider[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    icon: '⚡',
    description: 'GPT-4, GPT-3.5 Turbo for complex reasoning and creative tasks',
    apiEndpoint: 'https://api.openai.com/v1',
    models: ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
    costPerToken: { input: 0.03, output: 0.06 },
    features: ['reasoning', 'writing', 'code_generation', 'complex_analysis'],
    keyPlaceholder: 'sk-...'
  },
  {
    id: 'claude',
    name: 'Claude (Anthropic)',
    icon: '🤖',
    description: 'Advanced reasoning and analysis with Claude-3 models',
    apiEndpoint: 'https://api.anthropic.com/v1/messages',
    models: ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku'],
    costPerToken: { input: 0.008, output: 0.024 },
    features: ['analysis', 'creative', 'long_context', 'document_processing'],
    keyPlaceholder: 'sk-ant-...'
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    icon: '🔍',
    description: 'Multimodal capabilities and large context windows',
    apiEndpoint: 'https://generativelanguage.googleapis.com/v1beta',
    models: ['gemini-pro', 'gemini-pro-vision'],
    costPerToken: { input: 0.0005, output: 0.0015 },
    features: ['multimodal', 'large_context', 'google_integration'],
    keyPlaceholder: 'AIzaSy...'
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    icon: '🌐',
    description: 'Access to 100+ models including Llama, Mistral, Claude, and more',
    apiEndpoint: 'https://openrouter.ai/api/v1',
    models: ['meta-llama/llama-2-70b', 'mistral/mixtral-8x7b', 'anthropic/claude-3-sonnet'],
    costPerToken: { input: 0.0005, output: 0.0015 },
    features: ['universal_access', 'model_switching', 'cost_optimization'],
    keyPlaceholder: 'sk-or-...'
  },
  {
    id: 'moonshot',
    name: 'Moonshot AI',
    icon: '🌙',
    description: 'Chinese-optimized models with strong code and reasoning',
    apiEndpoint: 'https://api.moonshot.cn/v1',
    models: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
    costPerToken: { input: 0.0005, output: 0.0015 },
    features: ['chinese_optimzed', 'code_generation', 'fast_response'],
    keyPlaceholder: 'sk-...'
  },
  {
    id: 'llama',
    name: 'Local Llama.cpp',
    icon: '🖥️',
    description: 'Self-hosted models with complete privacy and zero cost',
    apiEndpoint: 'http://localhost:8080',
    models: ['llama-3-8b', 'llama-3-70b', 'mistral-7b'],
    costPerToken: undefined,
    features: ['privacy', 'zero_cost', 'full_control', 'offline_mode'],
    keyPlaceholder: 'Not required for local models'
  }
];

interface APIKeyStore {
  [providerId: string]: {
    apiKey: string;
    endpoint?: string;
    model?: string;
    isActive: boolean;
    lastTested: string;
    testResult?: 'success' | 'error';
    errorMessage?: string;
  };
}

export const LLMProviderManager: React.FC = () => {
  const [apiKeys, setApiKeys] =
