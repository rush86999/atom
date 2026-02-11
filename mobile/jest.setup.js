/**
 * Jest Setup File for Atom Mobile Tests
 *
 * This file configures Jest with global mocks for Expo modules and React Native components.
 * It is loaded automatically by jest-expo via setupFilesAfterEnv configuration.
 *
 * Mocks provided:
 * - expo-camera: Camera permissions and picture capture
 * - expo-location: Location permissions and position data
 * - expo-notifications: Notification permissions and scheduling
 * - expo-local-authentication: Biometric authentication
 * - expo-secure-store: Secure key-value storage
 * - @react-native-async-storage/async-storage: In-memory storage
 * - expo-device: Device information
 */

import '@testing-library/jest-native';

// ============================================================================
// Mock Expo environment variables
// ============================================================================

// Note: expo/virtual/env is not available in Jest, use process.env instead
process.env.EXPO_PUBLIC_API_URL = 'http://localhost:8000';

// Mock the expo/virtual/env module to prevent import errors
jest.mock('expo/virtual/env', () => ({
  EXPO_PUBLIC_API_URL: 'http://localhost:8000',
}), { virtual: true });

// ============================================================================
// expo-camera Mock
// ============================================================================

jest.mock('expo-camera', () => ({
  Camera: {
    Constants: {
      Type: {
        back: 'back',
        front: 'front',
      },
      FlashMode: {
        off: 'off',
        on: 'on',
        auto: 'auto',
        torch: 'torch',
      },
      CameraPermissionStatus: {
        granted: 'granted',
        denied: 'denied',
        notAsked: 'notAsked',
      },
    },
  },
  CameraView: jest.fn(),
  requestCameraPermissionsAsync: jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  }),
  getCameraPermissionsAsync: jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  }),
  takePictureAsync: jest.fn().mockResolvedValue({
    uri: 'file:///mock/photo.jpg',
    width: 1920,
    height: 1080,
  }),
}));

// ============================================================================
// expo-location Mock
// ============================================================================

jest.mock('expo-location', () => ({
  requestForegroundPermissionsAsync: jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  }),
  requestBackgroundPermissionsAsync: jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  }),
  getCurrentPositionAsync: jest.fn().mockResolvedValue({
    coords: {
      latitude: 37.7749,
      longitude: -122.4194,
      altitude: 100,
      accuracy: 10,
      altitudeAccuracy: 5,
      heading: 0,
      speed: 0,
    },
    timestamp: Date.now(),
  }),
  getLastKnownPositionAsync: jest.fn().mockResolvedValue(null),
  watchPositionAsync: jest.fn().mockReturnValue({
    remove: jest.fn(),
  }),
  geocodeAsync: jest.fn().mockResolvedValue([
    {
      latitude: 37.7749,
      longitude: -122.4194,
      street: '123 Market St',
      city: 'San Francisco',
      region: 'CA',
      country: 'USA',
      postalCode: '94103',
    },
  ]),
  reverseGeocodeAsync: jest.fn().mockResolvedValue([
    {
      latitude: 37.7749,
      longitude: -122.4194,
      street: '123 Market St',
      city: 'San Francisco',
      region: 'CA',
      country: 'USA',
      postalCode: '94103',
    },
  ]),
}));

// ============================================================================
// expo-notifications Mock
// ============================================================================

