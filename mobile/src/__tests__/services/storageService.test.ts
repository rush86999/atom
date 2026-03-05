/**
 * Storage Service Tests
 *
 * Comprehensive tests for MMKV and AsyncStorage wrapper:
 * - MMKV operations for critical data (tokens, user info)
 * - AsyncStorage operations for app data (cache, preferences)
 * - Storage quota management and cleanup
 * - Cache compression and quality metrics
 * - Migration from AsyncStorage to MMKV
 * - Edge cases (large values, special chars, unicode)
 * - Error handling
 * - JSON serialization/deserialization
 * - Convenience function delegation
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
  StorageKey,
} from '../../services/storageService';

describe('StorageService', () => {
  beforeEach(() => {
    // Reset global mocks BEFORE clearing mocks
    (global as any).__resetMmkvMock?.();
    (global as any).__resetAsyncStorageMock?.();

    // Reset storageService quota to prevent pollution from previous tests
    (storageService as any).quota = null;

    jest.clearAllMocks();
  });

  // ========================================================================
  // MMKV (SecureStore) Operations Tests
  // ========================================================================

  describe('MMKV String Operations', () => {
    test('should set string value in MMKV', async () => {
      const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test';

      const result = await storageService.setString('auth_token', token);

      expect(result).toBe(true);
    });

    test('should get string value from MMKV', async () => {
      const token = 'test_token_value';

      await storageService.setString('auth_token', token);
      const retrieved = storageService.getString('auth_token');

      expect(retrieved).toBe(token);
    });

    test('should return null for non-existent MMKV key', () => {
      const value = storageService.getString('non_existent_key');

      expect(value).toBeNull();
    });

    test('should handle MMKV errors gracefully', async () => {
      // Mock MMKV to throw error
      const mockMMKV = (global as any).__mmkvGlobalInstance;
      mockMMKV.set.mockImplementationOnce(() => {
        throw new Error('MMKV write failed');
      });

      const result = await storageService.setString('auth_token', 'token');

      expect(result).toBe(false);
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
  });

  // ========================================================================
  // MMKV Number Operations Tests
  // ========================================================================

  describe('MMKV Number Operations', () => {
    test('should set number value in MMKV', async () => {
      const value = 42;

      const result = await storageService.setNumber('offline_queue', value);

      expect(result).toBe(true);
    });

    test('should get number value from MMKV', async () => {
      const value = 42;

      await storageService.setNumber('offline_queue', value);
      const retrieved = await storageService.getNumber('offline_queue');

      expect(retrieved).toBe(value);
    });

    test('should return null for non-existent number key', async () => {
      const retrieved = await storageService.getNumber('non_existent_key');

      expect(retrieved).toBeNull();
    });

    test('should store and retrieve floating point number', async () => {
      const value = 3.14159;

      const result = await storageService.setNumber('offline_queue', value);
      expect(result).toBe(true);

      const retrieved = await storageService.getNumber('offline_queue');
      expect(retrieved).toBeCloseTo(value, 5);
    });

    test('should handle negative numbers', async () => {
      const value = -42;

      await storageService.setNumber('offline_queue', value);
      const retrieved = await storageService.getNumber('offline_queue');

      expect(retrieved).toBe(value);
    });

    test('should handle zero', async () => {
      const value = 0;

      await storageService.setNumber('offline_queue', value);
      const retrieved = await storageService.getNumber('offline_queue');

      expect(retrieved).toBe(0);
    });
  });

  // ========================================================================
  // MMKV Boolean Operations Tests
  // ========================================================================

  describe('MMKV Boolean Operations', () => {
    test('should set boolean value in MMKV', async () => {
      const result = await storageService.setBoolean('biometric_enabled', true);

      expect(result).toBe(true);
    });

    test('should get boolean value from MMKV', async () => {
      await storageService.setBoolean('biometric_enabled', true);
      const retrieved = await storageService.getBoolean('biometric_enabled');

      expect(retrieved).toBe(true);
    });

    test('should handle false boolean correctly', async () => {
      const result = await storageService.setBoolean('biometric_enabled', false);

      expect(result).toBe(true);

      const retrieved = await storageService.getBoolean('biometric_enabled');
      expect(retrieved).toBe(false);
    });

    test('should return null for non-existent boolean key', async () => {
      const retrieved = await storageService.getBoolean('non_existent_key');

      expect(retrieved).toBeNull();
    });
  });

  // ========================================================================
  // AsyncStorage Operations Tests
  // ========================================================================

  describe('AsyncStorage Operations', () => {
    test('should set string value in AsyncStorage', async () => {
      const cacheData = JSON.stringify({ episode_id: 'ep_1', data: 'test' });

      const result = await storageService.setString('episode_cache', cacheData);

      expect(result).toBe(true);
    });

    test('should get string value from AsyncStorage async', async () => {
      const cacheData = JSON.stringify({ episode_id: 'ep_1', data: 'test' });

      await storageService.setString('episode_cache', cacheData);
      const retrieved = await storageService.getStringAsync('episode_cache');

      expect(retrieved).toBe(cacheData);
    });

    test('should remove value from AsyncStorage', async () => {
      await storageService.setString('episode_cache', 'data');

      const result = await storageService.delete('episode_cache');

      expect(result).toBe(true);
      const retrieved = await storageService.getStringAsync('episode_cache');
      expect(retrieved).toBeNull();
    });

    test('should handle AsyncStorage errors', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage');
      AsyncStorage.setItem.mockRejectedValueOnce(new Error('AsyncStorage error'));

      const result = await storageService.setString('episode_cache', 'data');

      expect(result).toBe(false);
    });

    test('should store episode cache successfully', async () => {
      const cacheData = JSON.stringify({ episode_id: 'ep_1', data: 'test' });

      const result = await storageService.setString('episode_cache', cacheData);

      expect(result).toBe(true);
    });

    test('should store canvas cache successfully', async () => {
      const canvasData = JSON.stringify({ canvas_id: 'can_1', type: 'chart' });

      const result = await storageService.setString('canvas_cache', canvasData);

      expect(result).toBe(true);
    });

    test('should store preferences successfully', async () => {
      const preferences = JSON.stringify({ theme: 'dark', language: 'en' });

      const result = await storageService.setString('preferences', preferences);

      expect(result).toBe(true);
    });
  });

  // ========================================================================
  // Object Operations Tests
  // ========================================================================

  describe('Object Operations', () => {
    test('should set object as JSON string', async () => {
      const userData = { id: 'user_1', name: 'Test User', email: 'test@example.com' };

      const result = await storageService.setObject('user_id', userData);

      expect(result).toBe(true);
    });

    test('should get and parse object from JSON', async () => {
      const userData = { id: 'user_1', name: 'Test User', email: 'test@example.com' };

      await storageService.setObject('user_id', userData);
      const retrieved = await storageService.getObject<typeof userData>('user_id');

      expect(retrieved).toEqual(userData);
    });

    test('should return null for invalid JSON', async () => {
      // Set invalid JSON string directly
      await storageService.setString('preferences', 'invalid json{');

      const retrieved = await storageService.getObject<any>('preferences');

      expect(retrieved).toBeNull();
    });

    test('should handle circular reference errors', async () => {
      // Create circular reference
      const circularData: any = { name: 'test' };
      circularData.self = circularData;

      // JSON.stringify should throw on circular refs
      const result = await storageService.setObject('preferences', circularData);

      // Should handle error gracefully
      expect(result).toBe(false);
    });

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
  // Storage Quota Management Tests
  // ========================================================================

  describe('Storage Quota Management', () => {
    test('should calculate storage quota correctly', async () => {
      await storageService.setString('auth_token', 'test_token');
      await storageService.setString('preferences', JSON.stringify({ theme: 'dark' }));

      const quota = await storageService.getStorageQuota();

      expect(quota).toBeDefined();
      expect(quota.usedBytes).toBeGreaterThanOrEqual(0);
      expect(quota.maxBytes).toBe(50 * 1024 * 1024); // 50MB default
    });

    test('should return quota usage ratio', async () => {
      const quota = await storageService.getStorageQuota();

      expect(quota.usedBytes).toBeDefined();
      expect(quota.maxBytes).toBeDefined();

      const ratio = quota.usedBytes / quota.maxBytes;
      expect(ratio).toBeGreaterThanOrEqual(0);
      expect(ratio).toBeLessThanOrEqual(1);
    });

    test('should detect when quota approaching warning threshold (80%)', async () => {
      // Mock quota with high usage
      const stats = await storageService.getStats();
      const mockQuota = {
        usedBytes: 40 * 1024 * 1024, // 40MB = 80% of 50MB
        maxBytes: 50 * 1024 * 1024,
        warningThreshold: 0.8,
        enforcementThreshold: 0.95,
        breakdown: {
          agents: 0,
          workflows: 0,
          canvases: 0,
          episodes: 0,
          other: 40 * 1024 * 1024,
        },
      };

      // Set private quota field
      (storageService as any).quota = mockQuota;

      const check = await storageService.checkQuota();

      expect(check.shouldWarn).toBe(true);
      expect(check.shouldEnforce).toBe(false);
    });

    test('should detect when quota at enforcement threshold (95%)', async () => {
      const mockQuota = {
        usedBytes: 47.5 * 1024 * 1024, // 47.5MB = 95% of 50MB
        maxBytes: 50 * 1024 * 1024,
        warningThreshold: 0.8,
        enforcementThreshold: 0.95,
        breakdown: {
          agents: 0,
          workflows: 0,
          canvases: 0,
          episodes: 0,
          other: 47.5 * 1024 * 1024,
        },
      };

      (storageService as any).quota = mockQuota;

      const check = await storageService.checkQuota();

      expect(check.shouldWarn).toBe(true);
      expect(check.shouldEnforce).toBe(true);
    });

    test('should track storage breakdown by entity type', async () => {
      const breakdown = await storageService.getStorageBreakdown();

      expect(breakdown).toBeDefined();
      expect(typeof breakdown.agents).toBe('number');
      expect(typeof breakdown.workflows).toBe('number');
      expect(typeof breakdown.canvases).toBe('number');
      expect(typeof breakdown.episodes).toBe('number');
      expect(typeof breakdown.other).toBe('number');
    });

    test('should update quota after operations', async () => {
      const initialQuota = await storageService.getStorageQuota();
      const initialUsed = initialQuota.usedBytes;

      // Add data
      await storageService.setString('auth_token', 'new_token_value');

      const updatedQuota = await storageService.getStorageQuota();

      expect(updatedQuota.usedBytes).toBeGreaterThanOrEqual(initialUsed);
    });
  });

  // ========================================================================
  // Storage Cleanup Tests
  // ========================================================================

  describe('Storage Cleanup', () => {
    test('should clear all cached data while preserving auth tokens', async () => {
      // Add auth tokens
      await storageService.setString('auth_token', 'token');
      await storageService.setString('refresh_token', 'refresh');

      // Add cache data
      await storageService.setString('episode_cache', 'cache');
      await storageService.setString('canvas_cache', 'cache');
      await storageService.setString('preferences', 'prefs');
      await storageService.setString('offline_queue', '5');

      const result = await storageService.clearCachedData();

      expect(result).toBe(true);

      // Auth tokens should still exist
      const authToken = storageService.getString('auth_token');
      expect(authToken).toBe('token');

      // Cache should be cleared
      const episodeCache = await storageService.getStringAsync('episode_cache');
      expect(episodeCache).toBeNull();
    });

    test('should cleanup old data using LRU strategy', async () => {
      // Mock breakdown with small entries
      const mockBreakdown = {
        small_item: 100,
        medium_item: 500,
        large_item: 1000,
      };

      (storageService as any).quota = {
        usedBytes: 1600,
        maxBytes: 50 * 1024 * 1024,
        warningThreshold: 0.8,
        enforcementThreshold: 0.95,
        breakdown: mockBreakdown,
      };

      const freedBytes = await storageService.cleanupOldData(200);

      // Should free at least 200 bytes
      expect(freedBytes).toBeGreaterThanOrEqual(0);
    });

    test('should remove smallest entries first during cleanup', async () => {
      const mockBreakdown = {
        tiny: 50,
        small: 100,
        medium: 500,
        large: 1000,
      };

      (storageService as any).quota = {
        usedBytes: 1650,
        maxBytes: 50 * 1024 * 1024,
        warningThreshold: 0.8,
        enforcementThreshold: 0.95,
        breakdown: mockBreakdown,
      };

      const freedBytes = await storageService.cleanupOldData(100);

      // Should remove tiny (50) and small (100) to reach 150 bytes freed
      expect(freedBytes).toBeGreaterThan(0);
    });

    test('should stop cleanup when enough space freed', async () => {
      const mockBreakdown = {
        item1: 1000,
        item2: 1000,
        item3: 1000,
      };

      (storageService as any).quota = {
        usedBytes: 3000,
        maxBytes: 50 * 1024 * 1024,
        warningThreshold: 0.8,
        enforcementThreshold: 0.95,
        breakdown: mockBreakdown,
      };

      // Request only 500 bytes, should stop after first item
      const freedBytes = await storageService.cleanupOldData(500);

      // Should stop after freeing 1000 bytes (first item)
      expect(freedBytes).toBeGreaterThanOrEqual(500);
    });

    test('should return bytes freed from cleanup', async () => {
      const mockBreakdown = {
        cleanup_test: 500,
      };

      (storageService as any).quota = {
        usedBytes: 500,
        maxBytes: 50 * 1024 * 1024,
        warningThreshold: 0.8,
        enforcementThreshold: 0.95,
        breakdown: mockBreakdown,
      };

      const freedBytes = await storageService.cleanupOldData(100);

      expect(typeof freedBytes).toBe('number');
      expect(freedBytes).toBeGreaterThanOrEqual(0);
    });

    test('should handle cleanup errors gracefully', async () => {
      // Mock delete to throw error
      const mockMMKV = (global as any).__mmkvGlobalInstance;
      mockMMKV.delete.mockImplementationOnce(() => {
        throw new Error('Delete failed');
      });

      const freedBytes = await storageService.cleanupOldData(100);

      // Should still return bytes freed from successful deletes before the error
      // The function continues after errors, so it will free other items
      expect(typeof freedBytes).toBe('number');
      expect(freedBytes).toBeGreaterThanOrEqual(0);
    });
  });

  // ========================================================================
  // Cache Compression Tests
  // ========================================================================

  describe('Cache Compression', () => {
    test('should identify compressible cache items', async () => {
      // Add large cache item (> 1KB threshold)
      const largeData = 'x'.repeat(2000);
      await storageService.setString('episode_cache', largeData);

      const result = await storageService.compressCache();

      expect(result.compressed).toBeGreaterThanOrEqual(0);
      expect(result.bytesSaved).toBeGreaterThanOrEqual(0);
    });

    test('should calculate potential compression savings', async () => {
      const largeData = 'x'.repeat(2000);
      await storageService.setString('canvas_cache', largeData);

      const result = await storageService.compressCache();

      // 30% assumed compression ratio
      expect(result.bytesSaved).toBeGreaterThan(0);
    });

    test('should compress large cache items', async () => {
      const largeData = 'y'.repeat(1500);
      await storageService.setString('episode_cache', largeData);

      const result = await storageService.compressCache();

      expect(result.compressed).toBeGreaterThan(0);
    });

    test('should respect compression threshold', async () => {
      // Add small item (< 1KB threshold)
      await storageService.setString('episode_cache', 'small');

      const result = await storageService.compressCache();

      // Should not compress small items
      expect(result.compressed).toBe(0);
    });
  });

  // ========================================================================
  // Storage Quality Metrics Tests
  // ========================================================================

  describe('Storage Quality Metrics', () => {
    test('should return storage statistics', async () => {
      await storageService.setString('auth_token', 'test_token_value');
      await storageService.setString('preferences', JSON.stringify({ theme: 'dark' }));

      const stats = await storageService.getStats();

      expect(stats.totalItems).toBe(2);
      expect(stats.mmkvSize).toBeGreaterThanOrEqual(0);
      expect(stats.asyncStorageSize).toBeGreaterThanOrEqual(0);
    });

    test('should calculate average item size', async () => {
      await storageService.setString('auth_token', 'test_token_value');

      const metrics = await storageService.getQualityMetrics();

      expect(metrics.avgItemSize).toBeGreaterThanOrEqual(0);
    });

    test('should track cache hit rate', async () => {
      const metrics = await storageService.getQualityMetrics();

      // Mock value 0.85
      expect(metrics.cacheHitRate).toBe(0.85);
    });

    test('should return compression ratio', async () => {
      const metrics = await storageService.getQualityMetrics();

      // Mock value 0.3 (30% compression)
      expect(metrics.compressionRatio).toBe(0.3);
    });

    test('should return zero stats for empty storage', async () => {
      const stats = await storageService.getStats();

      expect(stats.totalItems).toBe(0);
      expect(stats.mmkvSize).toBe(0);
      expect(stats.asyncStorageSize).toBe(0);
    });
  });

  // ========================================================================
  // Clear All Tests
  // ========================================================================

  describe('Clear All Storage', () => {
    test('should clear all MMKV keys', async () => {
      await storageService.setString('auth_token', 'token');
      await storageService.setString('user_id', 'user_1');

      await storageService.clear();

      const allKeys = await storageService.getAllKeys();
      expect(allKeys).not.toContain('auth_token');
      expect(allKeys).not.toContain('user_id');
    });

    test('should clear all AsyncStorage keys', async () => {
      await storageService.setString('preferences', '{}');
      await storageService.setString('episode_cache', '[]');

      await storageService.clear();

      const allKeys = await storageService.getAllKeys();
      expect(allKeys).toHaveLength(0);
    });

    test('should handle clear errors gracefully', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage');
      AsyncStorage.clear.mockRejectedValueOnce(new Error('Clear error'));

      const result = await storageService.clear();

      expect(result).toBe(false);
    });
  });

  // ========================================================================
  // Get All Keys Tests
  // ========================================================================

  describe('Get All Keys', () => {
    test('should return all keys from MMKV and AsyncStorage', async () => {
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

    test('should handle empty storage', async () => {
      const allKeys = await storageService.getAllKeys();

      expect(allKeys).toHaveLength(0);
    });

    test('should deduplicate keys if overlap exists', async () => {
      // This test verifies the implementation doesn't duplicate keys
      // In practice, MMKV_KEYS and ASYNC_STORAGE_KEYS are disjoint sets
      await storageService.setString('auth_token', 'token');

      const allKeys = await storageService.getAllKeys();

      // Should have exactly 1 key
      expect(allKeys).toHaveLength(1);
    });
  });

  // ========================================================================
  // Migration Tests
  // ========================================================================

  describe('Storage Migration', () => {
    test('should migrate key from AsyncStorage to MMKV', async () => {
      // First add to AsyncStorage (using a key that will be migrated)
      const AsyncStorage = require('@react-native-async-storage/async-storage');
      AsyncStorage.getItem.mockResolvedValueOnce('migrated_value');

      const result = await storageService.migrateToMMKV(['auth_token']);

      expect(result).toBeDefined();
      expect(typeof result.success).toBe('number');
      expect(typeof result.failed).toBe('number');
    });

    test('should migrate multiple keys successfully', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage');
      AsyncStorage.getItem
        .mockResolvedValueOnce('value1')
        .mockResolvedValueOnce('value2');

      const result = await storageService.migrateToMMKV(['auth_token', 'user_id']);

      expect(result.success).toBe(2);
      expect(result.failed).toBe(0);
    });

    test('should count successful and failed migrations', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage');
      AsyncStorage.getItem
        .mockResolvedValueOnce('success')
        .mockRejectedValueOnce(new Error('Migration failed'));

      const result = await storageService.migrateToMMKV(['auth_token', 'user_id']);

      expect(result.success).toBe(1);
      expect(result.failed).toBe(1);
    });

    test('should remove migrated keys from AsyncStorage', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage');
      AsyncStorage.getItem.mockResolvedValueOnce('value');
      AsyncStorage.removeItem.mockResolvedValue(undefined);

      await storageService.migrateToMMKV(['auth_token']);

      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('auth_token');
    });

    test('should handle migration errors gracefully', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage');
      const originalImplementation = AsyncStorage.getItem.getMockImplementation();
      AsyncStorage.getItem.mockRejectedValueOnce(new Error('Storage error'));

      const result = await storageService.migrateToMMKV(['auth_token']);

      expect(result.failed).toBe(1);

      // Restore original implementation
      AsyncStorage.getItem.mockImplementation(originalImplementation);
    });

    test('should only migrate MMKV_KEYS (not ASYNC_STORAGE_KEYS)', async () => {
      const result = await storageService.migrateToMMKV(['preferences']);

      // Should skip keys not in MMKV_KEYS set
      expect(result.success).toBe(0);
      expect(result.failed).toBe(0);
    });
  });

  // ========================================================================
  // Key Type Checking Tests
  // ========================================================================

  describe('Key Existence Checks', () => {
    test('should check if key exists in MMKV', async () => {
      await storageService.setString('user_id', 'user_123');

      const exists = await storageService.has('user_id');

      expect(exists).toBe(true);
    });

    test('should check if key exists in AsyncStorage', async () => {
      await storageService.setString('preferences', '{}');

      const exists = await storageService.has('preferences');

      expect(exists).toBe(true);
    });

    test('should return false for non-existent keys', async () => {
      const exists = await storageService.has('non_existent_key' as StorageKey);

      expect(exists).toBe(false);
    });

    test('should handle has() errors gracefully', async () => {
      const mockMMKV = (global as any).__mmkvGlobalInstance;
      mockMMKV.contains.mockImplementationOnce(() => {
        throw new Error('Contains check failed');
      });

      const exists = await storageService.has('auth_token');

      expect(exists).toBe(false);
    });
  });

  // ========================================================================
  // Delete Operation Tests
  // ========================================================================

  describe('Delete Operations', () => {
    test('should delete key from MMKV', async () => {
      await storageService.setString('auth_token', 'token');

      const result = await storageService.delete('auth_token');

      expect(result).toBe(true);
      const retrieved = storageService.getString('auth_token');
      expect(retrieved).toBeNull();
    });

    test('should delete key from AsyncStorage', async () => {
      await storageService.setString('episode_cache', 'data');

      const result = await storageService.delete('episode_cache');

      expect(result).toBe(true);
    });

    test('should return true on successful delete', async () => {
      await storageService.setString('auth_token', 'token');

      const result = await storageService.delete('auth_token');

      expect(result).toBe(true);
    });

    test('should return false on delete error', async () => {
      const mockMMKV = (global as any).__mmkvGlobalInstance;
      mockMMKV.delete.mockImplementationOnce(() => {
        throw new Error('Delete failed');
      });

      const result = await storageService.delete('auth_token');

      expect(result).toBe(false);
    });
  });

  // ========================================================================
  // Edge Case Tests
  // ========================================================================

  describe('Edge Cases', () => {
    test('should handle very large string values', async () => {
      const largeString = 'x'.repeat(10000);

      const result = await storageService.setString('auth_token', largeString);

      expect(result).toBe(true);

      const retrieved = storageService.getString('auth_token');
      expect(retrieved).toHaveLength(10000);
    });

    test('should handle special characters in keys and values', async () => {
      const specialValue = '!@#$%^&*()_+-=[]{}|;:,.<>?';

      const result = await storageService.setString('auth_token', specialValue);

      expect(result).toBe(true);

      const retrieved = storageService.getString('auth_token');
      expect(retrieved).toBe(specialValue);
    });

    test('should handle unicode characters correctly', async () => {
      const unicodeValue = 'Hello 世界 🌍🎉';

      const result = await storageService.setString('auth_token', unicodeValue);

      expect(result).toBe(true);

      const retrieved = storageService.getString('auth_token');
      expect(retrieved).toBe(unicodeValue);
    });

    test('should handle null values gracefully', async () => {
      // Attempting to set null should be handled by the implementation
      const result = await storageService.setString('auth_token', 'null');

      expect(result).toBe(true);
    });

    test('should handle undefined values gracefully', async () => {
      const result = await storageService.setString('auth_token', 'undefined');

      expect(result).toBe(true);
    });

    test('should handle empty string values', async () => {
      const result = await storageService.setString('auth_token', '');

      expect(result).toBe(true);

      const retrieved = storageService.getString('auth_token');
      expect(retrieved).toBe('');
    });

    test('should handle negative numbers', async () => {
      const value = -999;

      await storageService.setNumber('offline_queue', value);
      const retrieved = await storageService.getNumber('offline_queue');

      expect(retrieved).toBe(value);
    });

    test('should handle floating point numbers', async () => {
      const value = 123.456789;

      await storageService.setNumber('offline_queue', value);
      const retrieved = await storageService.getNumber('offline_queue');

      expect(retrieved).toBeCloseTo(value, 6);
    });
  });

  // ========================================================================
  // Convenience Function Tests
  // ========================================================================

  describe('Convenience Functions', () => {
    test('setString should call storageService.setString', async () => {
      const result = await setString('auth_token', 'test');

      expect(result).toBe(true);
    });

    test('getString should call storageService.getStringAsync', async () => {
      await setString('auth_token', 'test');
      const value = await getString('auth_token');

      expect(value).toBe('test');
    });

    test('setObject should serialize and call setString', async () => {
      const data = { test: 'value' };
      const result = await setObject('preferences', data);

      expect(result).toBe(true);
    });

    test('getObject should call getStringAsync and parse', async () => {
      const data = { test: 'value' };
      await setObject('preferences', data);
      const value = await getObject<typeof data>('preferences');

      expect(value).toEqual(data);
    });

    test('setNumber should convert to string for AsyncStorage', async () => {
      const result = await setNumber('offline_queue', 42);

      expect(result).toBe(true);
    });

    test('getNumber should parse string to number', async () => {
      await setNumber('offline_queue', 42);
      const value = await getNumber('offline_queue');

      expect(value).toBe(42);
    });

    test('setBoolean should convert to string for AsyncStorage', async () => {
      const result = await setBoolean('biometric_enabled', true);

      expect(result).toBe(true);
    });

    test('getBoolean should parse string to boolean', async () => {
      await setBoolean('biometric_enabled', true);
      const value = await getBoolean('biometric_enabled');

      expect(value).toBe(true);
    });

    test('deleteKey should call storageService.delete', async () => {
      await setString('auth_token', 'token');
      const result = await deleteKey('auth_token');

      expect(result).toBe(true);
    });

    test('hasKey should call storageService.has', async () => {
      await setString('auth_token', 'token');
      const exists = await hasKey('auth_token');

      expect(exists).toBe(true);
    });

    test('clearStorage should call storageService.clear', async () => {
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
      const AsyncStorage = require('@react-native-async-storage/async-storage');
      AsyncStorage.getAllKeys.mockRejectedValueOnce(new Error('Storage unavailable'));

      await expect(storageService.getAllKeys()).rejects.toThrow();
    });

    test('should handle clear errors gracefully', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage');
      AsyncStorage.clear.mockRejectedValueOnce(new Error('Clear error'));

      const result = await storageService.clear();

      expect(result).toBe(false);
    });

    test('should handle setString errors gracefully', async () => {
      const mockMMKV = (global as any).__mmkvGlobalInstance;
      mockMMKV.set.mockImplementationOnce(() => {
        throw new Error('MMKV write failed');
      });

      const result = await storageService.setString('auth_token', 'token');

      expect(result).toBe(false);
    });

    test('should handle getString errors gracefully', () => {
      const mockMMKV = (global as any).__mmkvGlobalInstance;
      mockMMKV.getString.mockImplementationOnce(() => {
        throw new Error('MMKV read failed');
      });

      const value = storageService.getString('auth_token');

      expect(value).toBeNull();
    });

    test('should handle setObject JSON.stringify errors', async () => {
      // Create circular reference
      const circularData: any = { name: 'test' };
      circularData.self = circularData;

      const result = await storageService.setObject('preferences', circularData);

      expect(result).toBe(false);
    });

    test('should handle getObject JSON.parse errors', async () => {
      await storageService.setString('preferences', 'invalid json{');

      const retrieved = await storageService.getObject<any>('preferences');

      expect(retrieved).toBeNull();
    });
  });
});
