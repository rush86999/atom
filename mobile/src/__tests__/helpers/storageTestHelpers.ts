/**
 * Storage Test Helper Utilities
 *
 * Provides helper functions for mocking storage state in tests:
 * - SecureStore (tokens, sensitive data)
 * - AsyncStorage (user data, device state, preferences)
 * - MMKV (app state, cache)
 *
 * Usage:
 *   import { mockSecureStoreState, setupAuthenticatedState } from './helpers/storageTestHelpers';
 *
 *   // Set up storage before mounting provider
 *   await mockSecureStoreState({ access_token: 'token123' });
 *
 *   // Or use predefined scenarios
 *   await setupAuthenticatedState();
 */

import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';

// ============================================================================
// Types
// ============================================================================

interface SecureStoreState {
  atom_access_token?: string;
  atom_refresh_token?: string;
  atom_token_expiry?: string;
  atom_biometric_enabled?: string;
}

interface AsyncStorageState {
  atom_user_data?: string; // JSON string
  atom_device_id?: string;
  atom_device_token?: string;
  atom_device_registered?: string; // 'true' | 'false'
  atom_device_capabilities?: string; // JSON string
  atom_last_sync?: string; // ISO date string
  socket_room_*?: string; // Room subscriptions
}

interface MMKVState {
  [key: string]: any;
}

interface AuthState {
  access_token: string;
  refresh_token?: string;
  expires_at: number;
  user: any;
}

interface DeviceState {
  device_id: string;
  device_token?: string;
  is_registered: boolean;
  capabilities: any;
  last_sync?: Date;
}

// ============================================================================
// Storage State Helpers
// ============================================================================

/**
 * Mock SecureStore items (tokens, biometric settings)
 * @param tokens - Partial secure store state to mock
 */
export const mockSecureStoreState = async (tokens: Partial<SecureStoreState>): Promise<void> => {
  const mocks = {
    atom_access_token: tokens.atom_access_token || null,
    atom_refresh_token: tokens.atom_refresh_token || null,
    atom_token_expiry: tokens.atom_token_expiry || null,
    atom_biometric_enabled: tokens.atom_biometric_enabled || null,
  };

  // Mock getItemAsync to return stored values
  (SecureStore.getItemAsync as jest.Mock).mockImplementation((key: string) => {
    return Promise.resolve(mocks[key] || null);
  });

  // Mock setItemAsync to update internal state
  (SecureStore.setItemAsync as jest.Mock).mockImplementation(async (key: string, value: string) => {
    (mocks as any)[key] = value;
    return Promise.resolve(undefined);
  });

  // Mock deleteItemAsync to remove from internal state
  (SecureStore.deleteItemAsync as jest.Mock).mockImplementation(async (key: string) => {
    delete (mocks as any)[key];
    return Promise.resolve(undefined);
  });
};

/**
 * Mock AsyncStorage items (user data, device state, preferences)
 * @param items - Key-value pairs to store
 */
export const mockAsyncStorageState = async (items: Record<string, string>): Promise<void> => {
  const storage = { ...items };

  // Mock getItem to return stored values
  (AsyncStorage.getItem as jest.Mock).mockImplementation((key: string) => {
    return Promise.resolve(storage[key] || null);
  });

  // Mock setItem to update internal state
  (AsyncStorage.setItem as jest.Mock).mockImplementation(async (key: string, value: string) => {
    storage[key] = value;
    return Promise.resolve(undefined);
  });

  // Mock removeItem to delete from internal state
  (AsyncStorage.removeItem as jest.Mock).mockImplementation(async (key: string) => {
    delete storage[key];
    return Promise.resolve(undefined);
  });

  // Mock getAllKeys to return all keys
  (AsyncStorage.getAllKeys as jest.Mock).mockImplementation(() => {
    return Promise.resolve(Object.keys(storage));
  });
};

/**
 * Mock MMKV items (app state, cache)
 * Note: This uses the global MMKV instance from jest.setup.js
 * @param items - Key-value pairs to store
 */
export const mockMMKVState = async (items: Record<string, any>): Promise<void> => {
  const mmkvInstance = global.__mmkvGlobalInstance;
  if (!mmkvInstance) {
    console.warn('MMKV instance not found. Make sure jest.setup.js is loaded.');
    return;
  }

  // Clear existing data
  mmkvInstance.removeAll();

  // Set all items
  Object.entries(items).forEach(([key, value]) => {
    mmkvInstance.set(key, value);
  });
};

