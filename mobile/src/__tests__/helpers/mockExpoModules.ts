/**
 * Centralized Expo Module Mock Helpers
 *
 * This file provides configurable mock objects for Expo modules that can be
 * imported and customized in individual test files. Each mock provides helper
 * functions to control permissions, behavior, and state for testing different scenarios.
 *
 * Usage:
 * ```typescript
 * import { MockCamera, MockLocation, resetAllMocks } from './mockExpoModules';
 *
 * beforeEach(() => {
 *   resetAllMocks();
 *   MockCamera.setPermissionGranted(false); // Test denied permissions
 * });
 * ```
 */

import type { CameraType, CameraPermissionStatus, FlashMode } from 'expo-camera';
import type { LocationSubscription } from 'expo-location';

// ============================================================================
// MockCamera
// ============================================================================

interface MockCameraPermissionResponse {
  status: CameraPermissionStatus;
  canAskAgain: boolean;
  granted: boolean;
  expires: 'never' | string;
}

interface MockCameraPictureResult {
  uri: string;
  width: number;
  height: number;
}

export const MockCamera = {
  /**
   * Configure camera permission status
   * @param granted - Whether permission is granted
   * @param canAskAgain - Whether permission can be requested again
   */
  setPermissionGranted: (granted: boolean = true, canAskAgain: boolean = true) => {
    const status: CameraPermissionStatus = granted ? 'granted' : 'denied';
    // Update mock implementation
    jest.requireMock('expo-camera').requestCameraPermissionsAsync.mockResolvedValue({
      status,
      canAskAgain,
      granted,
      expires: 'never',
    });
    jest.requireMock('expo-camera').getCameraPermissionsAsync.mockResolvedValue({
      status,
      canAskAgain,
      granted,
      expires: 'never',
    });
  },

  /**
   * Configure picture capture result
   * @param uri - URI of captured photo
   * @param width - Photo width in pixels
   * @param height - Photo height in pixels
   */
  setPictureResult: (uri: string = 'file:///mock/photo.jpg', width: number = 1920, height: number = 1080) => {
    jest.requireMock('expo-camera').takePictureAsync.mockResolvedValue({
      uri,
      width,
      height,
    });
  },

  /**
   * Configure picture capture to fail
   * @param error - Error message
   */
  setPictureError: (error: string = 'Camera not available') => {
    jest.requireMock('expo-camera').takePictureAsync.mockRejectedValue(new Error(error));
  },

  /**
   * Get the number of times permission was requested
   */
  getPermissionRequestCount: () => {
    return jest.requireMock('expo-camera').requestCameraPermissionsAsync.mock.calls.length;
  },

  /**
   * Get the number of times picture was taken
   */
  getPictureCount: () => {
    return jest.requireMock('expo-camera').takePictureAsync.mock.calls.length;
  },
};

// ============================================================================
// MockLocation
// ============================================================================

interface MockLocationCoords {
  latitude: number;
  longitude: number;
  altitude?: number;
  accuracy?: number;
  altitudeAccuracy?: number;
  heading?: number;
  speed?: number;
}

interface MockLocationPermissionResponse {
  status: 'granted' | 'denied' | 'notAsked';
  canAskAgain: boolean;
  granted: boolean;
  expires: 'never' | string;
}

interface MockLocationObject {
  coords: MockLocationCoords;
  timestamp: number;
}

