/**
 * React Native Module Mocks
 *
 * Comprehensive mocks for React Native and Expo modules used in testing.
 * These mocks provide controllable behavior via jest.fn() for testing.
 *
 * Usage:
 * - Import specific mocks: import { Animated } from '../__mocks__/react-native.mock';
 * - Mock entire module: jest.mock('react-native', () => require('../__mocks__/react-native.mock'));
 */

import { jest } from '@jest/globals';

// ============================================================================
// Animated Mocks
// ============================================================================

export const Animated = {
  Value: jest.fn((initialValue: number = 0) => ({
    value: initialValue,
    setValue: jest.fn(),
    interpolate: jest.fn(() => ({
      __getValue: jest.fn(() => initialValue),
    })),
    addListener: jest.fn(),
    removeListener: jest.fn(),
  })),
  timing: jest.fn((value: any, config: any) => ({
    start: jest.fn((callback?: () => void) => callback?.()),
    stop: jest.fn(),
    reset: jest.fn(),
  })),
  spring: jest.fn((value: any, config: any) => ({
    start: jest.fn((callback?: () => void) => callback?.()),
    stop: jest.fn(),
    reset: jest.fn(),
  })),
  decay: jest.fn((value: any, config: any) => ({
    start: jest.fn((callback?: () => void) => callback?.()),
    stop: jest.fn(),
  })),
  View: 'View',
  Text: 'Text',
  Image: 'Image',
  ScrollView: 'ScrollView',
};

// ============================================================================
// Platform Mocks
// ============================================================================

export const Platform = {
  OS: 'ios',
  Version: '16.0',
  select: jest.fn((obj: any) => {
    const os = Platform.OS as string;
    if (obj[os]) return obj[os];
    if (obj.android && os === 'android') return obj.android;
    if (obj.ios && os === 'ios') return obj.ios;
    if (obj.web && os === 'web') return obj.web;
    if (obj.native) return obj.native;
    if (obj.default) return obj.default;
    return obj.ios || obj.android || obj.default;
  }),
  isTesting: true,
  isTV: false,
  isTVOS: false,
  isOSX: false,
  isWindows: false,
  isPad: false,
  isPhone: true,
  isTouch: true,
  constants: {
    /* @react-native/compat: deprecated */
    get: jest.fn(() => ({
      forceTouchAvailable: false,
      interfaceIdiom: 'handheld',
      osVersion: '16.0',
      systemName: 'iOS',
      model: 'iPhone',
    })),
  },
};

// ============================================================================
// Dimensions Mocks
// ============================================================================

export const Dimensions = {
  get: jest.fn((dim: 'window' | 'screen') => {
    if (dim === 'window') {
      return {
        width: 375,
        height: 812,
        scale: 3,
        fontScale: 1,
      };
    }
    return {
      width: 375,
      height: 812,
      scale: 3,
      fontScale: 1,
    };
  }),
  set: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
};

// ============================================================================
// StyleSheet Mocks
// ============================================================================

export const StyleSheet = {
  create: jest.fn((styles: any) => styles),
  flatten: jest.fn((style: any) => {
    if (Array.isArray(style)) {
      return Object.assign({}, ...style);
    }
    return style;
  }),
  compose: jest.fn((style1: any, style2: any) => {
    if (Array.isArray(style1)) {
      return [...style1, style2];
    }
    return [style1, style2];
  }),
  hairlineWidth: 1,
};

// ============================================================================
// AsyncStorage Mocks
// ============================================================================

const mockStorage: Record<string, string> = {};

export const AsyncStorage = {
  getItem: jest.fn(async (key: string) => mockStorage[key] || null),
  setItem: jest.fn(async (key: string, value: string) => {
    mockStorage[key] = value;
    return null;
  }),
  removeItem: jest.fn(async (key: string) => {
    delete mockStorage[key];
    return null;
  }),
  clear: jest.fn(async () => {
    Object.keys(mockStorage).forEach(key => delete mockStorage[key]);
    return null;
  }),
  getAllKeys: jest.fn(async () => Object.keys(mockStorage)),
  multiGet: jest.fn(async (keys: string[]) =>
    keys.map(key => [key, mockStorage[key] || null])
  ),
  multiSet: jest.fn(async (keyValuePairs: Array<[string, string]>) => {
    keyValuePairs.forEach(([key, value]) => {
      mockStorage[key] = value;
    });
    return null;
  }),
  multiRemove: jest.fn(async (keys: string[]) => {
    keys.forEach(key => delete mockStorage[key]);
    return null;
  }),
  mergeItem: jest.fn(async (key: string, value: string) => {
    const existing = mockStorage[key] || '{}';
    const merged = JSON.stringify({ ...JSON.parse(existing), ...JSON.parse(value) });
    mockStorage[key] = merged;
    return null;
  }),
};

