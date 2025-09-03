atom/src/ui-shared/hooks/useAISettings.ts
import { useState, useEffect, useCallback } from 'react';

export interface AIProvider {
  id: string;
  name: string;
  type: 'openai' | 'anthropic' | 'cohere' | 'huggingface' | 'custom';
  apiKey?: string;
  baseUrl?: string;
  model: string;
  enabled: boolean;
  priority: number;
}

export interface AISettings {
  providers: AIProvider[];
  defaultProvider?: string;
  temperature: number;
  maxTokens: number;
  autoDetectLanguage: boolean;
  voiceResponseEnabled: boolean;
}

const DEFAULT_SETTINGS: AISettings = {
  providers: [
    {
      id: 'openai-default',
      name: 'OpenAI',
      type: 'openai',
      model: 'gpt-4',
      enabled: true,
      priority: 1
    }
  ],
  temperature: 0.7,
  maxTokens: 1000,
  autoDetectLanguage: true,
  voiceResponseEnabled: false
};

export const useAISettings = () => {
  const [settings, setSettings] = useState<AISettings>(DEFAULT_SETTINGS);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load settings from storage
  useEffect(() => {
    const loadSettings = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Try to load from localStorage first
        const savedSettings = localStorage.getItem('ai-settings');
        if (savedSettings) {
          const parsedSettings = JSON.parse(savedSettings);
          setSettings({ ...DEFAULT_SETTINGS, ...parsedSettings });
        } else {
          setSettings(DEFAULT_SETTINGS);
        }
      } catch (err) {
        console.error('Failed to load AI settings:', err);
        setError('Failed to load settings');
        setSettings(DEFAULT_SETTINGS);
      } finally {
        setIsLoading(false);
      }
    };

    loadSettings();
  }, []);

  // Save settings to storage
  const saveSettings = useCallback(async (newSettings: AISettings) => {
    try {
      setError(null);
      localStorage.setItem('ai-settings', JSON.stringify(newSettings));
      setSettings(newSettings);
      return { success: true };
    } catch (err) {
      console.error('Failed to save AI settings:', err);
      setError('Failed to save settings');
      return { success: false, error: 'Failed to save settings' };
    }
  }, []);

  // Update specific settings
  const updateSettings = useCallback(async (updates: Partial<AISettings>) => {
    const newSettings = { ...settings, ...updates };
    return saveSettings(newSettings);
  }, [settings, saveSettings]);

  // Add a new provider
  const addProvider = useCallback(async (provider: Omit<AIProvider, 'id'>) => {
    const newProvider: AIProvider = {
      ...provider,
      id: `provider-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    };

    const newSettings: AISettings = {
      ...settings,
      providers: [...settings.providers, newProvider]
    };

    return saveSettings(newSettings);
  }, [settings, saveSettings]);

  // Update a provider
  const updateProvider = useCallback(async (providerId: string, updates: Partial<AIProvider>) => {
    const newSettings: AISettings = {
      ...settings,
      providers: settings.providers.map(provider =>
        provider.id === providerId ? { ...provider, ...updates } : provider
      )
    };

    return saveSettings(newSettings);
  }, [settings, saveSettings]);

  // Remove a provider
  const removeProvider = useCallback(async (providerId: string) => {
    const newSettings: AISettings = {
      ...settings,
      providers: settings.providers.filter(provider => provider.id !== providerId)
    };

    // If we're removing the default provider, set a new default
    if (settings.defaultProvider === providerId) {
      newSettings.defaultProvider = newSettings.providers[0]?.id;
    }

    return saveSettings(newSettings);
  }, [settings, saveSettings]);

  // Set default provider
  const setDefaultProvider = useCallback(async (providerId: string) => {
    const newSettings: AISettings = {
      ...settings,
      defaultProvider: providerId
    };

    return saveSettings(newSettings);
  }, [settings, saveSettings]);

  // Reset to default settings
  const resetSettings = useCallback(async () => {
    return saveSettings(DEFAULT_SETTINGS);
  }, [saveSettings]);

  // Get the active provider (either default or first enabled)
  const getActiveProvider = useCallback(() => {
    if (settings.defaultProvider) {
      return settings.providers.find(p => p.id === settings.defaultProvider && p.enabled);
    }
    return settings.providers.find(p => p.enabled);
  }, [settings]);

  return {
    settings,
    isLoading,
    error,
    updateSettings,
    addProvider,
    updateProvider,
    removeProvider,
    setDefaultProvider,
    resetSettings,
    getActiveProvider
  };
};

export default useAISettings;
