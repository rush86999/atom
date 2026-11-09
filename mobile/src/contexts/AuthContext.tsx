/**
 * AuthContext - Mobile Authentication Context
 *
 * Provides authentication functionality for the mobile app including:
 * - Login/logout with JWT tokens
 * - Biometric authentication (Face ID, Touch ID)
 * - Token management with SecureStore
 * - Device registration
 * - Session management
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { secureGet, secureSet, readAccessTokenSnapshot, commitAuthSession, clearAuthSession, AccessTokenSnapshot, subscribeToSessionRevocation, isAccessTokenSnapshotCurrent, getAccessTokenGeneration } from '../storage/secureTokenStorage';
import * as Device from 'expo-device';
import Constants from 'expo-constants';

// Types
interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  expires_at: number;
}

interface DeviceInfo {
  device_token: string;
  platform: 'ios' | 'android';
  model: string;
  os_version: string;
  app_version: string;
}

interface LoginCredentials {
  email: string;
  password: string;
}

interface BiometricResult {
  success: boolean;
  error?: string;
}

interface AuthContextType {
  // State
  isAuthenticated: boolean;
  isLoading: boolean;
  user: any | null;
  deviceInfo: DeviceInfo | null;

  // Methods
  login: (credentials: LoginCredentials) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<boolean>;
  registerBiometric: (publicKey: string) => Promise<BiometricResult>;
  authenticateWithBiometric: () => Promise<BiometricResult>;
  isBiometricAvailable: () => Promise<boolean>;
  registerDevice: (deviceToken: string) => Promise<{ success: boolean; deviceId?: string; error?: string }>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Constants
const ACCESS_TOKEN_KEY = 'atom_access_token';
const REFRESH_TOKEN_KEY = 'atom_refresh_token';
const TOKEN_EXPIRY_KEY = 'atom_token_expiry';
const USER_DATA_KEY = 'atom_user_data';
const DEVICE_ID_KEY = 'atom_device_id';
const BIOMETRIC_KEY = 'atom_biometric_enabled';

// API Base URL - use Constants.expoConfig pattern for Jest compatibility
const API_BASE_URL = Constants.expoConfig?.extra?.apiUrl || 'http://localhost:8000';

/** Accept the timezone-qualified expiry emitted by the mobile auth API. */
function serverExpiry(value: unknown): string | null {
  if (typeof value !== 'string' || !/(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
  const milliseconds = Date.parse(value);
  return Number.isFinite(milliseconds) && milliseconds > Date.now() ? String(milliseconds) : null;
}

/**
 * AuthProvider Component
 */
export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<any | null>(null);
  const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null);
  const refreshInFlight = React.useRef<{ generation: number; promise: Promise<boolean> } | null>(null);

  /**
   * Initialize authentication state on mount
   */
  useEffect(() => {
    const unsubscribe = subscribeToSessionRevocation(() => {
      setIsAuthenticated(false);
      setUser(null);
      setDeviceInfo(null);
    });
    initializeAuth();
    return unsubscribe;
  }, []);

  const initializeAuth = async () => {
    const startingGeneration = getAccessTokenGeneration();
    try {
      setIsLoading(true);

      // Check for stored tokens
      const startingSession = await readAccessTokenSnapshot();
      const accessToken = startingSession.token;
      const tokenExpiry = await SecureStore.getItemAsync(TOKEN_EXPIRY_KEY);
      const userData = await AsyncStorage.getItem(USER_DATA_KEY);
      if (!isAccessTokenSnapshotCurrent(startingSession)) return;

      if (accessToken && tokenExpiry) {
        const expiryTime = parseInt(tokenExpiry, 10);
        const now = Date.now();

        // Check if token is expired
        if (expiryTime > now) {
          // Token is valid
          if (userData) {
            setUser(JSON.parse(userData));
          }
          setIsAuthenticated(true);

          // Refresh token if expiring soon (< 5 minutes)
          if (expiryTime - now < 5 * 60 * 1000) {
            await refreshToken();
          }
        } else {
          // Token expired, try to refresh
          const refreshed = await refreshToken();
          if (!refreshed) {
            await clearAuthSession(startingSession.generation);
          } else {
            const current = await readAccessTokenSnapshot();
            const currentUser = await AsyncStorage.getItem(USER_DATA_KEY);
            if (current.token && isAccessTokenSnapshotCurrent(current)) {
              setUser(currentUser ? JSON.parse(currentUser) : null);
              setIsAuthenticated(true);
            }
          }
        }
      }

      // Load device info
      await loadDeviceInfo();
    } catch (error) {
      console.error('Failed to initialize auth');
      try { await clearAuthSession(startingGeneration); } catch {
        console.error('Local session cleanup unavailable; access remains revoked');
      }
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Load device information
   */
  const loadDeviceInfo = async () => {
    try {
      const storedDeviceId = await secureGet(DEVICE_ID_KEY);
      // Device info would be populated from expo-device constants
      setDeviceInfo({
        device_token: storedDeviceId || generateDeviceId(),
        platform: Platform.OS as 'ios' | 'android',
        model: `${Platform.OS} ${Platform.Version}`,
        os_version: Platform.Version as any,
        app_version: '1.0.0', // Would come from app.json
      });
    } catch (error) {
      console.error('Failed to load device info:', error);
    }
  };

  /**
   * Generate a unique device ID
   */
  const generateDeviceId = (): string => {
    return `device_${Date.now()}_${Math.random().toString(36).substring(7)}`;
  };

  /**
   * Login with email and password
   */
  const login = async (credentials: LoginCredentials): Promise<{ success: boolean; error?: string }> => {
    try {
      setIsLoading(true);

      const startingSession = await readAccessTokenSnapshot();

      // Generate device token if not exists
      let deviceToken = await secureGet(DEVICE_ID_KEY);
      if (!deviceToken) {
        deviceToken = generateDeviceId();
        await secureSet(DEVICE_ID_KEY, deviceToken);
      }

      // Build device info
      const deviceInfo = {
        platform: Platform.OS as 'ios' | 'android',
        model: Device.modelName || 'Unknown',
        os_version: Platform.Version as string,
        app_version: Constants.expoConfig?.version || '1.0.0',
        device_name: Device.deviceName || 'Unknown Device',
        is_device: Device.isDevice,
      };

      // Send login request with device information
      const response = await fetch(`${API_BASE_URL}/api/auth/mobile/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...credentials,
          device_token: deviceToken,
          platform: Platform.OS,
          device_info: deviceInfo,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));

        // Provide specific error messages based on status code
        if (response.status === 401) {
          return {
            success: false,
            error: 'Invalid email or password',
          };
        } else if (response.status === 400) {
          return {
            success: false,
            error: errorData.detail || 'Invalid request. Please check your input.',
          };
        } else if (response.status === 429) {
          return {
            success: false,
            error: 'Too many login attempts. Please try again later.',
          };
        } else if (response.status >= 500) {
          return {
            success: false,
            error: 'Server error. Please try again later.',
          };
        }

        return {
          success: false,
          error: errorData.detail || `Login failed (status: ${response.status})`,
        };
      }

      const data = await response.json();

      const expiresAt = serverExpiry(data.expires_at);
      if (!expiresAt) return { success: false, error: 'Invalid session expiry from server' };
      const committed = await commitAuthSession(startingSession, {
        token: data.access_token,
        refreshToken: data.refresh_token,
        expiresAt: String(expiresAt),
        userData: data.user ? JSON.stringify(data.user) : null,
      });
      if (!committed) return { success: false, error: 'Login superseded by a session change' };
      setUser(data.user || null);

      // Update device info
      setDeviceInfo({
        device_token: deviceToken,
        platform: Platform.OS as 'ios' | 'android',
        model: deviceInfo.model,
        os_version: deviceInfo.os_version,
        app_version: deviceInfo.app_version,
      });

      setIsAuthenticated(true);

      return { success: true };
    } catch (error: any) {
      console.error('Login error:', error);
      return {
        success: false,
        error: error.message || 'Network error',
      };
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Logout and clear tokens
   */
  const logout = async () => {
    const accessToken = await secureGet(ACCESS_TOKEN_KEY);
    // Revoke locally before waiting for an unavailable or slow backend.
    setIsAuthenticated(false);
    setUser(null);
    setDeviceInfo(null);
    await clearTokens();
    if (accessToken) {
      try {
        await fetch(`${API_BASE_URL}/api/auth/mobile/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${accessToken}` },
        });
      } catch {
        console.warn('Backend logout unavailable after local session clear');
      }
    }
  };

  /** Clear the same canonical bundle used by login and refresh. */
  const clearTokens = async () => {
    await clearAuthSession();
  };

  /**
   * Refresh access token
   */
  const refreshToken = async (): Promise<boolean> => {
    try {
      const startingSession = await readAccessTokenSnapshot();
      const existing = refreshInFlight.current;
      if (existing?.generation === startingSession.generation) return existing.promise;
      const promise = performTokenRefresh(startingSession);
      refreshInFlight.current = { generation: startingSession.generation, promise };
      const cleanup = () => {
        if (refreshInFlight.current?.promise === promise) refreshInFlight.current = null;
      };
      promise.then(cleanup, cleanup);
      return promise;
    } catch {
      return false;
    }
  };

  const performTokenRefresh = async (startingSession: AccessTokenSnapshot): Promise<boolean> => {
    try {
      const refreshTokenValue = await secureGet(REFRESH_TOKEN_KEY);

      if (!refreshTokenValue) {
        return false;
      }

      const response = await fetch(`${API_BASE_URL}/api/auth/mobile/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshTokenValue }),
      });

      if (!response.ok) {
        return false;
      }

      const data = await response.json();

      const expiresAt = serverExpiry(data.expires_at);
      if (!expiresAt) return false;
      return await commitAuthSession(startingSession, {
        token: data.access_token,
        refreshToken: data.refresh_token || refreshTokenValue,
        expiresAt: String(expiresAt),
      }, refreshTokenValue);
    } catch (error) {
      console.error('Token refresh error:', error);
      return false;
    }
  };

  /**
   * Check if biometric authentication is available
   */
  const isBiometricAvailable = async (): Promise<boolean> => {
    try {
      const compatible = await LocalAuthentication.hasHardwareAsync();
      const enrolled = await LocalAuthentication.isEnrolledAsync();
      return compatible && enrolled;
    } catch (error) {
      console.error('Biometric check error:', error);
      return false;
    }
  };

  /**
   * Register device for biometric authentication
   */
  const registerBiometric = async (publicKey: string): Promise<BiometricResult> => {
    try {
      const accessToken = await secureGet(ACCESS_TOKEN_KEY);
      if (!accessToken) {
        return { success: false, error: 'Not authenticated' };
      }

      const response = await fetch(`${API_BASE_URL}/api/auth/mobile/biometric/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ public_key: publicKey }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        return { success: false, error: errorData.detail || 'Registration failed' };
      }

      // Mark biometric as enabled
      await AsyncStorage.setItem(BIOMETRIC_KEY, 'true');

      return { success: true };
    } catch (error: any) {
      console.error('Biometric registration error:', error);
      return { success: false, error: error.message || 'Network error' };
    }
  };

  /**
   * Authenticate with biometric (Face ID / Touch ID)
   */
  const authenticateWithBiometric = async (): Promise<BiometricResult> => {
    try {
      const hasBiometric = await isBiometricAvailable();
      if (!hasBiometric) {
        return { success: false, error: 'Biometric not available' };
      }

      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Authenticate to access Atom',
        fallbackLabel: 'Use password',
        cancelLabel: 'Cancel',
      });

      if (result.success) {
        return { success: true };
      } else {
        return { success: false, error: 'Biometric authentication failed' };
      }
    } catch (error: any) {
      console.error('Biometric auth error:', error);
      if (error.code === 'user_cancel') {
        return { success: false, error: 'Cancelled by user' };
      }
      return { success: false, error: error.message || 'Authentication error' };
    }
  };

  /**
   * Register device for push notifications
   */
  const registerDevice = async (deviceToken: string): Promise<{ success: boolean; deviceId?: string; error?: string }> => {
    try {
      const accessToken = await secureGet(ACCESS_TOKEN_KEY);
      if (!accessToken) {
        return { success: false, error: 'Not authenticated' };
      }

      if (!deviceInfo) {
        return { success: false, error: 'Device info not available' };
      }

      const response = await fetch(`${API_BASE_URL}/api/mobile/notifications/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          device_token: deviceToken,
          platform: deviceInfo.platform,
          device_info: deviceInfo,
          notification_enabled: true,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        return { success: false, error: errorData.detail || 'Registration failed' };
      }

      const data = await response.json();

      // Store device ID
      await secureSet(DEVICE_ID_KEY, data.device_id);

      return { success: true, deviceId: data.device_id };
    } catch (error: any) {
      console.error('Device registration error:', error);
      return { success: false, error: error.message || 'Network error' };
    }
  };

  const value: AuthContextType = {
    isAuthenticated,
    isLoading,
    user,
    deviceInfo,
    login,
    logout,
    refreshToken,
    registerBiometric,
    authenticateWithBiometric,
    isBiometricAvailable,
    registerDevice,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

/**
 * useAuth Hook
 */
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