// Clear mock storage between tests
export function clearMockStorage() {
  Object.keys(mockStorage).forEach(key => delete mockStorage[key]);
}

// ============================================================================
// Alert Mocks
// ============================================================================

export const Alert = {
  alert: jest.fn(),
  alertWithButtons: jest.fn(),
  prompt: jest.fn(),
};

// ============================================================================
// Linking Mocks
// ============================================================================

export const Linking = {
  openURL: jest.fn(async (url: string) => true),
  canOpenURL: jest.fn(async (url: string) => true),
  openSettings: jest.fn(async () => true),
  getInitialURL: jest.fn(async () => null),
  addEventListener: jest.fn(() => ({ remove: jest.fn() })),
  removeEventListener: jest.fn(),
  sendIntent: jest.fn(async () => true),
  openAuthSessionAsync: jest.fn(async (url: string) => ({ type: 'success', url })),
  dismissAuthSessionAsync: jest.fn(async () => true),
};

// ============================================================================
// Keyboard Mocks
// ============================================================================

export const Keyboard = {
  dismiss: jest.fn(),
  scheduleLayoutAnimation: jest.fn((event: any) => {}),
  addListener: jest.fn((eventName: string, callback: any) => ({
    remove: jest.fn(),
  })),
  removeListener: jest.fn(),
  removeAllListeners: jest.fn(),
  isVisible: false,
  metrics: jest.fn(async () => ({
    endCoordinates: { screenX: 0, screenY: 0, width: 375, height: 0 },
  })),
};

// ============================================================================
// AccessibilityInfo Mocks
// ============================================================================

export const AccessibilityInfo = {
  isScreenReaderEnabled: jest.fn(async () => false),
  announceForAccessibility: jest.fn((announcement: string) => {}),
  addAccessibilityServiceChangeListener: jest.fn((handler: any) => ({
    remove: jest.fn(),
  })),
  removeAccessibilityServiceChangeListener: jest.fn(),
  isBoldTextEnabled: jest.fn(async () => false),
  isGrayscaleEnabled: jest.fn(async () => false),
  isInvertColorsEnabled: jest.fn(async () => false),
  isReduceMotionEnabled: jest.fn(async () => false),
  isReduceTransparencyEnabled: jest.fn(async () => false),
  preferredFontScale: jest.fn(async () => 1.0),
};

// ============================================================================
// AppState Mocks
// ============================================================================

let mockAppState = 'active';

export const AppState = {
  currentState: mockAppState,
  addEventListener: jest.fn((type: string, handler: any) => {
    if (type === 'change') {
      // Simulate app state change
      setTimeout(() => handler('background'), 100);
      setTimeout(() => handler('active'), 200);
    }
    return {
      remove: jest.fn(),
    };
  }),
  removeEventListener: jest.fn(),
};

export function setMockAppState(state: string) {
  mockAppState = state;
  (AppState as any).currentState = state;
}

// ============================================================================
// Appearance Mocks
// ============================================================================

let mockColorScheme = 'light';

export const Appearance = {
  getColorScheme: jest.fn(() => mockColorScheme),
  addChangeListener: jest.fn((callback: any) => ({
    remove: jest.fn(),
  })),
  removeChangeListener: jest.fn(),
};

export function setMockColorScheme(scheme: 'light' | 'dark' | null) {
  mockColorScheme = scheme;
}

// ============================================================================
// NetInfo Mocks (Network Status)
// ============================================================================

let mockNetInfoState = {
  isConnected: true,
  isInternetReachable: true,
  type: 'wifi' as const,
  details: {
    isConnectionExpensive: false,
    ssid: 'TestWiFi',
  },
};

