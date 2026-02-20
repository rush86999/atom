/**
 * Mock Storage Utilities for Atom Mobile Tests
 *
 * This file provides helper functions for managing mocked storage
 * (AsyncStorage, MMKV, SecureStore) during tests.
 *
 * Features:
 * - Reset AsyncStorage to clean state
 * - Reset MMKV to clean state
 * - Reset SecureStore to clean state
 * - Seed storage with test data
 * - Inspect storage state
 */

// ============================================================================
// AsyncStorage Helpers
// ============================================================================

/**
 * Reset AsyncStorage mock to clean state
 */
export function resetAsyncStorage() {
  if (global.__resetAsyncStorageMock) {
    global.__resetAsyncStorageMock();
  }
}

/**
 * Seed AsyncStorage with test data
 */
export function seedAsyncStorage(data: Record<string, any>) {
  const AsyncStorage = require('@react-native-async-storage/async-storage').default;

  Object.entries(data).forEach(([key, value]) => {
    AsyncStorage.setItem(key, JSON.stringify(value));
  });
}

/**
 * Get all items from AsyncStorage
 */
export async function getAllAsyncStorageItems(): Promise<Record<string, any>> {
  const AsyncStorage = require('@react-native-async-storage/async-storage').default;
  const keys = await AsyncStorage.getAllKeys();
  const pairs = await AsyncStorage.multiGet(keys);

  const result: Record<string, any> = {};
  pairs.forEach(([key, value]) => {
    if (value) {
      try {
        result[key] = JSON.parse(value);
      } catch {
        result[key] = value;
      }
    }
  });

  return result;
}

/**
 * Clear AsyncStorage
 */
export async function clearAsyncStorage() {
  const AsyncStorage = require('@react-native-async-storage/async-storage').default;
  await AsyncStorage.clear();
}

// ============================================================================
// MMKV Helpers
// ============================================================================

/**
 * Reset MMKV mock to clean state
 */
export function resetMmkvStorage() {
  if (global.__resetMmkvMock) {
    global.__resetMmkvMock();
  }
}

/**
 * Seed MMKV with test data
 */
export function seedMmkvStorage(data: Record<string, any>) {
  // Mock is accessed via global helpers
  const mockStorage = global.__mmkvStorage || new Map();

  Object.entries(data).forEach(([key, value]) => {
    mockStorage.set(key, value);
  });
}

// ============================================================================
// SecureStore Helpers
// ============================================================================

/**
 * Reset SecureStore mock to clean state
 */
export function resetSecureStore() {
  if (global.__resetSecureStoreMock) {
    global.__resetSecureStoreMock();
  }
}

/**
 * Seed SecureStore with test data
 */
export async function seedSecureStore(data: Record<string, string>) {
  const SecureStore = require('expo-secure-store');

  await Promise.all(
    Object.entries(data).map(([key, value]) =>
      SecureStore.setItemAsync(key, value)
    )
  );
}

/**
 * Get item from SecureStore
 */
export async function getSecureStoreItem(key: string): Promise<string | null> {
  const SecureStore = require('expo-secure-store');
  return await SecureStore.getItemAsync(key);
}

// ============================================================================
// Combined Storage Helpers
// ============================================================================

/**
 * Reset all storage mocks to clean state
 */
export function resetAllStorage() {
  resetAsyncStorage();
  resetMmkvStorage();
  resetSecureStore();
}

/**
 * Seed all storage with test data
 */
export async function seedAllStorage(data: {
  asyncStorage?: Record<string, any>;
  mmkv?: Record<string, any>;
  secureStore?: Record<string, string>;
}) {
  if (data.asyncStorage) {
    seedAsyncStorage(data.asyncStorage);
  }

  if (data.mmkv) {
    seedMmkvStorage(data.mmkv);
  }

  if (data.secureStore) {
    await seedSecureStore(data.secureStore);
  }
}

/**
 * Clear all storage
 */
export async function clearAllStorage() {
  await clearAsyncStorage();
  resetMmkvStorage();
  resetSecureStore();
}

// ============================================================================
// Auth Token Helpers
// ============================================================================

/**
 * Set mock auth token in SecureStore
 */
export async function setMockAuthToken(token: string = 'test-auth-token') {
  await seedSecureStore({
    auth_token: token,
  });
}

/**
 * Get mock auth token from SecureStore
 */
export async function getMockAuthToken(): Promise<string | null> {
  return await getSecureStoreItem('auth_token');
}

/**
 * Clear mock auth token
 */
export async function clearMockAuthToken() {
  const SecureStore = require('expo-secure-store');
  await SecureStore.deleteItemAsync('auth_token');
}

// ============================================================================
// Default Export
// ============================================================================

export default {
  resetAsyncStorage,
  seedAsyncStorage,
  getAllAsyncStorageItems,
  clearAsyncStorage,
  resetMmkvStorage,
  seedMmkvStorage,
  resetSecureStore,
  seedSecureStore,
  getSecureStoreItem,
  resetAllStorage,
  seedAllStorage,
  clearAllStorage,
  setMockAuthToken,
  getMockAuthToken,
  clearMockAuthToken,
};
