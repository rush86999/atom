<file_path>
atom/src/ui-shared/components/AIProviderSettings.tsx
</file_path>

import React, { useState, useEffect } from 'react';
import { Settings, Key, Zap, Shield, CheckCircle, AlertCircle, DollarSign, Clock, Globe, HardDrive, Cloud } from 'lucide-react';

interface AIProviderConfig {
  id: string;
  name: string;
  type: 'local' | 'remote';
  icon: React.ReactNode;
  description: string;
  features: string[];
  models: string[];
  cost: {
    input_token?: number;
    output_token?: number;
    description: string;
  };
  connection: {
    requiresAPIKey: boolean;
    endpoint?: string;
    placeholder?: string;
    docsUrl?: string;
  };
}

const AI_PROVIDERS: AIProviderConfig[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    type: 'remote',
    icon: <Zap className="w-5 h-5" />,
    description: 'GPT models for complex reasoning, creative tasks, and code generation',
    features: ['GPT-4', 'GPT-3.5', 'DALL-E', 'Whisper', 'Code Interpreter'],
    models: ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo', 'dall-e-3', 'whisper-1'],
    cost: { input_token: 0.03, output_token: 0.06, description: 'From $0.0015/1K tokens' },
    connection: {
      requiresAPIKey: true,
      placeholder: 'sk-...',
      docsUrl: 'https://platform.openai.com/api-keys'
    }
  },
  {
    id: 'claude',
    name: 'Claude (Anthropic)',
    type: 'remote',
    icon: <Globe className="w-5 h-5" />,
    description: 'Anthropic Claude for advanced analysis and document processing with large context',
    features: ['Claude-3 Opus', 'Long Context', 'Document Analysis', 'Creative Writing'],
    models: ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
    cost: { input_token: 0.008, output_token: 0.024, description: 'From $0.003/1K tokens' },
    connection: {
      requiresAPIKey: true,
      placeholder: 'sk-ant...',
      docsUrl: 'https://console.anthropic.com/settings/keys'
    }
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    type: 'remote',
    icon: <Cloud className="w-5 h-5" />,
    description: 'Google Gemini with multimodal capabilities and large token windows',
    features: ['Multimodal', 'Large Context', 'Google Integration', 'Fast Response'],
    models: ['gemini-pro', 'gemini-pro-vision', 'gemini-1.5-pro'],
    cost: { input_token: 0.0005, output_token: 0.0015, description: 'From $0.50/million tokens' },
    connection: {
      requiresAPIKey: true,
      placeholder: 'AIzaSy...',
      docsUrl: 'https://makersuite.google.com/app/apikey'
    }
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    type: 'remote',
    icon: <Settings className="w-5 h-5" />,
    description: 'Access to 100+ models including Llama, Mistral, Claude, and more',
    features: ['Model Switching', 'Cost Optimization', 'Universal Access', 'Fallback'],
    models: ['meta-llama/llama-2-70b', 'mistral/mixtral-8x7b', 'anthropic/claude-3-sonnet', 'google/palm-2'],
    cost: { input_token: 0.0005, output_token: 0.0015, description: 'Model-specific pricing' },
    connection: {
      requiresAPIKey: true,
      placeholder: 'sk-or...',
      docsUrl: 'https://openrouter.ai/keys'
    }
  },
  {
    id: 'moonshot',
    name: 'Moonshot AI',
    type: 'remote',
    icon: <DollarSign className="w-5 h-5" />,
    description: 'Chinese-optimized models with strong code generation and reasoning',
    features: ['Chinese Optimized', 'Code Generation', 'Fast Response', 'Cost Effective'],
    models: ['moonshot-v1-
