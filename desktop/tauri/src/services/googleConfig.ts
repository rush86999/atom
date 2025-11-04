// Google Configuration Management
import { readTextFile, writeTextFile, exists } from '@tauri-apps/api/fs';
import { appConfigDir } from '@tauri-apps/api/path';

export interface GoogleConfig {
  clientId: string;
  clientSecret: string;
  redirectUri: string;
  scopes: string[];
  useMockApi: boolean;
  rateLimitPerSecond: number;
  requestTimeoutSeconds: number;
  maxRetries: number;
}

export interface GoogleStoredTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresAt: string;
  scope: string;
  userId: string;
}

export class GoogleConfigManager {
  private static instance: GoogleConfigManager;
  private config: GoogleConfig | null = null;
  private configPath: string = '';

  static getInstance(): GoogleConfigManager {
    if (!GoogleConfigManager.instance) {
      GoogleConfigManager.instance = new GoogleConfigManager();
    }
    return GoogleConfigManager.instance;
  }

  private constructor() {
    this.initialize();
  }

  private async initialize() {
    try {
      const configDir = await appConfigDir();
      this.configPath = `${configDir}/google-config.json`;
      
      // Load existing config or create default
      if (await exists(this.configPath)) {
        const configData = await readTextFile(this.configPath);
        this.config = JSON.parse(configData);
      } else {
        this.config = this.getDefaultConfig();
        await this.saveConfig();
      }
    } catch (error) {
      console.error('Failed to initialize Google config:', error);
      this.config = this.getDefaultConfig();
    }
  }

  private getDefaultConfig(): GoogleConfig {
    return {
      clientId: process.env.GOOGLE_CLIENT_ID || '',
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || '',
      redirectUri: process.env.GOOGLE_REDIRECT_URI || 'http://localhost:3000/oauth/google/callback',
      scopes: [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file'
      ],
      useMockApi: process.env.GOOGLE_USE_MOCK_API === 'true' || true, // Default to mock for development
      rateLimitPerSecond: parseInt(process.env.GOOGLE_RATE_LIMIT_PER_SECOND || '100'),
      requestTimeoutSeconds: parseInt(process.env.GOOGLE_REQUEST_TIMEOUT_SECONDS || '30'),
      maxRetries: parseInt(process.env.GOOGLE_MAX_RETRIES || '3')
    };
  }

  // Get configuration
  getConfig(): GoogleConfig {
    if (!this.config) {
      throw new Error('Google configuration not initialized');
    }
    return { ...this.config };
  }