export const MockLocation = {
  /**
   * Configure foreground location permission status
   * @param granted - Whether permission is granted
   * @param canAskAgain - Whether permission can be requested again
   */
  setForegroundPermissionGranted: (granted: boolean = true, canAskAgain: boolean = true) => {
    const status = granted ? 'granted' : 'denied';
    jest.requireMock('expo-location').requestForegroundPermissionsAsync.mockResolvedValue({
      status,
      canAskAgain,
      granted,
      expires: 'never',
    });
  },

  /**
   * Configure background location permission status
   * @param granted - Whether permission is granted
   * @param canAskAgain - Whether permission can be requested again
   */
  setBackgroundPermissionGranted: (granted: boolean = true, canAskAgain: boolean = true) => {
    const status = granted ? 'granted' : 'denied';
    jest.requireMock('expo-location').requestBackgroundPermissionsAsync.mockResolvedValue({
      status,
      canAskAgain,
      granted,
      expires: 'never',
    });
  },

  /**
   * Configure current position result
   * @param coords - Location coordinates
   * @param timestamp - Timestamp of location reading
   */
  setCurrentPosition: (coords: MockLocationCoords = {
    latitude: 37.7749,
    longitude: -122.4194,
    altitude: 100,
    accuracy: 10,
  }, timestamp: number = Date.now()) => {
    jest.requireMock('expo-location').getCurrentPositionAsync.mockResolvedValue({
      coords,
      timestamp,
    });
  },

  /**
   * Configure location retrieval to fail
   * @param error - Error message
   */
  setPositionError: (error: string = 'Location not available') => {
    jest.requireMock('expo-location').getCurrentPositionAsync.mockRejectedValue(new Error(error));
  },

  /**
   * Configure geocoding result
   * @param addresses - Array of addresses to return
   */
  setGeocodeResult: (addresses: Array<{
    latitude: number;
    longitude: number;
    street?: string;
    city?: string;
    region?: string;
    country?: string;
    postalCode?: string;
  }> = []) => {
    jest.requireMock('expo-location').geocodeAsync.mockResolvedValue(addresses);
    jest.requireMock('expo-location').reverseGeocodeAsync.mockResolvedValue(addresses);
  },

  /**
   * Get the number of times position was requested
   */
  getPositionRequestCount: () => {
    return jest.requireMock('expo-location').getCurrentPositionAsync.mock.calls.length;
  },
};

// ============================================================================
// MockNotifications
// ============================================================================

interface MockNotificationPermissionResponse {
  status: 'granted' | 'denied' | 'notAsked';
  canAskAgain: boolean;
  granted: boolean;
  expires: 'never' | string;
  ios?: {
    allowsAlert: boolean;
    allowsBadge: boolean;
    allowsSound: boolean;
  };
  android?: Record<string, unknown>;
}

export const MockNotifications = {
  /**
   * Configure notification permission status
   * @param granted - Whether permission is granted
   * @param canAskAgain - Whether permission can be requested again
   */
  setPermissionGranted: (granted: boolean = true, canAskAgain: boolean = true) => {
    const status = granted ? 'granted' : 'denied';
    jest.requireMock('expo-notifications').requestPermissionsAsync.mockResolvedValue({
      status,
      canAskAgain,
      granted,
      expires: 'never',
      ios: {
        allowsAlert: granted,
        allowsBadge: granted,
        allowsSound: granted,
      },
      android: {},
    });
    jest.requireMock('expo-notifications').getPermissionsAsync.mockResolvedValue({
      status,
      canAskAgain,
      granted,
      expires: 'never',
    });
  },

  /**
   * Configure notification scheduling result
   * @param notificationId - ID to return when scheduling
   */
  setScheduleResult: (notificationId: string = 'notification-id-123') => {
    jest.requireMock('expo-notifications').scheduleNotificationAsync.mockResolvedValue(notificationId);
  },

  /**
   * Configure notification scheduling to fail
   * @param error - Error message
   */
  setScheduleError: (error: string = 'Failed to schedule notification') => {
    jest.requireMock('expo-notifications').scheduleNotificationAsync.mockRejectedValue(new Error(error));
  },

  /**
   * Configure push token result
   * @param token - Push token to return
   */
  setPushToken: (token: string = 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]') => {
    jest.requireMock('expo-notifications').getExpoPushTokenAsync.mockResolvedValue({
      type: 'expo',
      data: token,
    });
  },

  /**
   * Configure badge count
   * @param count - Badge count
   */
  setBadgeCount: (count: number = 0) => {
    jest.requireMock('expo-notifications').getBadgeCountAsync.mockResolvedValue(count);
  },

  /**
   * Get the number of times notification was scheduled
   */
  getScheduleCount: () => {
    return jest.requireMock('expo-notifications').scheduleNotificationAsync.mock.calls.length;
  },

  /**
   * Get the number of times push token was requested
   */
  getPushTokenRequestCount: () => {
    return jest.requireMock('expo-notifications').getExpoPushTokenAsync.mock.calls.length;
  },
};

// ============================================================================
// MockLocalAuthentication
// ============================================================================

interface MockAuthResult {
  success: boolean;
  error?: string;
  warning?: string;
}

