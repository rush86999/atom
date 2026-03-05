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

jest.mock('expo-camera', () => {
  const CameraType = {
    Front: 'front',
    Back: 'back',
  };

  const requestCameraPermissionsAsync = jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  });

  const getCameraPermissionsAsync = jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  });

  const isAvailableAsync = jest.fn().mockResolvedValue(true);

  return {
    requestCameraPermissionsAsync,
    getCameraPermissionsAsync,
    isAvailableAsync,
    Camera: {
      Constants: {
        Type: CameraType,
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
      Type: CameraType,
      requestCameraPermissionsAsync,
      getCameraPermissionsAsync,
      isAvailableAsync,
    },
    CameraView: {
      requestCameraPermissionsAsync,
      getCameraPermissionsAsync,
      isAvailableAsync,
      takePictureAsync: jest.fn().mockResolvedValue({
        uri: 'file:///mock/photo.jpg',
        width: 1920,
        height: 1080,
      }),
      recordAsync: jest.fn().mockResolvedValue({
        uri: 'file:///mock/video.mp4',
      }),
      savePhotoToLibraryAsync: jest.fn().mockResolvedValue(undefined),
    },
    CameraType,
  };
});

// ============================================================================
// expo-location Mock
// ============================================================================

jest.mock('expo-location', () => {
  const requestForegroundPermissionsAsync = jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  });

  const getForegroundPermissionsAsync = jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  });

  const requestBackgroundPermissionsAsync = jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  });

  const getCurrentPositionAsync = jest.fn().mockResolvedValue({
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
  });

  const mockGeocodeResult = [
    {
      latitude: 37.7749,
      longitude: -122.4194,
      street: '123 Market St',
      city: 'San Francisco',
      region: 'CA',
      country: 'USA',
      postalCode: '94103',
    },
  ];

  return {
    requestForegroundPermissionsAsync,
    getForegroundPermissionsAsync,
    requestBackgroundPermissionsAsync,
    getCurrentPositionAsync,
    getLastKnownPositionAsync: jest.fn().mockResolvedValue(null),
    watchPositionAsync: jest.fn().mockReturnValue({
      remove: jest.fn(),
    }),
    geocodeAsync: jest.fn().mockResolvedValue(mockGeocodeResult),
    reverseGeocodeAsync: jest.fn().mockResolvedValue(mockGeocodeResult),
    Accuracy: {
      Low: 1,
      Balanced: 2,
      High: 3,
      Highest: 4,
    },
    PermissionStatus: {
      GRANTED: 'granted',
      DENIED: 'denied',
      UNDETERMINED: 'undetermined',
    },
  };
});

// ============================================================================
// expo-notifications Mock
// ============================================================================