/**
 * Get all currently stored state across all storage systems
 * @returns Object with current state from all storage systems
 */
export const getAllStoredState = async (): Promise<{
  secureStore: SecureStoreState;
  asyncStorage: AsyncStorageState;
  mmkv: MMKVState;
}> => {
  // Get SecureStore state
  const secureStore: SecureStoreState = {};
  const secureKeys = ['atom_access_token', 'atom_refresh_token', 'atom_token_expiry', 'atom_biometric_enabled'];
  for (const key of secureKeys) {
    const value = await SecureStore.getItemAsync(key);
    if (value !== null) {
      (secureStore as any)[key] = value;
    }
  }

  // Get AsyncStorage state
  const asyncStorage: AsyncStorageState = {};
  const allKeys = await AsyncStorage.getAllKeys();
  for (const key of allKeys) {
    const value = await AsyncStorage.getItem(key);
    if (value !== null) {
      (asyncStorage as any)[key] = value;
    }
  }

  // Get MMKV state
  const mmkv: MMKVState = {};
  const mmkvInstance = global.__mmkvGlobalInstance;
  if (mmkvInstance) {
    const keys = mmkvInstance.getAllKeys();
    for (const key of keys) {
      mmkv[key] = mmkvInstance.getString(key);
    }
  }

  return { secureStore, asyncStorage, mmkv };
};

/**
 * Clear all storage (SecureStore, AsyncStorage, MMKV)
 * Useful for test cleanup or testing "fresh install" scenarios
 */
export const clearAllStorage = async (): Promise<void> => {
  // Clear SecureStore mocks
  await mockSecureStoreState({});

  // Clear AsyncStorage mocks
  await mockAsyncStorageState({});

  // Clear MMKV
  const mmkvInstance = global.__mmkvGlobalInstance;
  if (mmkvInstance) {
    mmkvInstance.removeAll();
  }

  // Reset global mock helpers
  if (global.__resetSecureStoreMock) {
    global.__resetSecureStoreMock();
  }
  if (global.__resetAsyncStorageMock) {
    global.__resetAsyncStorageMock();
  }
  if (global.__resetMmkvMock) {
    global.__resetMmkvMock();
  }
};

// ============================================================================
// Token Helpers
// ============================================================================

/**
 * Create a valid JWT-like token mock
 * @param expiryHours - Hours until token expires (default: 24)
 * @returns Mock JWT token string
 */
export const createValidToken = (expiryHours: number = 24): string => {
  const expiry = Date.now() + (expiryHours * 60 * 60 * 1000);
  return `mock_access_token_${expiry}`;
};

/**
 * Create an expired token
 * @returns Mock JWT token that is already expired
 */
export const createExpiredToken = (): string => {
  const past = Date.now() - (60 * 60 * 1000); // 1 hour ago
  return `mock_access_token_${past}`;
};

/**
 * Create a token that will expire soon (<5 minutes)
 * @returns Mock JWT token expiring in 4 minutes
 */
export const createExpiringSoonToken = (): string => {
  const soon = Date.now() + (4 * 60 * 1000); // 4 minutes from now
  return `mock_access_token_${soon}`;
};

/**
 * Parse expiry timestamp from mock token
 * @param token - Mock token string
 * @returns Expiry timestamp in milliseconds
 */
export const parseTokenExpiry = (token: string): number => {
  // Extract timestamp from mock token format: mock_access_token_1234567890
  const match = token.match(/mock_access_token_(\d+)/);
  if (match && match[1]) {
    return parseInt(match[1], 10);
  }
  return Date.now() + (24 * 60 * 60 * 1000); // Default to 24 hours from now
};

/**
 * Calculate expiry timestamp from now
 * @param hours - Hours from now
 * @returns Expiry timestamp as string (for storage)
 */
export const calculateTokenExpiry = (hours: number = 24): string => {
  return (Date.now() + (hours * 60 * 60 * 1000)).toString();
};

// ============================================================================
// User Data Helpers
// ============================================================================

/**
 * Create a mock user object
 * @param overrides - Override default user properties
 * @returns Mock user object
 */
