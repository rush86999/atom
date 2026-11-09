/**
 * Biometric Service
 *
 * Manages biometric authentication for secure actions.
 *
 * Features:
 * - Biometric availability check
 * - Biometric authentication
 * - Biometric enrollment check
 * - Fallback to passcode
 * - Biometric preference storage
 * - Authentication attempts tracking
 * - Lockout after failures
 * - Biometric type detection (Face ID vs Touch ID)
 * - Prompt customization
 * - Error handling
 *
 * Uses expo-local-authentication for cross-platform biometric support.
 */

import * as LocalAuthentication from 'expo-local-authentication';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

// Types
export type BiometricType = 'none' | 'fingerprint' | 'facial' | 'iris';

export type BiometricError =
  | 'not_available'
  | 'not_enrolled'
  | 'locked_out'
  | 'authentication_failed'
  | 'user_cancelled'
  | 'system_cancelled'
  | 'passcode_not_set'
  | 'unknown';

export interface BiometricResult {
  success: boolean;
  error?: string;
  biometricType?: BiometricType;
}

export interface BiometricPreferences {
  enabled: boolean;
  requireForLogin: boolean;
  requireForPayments: boolean;
  requireForSensitiveActions: boolean;
  lockoutEnabled: boolean;
  maxAttempts: number;
}

export interface AuthenticationAttempt {
  timestamp: number;
  success: boolean;
  error?: BiometricError;
  biometricType: BiometricType;
}

// Configuration
const PREFERENCES_KEY = 'atom_biometric_preferences';
const ATTEMPTS_KEY = 'atom_biometric_attempts';
const DEFAULT_PREFERENCES: BiometricPreferences = {
  enabled: true,
  requireForLogin: false,
  requireForPayments: true,
  requireForSensitiveActions: true,
  lockoutEnabled: true,
  maxAttempts: 5,
};

/**
 * Expo LocalAuthentication returns failure codes as plain strings. Native iOS/Android
 * emissions use `lockout`; `locked_out` is accepted only as an internal compatibility
 * alias and is never sent to the native module by this service.
 */
function getErrorCode(error: unknown): string | undefined {
  if (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    typeof error.code === 'string'
  ) {
    return error.code;
  }

  return undefined;
}

function getErrorMessage(error: unknown): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'message' in error &&
    typeof error.message === 'string' &&
    error.message.length > 0
  ) {
    return error.message;
  }

  return 'Authentication failed';
}

/**
 * Biometric Service
 */
class BiometricService {
  private preferences: BiometricPreferences = DEFAULT_PREFERENCES;
  private attempts: AuthenticationAttempt[] = [];
  private lockoutUntil: number | null = null;

  /**
   * Initialize the biometric service
   */
  async initialize(): Promise<void> {
    try {
      // Load preferences
      await this.loadPreferences();

      // Load attempts
      await this.loadAttempts();

      console.log('BiometricService: Initialized');
    } catch (error) {
      console.error('BiometricService: Failed to initialize:', error);
    }
  }

  /**
   * Check biometric availability
   */
  async isAvailable(): Promise<boolean> {
    try {
      const compatible = await LocalAuthentication.hasHardwareAsync();
      return compatible;
    } catch (error) {
      console.error('BiometricService: Failed to check availability:', error);
      return false;
    }
  }

  /**
   * Check if biometric is enrolled
   */
  async isEnrolled(): Promise<boolean> {
    try {
      const enrolled = await LocalAuthentication.isEnrolledAsync();
      return enrolled;
    } catch (error) {
      console.error('BiometricService: Failed to check enrollment:', error);
      return false;
    }
  }

  /**
   * Get biometric type
   */
  async getBiometricType(): Promise<BiometricType> {
    try {
      const supportedTypes = await LocalAuthentication.supportedAuthenticationTypesAsync();

      if (supportedTypes.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
        return 'facial';
      }

      if (supportedTypes.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
        return 'fingerprint';
      }

      if (supportedTypes.includes(LocalAuthentication.AuthenticationType.IRIS)) {
        return 'iris';
      }

      return 'none';
    } catch (error) {
      console.error('BiometricService: Failed to get biometric type:', error);
      return 'none';
    }
  }