jest.mock('expo-notifications', () => ({
  requestPermissionsAsync: jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
    ios: {
      allowsAlert: true,
      allowsBadge: true,
      allowsSound: true,
    },
    android: {},
  }),
  getPermissionsAsync: jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  }),
  getBadgeCountAsync: jest.fn().mockResolvedValue(0),
  setBadgeCountAsync: jest.fn().mockResolvedValue(undefined),
  scheduleNotificationAsync: jest.fn().mockResolvedValue('notification-id-123'),
  cancelScheduledNotificationAsync: jest.fn().mockResolvedValue(undefined),
  cancelAllScheduledNotificationsAsync: jest.fn().mockResolvedValue(undefined),
  getAllScheduledNotificationsAsync: jest.fn().mockResolvedValue([]),
  getExpoPushTokenAsync: jest.fn().mockResolvedValue({
    type: 'expo',
    data: 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]',
  }),
  presentNotificationAsync: jest.fn().mockResolvedValue(undefined),
  dismissNotificationAsync: jest.fn().mockResolvedValue(undefined),
  dismissAllNotificationsAsync: jest.fn().mockResolvedValue(undefined),
  getAllNotificationsAsync: jest.fn().mockResolvedValue([]),
  setNotificationHandler: jest.fn(),
  addNotificationReceivedListener: jest.fn().mockReturnValue({
    remove: jest.fn(),
  }),
  addNotificationResponseReceivedListener: jest.fn().mockReturnValue({
    remove: jest.fn(),
  }),
  removeNotificationSubscription: jest.fn(),
  NotificationContentInput: jest.fn(),
  NotificationRequestInput: jest.fn(),
}));

// ============================================================================
// expo-local-authentication Mock
// ============================================================================

jest.mock('expo-local-authentication', () => ({
  hasHardwareAsync: jest.fn().mockResolvedValue(true),
  isEnrolledAsync: jest.fn().mockResolvedValue(true),
  authenticateAsync: jest.fn().mockResolvedValue({
    success: true,
    error: undefined,
    warning: undefined,
  }),
  supportedAuthenticationTypesAsync: jest.fn().mockResolvedValue([1, 2]),
  getEnrolledLevelAsync: jest.fn().mockResolvedValue(2),
}));

// ============================================================================
// expo-secure-store Mock
// ============================================================================

const mockSecureStore = new Map();

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn().mockImplementation(async (key) => {
    return mockSecureStore.get(key) || null;
  }),
  setItemAsync: jest.fn().mockImplementation(async (key, value) => {
    mockSecureStore.set(key, value);
  }),
  deleteItemAsync: jest.fn().mockImplementation(async (key) => {
    mockSecureStore.delete(key);
  }),
  isAvailableAsync: jest.fn().mockResolvedValue(true),
}));

// Export helper to reset mock store for tests
global.__resetSecureStoreMock = () => {
  mockSecureStore.clear();
};

// ============================================================================
// @react-native-async-storage/async-storage Mock
// ============================================================================

const mockAsyncStorage = new Map();

jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn().mockImplementation((key) => {
    return Promise.resolve(mockAsyncStorage.get(key) || null);
  }),
  setItem: jest.fn().mockImplementation((key, value) => {
    mockAsyncStorage.set(key, value);
    return Promise.resolve(undefined);
  }),
  removeItem: jest.fn().mockImplementation((key) => {
    mockAsyncStorage.delete(key);
    return Promise.resolve(undefined);
  }),
  mergeItem: jest.fn().mockImplementation((key, value) => {
    const existing = JSON.parse(mockAsyncStorage.get(key) || '{}');
    const merged = { ...existing, ...JSON.parse(value) };
    mockAsyncStorage.set(key, JSON.stringify(merged));
    return Promise.resolve(undefined);
  }),
  clear: jest.fn().mockImplementation(() => {
    mockAsyncStorage.clear();
    return Promise.resolve(undefined);
  }),
  getAllKeys: jest.fn().mockImplementation(() => {
    return Promise.resolve(Array.from(mockAsyncStorage.keys()));
  }),
  multiGet: jest.fn().mockImplementation((keys) => {
    const pairs = keys.map((key) => [key, mockAsyncStorage.get(key) || null]);
    return Promise.resolve(pairs);
  }),
  multiSet: jest.fn().mockImplementation((keyValuePairs) => {
    keyValuePairs.forEach(([key, value]) => {
      mockAsyncStorage.set(key, value);
    });
    return Promise.resolve(undefined);
  }),
  multiRemove: jest.fn().mockImplementation((keys) => {
    keys.forEach((key) => {
      mockAsyncStorage.delete(key);
    });
    return Promise.resolve(undefined);
  }),
  multiMerge: jest.fn().mockImplementation((keyValuePairs) => {
    keyValuePairs.forEach(([key, value]) => {
      const existing = JSON.parse(mockAsyncStorage.get(key) || '{}');
      const merged = { ...existing, ...JSON.parse(value) };
      mockAsyncStorage.set(key, JSON.stringify(merged));
    });
    return Promise.resolve(undefined);
  }),
}));

