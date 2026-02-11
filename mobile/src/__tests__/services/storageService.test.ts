/**
 * Storage Service Tests
 *
 * Tests for MMKV and AsyncStorage wrapper:
 * - MMKV operations for critical data (tokens, user info)
 * - AsyncStorage operations for app data (cache, preferences)
 * - Multi-key retrieval
 * - Namespace/prefix handling
 * - Error handling
 * - JSON serialization/deserialization
 *
 * Note: Uses global mocks from jest.setup.js
 */

import {
  storageService,
  setString,
  getString,
  setObject,
  getObject,
  setNumber,
  getNumber,
  setBoolean,
  getBoolean,
  deleteKey,
  hasKey,
  clearStorage,
} from '../../services/storageService';

describe('StorageService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset global mocks
    (global as any).__resetMmkvMock?.();
    (global as any).__resetAsyncStorageMock?.();
  });

  // ========================================================================
  // MMKV (SecureStore) Operations Tests
  // ========================================================================

  describe('MMKV Operations (Critical Data)', () => {
    test('should store auth token successfully', async () => {
      const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test';

      const result = await storageService.setString('auth_token', token);

      expect(result).toBe(true);
    });

    test('should retrieve auth token after storing', async () => {
      const token = 'test_token_value';

      await storageService.setString('auth_token', token);
      const retrieved = storageService.getString('auth_token');

      expect(retrieved).toBe(token);
    });

    test('should store and retrieve refresh token', async () => {
      const refreshToken = 'refresh_token_value';

      const result = await storageService.setString('refresh_token', refreshToken);
      expect(result).toBe(true);

      const retrieved = storageService.getString('refresh_token');
      expect(retrieved).toBe(refreshToken);
    });

    test('should store and retrieve user_id', async () => {
      const userId = 'user_12345';

      await storageService.setString('user_id', userId);
      const retrieved = storageService.getString('user_id');

      expect(retrieved).toBe(userId);
    });

    test('should store and retrieve device_id', async () => {
      const deviceId = 'mobile_device_abc';

      await storageService.setString('device_id', deviceId);
      const retrieved = storageService.getString('device_id');

      expect(retrieved).toBe(deviceId);
    });

    test('should delete token successfully', async () => {
      await storageService.setString('auth_token', 'test_token');

      const result = await storageService.delete('auth_token');

      expect(result).toBe(true);
      const retrieved = storageService.getString('auth_token');
      expect(retrieved).toBeNull();
    });

    test('should check if key exists', async () => {
      await storageService.setString('user_id', 'user_123');

      const exists = await storageService.has('user_id');

      expect(exists).toBe(true);
    });

    test('should return null for non-existent key', () => {
      const value = storageService.getString('non_existent_key');

      expect(value).toBeNull();
    });
  });

  // ========================================================================
  // AsyncStorage Operations Tests
  // ========================================================================

  describe('AsyncStorage Operations (App Data)', () => {
    test('should store episode cache successfully', async () => {
      const cacheData = JSON.stringify({ episode_id: 'ep_1', data: 'test' });

      const result = await storageService.setString('episode_cache', cacheData);

      expect(result).toBe(true);
    });

    test('should retrieve episode cache after storing', async () => {
      const cacheData = JSON.stringify({ episode_id: 'ep_1', data: 'test' });

      await storageService.setString('episode_cache', cacheData);
      const retrieved = await storageService.getStringAsync('episode_cache');

      expect(retrieved).toBe(cacheData);
    });

    test('should store canvas cache successfully', async () => {
      const canvasData = JSON.stringify({ canvas_id: 'can_1', type: 'chart' });

      const result = await storageService.setString('canvas_cache', canvasData);

      expect(result).toBe(true);
    });

    test('should retrieve canvas cache after storing', async () => {
      const canvasData = JSON.stringify({ canvas_id: 'can_1', type: 'chart' });

      await storageService.setString('canvas_cache', canvasData);
      const retrieved = await storageService.getStringAsync('canvas_cache');

      expect(retrieved).toBe(canvasData);
    });

    test('should store preferences successfully', async () => {
      const preferences = JSON.stringify({ theme: 'dark', language: 'en' });

      const result = await storageService.setString('preferences', preferences);

      expect(result).toBe(true);
    });

    test('should retrieve preferences after storing', async () => {
      const preferences = JSON.stringify({ theme: 'dark', language: 'en' });

      await storageService.setString('preferences', preferences);
      const retrieved = await storageService.getStringAsync('preferences');

      expect(retrieved).toBe(preferences);
    });

    test('should delete from AsyncStorage successfully', async () => {
      await storageService.setString('episode_cache', 'data');

      const result = await storageService.delete('episode_cache');

      expect(result).toBe(true);
    });

    test('should check if AsyncStorage key exists', async () => {
      await storageService.setString('preferences', '{}');

      const exists = await storageService.has('preferences');

      expect(exists).toBe(true);
    });
  });

  // ========================================================================
  // JSON Serialization/Deserialization Tests
  // ========================================================================

  describe('JSON Serialization', () => {
    test('should store and retrieve object from MMKV', async () => {
      const userData = { id: 'user_1', name: 'Test User', email: 'test@example.com' };

      const result = await storageService.setObject('user_id', userData);
      expect(result).toBe(true);

      const retrieved = await storageService.getObject<typeof userData>('user_id');
      expect(retrieved).toEqual(userData);
    });

    test('should store and retrieve object from AsyncStorage', async () => {
      const episodeData = { id: 'ep_1', title: 'Test Episode', segments: [] };

      const result = await storageService.setObject('episode_cache', episodeData);
      expect(result).toBe(true);

      const retrieved = await storageService.getObject<typeof episodeData>('episode_cache');
      expect(retrieved).toEqual(episodeData);
    });

    test('should handle nested objects', async () => {
      const nestedData = {
        user: { id: 'user_1', profile: { name: 'Test', age: 30 } },
        meta: { created: '2026-01-01' },
      };

      const result = await storageService.setObject('preferences', nestedData);
      expect(result).toBe(true);

      const retrieved = await storageService.getObject<typeof nestedData>('preferences');
      expect(retrieved).toEqual(nestedData);
    });

    test('should handle arrays', async () => {
      const arrayData = [
        { id: 'ep_1', title: 'Episode 1' },
        { id: 'ep_2', title: 'Episode 2' },
      ];

      const result = await storageService.setObject('episode_cache', arrayData);
      expect(result).toBe(true);

      const retrieved = await storageService.getObject<typeof arrayData>('episode_cache');
      expect(retrieved).toEqual(arrayData);
    });

    test('should return null for non-existent object key', async () => {
      const retrieved = await storageService.getObject<any>('non_existent_key');

      expect(retrieved).toBeNull();
    });
  });

  // ========================================================================
  // Number and Boolean Operations Tests
  // ========================================================================

  describe('Number and Boolean Operations', () => {
    test('should store and retrieve number from MMKV', async () => {
      const value = 42;

      const result = await storageService.setNumber('offline_queue', value);
      expect(result).toBe(true);

      const retrieved = await storageService.getNumber('offline_queue');
      expect(retrieved).toBe(value);
    });

    test('should store and retrieve boolean from MMKV', async () => {
      const result = await storageService.setBoolean('biometric_enabled', true);
      expect(result).toBe(true);

      const retrieved = await storageService.getBoolean('biometric_enabled');
      expect(retrieved).toBe(true);
    });

    test('should store and retrieve false boolean', async () => {
      const result = await storageService.setBoolean('biometric_enabled', false);
      expect(result).toBe(true);

      const retrieved = await storageService.getBoolean('biometric_enabled');
      expect(retrieved).toBe(false);
    });

    test('should store and retrieve floating point number', async () => {
      const value = 3.14159;

      const result = await storageService.setNumber('offline_queue', value);
      expect(result).toBe(true);

      const retrieved = await storageService.getNumber('offline_queue');
      expect(retrieved).toBeCloseTo(value, 5);
    });

    test('should return null for non-existent number key', async () => {
      const retrieved = await storageService.getNumber('non_existent_key');

      expect(retrieved).toBeNull();
    });

    test('should return null for non-existent boolean key', async () => {
      const retrieved = await storageService.getBoolean('non_existent_key');

      expect(retrieved).toBeNull();
    });
  });

  // ========================================================================
  // Multi-Key Retrieval Tests
  // ========================================================================

  describe('Multi-Key Retrieval', () => {
    test('should get all keys from both storage systems', async () => {
      // Add MMKV keys
      await storageService.setString('auth_token', 'token');
      await storageService.setString('user_id', 'user_1');

      // Add AsyncStorage keys
      await storageService.setString('preferences', '{}');
      await storageService.setString('episode_cache', '[]');

      const allKeys = await storageService.getAllKeys();

      expect(allKeys).toHaveLength(4);
      expect(allKeys).toContain('auth_token');
      expect(allKeys).toContain('user_id');
      expect(allKeys).toContain('preferences');
      expect(allKeys).toContain('episode_cache');
    });

    test('should return empty array when no keys exist', async () => {
      const allKeys = await storageService.getAllKeys();

      expect(allKeys).toHaveLength(0);
    });

    test('should handle mixed MMKV and AsyncStorage keys', async () => {
      await storageService.setString('auth_token', 'token');
      await storageService.setString('preferences', '{}');

      const allKeys = await storageService.getAllKeys();

      expect(allKeys).toHaveLength(2);
    });
  });

  // ========================================================================
  // Storage Statistics Tests
  // ========================================================================

  describe('Storage Statistics', () => {
    test('should get storage stats', async () => {
      // Add some data
      await storageService.setString('auth_token', 'test_token_value');
      await storageService.setString('preferences', JSON.stringify({ theme: 'dark' }));

      const stats = await storageService.getStats();

      expect(stats.totalItems).toBe(2);
      expect(stats.mmkvSize).toBeGreaterThanOrEqual(0);
      expect(stats.asyncStorageSize).toBeGreaterThanOrEqual(0);
    });

    test('should return zero stats for empty storage', async () => {
      const stats = await storageService.getStats();

      expect(stats.totalItems).toBe(0);
      expect(stats.mmkvSize).toBe(0);
      expect(stats.asyncStorageSize).toBe(0);
    });
  });

  // ========================================================================
  // Clear Storage Tests
  // ========================================================================

  describe('Clear Storage', () => {
    test('should clear all storage', async () => {
      // Add data to both storages
      await storageService.setString('auth_token', 'token');
      await storageService.setString('preferences', '{}');

      const result = await storageService.clear();

      expect(result).toBe(true);

      const allKeys = await storageService.getAllKeys();
      expect(allKeys).toHaveLength(0);
    });

    test('should return true on successful clear', async () => {
      await storageService.setString('auth_token', 'token');
      await storageService.setString('preferences', '{}');

      const result = await storageService.clear();

      expect(result).toBe(true);
    });
  });

  // ========================================================================
  // Convenience Function Tests
  // ========================================================================

  describe('Convenience Functions', () => {
    test('setString should work', async () => {
      const result = await setString('auth_token', 'test');

      expect(result).toBe(true);
    });

    test('getString should work', async () => {
      await setString('auth_token', 'test');
      const value = await getString('auth_token');

      expect(value).toBe('test');
    });

    test('setObject should work', async () => {
      const data = { test: 'value' };
      const result = await setObject('preferences', data);

      expect(result).toBe(true);
    });

    test('getObject should work', async () => {
      const data = { test: 'value' };
      await setObject('preferences', data);
      const value = await getObject<typeof data>('preferences');

      expect(value).toEqual(data);
    });

    test('setNumber should work', async () => {
      const result = await setNumber('offline_queue', 42);

      expect(result).toBe(true);
    });

    test('getNumber should work', async () => {
      await setNumber('offline_queue', 42);
      const value = await getNumber('offline_queue');

      expect(value).toBe(42);
    });

    test('setBoolean should work', async () => {
      const result = await setBoolean('biometric_enabled', true);

      expect(result).toBe(true);
    });

    test('getBoolean should work', async () => {
      await setBoolean('biometric_enabled', true);
      const value = await getBoolean('biometric_enabled');

      expect(value).toBe(true);
    });

    test('deleteKey should work', async () => {
      await setString('auth_token', 'token');
      const result = await deleteKey('auth_token');

      expect(result).toBe(true);
    });

    test('hasKey should work', async () => {
      await setString('auth_token', 'token');
      const exists = await hasKey('auth_token');

      expect(exists).toBe(true);
    });

    test('clearStorage should work', async () => {
      await setString('auth_token', 'token');
      const result = await clearStorage();

      expect(result).toBe(true);
    });
  });

  // ========================================================================
  // Storage Layer Separation Tests
  // ========================================================================

  describe('Storage Layer Separation', () => {
    test('should use MMKV for auth_token (verified by sync access)', async () => {
      await storageService.setString('auth_token', 'token');

      // MMKV keys can be accessed sync
      const value = storageService.getString('auth_token');
      expect(value).toBe('token');
    });

    test('should use MMKV for refresh_token (verified by sync access)', async () => {
      await storageService.setString('refresh_token', 'refresh');

      const value = storageService.getString('refresh_token');
      expect(value).toBe('refresh');
    });

    test('should use MMKV for user_id (verified by sync access)', async () => {
      await storageService.setString('user_id', 'user_1');

      const value = storageService.getString('user_id');
      expect(value).toBe('user_1');
    });

    test('should use MMKV for device_id (verified by sync access)', async () => {
      await storageService.setString('device_id', 'device_1');

      const value = storageService.getString('device_id');
      expect(value).toBe('device_1');
    });

    test('should use MMKV for biometric_enabled (verified by sync access)', async () => {
      await storageService.setBoolean('biometric_enabled', true);

      const value = await storageService.getBoolean('biometric_enabled');
      expect(value).toBe(true);
    });

    test('should use MMKV for offline_queue (verified by sync access)', async () => {
      await storageService.setNumber('offline_queue', 5);

      const value = await storageService.getNumber('offline_queue');
      expect(value).toBe(5);
    });

    test('should use MMKV for sync_state (verified by sync access)', async () => {
      await storageService.setString('sync_state', 'syncing');

      const value = storageService.getString('sync_state');
      expect(value).toBe('syncing');
    });

    test('should use AsyncStorage for episode_cache (requires async access)', async () => {
      await storageService.setString('episode_cache', 'cache');

      // AsyncStorage keys require async access
      const value = await storageService.getStringAsync('episode_cache');
      expect(value).toBe('cache');
    });

    test('should use AsyncStorage for canvas_cache (requires async access)', async () => {
      await storageService.setString('canvas_cache', 'cache');

      const value = await storageService.getStringAsync('canvas_cache');
      expect(value).toBe('cache');
    });

    test('should use AsyncStorage for preferences (requires async access)', async () => {
      await storageService.setString('preferences', 'prefs');

      const value = await storageService.getStringAsync('preferences');
      expect(value).toBe('prefs');
    });
  });

  // ========================================================================
  // Error Handling Tests
  // ========================================================================

  describe('Error Handling', () => {
    test('should handle getAllKeys errors gracefully', async () => {
      // Force an error by making the mock throw
      const mockGetAllKeys = require('@react-native-async-storage/async-storage').getAllKeys;
      mockGetAllKeys.mockRejectedValueOnce(new Error('Storage unavailable'));

      await expect(storageService.getAllKeys()).rejects.toThrow();
    });

    test('should handle clear errors gracefully', async () => {
      const mockClear = require('@react-native-async-storage/async-storage').clear;
      mockClear.mockRejectedValueOnce(new Error('Clear error'));

      const result = await storageService.clear();

      expect(result).toBe(false);
    });
  });

  // ========================================================================
  // Migration Tests
  // ========================================================================

  describe('Migration to MMKV', () => {
    test('should migrate keys from AsyncStorage to MMKV', async () => {
      // Note: This test depends on the actual migrateToMMKV implementation
      // which reads from AsyncStorage and writes to MMKV
      const result = await storageService.migrateToMMKV(['auth_token', 'user_id']);

      // Should succeed even if no data to migrate
      expect(result).toBeDefined();
      expect(typeof result.success).toBe('number');
      expect(typeof result.failed).toBe('number');
    });

    test('should handle migration of non-MMKV keys gracefully', async () => {
      const result = await storageService.migrateToMMKV(['preferences']);

      // Should skip keys not in MMKV_KEYS set
      expect(result.success).toBe(0);
      expect(result.failed).toBe(0);
    });
  });
});
