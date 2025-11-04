// Google OAuth2 Frontend Integration
import { invoke } from '@tauri-apps/api/tauri';
import { open } from '@tauri-apps/api/shell';
import type { GoogleConnectionStatus, GoogleOAuthUrlResponse, GoogleOAuthCallbackResponse } from '../types/googleTypes';

export class GoogleAuthService {
  private static instance: GoogleAuthService;
  private connectionStatus: GoogleConnectionStatus | null = null;

  static getInstance(): GoogleAuthService {
    if (!GoogleAuthService.instance) {
      GoogleAuthService.instance = new GoogleAuthService();
    }
    return GoogleAuthService.instance;
  }

  // Get OAuth URL for Google authentication
  async getAuthUrl(userId: string): Promise<{ success: boolean; authUrl?: string; error?: string }> {
    try {
      const response: GoogleOAuthUrlResponse = await invoke('google_get_oauth_url', {
        userId
      });

      if (response.success) {
        return { 
          success: true, 
          authUrl: response.auth_url 
        };
      } else {
        return { 
          success: false, 
          error: response.error || 'Failed to get auth URL' 
        };
      }
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  }

  // Initiate Google OAuth flow
  async initiateAuth(userId: string): Promise<{ success: boolean; authUrl?: string; error?: string }> {
    try {
      const { success, authUrl, error } = await this.getAuthUrl(userId);
      
      if (!success || !authUrl) {
        return { success: false, error };
      }

      // Open OAuth URL in default browser
      await open(authUrl);

      return { success: true, authUrl };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to initiate OAuth' 
      };
    }
  }

  // Handle OAuth callback (called from redirect)
  async handleOAuthCallback(
    code: string, 
    state: string, 
    userId: string
  ): Promise<{ success: boolean; user?: any; error?: string }> {
    try {
      const response: GoogleOAuthCallbackResponse = await invoke('google_exchange_oauth_code', {
        code,
        state,
        userId
      });

      if (response.success && response.user) {
        // Cache connection status
        this.connectionStatus = {
          connected: true,
          user: response.user,
          tokens: response.tokens || undefined,
          last_sync: new Date().toISOString(),
          expires_at: response.tokens?.expires_at
        };

        return { 
          success: true, 
          user: response.user 
        };
      } else {
        return { 
          success: false, 
          error: response.error || 'OAuth callback failed' 
        };
      }
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'OAuth callback error' 
      };
    }
  }

  // Get current connection status
  async getConnectionStatus(userId: string): Promise<GoogleConnectionStatus> {
    try {
      const status: GoogleConnectionStatus = await invoke('google_get_connection', {
        userId
      });

      this.connectionStatus = status;
      return status;
    } catch (error) {
      const errorStatus: GoogleConnectionStatus = {
        connected: false,
        user: null,
        tokens: null,
        last_sync: null,
        expires_at: null
      };

      this.connectionStatus = errorStatus;
      return errorStatus;
    }
  }

  // Check if tokens are valid
  async checkTokens(userId: string): Promise<{ valid: boolean; expiresAt?: string; message?: string }> {
    try {
      const result = await invoke('google_check_tokens', { userId });
      
      return {
        valid: result.valid as boolean,
        expiresAt: result.expires_at as string,
        message: result.message as string
      };
    } catch (error) {
      return {
        valid: false,
        message: error instanceof Error ? error.message : 'Token check failed'
      };
    }
  }

  // Refresh expired tokens
  async refreshTokens(userId: string): Promise<{ success: boolean; error?: string }> {
    try {
      // First get current connection to get refresh token
      const currentStatus = await this.getConnectionStatus(userId);
      
      if (!currentStatus.tokens?.refresh_token) {
        return { 
          success: false, 
          error: 'No refresh token available. Please re-authenticate.' 
        };
      }

      const result = await invoke('google_refresh_tokens', {
        userId,
        refreshToken: currentStatus.tokens.refresh_token
      });

      if (result.success as boolean) {
        // Update cached status
        this.connectionStatus = {
          ...currentStatus,
          tokens: {
            access_token: result.access_token as string,
            refresh_token: result.refresh_token as string,
            token_type: 'Bearer',
            expires_at: result.expires_at as string,
            scope: currentStatus.tokens?.scope || ''
          },
          expires_at: result.expires_at as string
        };

        return { success: true };
      } else {
        return { 
          success: false, 
          error: 'Token refresh failed' 
        };
      }
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Token refresh error' 
      };
    }
  }

  // Disconnect from Google
  async disconnect(userId: string): Promise<{ success: boolean; error?: string }> {
    try {
      const success = await invoke('google_disconnect', { userId });
      
      if (success) {
        this.connectionStatus = {
          connected: false,
          user: null,
          tokens: null,
          last_sync: null,
          expires_at: null
        };
      }

      return { success: success as boolean };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Disconnect failed' 
      };
    }
  }

  // Get cached connection status
  getCachedConnectionStatus(): GoogleConnectionStatus | null {
    return this.connectionStatus;
  }

  // Check if user is connected
  isConnected(): boolean {
    return this.connectionStatus?.connected || false;
  }

  // Get current user
  getCurrentUser(): any | null {
    return this.connectionStatus?.user || null;
  }

  // Get access token (with auto-refresh)
  async getAccessToken(userId: string): Promise<{ success: boolean; token?: string; error?: string }> {
    try {
      // Check if current tokens are valid
      const tokenCheck = await this.checkTokens(userId);
      
      if (!tokenCheck.valid && tokenCheck.expiresAt) {
        // Try to refresh tokens
        const refreshResult = await this.refreshTokens(userId);
        
        if (!refreshResult.success) {
          return { 
            success: false, 
            error: refreshResult.error 
          };
        }
      }

      // Get updated connection status
      const status = await this.getConnectionStatus(userId);
      
      if (status.tokens?.access_token) {
        return { 
          success: true, 
          token: status.tokens.access_token 
        };
      } else {
        return { 
          success: false, 
          error: 'No access token available' 
        };
      }
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get access token' 
      };
    }
  }

  // Setup OAuth redirect listener (for web environment)
  setupOAuthRedirectListener(userId: string): void {
    // This would typically listen for OAuth redirect
    // In Tauri desktop app, this might be handled differently
    // For example, using deep links or custom protocol handlers
    
    console.log('OAuth redirect listener setup for user:', userId);
    
    // Example: Listen for custom protocol
    if (typeof window !== 'undefined') {
      window.addEventListener('message', (event) => {
        if (event.data.type === 'GOOGLE_OAUTH_CALLBACK') {
          const { code, state } = event.data.payload;
          this.handleOAuthCallback(code, state, userId);
        }
      });
    }
  }

  // Validate OAuth state (prevent CSRF attacks)
  validateState(state: string, expectedState: string): boolean {
    return state === expectedState;
  }
}

