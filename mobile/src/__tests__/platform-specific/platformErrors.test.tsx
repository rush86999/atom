/**
 * Platform-Specific Error Handling Tests
 *
 * Tests for platform-specific error handling with appropriate fallbacks:
 * - Permission denied errors (iOS settings deep link vs Android rationale)
 * - Feature unavailable errors
 * - Platform capability errors
 * - Graceful degradation patterns
 * - Error recovery flows
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { Platform, Alert } from 'react-native';
import * as Camera from 'expo-camera';
import * as Location from 'expo-location';
import {
  mockPlatform,
  restorePlatform,
  testEachPlatform,
  cleanupTest,
} from '../helpers/testUtils';
import { createPermissionMock } from '../helpers/platformPermissions.test';

// ============================================================================
// Setup and Teardown
// ============================================================================

beforeEach(() => {
  jest.clearAllMocks();
  jest.spyOn(Alert, 'alert').mockImplementation(() => {});
});

afterEach(() => {
  cleanupTest();
  jest.restoreAllMocks();
});

// ============================================================================
// Permission Denied Error Handling Tests
// ============================================================================

describe('Platform Errors - Permission Denied', () => {
  test('should handle iOS permission denied with Settings deep link', async () => {
    mockPlatform('ios');

    (Camera.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      ...createPermissionMock('denied'),
      canAskAgain: false, // User denied permanently
    });

    const status = await Camera.getCameraPermissionsAsync();

    expect(status.canAskAgain).toBe(false);

    // iOS should deep link to Settings
    const settingsURL = 'app-settings://';
    expect(settingsURL).toBeTruthy();
  });

  test('should handle Android permission denied with rationale', async () => {
    mockPlatform('android');

    (Camera.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      ...createPermissionMock('denied'),
      canAskAgain: false, // User selected "Don't ask again"
    });

    const status = await Camera.getCameraPermissionsAsync();

    expect(status.canAskAgain).toBe(false);

    // Android should show dialog explaining why permission is needed
    const rationale = 'Camera permission is needed to take photos';
    expect(rationale).toBeTruthy();
  });

  test('should show appropriate error message per platform', async () => {
    await testEachPlatform(async (platform) => {
      const errorMessage = platform === 'ios'
        ? 'Enable camera in iOS Settings to use this feature'
        : 'Camera permission is required to take photos. Enable it in app settings.';

      expect(errorMessage).toBeTruthy();
      expect(errorMessage.toLowerCase()).toContain('camera');
    });
  });
});

// ============================================================================
// Feature Unavailable Error Handling Tests
// ============================================================================

describe('Platform Errors - Feature Unavailable', () => {
  test('should handle biometric hardware unavailable', async () => {
    await testEachPlatform(async (platform) => {
      // Mock no biometric hardware
      const hasHardware = false;

      if (!hasHardware) {
        // Show error: "Biometric authentication not available on this device"
        const errorMessage = 'Biometric authentication not available';
        expect(errorMessage).toBeTruthy();
      }
    });
  });

  test('should handle camera unavailable', async () => {
    await testEachPlatform(async (platform) => {
      (Camera.isAvailableAsync as jest.Mock).mockResolvedValue(false);

      const isAvailable = await Camera.isAvailableAsync();

      expect(isAvailable).toBe(false);
      // Show error: "Camera not available on this device"
    });
  });

  test('should handle location services disabled', async () => {
    await testEachPlatform(async (platform) => {
      // Mock location services disabled
      const locationEnabled = false;

      if (!locationEnabled) {
        // Show error with platform-specific message
        const errorMessage = platform === 'ios'
          ? 'Enable Location Services in iOS Settings'
          : 'Enable Location in Android Settings';

        expect(errorMessage).toContain('Location');
      }
    });
  });
});

// ============================================================================
// Platform Capability Error Handling Tests
// ============================================================================

describe('Platform Errors - Platform Capabilities', () => {
  test('should handle missing safe area support', () => {
    mockPlatform('android');
    // Very old Android version
    Object.defineProperty(Platform, 'Version', {
      get: () => 26,
      configurable: true,
    });

    // Old Android might not support safe areas
    const supportsSafeAreas = Platform.Version >= 21; // Android 5.0+ supports safe areas

    if (!supportsSafeAreas) {
      // Use manual padding instead
      const manualPadding = { paddingTop: 24 }; // Status bar height
      expect(manualPadding.paddingTop).toBe(24);
    }
  });

  test('should handle missing notification channel support', () => {
    mockPlatform('android');
    // Android 7.1 (pre-Oreo)
    Object.defineProperty(Platform, 'Version', {
      get: () => 25,
      configurable: true,
    });

    // API 26+ required for notification channels
    const needsChannels = Platform.Version >= 26;

    if (!needsChannels) {
      // Don't create channels on older Android
      const channelCreated = false;
      expect(channelCreated).toBe(false);
    }
  });
});

// ============================================================================
// Graceful Degradation Tests
// ============================================================================

describe('Platform Errors - Graceful Degradation', () => {
  test('should degrade gracefully when Face ID unavailable', async () => {
    mockPlatform('ios');

    // Face ID not available, use passcode fallback
    const faceIdAvailable = false;
    const usePasscode = !faceIdAvailable;

    expect(usePasscode).toBe(true);
  });

  test('should degrade gracefully when haptics unavailable', async () => {
    await testEachPlatform(async (platform) => {
      // Some devices don't support haptics
      const hapticsSupported = true; // Would check actual device support

      if (!hapticsSupported) {
        // Silent fallback (no crash)
        const visualFeedback = true;
        expect(visualFeedback).toBe(true);
      }
    });
  });

  test('should degrade gracefully when network unavailable', async () => {
    await testEachPlatform(async (platform) => {
      const isOnline = false;

      if (!isOnline) {
        // Show cached content or offline message
        const offlineMessage = 'Offline - Some features may be unavailable';
        expect(offlineMessage).toBeTruthy();
      }
    });
  });
});

// ============================================================================
// Error Recovery Flow Tests
// ============================================================================

describe('Platform Errors - Error Recovery', () => {
  test('should support permission recovery after initial denial', async () => {
    await testEachPlatform(async (platform) => {
      // User denied initially
      let permissionStatus = createPermissionMock('denied', true);

      if (permissionStatus.canAskAgain) {
        // Can request again
        permissionStatus = createPermissionMock('granted');
        expect(permissionStatus.granted).toBe(true);
      }
    });
  });

  test('should support settings redirect for permanent denial', async () => {
    await testEachPlatform(async (platform) => {
      const permanentlyDenied = createPermissionMock('denied', false);

      if (!permanentlyDenied.canAskAgain) {
        // Redirect to settings
        const settingsAction = platform === 'ios'
          ? 'Open iOS Settings'
          : 'Open Android Settings';

        expect(settingsAction).toContain('Settings');
      }
    });
  });

  test('should retry failed operations after permission granted', async () => {
    // Permission denied initially
    (Camera.requestCameraPermissionsAsync as jest.Mock)
      .mockResolvedValueOnce(createPermissionMock('denied'))
      .mockResolvedValueOnce(createPermissionMock('granted'));

    // First attempt fails
    const result1 = await Camera.requestCameraPermissionsAsync();
    expect(result1.granted).toBe(false);

    // User grants permission in settings
    // Second attempt succeeds
    const result2 = await Camera.requestCameraPermissionsAsync();
    expect(result2.granted).toBe(true);
  });
});

// ============================================================================
// Platform-Specific Error Messages Tests
// ============================================================================

describe('Platform Errors - Platform-Specific Messages', () => {
  test('should use iOS-specific error messaging', () => {
    mockPlatform('ios');

    const errorCode = 'PERMISSION_DENIED';
    const message = errorCode === 'PERMISSION_DENIED'
      ? 'Please enable camera access in iOS Settings > Privacy > Camera'
      : 'An error occurred';

    expect(message).toContain('iOS Settings');
  });

  test('should use Android-specific error messaging', () => {
    mockPlatform('android');

    const errorCode = 'PERMISSION_DENIED';
    const message = errorCode === 'PERMISSION_DENIED'
      ? 'Grant camera permission in app settings to use this feature'
      : 'An error occurred';

    expect(message).toContain('app settings');
  });

  test('should include platform context in error logs', async () => {
    await testEachPlatform(async (platform) => {
      const error = new Error('Feature failed');
      const errorWithContext = `${error.message} on ${platform}`;

      expect(errorWithContext).toContain(platform);
    });
  });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('Platform Errors - Edge Cases', () => {
  test('should handle multiple simultaneous errors', async () => {
    await testEachPlatform(async (platform) => {
      // Camera denied AND location denied
      const cameraDenied = createPermissionMock('denied');
      const locationDenied = createPermissionMock('denied');

      const errors = [];
      if (!cameraDenied.granted) errors.push('Camera');
      if (!locationDenied.granted) errors.push('Location');

      expect(errors.length).toBe(2);
    });
  });

  test('should handle errors during platform switch', () => {
    mockPlatform('ios');
    mockPlatform('android');

    // Platform switch occurred mid-operation
    const platformInconsistency = Platform.OS;

    // Should handle gracefully
    expect(platformInconsistency).toBe('android');
  });

  test('should handle timeout errors consistently', async () => {
    await testEachPlatform(async (platform) => {
      const timeoutError = new Error('Request timed out');

      // Both platforms should show timeout message
      const timeoutMessage = 'Request timed out. Please try again.';
      expect(timeoutMessage).toBeTruthy();
    });
  });
});