jest.mock('expo-notifications', () => {
  const requestPermissionsAsync = jest.fn().mockResolvedValue({
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
  });

  const getPermissionsAsync = jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  });

  const getBadgeCountAsync = jest.fn().mockResolvedValue(0);
  const setBadgeCountAsync = jest.fn().mockResolvedValue(undefined);
  const scheduleNotificationAsync = jest.fn().mockResolvedValue('notification-id-123');
  const cancelScheduledNotificationAsync = jest.fn().mockResolvedValue(undefined);
  const cancelAllScheduledNotificationsAsync = jest.fn().mockResolvedValue(undefined);
  const getAllScheduledNotificationsAsync = jest.fn().mockResolvedValue([]);
  const getExpoPushTokenAsync = jest.fn().mockResolvedValue({
    type: 'expo',
    data: 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]',
  });
  const presentNotificationAsync = jest.fn().mockResolvedValue(undefined);
  const dismissNotificationAsync = jest.fn().mockResolvedValue(undefined);
  const dismissAllNotificationsAsync = jest.fn().mockResolvedValue(undefined);
  const getAllNotificationsAsync = jest.fn().mockResolvedValue([]);
  const setNotificationHandler = jest.fn();
  const setNotificationChannelAsync = jest.fn().mockResolvedValue(undefined);
  const addNotificationReceivedListener = jest.fn().mockReturnValue({
    remove: jest.fn(),
  });
  const addNotificationResponseReceivedListener = jest.fn().mockReturnValue({
    remove: jest.fn(),
  });
  const removeNotificationSubscription = jest.fn();

  const mockNotifications = {
    requestPermissionsAsync,
    getPermissionsAsync,
    getBadgeCountAsync,
    setBadgeCountAsync,
    scheduleNotificationAsync,
    cancelScheduledNotificationAsync,
    cancelAllScheduledNotificationsAsync,
    getAllScheduledNotificationsAsync,
    getExpoPushTokenAsync,
    presentNotificationAsync,
    dismissNotificationAsync,
    dismissAllNotificationsAsync,
    getAllNotificationsAsync,
    setNotificationHandler,
    setNotificationChannelAsync,
    addNotificationReceivedListener,
    addNotificationResponseReceivedListener,
    removeNotificationSubscription,
    NotificationContentInput: jest.fn(),
    NotificationRequestInput: jest.fn(),
    AndroidImportance: {
      HIGH: 'high',
      DEFAULT: 'default',
      LOW: 'low',
      MIN: 'min',
    },
  };

  return {
    ...mockNotifications,
    Notifications: mockNotifications,
    Notification: class MockNotification {},
    default: mockNotifications,
  };
});

// ============================================================================
// expo-local-authentication Mock
// ============================================================================

jest.mock('expo-local-authentication', () => {
  const hasHardwareAsync = jest.fn().mockResolvedValue(true);
  const isEnrolledAsync = jest.fn().mockResolvedValue(true);
  const authenticateAsync = jest.fn().mockResolvedValue({
    success: true,
    error: undefined,
    warning: undefined,
  });

  return {
    hasHardwareAsync,
    isEnrolledAsync,
    authenticateAsync,
    supportedAuthenticationTypesAsync: jest.fn().mockResolvedValue([1, 2]),
    getEnrolledLevelAsync: jest.fn().mockResolvedValue(2),
    AuthenticationType: {
      FACIAL_RECOGNITION: 1,
      FINGERPRINT: 2,
      IRIS: 3,
    },
  };
});

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
      apiUrl: 'http://localhost:8000',
      socketUrl: 'http://localhost:8000',
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
      extra: {
        apiUrl: 'http://localhost:8000',
        socketUrl: 'http://localhost:8000',
      },
    },
  },
}));

// ============================================================================
// expo-device Mock
// ============================================================================

jest.mock('expo-device', () => {
  const Device = {
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
  };

  // Support both `import * as Device` and `import { Device }` patterns
  return {
    default: Device,
    ...Device,
    Device,
  };
});

// ============================================================================
// react-native-mmkv Mock (for existing tests)
// ============================================================================

// Create storage map at module level for persistence
const mockMmkvStorage = new Map();

