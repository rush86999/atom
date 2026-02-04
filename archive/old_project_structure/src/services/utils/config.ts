/**
 * Shared Configuration for ATOM Services
 * This configuration is used by both web and desktop applications
 */

// Base configuration interface
export interface ServiceConfig {
  environment: 'development' | 'production' | 'test';
  platform: 'web' | 'desktop';
  apiBaseUrl?: string;
  useLocalStorage: boolean;
  offlineCapable: boolean;
  encryptionEnabled: boolean;
}

// Platform-specific configurations
export interface WebConfig extends ServiceConfig {
  platform: 'web';
  apiBaseUrl: string;
  useLocalStorage: false;
  corsEnabled: boolean;
}

export interface DesktopConfig extends ServiceConfig {
  platform: 'desktop';
  useLocalStorage: true;
  offlineCapable: true;
  localDataPath?: string;
  audioProcessingEnabled: boolean;
  wakeWordDetection: boolean;
}

// Service-specific configurations
export interface AIServiceConfig {
  provider: 'openai' | 'anthropic' | 'local' | 'hybrid';
  apiKey?: string;
  model: string;
  maxTokens: number;
  temperature: number;
  useCache: boolean;
}

export interface AuthServiceConfig {
  oauthProviders: string[];
  tokenRefreshInterval: number;
  secureStorage: boolean;
  sessionTimeout: number;
}

export interface WorkflowServiceConfig {
  maxConcurrentWorkflows: number;
  retryAttempts: number;
  timeout: number;
  persistence: boolean;
}

export interface IntegrationServiceConfig {
  enabledIntegrations: string[];
  syncInterval: number;
  batchSize: number;
  useWebhooks: boolean;
}

// Main configuration object
export interface AppConfig {
  service: ServiceConfig;
  ai: AIServiceConfig;
  auth: AuthServiceConfig;
  workflow: WorkflowServiceConfig;
  integrations: IntegrationServiceConfig;
}

// Default configurations
export const defaultWebConfig: WebConfig = {
  environment: 'development',
  platform: 'web',
  apiBaseUrl: 'http://localhost:8000',
  useLocalStorage: false,
  offlineCapable: false,
  encryptionEnabled: true,
  corsEnabled: true,
};

export const defaultDesktopConfig: DesktopConfig = {
  environment: 'development',
  platform: 'desktop',
  useLocalStorage: true,
  offlineCapable: true,
  encryptionEnabled: true,
  localDataPath: undefined,
  audioProcessingEnabled: true,
  wakeWordDetection: true,
};

export const defaultAIConfig: AIServiceConfig = {
  provider: 'openai',
  apiKey: undefined,
  model: 'gpt-4',
  maxTokens: 4000,
  temperature: 0.7,
  useCache: true,
};

export const defaultAuthConfig: AuthServiceConfig = {
  oauthProviders: ['google', 'github', 'microsoft'],
  tokenRefreshInterval: 3600000, // 1 hour
  secureStorage: true,
  sessionTimeout: 86400000, // 24 hours
};

export const defaultWorkflowConfig: WorkflowServiceConfig = {
  maxConcurrentWorkflows: 10,
  retryAttempts: 3,
  timeout: 300000, // 5 minutes
  persistence: true,
};

export const defaultIntegrationConfig: IntegrationServiceConfig = {
  enabledIntegrations: ['asana', 'dropbox', 'outlook', 'github', 'slack'],
  syncInterval: 300000, // 5 minutes
  batchSize: 100,
  useWebhooks: true,
};

// Configuration factory functions
export function createWebConfig(overrides: Partial<WebConfig> = {}): WebConfig {
  return {
    ...defaultWebConfig,
    ...overrides,
  };
}

export function createDesktopConfig(overrides: Partial<DesktopConfig> = {}): DesktopConfig {
  return {
    ...defaultDesktopConfig,
    ...overrides,
  };
}

export function createAppConfig(
  serviceConfig: ServiceConfig,
  overrides: Partial<AppConfig> = {}
): AppConfig {
  const baseConfig: AppConfig = {
    service: serviceConfig,
    ai: defaultAIConfig,
    auth: defaultAuthConfig,
    workflow: defaultWorkflowConfig,
    integrations: defaultIntegrationConfig,
  };

  return {
    ...baseConfig,
    ...overrides,
  };
}

// Environment detection
export function detectEnvironment(): 'development' | 'production' | 'test' {
  if (typeof process !== 'undefined' && process.env.NODE_ENV) {
    return process.env.NODE_ENV as 'development' | 'production' | 'test';
  }

  // For browser environments
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'development';
    }
    return 'production';
  }

  // Default to development
  return 'development';
}

export function detectPlatform(): 'web' | 'desktop' {
  // Check if we're in a Tauri environment
  if (typeof window !== 'undefined' && (window as any).__TAURI__) {
    return 'desktop';
  }

  // Check for Electron
  if (typeof window !== 'undefined' && (window as any).electron) {
    return 'desktop';
  }

  // Default to web
  return 'web';
}

// Configuration manager
class ConfigManager {
  private static instance: ConfigManager;
  private config: AppConfig;

  private constructor() {
    const environment = detectEnvironment();
    const platform = detectPlatform();

    let serviceConfig: ServiceConfig;

    if (platform === 'desktop') {
      serviceConfig = createDesktopConfig({ environment });
    } else {
      serviceConfig = createWebConfig({ environment });
    }

    this.config = createAppConfig(serviceConfig);
  }

  static getInstance(): ConfigManager {
    if (!ConfigManager.instance) {
      ConfigManager.instance = new ConfigManager();
    }
    return ConfigManager.instance;
  }

  getConfig(): AppConfig {
    return this.config;
  }

  updateConfig(updates: Partial<AppConfig>): void {
    this.config = {
      ...this.config,
      ...updates,
    };
  }

  // Platform-specific getters
  isDesktop(): boolean {
    return this.config.service.platform === 'desktop';
  }

  isWeb(): boolean {
    return this.config.service.platform === 'web';
  }

  isDevelopment(): boolean {
    return this.config.service.environment === 'development';
  }

  isProduction(): boolean {
    return this.config.service.environment === 'production';
  }

  // Service-specific getters
  getAIConfig(): AIServiceConfig {
    return this.config.ai;
  }

  getAuthConfig(): AuthServiceConfig {
    return this.config.auth;
  }

  getWorkflowConfig(): WorkflowServiceConfig {
    return this.config.workflow;
  }

  getIntegrationConfig(): IntegrationServiceConfig {
    return this.config.integrations;
  }
}

// Export singleton instance
export const configManager = ConfigManager.getInstance();

// Utility functions
export function getConfig(): AppConfig {
  return configManager.getConfig();
}

export function updateConfig(updates: Partial<AppConfig>): void {
  configManager.updateConfig(updates);
}

export function isDesktop(): boolean {
  return configManager.isDesktop();
}

export function isWeb(): boolean {
  return configManager.isWeb();
}

export function isDevelopment(): boolean {
  return configManager.isDevelopment();
}

export function isProduction(): boolean {
  return configManager.isProduction();
}

// Default export
export default configManager;