// Export singleton instance
export const googleAuth = GoogleAuthService.getInstance();

// OAuth Helper Functions
export class GoogleOAuthHelper {
  // Extract authorization code from URL
  static extractAuthCode(url: string): { code?: string; state?: string; error?: string } | null {
    try {
      const urlObj = new URL(url);
      const code = urlObj.searchParams.get('code');
      const state = urlObj.searchParams.get('state');
      const error = urlObj.searchParams.get('error');

      if (error) {
        return { error };
      }

      if (code && state) {
        return { code, state };
      }

      return null;
    } catch {
      return null;
    }
  }

  // Generate secure state for OAuth
  static generateState(userId: string): string {
    const timestamp = Date.now().toString();
    const random = Math.random().toString(36).substring(2, 15);
    return `google_oauth_${userId}_${timestamp}_${random}`;
  }

  // Check if URL is OAuth callback
  static isOAuthCallback(url: string): boolean {
    const callbackUrls = [
      'http://localhost:3000/oauth/google/callback',
      'http://127.0.0.1:3000/oauth/google/callback'
    ];

    return callbackUrls.some(callbackUrl => url.startsWith(callbackUrl));
  }
}

// React Hook for Google Authentication
export function useGoogleAuth(userId: string) {
  const [connectionStatus, setConnectionStatus] = React.useState<GoogleConnectionStatus | null>(null);
  const [isConnecting, setIsConnecting] = React.useState(false);

  // Initialize connection status on mount
  React.useEffect(() => {
    googleAuth.getConnectionStatus(userId).then(setConnectionStatus);
  }, [userId]);

  const connect = async () => {
    setIsConnecting(true);
    const result = await googleAuth.initiateAuth(userId);
    
    if (result.success) {
      // Set up redirect listener
      googleAuth.setupOAuthRedirectListener(userId);
    }
    
    setIsConnecting(false);
    return result;
  };

  const disconnect = async () => {
    setIsConnecting(true);
    const result = await googleAuth.disconnect(userId);
    
    if (result.success) {
      setConnectionStatus({
        connected: false,
        user: null,
        tokens: null,
        last_sync: null,
        expires_at: null
      });
    }
    
    setIsConnecting(false);
    return result;
  };

  const refreshConnection = async () => {
    const result = await googleAuth.getConnectionStatus(userId);
    setConnectionStatus(result);
    return result;
  };

  return {
    connectionStatus,
    isConnecting,
    isConnected: connectionStatus?.connected || false,
    user: connectionStatus?.user || null,
    connect,
    disconnect,
    refreshConnection
  };
}

// Export types for external use
export type { GoogleConnectionStatus, GoogleOAuthUrlResponse, GoogleOAuthCallbackResponse };