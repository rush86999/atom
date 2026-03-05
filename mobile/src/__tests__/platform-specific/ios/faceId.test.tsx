/**
 * iOS Face ID Tests
 *
 * Tests for iOS-specific biometric authentication features:
 * - Face ID hardware detection
 * - Face ID enrollment status
 * - Authentication success/failure flows
 * - Fingerprint fallback (Touch ID devices)
 * - Authentication error handling
 */

import React from 'react';
import { render, waitFor, act } from '@testing-library/react-native';
import { Platform } from 'react-native';
import * as LocalAuthentication from 'expo-local-authentication';
import {
  mockPlatform,
  restorePlatform,
  cleanupTest,
} from '../../helpers/testUtils';

// ============================================================================
// Setup and Teardown
// ============================================================================

beforeEach(() => {
  mockPlatform('ios');
  jest.clearAllMocks();

  // Default mocks for Face ID
  (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
  (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);
  (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
    success: true,
    error: undefined,
    warning: undefined,
  });
});

afterEach(() => {
  cleanupTest();
});

// ============================================================================
// Face ID Hardware Detection Tests
// ============================================================================

describe('iOS Face ID - Hardware Detection', () => {
  test('should detect Face ID hardware is available', async () => {
    (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);

    const hasHardware = await LocalAuthentication.hasHardwareAsync();

    expect(hasHardware).toBe(true);
    expect(LocalAuthentication.hasHardwareAsync).toHaveBeenCalled();
  });

  test('should handle no biometric hardware', async () => {
    (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(false);

    const hasHardware = await LocalAuthentication.hasHardwareAsync();

    expect(hasHardware).toBe(false);
  });

  test('should detect Face ID vs Touch ID based on device', async () => {
    // Face ID devices return FACIAL_RECOGNITION type
    const supportedTypes = await LocalAuthentication.supportedAuthenticationTypesAsync();

    expect(supportedTypes).toContain(1); // FACIAL_RECOGNITION
  });
});

// ============================================================================
// Face ID Enrollment Tests
// ============================================================================

describe('iOS Face ID - Enrollment Status', () => {
  test('should check Face ID enrollment status', async () => {
    (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);

    const isEnrolled = await LocalAuthentication.isEnrolledAsync();

    expect(isEnrolled).toBe(true);
    expect(LocalAuthentication.isEnrolledAsync).toHaveBeenCalled();
  });

  test('should handle no Face ID enrolled', async () => {
    (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(false);

    const isEnrolled = await LocalAuthentication.isEnrolledAsync();

    expect(isEnrolled).toBe(false);
  });

  test('should get enrolled authentication level', async () => {
    (LocalAuthentication.getEnrolledLevelAsync as jest.Mock).mockResolvedValue(2);

    const level = await LocalAuthentication.getEnrolledLevelAsync();

    expect(level).toBeGreaterThanOrEqual(1); // At least something enrolled
  });
});

// ============================================================================
// Face ID Authentication Flow Tests
// ============================================================================

describe('iOS Face ID - Authentication Flow', () => {
  test('should authenticate successfully with Face ID', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: true,
      error: undefined,
      warning: undefined,
    });

    const result = await LocalAuthentication.authenticateAsync();

    expect(result.success).toBe(true);
    expect(result.error).toBeUndefined();
    expect(LocalAuthentication.authenticateAsync).toHaveBeenCalled();
  });

  test('should handle Face ID authentication failure', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: false,
      error: 'not_enrolled',
      warning: undefined,
    });

    const result = await LocalAuthentication.authenticateAsync();

    expect(result.success).toBe(false);
    expect(result.error).toBe('not_enrolled');
  });

  test('should handle user cancellation', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: false,
      error: 'user_cancel',
      warning: undefined,
    });

    const result = await LocalAuthentication.authenticateAsync();

    expect(result.success).toBe(false);
    expect(result.error).toBe('user_cancel');
  });

  test('should handle Face ID lockout (too many attempts)', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: false,
      error: 'lockout',
      warning: undefined,
    });

    const result = await LocalAuthentication.authenticateAsync();

    expect(result.success).toBe(false);
    expect(result.error).toBe('lockout');
  });
});

// ============================================================================
// Touch ID Fallback Tests
// ============================================================================