jest.mock('react-native-mmkv', () => {
  // Create mock instance inside the factory function
  const createMMKVMock = () => ({
    set: jest.fn((key, value) => {
      mockMmkvStorage.set(key, value);
    }),
    get: jest.fn((key) => {
      return mockMmkvStorage.has(key) ? mockMmkvStorage.get(key) : undefined;
    }),
    getString: jest.fn((key) => {
      // This is the critical fix - return string or null
      return mockMmkvStorage.has(key) ? String(mockMmkvStorage.get(key)) : null;
    }),
    getNumber: jest.fn((key) => {
      const val = mockMmkvStorage.get(key);
      return typeof val === 'number' ? val : null;
    }),
    getBoolean: jest.fn((key) => {
      const val = mockMmkvStorage.get(key);
      return typeof val === 'boolean' ? val : null;
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

  // Create a single global MMKV instance that will be used by all tests
  const globalMMKVInstance = createMMKVMock();

  // Support both MMKV() constructor and direct module usage
  const MMKVConstructor = jest.fn(() => globalMMKVInstance);

  const mockModule = {
    MMKV: MMKVConstructor,
    createMMKV: jest.fn(() => globalMMKVInstance),
  };

  // Store instance globally for reset access
  global.__mmkvGlobalInstance = globalMMKVInstance;

  // Default export
  Object.defineProperty(mockModule, 'default', {
    value: mockModule,
    enumerable: false,
  });
  return mockModule;
}, { virtual: true });

// Export helper to reset mock MMKV storage for tests
global.__resetMmkvMock = () => {
  mockMmkvStorage.clear();
  // Clear all mock call history
  if (global.__mmkvGlobalInstance) {
    global.__mmkvGlobalInstance.set.mockClear();
    global.__mmkvGlobalInstance.get.mockClear();
    global.__mmkvGlobalInstance.getString.mockClear();
    global.__mmkvGlobalInstance.getNumber.mockClear();
    global.__mmkvGlobalInstance.getBoolean.mockClear();
    global.__mmkvGlobalInstance.delete.mockClear();
    global.__mmkvGlobalInstance.contains.mockClear();
    global.__mmkvGlobalInstance.getAllKeys.mockClear();
    global.__mmkvGlobalInstance.removeAll.mockClear();
    global.__mmkvGlobalInstance.getSizeInBytes.mockClear();
  }
};

// ============================================================================
// @react-native-community/netinfo Mock
// ============================================================================

jest.mock('@react-native-community/netinfo', () => {
  const mockFetch = jest.fn().mockResolvedValue({
    isConnected: true,
    isInternetReachable: true,
    type: 'wifi',
    details: {
      isConnectionExpensive: false,
      ssid: 'TestNetwork',
    },
  });

  const mockModule = {
    fetch: mockFetch,
    addEventListener: jest.fn().mockReturnValue({
      remove: jest.fn(),
    }),
    useNetInfo: jest.fn().mockReturnValue({
      isConnected: true,
      isInternetReachable: true,
      type: 'wifi',
    }),
  };

  return {
    default: mockModule,
    ...mockModule,
  };
});

// ============================================================================
// Alert Mock (React Native)
// ============================================================================

jest.mock('react-native/Libraries/Alert/Alert', () => ({
  alert: jest.fn(),
}));

// ============================================================================
// expo-image-manipulator Mock
// ============================================================================

jest.mock('expo-image-manipulator', () => ({
  manipulateAsync: jest.fn().mockResolvedValue({
    uri: 'file:///mock/manipulated.jpg',
    width: 1920,
    height: 1080,
  }),
  ImageManipulator: {
    SaveFormat: {
      JPEG: 'jpeg',
      PNG: 'png',
    },
  },
}), { virtual: true });

// ============================================================================
// expo-file-system Mock
// ============================================================================

jest.mock('expo-file-system', () => ({
  documentDirectory: '/mock/documents/',
  cacheDirectory: '/mock/cache/',
  getInfoAsync: jest.fn().mockResolvedValue({
    exists: true,
    isDirectory: false,
    uri: 'file:///mock/file.txt',
    size: 1024,
  }),
  readAsStringAsync: jest.fn().mockResolvedValue('mock file content'),
  writeAsStringAsync: jest.fn().mockResolvedValue(undefined),
  deleteAsync: jest.fn().mockResolvedValue(undefined),
  makeDirectoryAsync: jest.fn().mockResolvedValue(undefined),
  FileSystem: {
    documentDirectory: '/mock/documents/',
    cacheDirectory: '/mock/cache/',
    getInfoAsync: jest.fn().mockResolvedValue({
      exists: true,
      isDirectory: false,
      uri: 'file:///mock/file.txt',
      size: 1024,
    }),
    readAsStringAsync: jest.fn().mockResolvedValue('mock file content'),
    writeAsStringAsync: jest.fn().mockResolvedValue(undefined),
    deleteAsync: jest.fn().mockResolvedValue(undefined),
    makeDirectoryAsync: jest.fn().mockResolvedValue(undefined),
  },
}), { virtual: true });

// ============================================================================
// expo-web-browser Mock
// ============================================================================

jest.mock('expo-web-browser', () => ({
  openBrowserAsync: jest.fn().mockResolvedValue(undefined),
  WebBrowser: {
    dismissBrowser: jest.fn().mockResolvedValue(undefined),
    openAuthSessionAsync: jest.fn().mockResolvedValue({
      type: 'success',
      url: 'http://localhost:8000/auth/callback',
    }),
  },
}), { virtual: true });

// ============================================================================
// expo-haptics Mock
// ============================================================================

jest.mock('expo-haptics', () => ({
  ImpactFeedbackStyle: {
    Light: 0,
    Medium: 1,
    Heavy: 2,
    Rigid: 3,
    Soft: 4,
  },
  NotificationFeedbackType: {
    Success: 0,
    Warning: 1,
    Error: 2,
  },
  SelectionFeedbackType: {
    Change: 0,
  },
  impactAsync: jest.fn().mockResolvedValue(undefined),
  notificationAsync: jest.fn().mockResolvedValue(undefined),
  selectionAsync: jest.fn().mockResolvedValue(undefined),
}), { virtual: true });

// ============================================================================
// expo-sharing Mock
// ============================================================================

jest.mock('expo-sharing', () => ({
  shareAsync: jest.fn().mockResolvedValue(undefined),
  isAvailableAsync: jest.fn().mockResolvedValue(true),
  Sharing: {
    shareAsync: jest.fn().mockResolvedValue(undefined),
    isAvailableAsync: jest.fn().mockResolvedValue(true),
  },
}), { virtual: true });

// ============================================================================
// Mock Timers for Async Tests
// ============================================================================

beforeEach(() => {
  // Use fake timers for all tests to prevent flaky async behavior
  jest.useFakeTimers();

  // Reset Alert mock before each test
  jest.requireMock('react-native/Libraries/Alert/Alert').alert.mockClear();
});

afterEach(() => {
  // Restore real timers after each test
  jest.useRealTimers();
  jest.clearAllMocks();

  // Reset MMKV mock storage
  if (global.__resetMmkvMock) {
    global.__resetMmkvMock();
  }
});

// ============================================================================
// Mock WebSocket (for service layer tests)
// ============================================================================

global.MockWebSocket = class MockWebSocket {
  static url: string;
  static protocols: string | string[];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  onopen: ((event: any) => void) | null = null;
  onmessage: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  onclose: ((event: any) => void) | null = null;

  readyState = MockWebSocket.OPEN;
  url: string;

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    MockWebSocket.url = url;
    MockWebSocket.protocols = protocols || [];

    // Simulate connection in next tick
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen({ type: 'open' });
      }
    }, 0);
  }

  send(data: string) {
    // Simulate message handling
    setTimeout(() => {
      if (this.onmessage) {
        this.onmessage({
          type: 'message',
          data: JSON.stringify({ type: 'pong', data: JSON.parse(data) }),
        });
      }
    }, 0);
  }

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose({
        type: 'close',
        code: code || 1000,
        reason: reason || '',
        wasClean: true,
      });
    }
  }

  addEventListener(type: string, listener: (event: any) => void) {
    if (type === 'open') this.onopen = listener;
    if (type === 'message') this.onmessage = listener;
    if (type === 'error') this.onerror = listener;
    if (type === 'close') this.onclose = listener;
  }

  removeEventListener(type: string, listener: (event: any) => void) {
    if (type === 'open' && this.onopen === listener) this.onopen = null;
    if (type === 'message' && this.onmessage === listener) this.onmessage = null;
    if (type === 'error' && this.onerror === listener) this.onerror = null;
    if (type === 'close' && this.onclose === listener) this.onclose = null;
  }
};
