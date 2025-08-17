import React, { useState, useEffect } from 'react';
import { Key, Settings, Zap, CheckCircle, AlertCircle, ExternalLink, DollarSign, Globe, HardDrive } from 'lucide-react';

interface AIProvider {
  id: string;
  name: string;
  type: string;
  description: string;
  models: string[];
  cost: string;
  placeholder: string;
  docs: string;
  icon: React.ReactNode;
}

const AI_PROVIDERS: AIProvider[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    type: 'remote',
    description: 'GPT-4, GPT-3.5 Turbo for advanced tasks',
    models: ['gpt-4', 'gpt-3.5-turbo'],
    cost: '$0.03-$0.06/1K tokens',
    placeholder: 'sk-...',
    docs: 'https://platform.openai.com/api-keys',
    icon: <Zap className="w-4 h-4" />
  },
  {
    id: 'claude',
    name: 'Claude (Anthropic)',
    type: 'remote',
    description: 'Advanced reasoning and analysis models',
    models: ['claude-3-opus', 'claude-3-sonnet'],
    cost: '$0.008-$0.024/1K tokens',
    placeholder: 'sk-ant-...',
    docs: 'https://console.anthropic.com/settings/keys',
    icon: <Globe className="w-4 h-4" />
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    type: 'remote',
    description: 'Multimodal capabilities with Google integration',
    models: ['gemini-pro', 'gemini-pro-vision'],
    cost: '$0.0005-$0.0015/1K tokens',
    placeholder: 'AIzaSy...',
    docs: 'https://makersuite.google.com/app/apikey',
    icon: <Globe className="w-4 h-4" />
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    type: 'remote',
    description: 'Access to 100+ models including Llama, Claude, Gemini',
    models: ['Universal access', 'Model switching', 'Cost optimization'],
    cost: 'Varies by model',
    placeholder: 'sk-or-...',
    docs: 'https://openrouter.ai/keys',
    icon: <Globe className="w-4 h-4" />
  },
  {
    id: 'moonshot',
    name: 'Moonshot AI',
    type: 'remote',
    description: 'Chinese-optimized models with strong code generation',
    models: ['moonshot-v1-8k', 'moonshot-v1-32k'],
    cost: '$0.0005-$0.0015/1K tokens',
    placeholder: 'sk-...',
    docs: 'https://platform.moonshot.cn/api-keys',
    icon: <DollarSign className="w-4 h-4" />
  },
  {
    id: 'llama',
    name: 'Local Llama.cpp',
    type: 'local',
    description: 'Self-hosted models with complete privacy',
    models: ['llama-3-8b', 'llama-3-70b', 'mistral-7b'],
    cost: 'Free (local)',
    placeholder: 'Not required',
    docs: 'https://github.com/ollama/ollama',
    icon: <HardDrive className="w-4 h-4" />
  }
];

interface APIKeyValue {
  key: string;
  isValid: boolean;
  lastTest: string;
}

export const AISettingsModal: React.FC = () => {
  const [keys, setKeys] = useState<Record<string, APIKeyValue>>({});
  const [activeProvider, setActiveProvider] = useState<string>('openai');
  const [isTesting, setIsTesting] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    loadKeys();
  }, []);

  const loadKeys = () => {
    const stored = localStorage.getItem('atom_llm_keys');
    if (stored) {
      setKeys(JSON.parse(stored));
    }
  };

  const saveKeys = () => {
    localStorage.setItem('atom_llm_keys', JSON.stringify(keys));
  };

  const handleKeyChange = (provider: string, key: string) => {
    setKeys(prev => ({
      ...prev,
      [provider]: { key: key.trim(), isValid: false, lastTest: '' }
    }));
  };

  const testKey = async