export const MockLocalAuthentication = {
  /**
   * Configure hardware availability
   * @param hasHardware - Whether device has biometric hardware
   */
  setHasHardware: (hasHardware: boolean = true) => {
    jest.requireMock('expo-local-authentication').hasHardwareAsync.mockResolvedValue(hasHardware);
  },

  /**
   * Configure enrollment status
   * @param isEnrolled - Whether user has enrolled biometrics
   */
  setIsEnrolled: (isEnrolled: boolean = true) => {
    jest.requireMock('expo-local-authentication').isEnrolledAsync.mockResolvedValue(isEnrolled);
  },

  /**
   * Configure authentication result
   * @param success - Whether authentication succeeds
   * @param error - Error message if failed
   */
  setAuthResult: (success: boolean = true, error?: string) => {
    jest.requireMock('expo-local-authentication').authenticateAsync.mockResolvedValue({
      success,
      error,
      warning: undefined,
    });
  },

  /**
   * Get the number of times authentication was attempted
   */
  getAuthAttemptCount: () => {
    return jest.requireMock('expo-local-authentication').authenticateAsync.mock.calls.length;
  },
};

// ============================================================================
// MockSecureStore
// ============================================================================

const secureStore = new Map<string, string>();

export const MockSecureStore = {
  /**
   * Get item from secure store
   * @param key - Storage key
   */
  getItem: async (key: string): Promise<string | null> => {
    return secureStore.get(key) || null;
  },

  /**
   * Set item in secure store
   * @param key - Storage key
   * @param value - Value to store
   */
  setItem: async (key: string, value: string): Promise<void> => {
    secureStore.set(key, value);
  },

  /**
   * Delete item from secure store
   * @param key - Storage key
   */
  deleteItem: async (key: string): Promise<void> => {
    secureStore.delete(key);
  },

  /**
   * Check if secure store is available
   */
  isAvailable: async (): Promise<boolean> => {
    return true;
  },

  /**
   * Get all keys in secure store
   */
  getAllKeys: (): string[] => {
    return Array.from(secureStore.keys());
  },

  /**
   * Clear all items from secure store
   */
  clear: (): void => {
    secureStore.clear();
  },

  /**
   * Get number of items in secure store
   */
  size: (): number => {
    return secureStore.size;
  },
};

// ============================================================================
// MockAsyncStorage
// ============================================================================

const asyncStorage = new Map<string, string>();

export const MockAsyncStorage = {
  /**
   * Get item from async storage
   * @param key - Storage key
   */
  getItem: async (key: string): Promise<string | null> => {
    return asyncStorage.get(key) || null;
  },

  /**
   * Set item in async storage
   * @param key - Storage key
   * @param value - Value to store
   */
  setItem: async (key: string, value: string): Promise<void> => {
    asyncStorage.set(key, value);
  },

  /**
   * Remove item from async storage
   * @param key - Storage key
   */
  removeItem: async (key: string): Promise<void> => {
    asyncStorage.delete(key);
  },

  /**
   * Merge item in async storage
   * @param key - Storage key
   * @param value - Value to merge (JSON string)
   */
  mergeItem: async (key: string, value: string): Promise<void> => {
    const existing = JSON.parse(asyncStorage.get(key) || '{}');
    const merged = { ...existing, ...JSON.parse(value) };
    asyncStorage.set(key, JSON.stringify(merged));
  },

  /**
   * Clear all items from async storage
   */
  clear: async (): Promise<void> => {
    asyncStorage.clear();
  },

  /**
   * Get all keys in async storage
   */
  getAllKeys: async (): Promise<string[]> => {
    return Array.from(asyncStorage.keys());
  },

  /**
   * Get multiple items from async storage
   * @param keys - Array of keys
   */
  multiGet: async (keys: string[]): Promise<Array<[string, string | null]>> => {
    return keys.map((key) => [key, asyncStorage.get(key) || null]);
  },

  /**
   * Set multiple items in async storage
   * @param keyValuePairs - Array of [key, value] pairs
   */
  multiSet: async (keyValuePairs: Array<[string, string]>): Promise<void> => {
    keyValuePairs.forEach(([key, value]) => {
      asyncStorage.set(key, value);
    });
  },

  /**
   * Remove multiple items from async storage
   * @param keys - Array of keys
   */
  multiRemove: async (keys: string[]): Promise<void> => {
    keys.forEach((key) => {
      asyncStorage.delete(key);
    });
  },

  /**
   * Get all keys in async storage
   */
  getAllKeysSync: (): string[] => {
    return Array.from(asyncStorage.keys());
  },

  /**
   * Clear all items from async storage
   */
  clearSync: (): void => {
    asyncStorage.clear();
  },

  /**
   * Get number of items in async storage
   */
  size: (): number => {
    return asyncStorage.size;
  },
};