export const NetInfo = {
  fetch: jest.fn(async () => mockNetInfoState),
  addEventListener: jest.fn((handler: any) => {
    handler(mockNetInfoState);
    return {
      remove: jest.fn(),
    };
  }),
  removeEventListener: jest.fn(),
};

export function setMockNetInfoState(state: Partial<typeof mockNetInfoState>) {
  mockNetInfoState = { ...mockNetInfoState, ...state };
}

// ============================================================================
// PixelRatio Mocks
// ============================================================================

export const PixelRatio = {
  get: jest.fn(() => 3),
  getFontScale: jest.fn(() => 1),
  getPixelSizeForLayoutSize: jest.fn((layoutSize: number) => layoutSize * 3),
  roundToNearestPixel: jest.fn((pixelSize: number) => Math.round(pixelSize)),
};

// ============================================================================
// InteractionManager Mocks
// ============================================================================

export const InteractionManager = {
  runAfterInteractions: jest.fn((callback: any) => {
    setTimeout(() => callback(), 0);
  }),
  createInteractionHandle: jest.fn(() => ({})),
  clearInteractionHandle: jest.fn(),
  setDeadline: jest.fn(),
};

// ============================================================================
// NativeModules Mocks
// ============================================================================

export const NativeModules = {
  // Add platform-specific native modules here
  SettingsManager: {
    settings: {},
    getSettings: jest.fn(() => ({})),
    setSettings: jest.fn(() => {}),
    watchSettings: jest.fn(() => ({ remove: jest.fn() })),
  },
};

// ============================================================================
// PanResponder Mocks
// ============================================================================

export const PanResponder = {
  create: jest.fn((config: any) => ({
    panHandlers: {
      onStartShouldSetResponder: config.onStartShouldSetResponder,
      onMoveShouldSetResponder: config.onMoveShouldSetResponder,
      onResponderGrant: config.onResponderGrant,
      onResponderMove: config.onResponderMove,
      onResponderRelease: config.onResponderRelease,
      onResponderTerminate: config.onResponderTerminate,
      onResponderTerminationRequest: config.onResponderTerminationRequest,
    },
  })),
};

// ============================================================================
// Permissions Mocks (expo-permissions)
// ============================================================================

export const Permissions = {
  askAsync: jest.fn(async (permission: string) => ({
    status: 'granted',
    expires: 'never',
    canAskAgain: true,
  })),
  getAsync: jest.fn(async (permission: string) => ({
    status: 'undetermined',
    expires: 'never',
    canAskAgain: true,
  })),
};

// ============================================================================
// Haptics Mocks (expo-haptics)
// ============================================================================

export const Haptics = {
  impactAsync: jest.fn(async (style?: any) => {}),
  notificationAsync: jest.fn(async (type: any) => {}),
  selectionAsync: jest.fn(async () => {}),
};

// ============================================================================
// Default Export
// ============================================================================

export default {
  Animated,
  Platform,
  Dimensions,
  StyleSheet,
  AsyncStorage,
  Alert,
  Linking,
  Keyboard,
  AccessibilityInfo,
  AppState,
  Appearance,
  NetInfo,
  PixelRatio,
  InteractionManager,
  NativeModules,
  PanResponder,
  Permissions,
  Haptics,
};

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Reset all mocks to their initial state
 */
export function resetAllMocks() {
  AsyncStorage.getItem.mockClear();
  AsyncStorage.setItem.mockClear();
  AsyncStorage.removeItem.mockClear();
  AsyncStorage.clear.mockClear();
  Alert.alert.mockClear();
  Alert.prompt.mockClear();
  Linking.openURL.mockClear();
  Keyboard.dismiss.mockClear();
  clearMockStorage();
}

/**
 * Set mock platform (for testing platform-specific code)
 */
export function setMockPlatform(platform: 'ios' | 'android' | 'windows' | 'macos' | 'web') {
  (Platform as any).OS = platform;
}

/**
 * Set mock dimensions (for testing responsive layouts)
 */
export function setMockDimensions(width: number, height: number, scale: number = 1) {
  const mockWindow = { width, height, scale, fontScale: 1 };
  Dimensions.get.mockImplementation((dim: string) => {
    if (dim === 'window') return mockWindow;
    return mockWindow;
  });
}