export const createMockUser = (overrides: any = {}): any => {
  return {
    id: 'user_123',
    email: 'test@example.com',
    name: 'Test User',
    avatar: 'https://example.com/avatar.jpg',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
};

/**
 * Create mock device info
 * @param overrides - Override default device properties
 * @returns Mock device info object
 */
export const createMockDevice = (overrides: any = {}): any => {
  return {
    device_token: 'device_token_123',
    platform: 'ios',
    model: 'iPhone 14',
    os_version: '16.0',
    app_version: '1.0.0',
    device_name: 'Test Device',
    is_device: true,
    ...overrides,
  };
};

/**
 * Create mock device capabilities
 * @param overrides - Override default capabilities
 * @returns Mock capabilities object
 */
export const createMockCapabilities = (overrides: any = {}): any => {
  return {
    camera: false,
    location: false,
    notifications: false,
    biometric: false,
    screenRecording: false,
    ...overrides,
  };
};

// ============================================================================
// Scenario Helpers
// ============================================================================

/**
 * Set up full authenticated user state in storage
 * This simulates a user who is logged in with valid tokens
 * @param customUser - Optional custom user object
 * @param customDevice - Optional custom device info
 */
export const setupAuthenticatedState = async (
  customUser?: any,
  customDevice?: any
): Promise<void> => {
  const user = customUser || createMockUser();
  const device = customDevice || createMockDevice();

  // Set up tokens
  await mockSecureStoreState({
    atom_access_token: createValidToken(24),
    atom_refresh_token: 'mock_refresh_token_123',
    atom_token_expiry: calculateTokenExpiry(24),
  });

  // Set up user data and device info
  await mockAsyncStorageState({
    atom_user_data: JSON.stringify(user),
    atom_device_id: device.device_token,
    atom_device_token: device.device_token,
  });
};

/**
 * Set up unauthenticated state (no auth tokens)
 * This simulates a fresh install or logged-out state
 */
export const setupUnauthenticatedState = async (): Promise<void> => {
  await clearAllStorage();
};

/**
 * Set up registered device state
 * Device is registered but user may not be authenticated
 * @param deviceToken - Device push token
 */
export const setupRegisteredDevice = async (deviceToken: string = 'device_token_123'): Promise<void> => {
  await mockAsyncStorageState({
    atom_device_id: 'device_id_123',
    atom_device_token: deviceToken,
    atom_device_registered: 'true',
    atom_device_capabilities: JSON.stringify(createMockCapabilities()),
    atom_last_sync: new Date().toISOString(),
  });
};

/**
 * Set up partial/expired auth state
 * This simulates tokens that are expired or missing
 * Useful for testing refresh flows
 * @param scenario - Which partial scenario to set up
 */
export const setupPartialAuthState = async (
  scenario: 'expired' | 'expiring-soon' | 'missing-refresh' | 'user-data-only' = 'expired'
): Promise<void> => {
  switch (scenario) {
    case 'expired':
      // Token exists but is expired
      await mockSecureStoreState({
        atom_access_token: createExpiredToken(),
        atom_refresh_token: 'mock_refresh_token_123',
        atom_token_expiry: calculateTokenExpiry(-1), // 1 hour ago
      });
      break;

    case 'expiring-soon':
      // Token valid but expiring in <5 minutes
      await mockSecureStoreState({
        atom_access_token: createExpiringSoonToken(),
        atom_refresh_token: 'mock_refresh_token_123',
        atom_token_expiry: calculateTokenExpiry(0.067), // 4 minutes
      });
      break;

    case 'missing-refresh':
      // Access token exists but no refresh token
      await mockSecureStoreState({
        atom_access_token: createValidToken(24),
        atom_token_expiry: calculateTokenExpiry(24),
      });
      break;

    case 'user-data-only':
      // Only user data in AsyncStorage, no tokens
      await mockAsyncStorageState({
        atom_user_data: JSON.stringify(createMockUser()),
      });
      break;
  }
};

/**
 * Set up WebSocket room subscriptions
 * @param rooms - Array of room names to subscribe to
 */
export const setupWebSocketRooms = async (rooms: string[]): Promise<void> => {
  const roomState: Record<string, string> = {};
  rooms.forEach(room => {
    roomState[`socket_room_${room}`] = 'true';
  });
  await mockAsyncStorageState(roomState);
};

/**
 * Set up biometric authentication enabled
 * @param enabled - Whether biometric is enabled
 */
export const setupBiometricState = async (enabled: boolean = true): Promise<void> => {
  if (enabled) {
    await mockSecureStoreState({
      atom_biometric_enabled: 'true',
    });
  }
};

/**
 * Set up complete fresh install scenario
 * No stored data, all state at defaults
 */
export const setupFreshInstall = async (): Promise<void> => {
  await clearAllStorage();
};

/**
 * Set up returning user scenario
 * User has logged in before, tokens are valid
 */
export const setupReturningUser = async (): Promise<void> => {
  await setupAuthenticatedState();
};

/**
 * Set up expired session scenario
 * User was logged in but session has expired
 */
export const setupExpiredSession = async (): Promise<void> => {
  const user = createMockUser();
  const device = createMockDevice();

  // Expired tokens
  await mockSecureStoreState({
    atom_access_token: createExpiredToken(),
    atom_refresh_token: 'mock_refresh_token_123',
    atom_token_expiry: calculateTokenExpiry(-1),
  });

  // User and device data still present
  await mockAsyncStorageState({
    atom_user_data: JSON.stringify(user),
    atom_device_id: device.device_token,
  });
};

/**
 * Set up corrupted storage scenario
 * Simulates storage corruption (invalid JSON, malformed data)
 * Useful for testing error handling
 * @param corruptionType - Type of corruption to simulate
 */
export const setupCorruptedStorage = async (
  corruptionType: 'invalid-json' | 'malformed-token' | 'missing-keys' = 'invalid-json'
): Promise<void> => {
  switch (corruptionType) {
    case 'invalid-json':
      // User data is invalid JSON
      await mockAsyncStorageState({
        atom_user_data: '{invalid json}',
        atom_device_id: 'device_123',
      });
      break;

    case 'malformed-token':
      // Token has invalid format
      await mockSecureStoreState({
        atom_access_token: 'invalid_token_format',
        atom_token_expiry: 'not_a_number',
      });
      break;

    case 'missing-keys':
      // Some expected keys are missing
      await mockAsyncStorageState({
        atom_user_data: JSON.stringify(createMockUser()),
        // atom_device_id is missing
      });
      break;
  }
};

// ============================================================================
// Verification Helpers
// ============================================================================

/**
 * Verify that storage contains expected authentication state
 * @param expected - Expected state properties
 * @returns Object indicating which properties match
 */
export const verifyAuthState = async (expected: {
  isAuthenticated?: boolean;
  hasAccessToken?: boolean;
  hasRefreshToken?: boolean;
  hasUserData?: boolean;
}): Promise<{
  matches: boolean;
  details: Record<string, boolean>;
}> => {
  const details: Record<string, boolean> = {};

  if (expected.hasAccessToken !== undefined) {
    const token = await SecureStore.getItemAsync('atom_access_token');
    details.hasAccessToken = token !== null;
  }

  if (expected.hasRefreshToken !== undefined) {
    const token = await SecureStore.getItemAsync('atom_refresh_token');
    details.hasRefreshToken = token !== null;
  }

  if (expected.hasUserData !== undefined) {
    const userData = await AsyncStorage.getItem('atom_user_data');
    details.hasUserData = userData !== null;
  }

  const matches = Object.values(details).every(result => result === true);

  return { matches, details };
};

/**
 * Verify that storage contains expected device state
 * @param expected - Expected device state properties
 * @returns Object indicating which properties match
 */
export const verifyDeviceState = async (expected: {
  isRegistered?: boolean;
  hasDeviceId?: boolean;
  hasDeviceToken?: boolean;
  hasCapabilities?: boolean;
}): Promise<{
  matches: boolean;
  details: Record<string, boolean>;
}> => {
  const details: Record<string, boolean> = {};

  if (expected.hasDeviceId !== undefined) {
    const deviceId = await AsyncStorage.getItem('atom_device_id');
    details.hasDeviceId = deviceId !== null;
  }

  if (expected.hasDeviceToken !== undefined) {
    const deviceToken = await AsyncStorage.getItem('atom_device_token');
    details.hasDeviceToken = deviceToken !== null;
  }

  if (expected.isRegistered !== undefined) {
    const isRegistered = await AsyncStorage.getItem('atom_device_registered');
    details.isRegistered = isRegistered === 'true';
  }

  if (expected.hasCapabilities !== undefined) {
    const capabilities = await AsyncStorage.getItem('atom_device_capabilities');
    details.hasCapabilities = capabilities !== null;
  }

  const matches = Object.values(details).every(result => result === true);

  return { matches, details };
};