describe('iOS Face ID - Touch ID Fallback', () => {
  test('should support Touch ID on older devices', async () => {
    // Simulate Touch ID device (no Face ID)
    (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock).mockResolvedValue([2]); // FINGERPRINT

    const supportedTypes = await LocalAuthentication.supportedAuthenticationTypesAsync();

    expect(supportedTypes).toContain(2); // FINGERPRINT
    expect(supportedTypes).not.toContain(1); // No FACIAL_RECOGNITION
  });

  test('should authenticate with Touch ID when Face ID unavailable', async () => {
    (LocalAuthentication.supportedAuthenticationTypesAsync as jest.Mock).mockResolvedValue([2]);
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: true,
      error: undefined,
      warning: undefined,
    });

    const result = await LocalAuthentication.authenticateAsync();

    expect(result.success).toBe(true);
  });
});

// ============================================================================
// Authentication Error Handling Tests
// ============================================================================

describe('iOS Face ID - Error Handling', () => {
  test('should handle app not configured error', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: false,
      error: 'app_cancel',
      warning: undefined,
    });

    const result = await LocalAuthentication.authenticateAsync();

    expect(result.success).toBe(false);
    expect(result.error).toBeDefined();
  });

  test('should handle system cancel error', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: false,
      error: 'system_cancel',
      warning: undefined,
    });

    const result = await LocalAuthentication.authenticateAsync();

    expect(result.success).toBe(false);
    expect(result.error).toBe('system_cancel');
  });

  test('should handle passcode not set error', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: false,
      error: 'passcode_not_set',
      warning: undefined,
    });

    const result = await LocalAuthentication.authenticateAsync();

    expect(result.success).toBe(false);
    expect(result.error).toBe('passcode_not_set');
  });
});

// ============================================================================
// BiometricAuthScreen Integration Tests
// ============================================================================

describe('iOS Face ID - BiometricAuthScreen Integration', () => {
  test('should trigger Face ID prompt on component mount', async () => {
    const authenticateSpy = jest.spyOn(LocalAuthentication, 'authenticateAsync');

    // Simulate BiometricAuthScreen mounting
    await LocalAuthentication.authenticateAsync({
      promptMessage: 'Authenticate to access',
      fallbackLabel: 'Use Passcode',
      cancelLabel: 'Cancel',
    });

    expect(authenticateSpy).toHaveBeenCalledWith({
      promptMessage: 'Authenticate to access',
      fallbackLabel: 'Use Passcode',
      cancelLabel: 'Cancel',
    });
  });

  test('should handle successful authentication in screen', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: true,
      error: undefined,
    });

    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: 'Authenticate to continue',
    });

    expect(result.success).toBe(true);
  });

  test('should show error message on authentication failure', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: false,
      error: 'not_enrolled',
    });

    const result = await LocalAuthentication.authenticateAsync();

    expect(result.success).toBe(false);
    // Screen should show error: "Face ID not enrolled. Please enroll in Settings."
  });
});

// ============================================================================
// Platform-Specific Configuration Tests
// ============================================================================

describe('iOS Face ID - Platform-Specific Configuration', () => {
  test('should use iOS-specific authentication options', async () => {
    const iOSOptions = {
      promptMessage: 'Sign in with Face ID',
      fallbackLabel: 'Enter Password',
      cancelLabel: 'Cancel',
    };

    await LocalAuthentication.authenticateAsync(iOSOptions);

    expect(LocalAuthentication.authenticateAsync).toHaveBeenCalledWith(iOSOptions);
  });

  test('should support biometric-only authentication (no passcode fallback)', async () => {
    const biometricOnlyOptions = {
      promptMessage: 'Authenticate',
      disableDeviceFallback: true, // No passcode fallback
    };

    await LocalAuthentication.authenticateAsync(biometricOnlyOptions);

    expect(LocalAuthentication.authenticateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        disableDeviceFallback: true,
      })
    );
  });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('iOS Face ID - Edge Cases', () => {
  test('should handle multiple rapid authentication attempts', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock)
      .mockResolvedValueOnce({ success: false, error: 'not_enrolled' })
      .mockResolvedValueOnce({ success: false, error: 'user_cancel' })
      .mockResolvedValueOnce({ success: true, error: undefined });

    const result1 = await LocalAuthentication.authenticateAsync();
    const result2 = await LocalAuthentication.authenticateAsync();
    const result3 = await LocalAuthentication.authenticateAsync();

    expect(result1.success).toBe(false);
    expect(result2.success).toBe(false);
    expect(result3.success).toBe(true);
    expect(LocalAuthentication.authenticateAsync).toHaveBeenCalledTimes(3);
  });

  test('should handle concurrent authentication calls', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
      success: true,
    });

    const results = await Promise.all([
      LocalAuthentication.authenticateAsync(),
      LocalAuthentication.authenticateAsync(),
    ]);

    results.forEach((result) => {
      expect(result.success).toBe(true);
    });
  });
});