  // Update configuration
  async updateConfig(updates: Partial<GoogleConfig>): Promise<{ success: boolean; error?: string }> {
    if (!this.config) {
      return { success: false, error: 'Configuration not initialized' };
    }

    try {
      this.config = { ...this.config, ...updates };
      return await this.saveConfig();
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to update config' 
      };
    }
  }

  // Save configuration to file
  private async saveConfig(): Promise<{ success: boolean; error?: string }> {
    if (!this.config) {
      return { success: false, error: 'No configuration to save' };
    }

    try {
      await writeTextFile(this.configPath, JSON.stringify(this.config, null, 2));
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to save config' 
      };
    }
  }

  // Validate configuration
  validateConfig(config: GoogleConfig): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!config.clientId) {
      errors.push('Google Client ID is required');
    }

    if (!config.clientSecret) {
      errors.push('Google Client Secret is required');
    }

    if (!config.redirectUri) {
      errors.push('Redirect URI is required');
    }

    if (!config.scopes || config.scopes.length === 0) {
      errors.push('At least one OAuth scope is required');
    }

    if (config.rateLimitPerSecond < 1 || config.rateLimitPerSecond > 1000) {
      errors.push('Rate limit must be between 1 and 1000 requests per second');
    }

    if (config.requestTimeoutSeconds < 1 || config.requestTimeoutSeconds > 300) {
      errors.push('Request timeout must be between 1 and 300 seconds');
    }

    if (config.maxRetries < 0 || config.maxRetries > 10) {
      errors.push('Max retries must be between 0 and 10');
    }

    // Validate redirect URI format
    try {
      const url = new URL(config.redirectUri);
      if (!['http:', 'https:'].includes(url.protocol)) {
        errors.push('Redirect URI must use HTTP or HTTPS protocol');
      }
    } catch {
      errors.push('Redirect URI must be a valid URL');
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  // Get OAuth scope string
  getScopeString(): string {
    if (!this.config || !this.config.scopes) {
      return '';
    }
    return this.config.scopes.join(' ');
  }

  // Check if using mock API
  isUsingMockApi(): boolean {
    return this.config?.useMockApi || false;
  }

  // Get API endpoints
  getApiEndpoints() {
    return {
      gmail: 'https://gmail.googleapis.com/gmail/v1',
      calendar: 'https://www.googleapis.com/calendar/v3',
      drive: 'https://www.googleapis.com/drive/v3',
      oauth: 'https://oauth2.googleapis.com'
    };
  }

  // Check if configuration is complete for production
  isProductionReady(): boolean {
    if (!this.config) return false;

    const { valid, errors } = this.validateConfig(this.config);
    
    if (!valid) {
      console.warn('Google config validation errors:', errors);
      return false;
    }

    // Additional production checks
    if (this.config.useMockApi) {
      console.warn('Mock API is enabled - not suitable for production');
      return false;
    }

    if (!this.config.clientId || this.config.clientId === 'your_google_client_id_here') {
      console.warn('Google Client ID is not configured');
      return false;
    }

    if (!this.config.clientSecret || this.config.clientSecret === 'your_google_client_secret_here') {
      console.warn('Google Client Secret is not configured');
      return false;
    }

    return true;
  }

  // Store user tokens
  async storeTokens(userId: string, tokens: GoogleStoredTokens): Promise<{ success: boolean; error?: string }> {
    try {
      const tokensPath = await this.getTokensPath(userId);
      await writeTextFile(tokensPath, JSON.stringify(tokens, null, 2));
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to store tokens' 
      };
    }
  }

  // Get user tokens
  async getTokens(userId: string): Promise<{ success: boolean; tokens?: GoogleStoredTokens; error?: string }> {
    try {
      const tokensPath = await this.getTokensPath(userId);
      
      if (!(await exists(tokensPath))) {
        return { success: false, error: 'No tokens found for user' };
      }

      const tokensData = await readTextFile(tokensPath);
      const tokens: GoogleStoredTokens = JSON.parse(tokensData);

      // Check if tokens are expired
      const expiresAt = new Date(tokens.expiresAt);
      const now = new Date();
      
      if (now >= expiresAt) {
        return { success: false, error: 'Tokens have expired' };
      }

      return { success: true, tokens };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to retrieve tokens' 
      };
    }
  }

  // Delete user tokens
  async deleteTokens(userId: string): Promise<{ success: boolean; error?: string }> {
    try {
      const tokensPath = await this.getTokensPath(userId);
      
      if (await exists(tokensPath)) {
        // Delete tokens file
        await writeTextFile(tokensPath, '');
      }
      
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to delete tokens' 
      };
    }
  }

  // Get tokens file path for user
  private async getTokensPath(userId: string): Promise<string> {
    const configDir = await appConfigDir();
    return `${configDir}/google_tokens_${userId}.json`;
  }

  // Reset configuration to defaults
  async resetConfig(): Promise<{ success: boolean; error?: string }> {
    try {
      this.config = this.getDefaultConfig();
      return await this.saveConfig();
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to reset config' 
      };
    }
  }

  // Get configuration status
  getConfigStatus() {
    if (!this.config) {
      return {
        status: 'not_initialized' as const,
        isProductionReady: false,
        hasClientCredentials: false,
        isUsingMockApi: false
      };
    }

    const { valid, errors } = this.validateConfig(this.config);

    return {
      status: valid ? 'valid' : 'invalid' as const,
      isProductionReady: this.isProductionReady(),
      hasClientCredentials: !!(this.config.clientId && this.config.clientSecret),
      isUsingMockApi: this.config.useMockApi || false,
      errors: valid ? [] : errors,
      config: this.config
    };
  }

  // Export configuration (for backup)
  async exportConfig(): Promise<{ success: boolean; data?: string; error?: string }> {
    try {
      if (!this.config) {
        return { success: false, error: 'No configuration to export' };
      }

      // Create export data (without secrets for security)
      const exportData = {
        ...this.config,
        clientSecret: this.config.clientSecret ? '[REDACTED]' : '',
        exportedAt: new Date().toISOString(),
        version: '1.0'
      };

      return { 
        success: true, 
        data: JSON.stringify(exportData, null, 2) 
      };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to export config' 
      };
    }
  }
}

// Export singleton instance
export const googleConfig = GoogleConfigManager.getInstance();

// Export types
export type { GoogleConfig, GoogleStoredTokens };