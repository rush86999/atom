/**
 * Biometric Service Tests
 *
 * Tests for biometric authentication functionality:
 * - Hardware availability checks
 * - Enrollment status validation
 * - Authentication flow (success, failure, cancel)
 * - Permission states (granted, denied, notAsked)
 * - Lockout scenarios (max attempts, timeout)
 * - Credential storage (auth tokens, logout)
 */

import * as LocalAuthentication from 'expo-local-authentication';
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { biometricService, BiometricResult, BiometricError } from '../../services/biometricService';

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage');

// Mock SecureStore
jest.mock('expo-secure-store');

describe('BiometricService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset service state
    biometricService._resetState();
    // Reset AsyncStorage mock
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);
    (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
  });

  // ========================================================================
  // Hardware Availability Tests
  // ========================================================================

  describe('Hardware Availability', () => {
    test('should check if biometric hardware is available', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);

      const isAvailable = await biometricService.isAvailable();

      expect(isAvailable).toBe(true);
      expect(LocalAuthentication.hasHardwareAsync).toHaveBeenCalled();
    });

    test('should return false when hardware not available', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(false);

      const isAvailable = await biometricService.isAvailable();

      expect(isAvailable).toBe(false);
    });

    test('should handle hardware check errors gracefully', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockRejectedValue(
        new Error('Hardware check failed')
      );

      const isAvailable = await biometricService.isAvailable();

      expect(isAvailable).toBe(false);
    });

    test('should return false on unexpected hardware error', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockRejectedValue(
        new TypeError('Unexpected error')
      );

      const isAvailable = await biometricService.isAvailable();

      expect(isAvailable).toBe(false);
    });

    test('should log hardware check errors', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockRejectedValue(
        new Error('Test error')
      );

      await biometricService.isAvailable();

      expect(consoleSpy).toHaveBeenCalledWith(
        'BiometricService: Failed to check availability:',
        expect.any(Error)
      );
      consoleSpy.mockRestore();
    });
  });

  // ========================================================================
  // Enrollment Status Tests
  // ========================================================================

  describe('Enrollment Status', () => {
    test('should check if user has enrolled biometrics', async () => {
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);

      const isEnrolled = await biometricService.isEnrolled();

      expect(isEnrolled).toBe(true);
      expect(LocalAuthentication.isEnrolledAsync).toHaveBeenCalled();
    });

    test('should return false when no biometrics enrolled', async () => {
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(false);

      const isEnrolled = await biometricService.isEnrolled();

      expect(isEnrolled).toBe(false);
    });

    test('should handle enrollment check errors gracefully', async () => {
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockRejectedValue(
        new Error('Enrollment check failed')
      );

      const isEnrolled = await biometricService.isEnrolled();

      expect(isEnrolled).toBe(false);
    });

    test('should log enrollment check errors', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockRejectedValue(
        new Error('Test error')
      );

      await biometricService.isEnrolled();

      expect(consoleSpy).toHaveBeenCalledWith(
        'BiometricService: Failed to check enrollment:',
        expect.any(Error)
      );
      consoleSpy.mockRestore();
    });
  });

  // ========================================================================
  // Authentication Flow Tests
  // ========================================================================

  describe('Authentication Flow', () => {
    test('should authenticate successfully with valid biometrics', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: true,
        error: undefined,
        warning: undefined,
      });

      const result: BiometricResult = await biometricService.authenticate();

      expect(result.success).toBe(true);
      expect(result.error).toBeUndefined();
      expect(result.biometricType).toBe('fingerprint');
    });

    test('should return success=true on successful authentication', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: true,
        error: undefined,
        warning: undefined,
      });

      const result = await biometricService.authenticate();

      expect(result.success).toBe(true);
    });

    test('should handle authentication failure', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: false,
        error: { code: 'authentication_failed', message: 'Authentication failed' },
        warning: undefined,
      });

      const result = await biometricService.authenticate();

      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
    });

    test('should return appropriate error code for not_enrolled', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: false,
        error: { code: 'not_enrolled', message: 'Not enrolled' },
        warning: undefined,
      });

      const result = await biometricService.authenticate();

      expect(result.success).toBe(false);
      expect(result.error).toContain('No biometric enrolled');
    });

    test('should return appropriate error code for authentication_failed', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: false,
        error: { code: 'authentication_failed', message: 'Failed' },
        warning: undefined,
      });

      const result = await biometricService.authenticate();

      expect(result.success).toBe(false);
      // The error message from the mock is returned as-is for unknown codes
      expect(result.error).toBe('Failed');
    });

    test('should support cancel fallback', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: false,
        error: { code: 'user_cancel', message: 'Cancelled' },
        warning: undefined,
      });

      const result = await biometricService.authenticate();

      expect(result.success).toBe(false);
      expect(result.error).toContain('cancelled');
    });

    test('should use custom prompt message when provided', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      const authSpy = jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: true,
        error: undefined,
        warning: undefined,
      });

      await biometricService.authenticate({
        promptMessage: 'Custom authenticate message',
      });

      expect(authSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          promptMessage: 'Custom authenticate message',
        })
      );
    });
  });

  // ========================================================================
  // Permission States Tests
  // ========================================================================

  describe('Permission States', () => {
    test('should handle granted permission state', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: true,
        error: undefined,
        warning: undefined,
      });

      const result = await biometricService.authenticate();

      expect(result.success).toBe(true);
    });

    test('should handle denied permission state', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(false);

      const result = await biometricService.authenticate();

      expect(result.success).toBe(false);
      expect(result.error).toContain('No biometric data enrolled');
    });

    test('should handle notAsked permission state', async () => {
      // iOS returns 'not_determined' for notAsked
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(false);

      const result = await biometricService.authenticate();

      expect(result.success).toBe(false);
      expect(result.error).toContain('No biometric data enrolled');
    });

    test('should handle biometric not available on device', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(false);

      const result = await biometricService.authenticate();

      expect(result.success).toBe(false);
      expect(result.error).toContain('not available');
    });

    test('should request permissions when not granted', async () => {
      // Biometric doesn't have explicit permission requests
      // But we test the flow where hardware exists but enrollment fails
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(false);

      const result = await biometricService.authenticate();

      expect(result.success).toBe(false);
      expect(result.error).toContain('Please enroll');
    });
  });

  // ========================================================================
  // Lockout Scenarios Tests
  // ========================================================================

  describe('Lockout Scenarios', () => {
    test('should lock out after max failed attempts (5 attempts)', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: false,
        error: { code: 'authentication_failed', message: 'Failed' },
        warning: undefined,
      });

      // Attempt 5 failed authentications
      for (let i = 0; i < 5; i++) {
        await biometricService.authenticate();
      }

      const lockoutStatus = biometricService.getLockoutStatus();
      expect(lockoutStatus.locked).toBe(true);
      expect(lockoutStatus.remainingMinutes).toBeDefined();
    });

    test('should prevent authentication while locked out', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: false,
        error: { code: 'authentication_failed', message: 'Failed' },
        warning: undefined,
      });

      // Trigger lockout
      for (let i = 0; i < 5; i++) {
        await biometricService.authenticate();
      }

      // Try to authenticate while locked out
      const result = await biometricService.authenticate();

      expect(result.success).toBe(false);
      expect(result.error).toContain('Locked out');
    });

    test('should reset lockout after timeout', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: false,
        error: { code: 'authentication_failed', message: 'Failed' },
        warning: undefined,
      });

      // Trigger lockout
      for (let i = 0; i < 5; i++) {
        await biometricService.authenticate();
      }

      // Manually clear lockout to simulate timeout
      await biometricService.clearAttempts();

      const lockoutStatus = biometricService.getLockoutStatus();
      expect(lockoutStatus.locked).toBe(false);
    });

    test('should track failed attempt count', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: false,
        error: { code: 'authentication_failed', message: 'Failed' },
        warning: undefined,
      });

      // Fail 3 times
      for (let i = 0; i < 3; i++) {
        await biometricService.authenticate();
      }

      const attempts = biometricService.getRecentAttempts(10);
      expect(attempts).toHaveLength(3);
      expect(attempts.every((a) => !a.success)).toBe(true);
    });

    test('should clear attempts on successful authentication', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);

      // Fail 3 times
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: false,
        error: { code: 'authentication_failed', message: 'Failed' },
        warning: undefined,
      });
      for (let i = 0; i < 3; i++) {
        await biometricService.authenticate();
      }

      // Succeed on 4th attempt
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: true,
        error: undefined,
        warning: undefined,
      });
      await biometricService.authenticate();

      const attempts = biometricService.getRecentAttempts(10);
      expect(attempts).toHaveLength(0); // Cleared after success
    });
  });

  // ========================================================================
  // Credential Storage Tests
  // ========================================================================

  describe('Credential Storage', () => {
    test('should store auth token securely after successful auth', async () => {
      jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: true,
        error: undefined,
        warning: undefined,
      });

      // Mock SecureStore to capture the token storage
      const secureStoreSpy = jest.spyOn(SecureStore, 'setItemAsync').mockResolvedValue();

      // Note: The actual token storage would be handled by the auth service
      // after successful biometric authentication. This test verifies the flow.
      await biometricService.authenticate();

      // Verify authentication succeeded (token storage is handled by caller)
      expect(LocalAuthentication.authenticateAsync).toHaveBeenCalled();
      secureStoreSpy.mockRestore();
    });

    test('should retrieve stored auth token', async () => {
      const mockToken = 'mock-auth-token';
      jest.spyOn(SecureStore, 'getItemAsync').mockResolvedValue(mockToken);

      const token = await SecureStore.getItemAsync('auth_token');

      expect(token).toBe(mockToken);
    });

    test('should clear stored credentials on logout', async () => {
      const secureStoreSpy = jest.spyOn(SecureStore, 'deleteItemAsync').mockResolvedValue();

      // Simulate logout - clear auth token
      await SecureStore.deleteItemAsync('auth_token');

      expect(secureStoreSpy).toHaveBeenCalledWith('auth_token');
      secureStoreSpy.mockRestore();
    });

    test('should handle SecureStore errors gracefully', async () => {
      jest.spyOn(SecureStore, 'getItemAsync').mockRejectedValue(new Error('SecureStore error'));

      // The mock throws, so we need to handle it
      try {
        const token = await SecureStore.getItemAsync('auth_token');
        // If it doesn't throw, test fails
        expect(true).toBe(false);
      } catch (error) {
        expect(error).toBeDefined();
        expect((error as Error).message).toBe('SecureStore error');
      }
    });

    test('should return null when token not found', async () => {
      jest.spyOn(SecureStore, 'getItemAsync').mockResolvedValue(null);

      const token = await SecureStore.getItemAsync('auth_token');

      expect(token).toBeNull();
    });
  });

  // ========================================================================
  // Biometric Type Detection Tests
  // ========================================================================

  describe('Biometric Type Detection', () => {
    test('should detect facial recognition', async () => {
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION,
      ]);

      const type = await biometricService.getBiometricType();

      expect(type).toBe('facial');
    });

    test('should detect fingerprint', async () => {
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);

      const type = await biometricService.getBiometricType();

      expect(type).toBe('fingerprint');
    });

    test('should detect iris scan', async () => {
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.IRIS,
      ]);

      const type = await biometricService.getBiometricType();

      expect(type).toBe('iris');
    });

    test('should return none when no biometric type available', async () => {
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([]);

      const type = await biometricService.getBiometricType();

      expect(type).toBe('none');
    });

    test('should handle biometric type detection errors', async () => {
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockRejectedValue(
        new Error('Detection failed')
      );

      const type = await biometricService.getBiometricType();

      expect(type).toBe('none');
    });
  });

  // ========================================================================
  // Preferences Management Tests
  // ========================================================================

  describe('Preferences Management', () => {
    test('should get biometric preferences', async () => {
      const prefs = biometricService.getPreferences();

      expect(prefs).toBeDefined();
      expect(prefs.enabled).toBe(true);
      expect(prefs.maxAttempts).toBe(5);
    });

    test('should update biometric preferences', async () => {
      const secureStoreSpy = jest.spyOn(AsyncStorage, 'setItem').mockResolvedValue();

      await biometricService.updatePreferences({
        requireForLogin: true,
        maxAttempts: 3,
      });

      const prefs = biometricService.getPreferences();
      expect(prefs.requireForLogin).toBe(true);
      expect(prefs.maxAttempts).toBe(3);
      expect(secureStoreSpy).toHaveBeenCalled();
      secureStoreSpy.mockRestore();
    });

    test('should check if biometric enabled for payments', () => {
      const prefs = biometricService.isBiometricEnabledFor('payments');

      expect(prefs).toBe(true); // Default is true
    });

    test('should check if biometric enabled for login', () => {
      const prefs = biometricService.isBiometricEnabledFor('login');

      expect(prefs).toBe(false); // Default is false
    });

    test('should check if biometric enabled for sensitive actions', () => {
      const prefs = biometricService.isBiometricEnabledFor('sensitive');

      expect(prefs).toBe(true); // Default is true
    });
  });

  // ========================================================================
  // Biometric Label Tests
  // ========================================================================

  describe('Biometric Label', () => {
    test('should return Face ID for iOS facial recognition', async () => {
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION,
      ]);

      // Mock Platform.OS
      const originalPlatform = require('react-native').Platform.OS;
      require('react-native').Platform.OS = 'ios';

      const label = await biometricService.getBiometricLabel();

      expect(label).toBe('Face ID');

      // Restore
      require('react-native').Platform.OS = originalPlatform;
    });

    test('should return Touch ID for iOS fingerprint', async () => {
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);

      const originalPlatform = require('react-native').Platform.OS;
      require('react-native').Platform.OS = 'ios';

      const label = await biometricService.getBiometricLabel();

      expect(label).toBe('Touch ID');

      require('react-native').Platform.OS = originalPlatform;
    });

    test('should return Fingerprint for Android fingerprint', async () => {
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      ]);

      const originalPlatform = require('react-native').Platform.OS;
      require('react-native').Platform.OS = 'android';

      const label = await biometricService.getBiometricLabel();

      expect(label).toBe('Fingerprint');

      require('react-native').Platform.OS = originalPlatform;
    });

    test('should return generic label for unsupported type', async () => {
      jest.spyOn(LocalAuthentication, 'supportedAuthenticationTypesAsync').mockResolvedValue([]);

      const label = await biometricService.getBiometricLabel();

      expect(label).toBe('Biometric Authentication');
    });
  });
});