  /**
   * Authenticate with biometric
   */
  async authenticate(options?: {
    promptMessage?: string;
    fallbackLabel?: string;
    cancelLabel?: string;
    disableDeviceFallback?: boolean;
  }): Promise<BiometricResult> {
    try {
      // Check if locked out
      if (this.lockoutUntil && Date.now() < this.lockoutUntil) {
        const remainingMinutes = Math.ceil((this.lockoutUntil - Date.now()) / 60000);
        return {
          success: false,
          error: `Locked out. Try again in ${remainingMinutes} minutes.`,
        };
      }

      // Check availability
      const available = await this.isAvailable();
      if (!available) {
        return {
          success: false,
          error: 'Biometric authentication is not available on this device.',
        };
      }

      // Check enrollment
      const enrolled = await this.isEnrolled();
      if (!enrolled) {
        return {
          success: false,
          error: 'No biometric data enrolled. Please enroll in your device settings.',
        };
      }

      // Get biometric type
      const biometricType = await this.getBiometricType();

      // Authenticate
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: options?.promptMessage || 'Authenticate to continue',
        fallbackLabel: options?.fallbackLabel || 'Use Passcode',
        cancelLabel: options?.cancelLabel || 'Cancel',
        disableDeviceFallback: options?.disableDeviceFallback || false,
      });

      if (!result.success) {
        const classification = this.classifySdkError(result.error);

        // Record attempt
        await this.recordAttempt(false, classification.type, biometricType);

        return {
          success: false,
          error: classification.message,
          biometricType,
        };
      }

      // Record the success, then clear prior failures and lockout.
      await this.recordAttempt(true, undefined, biometricType);
      this.lockoutUntil = null;
      this.attempts = [];
      await this.saveAttempts();

