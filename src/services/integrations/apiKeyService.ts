<file_path>
atom/src/services/apiKeyService.ts
</file_path>

import { EventEmitter } from 'events';

interface APIKeyConfig {
  [provider: string]: {
    apiKey: string;
    endpoint?: string;
    model?: string;
    isActive: boolean;
    displayName?: string;
  };
}

interface SecureStorageBackend {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

class DesktopStorage implements SecureStorageBackend {
  private key = 'atom_llm_keys';

  async getItem(key: string): Promise<string | null> {
    return localStorage.getItem(key);
  }

  async setItem(key: string, value: string): Promise<void> {
    localStorage.setItem(key, value);
  }

  async removeItem(key: string): Promise<void> {
    localStorage.removeItem(key);
  }
}

class WebAppStorage implements SecureStorageBackend {
  async getItem(key: string): Promise<string | null> {
    return localStorage.getItem(key);
  }

  async setItem(key: string, value: string): Promise<void> {
    localStorage.setItem(key, value);
  }

  async removeItem(key: string): Promise<void> {
    localStorage.removeItem(key);
  }
}

export class APIKeyService extends EventEmitter {
  private storage: SecureStorageBackend;
  private keys: APIKeyConfig = {};
  private persistedKey = 'atom_llm_api_keys';
  private encryptionEnabled = false;

  constructor(isDesktop = false) {
    super();
    this.storage = isDesktop ? new DesktopStorage() : new WebAppStorage();
    this.loadKeys();
  }

  async loadKeys(): Promise<void> {
    try {
      const stored = await this.storage.getItem(this.persistedKey);
      if (stored) {
        this.keys = this.decryptKeys(JSON.parse(stored));
        this.emit('keys-loaded', this.keys);
      }
    } catch (error) {
      console.error('Failed to load API keys:', error);
      this.keys = {};
    }
  }

  async saveKeys(): Promise<void> {
    try {
      const encrypted = this.encryptKeys(this.keys);
      await this.storage.setItem(this.persistedKey, JSON.stringify(encrypted));
      this.emit('keys-updated', this.keys);
    } catch (error) {
      console.error('Failed to save API keys:', error);
    }
  }

  setKey(provider: string, config: APIKeyConfig[string]): void {
    this.keys[provider] = { ...config, apiKey: this.sanitizeKey(config.apiKey) };
    this.saveKeys();
    this.emit('key-added', { provider, ...config });
  }

  getKey(provider: string): APIKeyConfig[string] | undefined {
    return this.keys[provider];
  }

  getAllKeys(): APIKeyConfig {
    return { ...this.keys };
  }

  removeKey(provider: string): void {
    delete this.keys[provider];
    this.saveKeys();
    this.emit('key-removed', { provider });
  }

  getActiveProviders(): string[] {
    return Object.keys(this.keys).filter(key => this.keys[key]?.isActive);
  }

  rotateKey(provider: string, newKey: string): void {
    if (this.keys[provider]) {
      this.keys[provider].apiKey = this.sanitizeKey(newKey);
      this.saveKeys();
      this.emit('key-rotated', { provider });
    }
  }

  testConnection(provider: string): Promise<boolean> {
    const config = this.keys[provider];
    if (!config || !config.apiKey) return Promise.resolve(false);

    // This would test the actual API connection
    return this.performConnectionTest(provider, config);
  }

  private async performConnectionTest(provider: string, config: APIKeyConfig[string]): Promise<boolean> {
    // Implementation would vary by provider
    const testEndpoints = {
      'openai': 'https://api.openai.com/v1/models',
      'claude': 'https://api.anthropic.com/v1/models',
      'gemini': 'https://generativelanguage.googleapis.com/v1beta/models',
      'openrouter': 'https://openrouter.ai/api/v1/models',
      'moonshot': 'https://api.moonshot.cn/v1/models'
    };

    const endpoint = testEndpoints[provider];
    if (!endpoint) return true; // Skip for custom/local

    try {
      const response = await fetch(endpoint, {
        headers: { 'Authorization': `Bearer ${config.apiKey}` },
        method: 'GET'
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  private sanitizeKey(key: string): string {
    // Remove any whitespace
    return key.trim();
