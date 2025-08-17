import { EventEmitter } from 'events';

interface LLMProviderConfig {
  id: string;
  name: string;
  apiKey: string;
  endpoint?: string;
  model?: string;
  isActive: boolean;
  isLocal?: boolean;
  costPerToken?: {
    input: number;
    output: number;
  };
}

interface LLMSettings {
  primaryProvider: string;
  fallbackProvider: string;
  cacheEnabled: boolean;
  costTracking: boolean;
  maxMonthlyBudget: number;
  providers: Record<string, LLMProviderConfig>;
}

// Storage abstraction for both desktop and web
class StorageBackend {
  private readonly KEY = 'atom_llm_settings';

  async get(): Promise<string | null> {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(this.KEY);
    }
    // Node.js desktop environment
    return null;
  }

  async set(value: string): Promise<void> {
    if (typeof window !== 'undefined') {
      localStorage.setItem(this.KEY, value);
    }
  }

  async remove(): Promise<void> {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(this.KEY);
    }
  }
}

// Tauri-specific storage for desktop
class TauriStorageBackend extends StorageBackend {
  private tauri: any = null;

  constructor() {
    super();
    if (typeof window !== 'undefined' && (window as any).__TAURI__) {
      this.tauri = (window as any).__;
    }
  }

  async get(): Promise<string | null> {
    if (this.tauri) {
      return await this.tauri.invoke('get_setting', { key: this.KEY });
    }
    return await super.get();
  }

  async set(value: string): Promise<void> {
    if (this.tauri) {
      await this.tauri.invoke('set_setting', { key: this.KEY, value });
    } else {
      await super.set(value);
    }
  }
}

export class LLMSettingsManager extends EventEmitter {
  private storage: StorageBackend;
  private settings: LLMSettings;

  constructor(isDesktop = false) {
    super();
    this.storage = isDesktop ? new TauriStorageBackend() : new StorageBackend();
    this.settings = this.getDefaultSettings();
    this.loadSettings();
  }

  private getDefaultSettings(): LLMSettings {
    return {
      primaryProvider: 'openai',
      fallbackProvider: 'openrouter',
      cacheEnabled: true,
      costTracking: true,
      maxMonthlyBudget: 50,
      providers: {
        openai: {
          id: 'openai',
          name: 'OpenAI',
          apiKey: '',
          isActive: false,
          costPerToken: { input: 0.03, output: 0.06 }
        },
        claude: {
          id: 'claude',
          name: 'Claude (Anthropic)',
          apiKey: '',
          isActive: false,
          costPerToken: { input: 0.008, output: 0.024 }
        },
        gemini: {
          id: 'gemini',
          name: 'Google Gemini',
          apiKey: '',
          isActive: false,
          costPerToken: { input: 0.0005, output: 0.0015 }
        },
        openrouter: {
          id: 'openrouter',
          name: 'OpenRouter',
          apiKey: '',
          isActive: false,
          costPerToken: { input: 0.0007, output: 0.0013 }
        },
        moonshot: {
          id: 'moonshot',
          name: 'Moonshot AI',
          apiKey: '',
          isActive: false,
          costPerToken: { input: 0.0005, output: 0.0015 }
        }
+      }
+    };
+  }
+
+  async loadSettings(): Promise<void> {
+    try {
+      const stored = await this.storage.get();
+      if (stored) {
+        const parsed = JSON.parse(stored);
+        this.settings = { ...this.getDefaultSettings(), ...parsed };
+        this.emit('settings-updated', this.settings);
+      }
+    } catch (error) {
+      console.error('Failed to load LLM settings:', error);
+    }
+  }
+
+  async saveSettings(): Promise<void> {
+    try {
+      await this.storage.set(JSON.stringify(this.settings));
+      this.emit('settings-updated', this.settings);
+    } catch (error) {
+      console.error('Failed to save LLM settings:', error);
+    }
+  }
+
+  getSettings(): LLMSettings {
+    return { ...this.settings };
+  }
+
+  get