// Export helper to reset mock storage for tests
global.__resetAsyncStorageMock = () => {
  mockAsyncStorage.clear();
};

// ============================================================================
// expo-constants Mock
// ============================================================================

jest.mock('expo-constants', () => ({
  expoConfig: {
    name: 'Atom',
    slug: 'atom',
    version: '1.0.0',
    orientation: 'portrait',
    icon: './assets/icon.png',
    splash: {
      image: './assets/splash.png',
      resizeMode: 'contain',
      backgroundColor: '#ffffff',
    },
    extra: {
      eas: {
        projectId: 'test-project-id',
      },
    },
  },
  default: {
    expoConfig: {
      name: 'Atom',
      slug: 'atom',
      version: '1.0.0',
    },
  },
}));

// ============================================================================
// expo-device Mock
// ============================================================================

jest.mock('expo-device', () => ({
  Device: {
    osName: 'iOS',
    osVersion: '16.0',
    modelName: 'iPhone 14',
    modelId: 'iPhone14,7',
    brand: 'Apple',
    manufacturerName: 'Apple',
    platformApiLevel: 16,
    deviceYearClass: 2022,
    totalMemory: 6 * 1024 * 1024 * 1024, // 6GB
    supportedCpuArchitectures: ['arm64'],
    isDevice: true, // Add isDevice property to Device object
  },
}));

// ============================================================================
// react-native-mmkv Mock (for existing tests)
// ============================================================================

const mockMmkvStorage = new Map();

const createMMKVMock = () => ({
  set: jest.fn((key, value) => {
    mockMmkvStorage.set(key, value);
  }),
  get: jest.fn((key) => {
    return mockMmkvStorage.has(key) ? mockMmkvStorage.get(key) : undefined;
  }),
  getString: jest.fn((key) => {
    return mockMmkvStorage.has(key) ? mockMmkvStorage.get(key) : null;
  }),
  getNumber: jest.fn((key) => {
    return mockMmkvStorage.has(key) ? mockMmkvStorage.get(key) : null;
  }),
  getBoolean: jest.fn((key) => {
    return mockMmkvStorage.has(key) ? mockMmkvStorage.get(key) : null;
  }),
  delete: jest.fn((key) => {
    mockMmkvStorage.delete(key);
  }),
  contains: jest.fn((key) => {
    return mockMmkvStorage.has(key);
  }),
  getAllKeys: jest.fn(() => {
    return Array.from(mockMmkvStorage.keys());
  }),
  removeAll: jest.fn(() => {
    mockMmkvStorage.clear();
  }),
  getSizeInBytes: jest.fn(() => {
    return Array.from(mockMmkvStorage.entries()).reduce((acc, [key, value]) => {
      return acc + key.length + String(value).length;
    }, 0);
  }),
});

jest.mock('react-native-mmkv', () => ({
  MMKV: jest.fn().mockImplementation(() => createMMKVMock()),
}));

// Export helper to reset mock MMKV storage for tests
global.__resetMmkvMock = () => {
  mockMmkvStorage.clear();
};

// ============================================================================
// @react-native-community/netinfo Mock
// ============================================================================

jest.mock('@react-native-community/netinfo', () => ({
  default: {
    fetch: jest.fn().mockResolvedValue({
      isConnected: true,
      isInternetReachable: true,
      type: 'wifi',
      details: {
        isConnectionExpensive: false,
        ssid: 'TestNetwork',
      },
    }),
    addEventListener: jest.fn().mockReturnValue({
      remove: jest.fn(),
    }),
    useNetInfo: jest.fn().mockReturnValue({
      isConnected: true,
      isInternetReachable: true,
      type: 'wifi',
    }),
  },
}));

// ============================================================================
// Global cleanup
// ============================================================================

afterEach(() => {
  jest.clearAllMocks();
});