      return {
        success: true,
        error: undefined,
        biometricType,
      };
    } catch (error: unknown) {
      // Record failed attempt
      const errorType = this.mapThrownErrorToType(error);
      await this.recordAttempt(false, errorType, await this.getBiometricType());

      return {
        success: false,
        error: getErrorMessage(error),
      };
    }
  }

  /**
   * Map an Expo LocalAuthentication failure string to our public error classification.
   * Unknown SDK codes are generic authentication failures, never successes.
   */
  private classifySdkError(error: string | undefined): {
    type: BiometricError;
    message: string;
  } {
    switch (error) {
      case 'not_enrolled':
        return {
          type: 'not_enrolled',
          message:
            'No biometric enrolled. Please set up biometric authentication in your device settings.',
        };
      case 'lockout':
      case 'locked_out':
        return {
          type: 'locked_out',
          message: 'Too many attempts. Biometric authentication is temporarily locked.',
        };
      case 'user_cancel':
        return {
          type: 'user_cancelled',
          message: 'Authentication was cancelled.',
        };
      case 'system_cancel':
        return {
          type: 'system_cancelled',
          message: 'Authentication was cancelled.',
        };
      case 'passcode_not_set':
        return {
          type: 'passcode_not_set',
          message:
            'Device passcode is not set. Please set a passcode in your device settings.',
        };
      case 'not_available':
        return {
          type: 'not_available',
          message: 'Biometric authentication is not available on this device.',
        };
      case 'authentication_failed':
      default:
        return {
          type: 'authentication_failed',
          message: 'Authentication failed',
        };
    }
  }

  /**
   * Map an unexpected thrown value to a BiometricError type.
   */
  private mapThrownErrorToType(error: unknown): BiometricError {
    const code = getErrorCode(error);

    if (!code) {
      return 'unknown';
    }

    return this.classifySdkError(code).type;
  }

  /**
   * Record authentication attempt
   */
  private async recordAttempt(
    success: boolean,
    error?: BiometricError,
    biometricType: BiometricType = 'none'
  ): Promise<void> {
    const attempt: AuthenticationAttempt = {
      timestamp: Date.now(),
      success,
      error,
      biometricType,
    };

    this.attempts.push(attempt);

    // Keep only recent attempts (last 20)
    if (this.attempts.length > 20) {
      this.attempts = this.attempts.slice(-20);
    }

    await this.saveAttempts();

    // Check if lockout should be applied
    if (!success && this.preferences.lockoutEnabled) {
      const recentFailures = this.attempts.filter(
        (a) => !a.success && Date.now() - a.timestamp < 300000 // 5 minutes
      );

      if (recentFailures.length >= this.preferences.maxAttempts) {
        // Lock out for 5 minutes
        this.lockoutUntil = Date.now() + 300000;
        console.warn('BiometricService: Locked out after too many failed attempts');
      }
    }
  }

  /**
   * Get recent authentication attempts
   */
  getRecentAttempts(count: number = 10): AuthenticationAttempt[] {
    return this.attempts.slice(-count);
  }

  /**
   * Clear authentication attempts
   */
  async clearAttempts(): Promise<void> {
    this.attempts = [];
    this.lockoutUntil = null;
    await this.saveAttempts();
    console.log('BiometricService: Attempts cleared');
  }

  /**
   * Get lockout status
   */
  getLockoutStatus(): { locked: boolean; remainingMinutes?: number } {
    if (!this.lockoutUntil || Date.now() >= this.lockoutUntil) {
      return { locked: false };
    }

    const remainingMinutes = Math.ceil((this.lockoutUntil - Date.now()) / 60000);
    return {
      locked: true,
      remainingMinutes,
    };
  }

  /**
   * Get biometric preferences
   */
  getPreferences(): BiometricPreferences {
    return { ...this.preferences };
  }

  /**
   * Update biometric preferences
   */
  async updatePreferences(updates: Partial<BiometricPreferences>): Promise<void> {
    this.preferences = {
      ...this.preferences,
      ...updates,
    };
    await this.savePreferences();
    console.log('BiometricService: Preferences updated', this.preferences);
  }

  /**
   * Get biometric label (Face ID, Touch ID, etc.)
   */
  async getBiometricLabel(): Promise<string> {
    const type = await this.getBiometricType();

    switch (type) {
      case 'facial':
        return Platform.OS === 'ios' ? 'Face ID' : 'Face Recognition';
      case 'fingerprint':
        return Platform.OS === 'ios' ? 'Touch ID' : 'Fingerprint';
      case 'iris':
        return 'Iris Scan';
      default:
        return 'Biometric Authentication';
    }
  }

  /**
   * Check if biometric is enabled for a specific action
   */
  isBiometricEnabledFor(action: 'login' | 'payments' | 'sensitive'): boolean {
    switch (action) {
      case 'login':
        return this.preferences.requireForLogin;
      case 'payments':
        return this.preferences.requireForPayments;
      case 'sensitive':
        return this.preferences.requireForSensitiveActions;
      default:
        return false;
    }
  }

  /**
   * Save preferences to storage
   */
  private async savePreferences(): Promise<void> {
    try {
      await AsyncStorage.setItem(PREFERENCES_KEY, JSON.stringify(this.preferences));
    } catch (error) {
      console.error('BiometricService: Failed to save preferences:', error);
    }
  }

  /**
   * Load preferences from storage
   */
  private async loadPreferences(): Promise<void> {
    try {
      const data = await AsyncStorage.getItem(PREFERENCES_KEY);
      if (data) {
        this.preferences = {
          ...DEFAULT_PREFERENCES,
          ...JSON.parse(data),
        };
        console.log('BiometricService: Preferences loaded');
      }
    } catch (error) {
      console.error('BiometricService: Failed to load preferences:', error);
    }
  }

  /**
   * Save attempts to storage
   */
  private async saveAttempts(): Promise<void> {
    try {
      await AsyncStorage.setItem(ATTEMPTS_KEY, JSON.stringify(this.attempts));
    } catch (error) {
      console.error('BiometricService: Failed to save attempts:', error);
    }
  }

  /**
   * Load attempts from storage
   */
  private async loadAttempts(): Promise<void> {
    try {
      const data = await AsyncStorage.getItem(ATTEMPTS_KEY);
      if (data) {
        this.attempts = JSON.parse(data);

        // Clean up old attempts (older than 1 hour)
        const oneHourAgo = Date.now() - 3600000;
        this.attempts = this.attempts.filter((a) => a.timestamp > oneHourAgo);

        console.log('BiometricService: Attempts loaded', this.attempts.length, 'entries');
      }
    } catch (error) {
      console.error('BiometricService: Failed to load attempts:', error);
    }
  }

  /**
   * Reset service state (for testing)
   */
  _resetState(): void {
    this.preferences = DEFAULT_PREFERENCES;
    this.attempts = [];
    this.lockoutUntil = null;
  }
}

// Export singleton instance
export const biometricService = new BiometricService();

export default biometricService;