// ============================================================================
// MockDevice
// ============================================================================

interface MockDeviceInfo {
  osName: string;
  osVersion: string;
  modelName: string;
  modelId: string;
  brand: string;
  manufacturerName: string;
  platformApiLevel: number;
  deviceYearClass: number;
  totalMemory: number;
}

export const MockDevice = {
  /**
   * Configure device information
   * @param deviceInfo - Device information
   */
  setDeviceInfo: (deviceInfo: Partial<MockDeviceInfo> = {}) => {
    const defaultInfo: MockDeviceInfo = {
      osName: 'iOS',
      osVersion: '16.0',
      modelName: 'iPhone 14',
      modelId: 'iPhone14,7',
      brand: 'Apple',
      manufacturerName: 'Apple',
      platformApiLevel: 16,
      deviceYearClass: 2022,
      totalMemory: 6 * 1024 * 1024 * 1024,
    };

    const merged = { ...defaultInfo, ...deviceInfo };
    const Device = jest.requireMock('expo-device').Device;

    Object.assign(Device, merged);
  },

  /**
   * Set device to iOS
   */
  setIOS: () => {
    MockDevice.setDeviceInfo({
      osName: 'iOS',
      osVersion: '16.0',
      modelName: 'iPhone 14',
      modelId: 'iPhone14,7',
      brand: 'Apple',
      manufacturerName: 'Apple',
    });
  },

  /**
   * Set device to Android
   */
  setAndroid: () => {
    MockDevice.setDeviceInfo({
      osName: 'Android',
      osVersion: '13.0',
      modelName: 'Pixel 7',
      modelId: 'Pixel 7',
      brand: 'Google',
      manufacturerName: 'Google',
    });
  },
};

// ============================================================================
// Permission Helper
// ============================================================================

/**
 * Set permission granted status for a specific module
 * @param moduleName - Name of the module ('camera', 'location', 'notifications', 'biometric')
 * @param granted - Whether permission is granted
 */
export const setPermissionGranted = (moduleName: string, granted: boolean = true) => {
  switch (moduleName.toLowerCase()) {
    case 'camera':
      MockCamera.setPermissionGranted(granted);
      break;
    case 'location':
      MockLocation.setForegroundPermissionGranted(granted);
      break;
    case 'notifications':
      MockNotifications.setPermissionGranted(granted);
      break;
    case 'biometric':
    case 'local-authentication':
      MockLocalAuthentication.setIsEnrolled(granted);
      break;
    default:
      throw new Error(`Unknown module: ${moduleName}`);
  }
};

// ============================================================================
// Reset Helper
// ============================================================================

/**
 * Reset all mock states to default values
 * Call this in beforeEach() blocks to ensure test isolation
 */
export const resetAllMocks = () => {
  // Reset Camera
  MockCamera.setPermissionGranted(true);
  MockCamera.setPictureResult();

  // Reset Location
  MockLocation.setForegroundPermissionGranted(true);
  MockLocation.setBackgroundPermissionGranted(true);
  MockLocation.setCurrentPosition();

  // Reset Notifications
  MockNotifications.setPermissionGranted(true);
  MockNotifications.setScheduleResult();
  MockNotifications.setPushToken();
  MockNotifications.setBadgeCount(0);

  // Reset LocalAuthentication
  MockLocalAuthentication.setHasHardware(true);
  MockLocalAuthentication.setIsEnrolled(true);
  MockLocalAuthentication.setAuthResult(true);

  // Reset SecureStore
  MockSecureStore.clear();

  // Reset AsyncStorage
  MockAsyncStorage.clear();

  // Reset Device
  MockDevice.setIOS();

  // Clear all jest mocks
  jest.clearAllMocks();
};
