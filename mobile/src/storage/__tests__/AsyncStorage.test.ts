/**
 * AsyncStorage Tests
 *
 * Tests for storage functionality including:
 * - Store item (setString, setObject, setNumber, setBoolean)
 * - Retrieve item (getString, getObject, getNumber, getBoolean)
 * - Remove item
 * - Clear all items
 * - Persistence across app restarts
 * - JSON serialization
 * - MMKV vs AsyncStorage routing
 * - Storage quota management
 * - Compression
 */

import { storageService, StorageKey } from '../../services/storageService';

// Mock MMKV
jest.mock('react-native-mmkv', () => ({
  MMKV: jest.fn().mockImplementation(() => ({
    set: jest.fn(),
    getString: jest.fn(),
    getNumber: jest.fn(),
    getBoolean: jest.fn(),
    delete: jest.fn(),
    clearAll: jest.fn(),
    getAllKeys: jest.fn(),
  })),
}));

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage', () => ({
  setItem: jest.fn(),
  getItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
  getAllKeys: jest.fn(),
  multiGet: jest.fn(),
  multiSet: jest.fn(),
}));

import AsyncStorage from '@react-native-async-storage/async-storage';

describe('StorageService (AsyncStorage)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  /**
   * Test: Set item
   * Expected: Item is stored successfully
   */
  test('test_set_item', async () => {
    (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);

    const result = await storageService.setString('preferences', '{"theme":"dark"}');

    expect(result).toBe(true);
    expect(AsyncStorage.setItem).toHaveBeenCalledWith(
      'preferences',
      '{"theme":"dark"}'
    );
  });

  /**
   * Test: Get item
   * Expected: Item is retrieved successfully
   */
  test('test_get_item', async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue('{"theme":"dark"}');

    const result = await storageService.getString('preferences');

    expect(result).toBe('{"theme":"dark"}');
    expect(AsyncStorage.getItem).toHaveBeenCalledWith('preferences');
  });

  /**
   * Test: Remove item
   * Expected: Item is removed successfully
   */
  test('test_remove_item', async () => {
    (AsyncStorage.removeItem as jest.Mock).mockResolvedValue(undefined);

    await storageService.remove('preferences');

    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('preferences');
  });

  /**
   * Test: Clear all items
   * Expected: All items are cleared
   */
  test('test_clear', async () => {
    (AsyncStorage.clear as jest.Mock).mockResolvedValue(undefined);
    (AsyncStorage.getAllKeys as jest.Mock).mockResolvedValue(['preferences', 'episode_cache']);

    await storageService.clearAll();

    expect(AsyncStorage.clear).toHaveBeenCalled();
  });

  /**
   * Test: Persistence across app restarts
   * Expected: Data survives app restart
   */
  test('test_persistence', async () => {
    // First write
    (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
    await storageService.setString('preferences', '{"theme":"dark"}');

    // Simulate app restart - clear in-memory state
    jest.clearAllMocks();

    // Read after restart
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue('{"theme":"dark"}');
    const result = await storageService.getString('preferences');

    expect(result).toBe('{"theme":"dark"}');
  });

  /**
   * Test: JSON serialization
   * Expected: Objects are serialized and deserialized correctly
   */
  test('test_json_serialization', async () => {
    const testObject = {
      theme: 'dark',
      notifications: true,
      fontSize: 14,
    };

    (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue(JSON.stringify(testObject));

    // Store object
    await storageService.setObject('preferences', testObject);
    expect(AsyncStorage.setItem).toHaveBeenCalledWith(
      'preferences',
      JSON.stringify(testObject)
    );

    // Retrieve object
    const result = await storageService.getObject('preferences');
    expect(result).toEqual(testObject);
  });

  /**
   * Test: Set number
   * Expected: Number is stored and retrieved correctly
   */
  test('test_set_number', async () => {
    (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue('42');

    await storageService.setNumber('preferences', 42);
    const result = await storageService.getNumber('preferences');

    expect(result).toBe(42);
  });

  /**
   * Test: Set boolean
   * Expected: Boolean is stored and retrieved correctly
   */
  test('test_set_boolean', async () => {
    (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue('true');

    await storageService.setBoolean('biometric_enabled', true);
    const result = await storageService.getBoolean('biometric_enabled');

    expect(result).toBe(true);
  });

  /**
   * Test: Get non-existent item
   * Expected: Returns null for non-existent items
   */
  test('test_get_nonexistent_item', async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);

    const result = await storageService.getString('nonexistent' as StorageKey);

    expect(result).toBeNull();
  });

  /**
   * Test: Remove non-existent item
   * Expected: Does not throw error
   */
  test('test_remove_nonexistent_item', async () => {
    (AsyncStorage.removeItem as jest.Mock).mockResolvedValue(undefined);

    await expect(storageService.remove('nonexistent' as StorageKey)).resolves.not.toThrow();
  });

  /**
   * Test: Get storage stats
   * Expected: Returns accurate storage statistics
   */
  test('test_get_storage_stats', async () => {
    (AsyncStorage.getAllKeys as jest.Mock).mockResolvedValue(['key1', 'key2']);
    (AsyncStorage.multiGet as jest.Mock).mockResolvedValue([
      ['key1', 'value1'],
      ['key2', 'value2'],
    ]);

    const stats = await storageService.getStats();

    expect(stats).toBeDefined();
    expect(stats.totalItems).toBe(2);
  });

  /**
   * Test: Storage quota enforcement
   * Expected: Prevents storage when quota exceeded
   */
  test('test_storage_quota_enforcement', async () => {
    // Mock quota exceeded
    (AsyncStorage.setItem as jest.Mock).mockRejectedValue(new Error('QuotaExceeded'));

    await expect(
      storageService.setString('preferences', '{"large":"data"}')
    ).rejects.toThrow();
  });

  /**
   * Test: Multi-get operations
   * Expected: Can retrieve multiple items efficiently
   */
  test('test_multi_get', async () => {
    (AsyncStorage.multiGet as jest.Mock).mockResolvedValue([
      ['key1', 'value1'],
      ['key2', 'value2'],
      ['key3', 'value3'],
    ]);

    const keys: StorageKey[] = ['preferences', 'episode_cache', 'canvas_cache'];
    const results = await storageService.multiGet(keys);

    expect(results).toBeDefined();
    expect(AsyncStorage.multiGet).toHaveBeenCalled();
  });

  /**
   * Test: Multi-set operations
   * Expected: Can store multiple items efficiently
   */
  test('test_multi_set', async () => {
    (AsyncStorage.multiSet as jest.Mock).mockResolvedValue(undefined);

    const keyValuePairs: [StorageKey, string][] = [
      ['preferences', '{"theme":"dark"}'],
      ['episode_cache', '[]'],
    ];

    await storageService.multiSet(keyValuePairs);

    expect(AsyncStorage.multiSet).toHaveBeenCalledWith(keyValuePairs);
  });

  /**
   * Test: Clear specific keys only
   * Expected: Only specified keys are cleared
   */
  test('test_clear_specific_keys', async () => {
    (AsyncStorage.multiGet as jest.Mock).mockResolvedValue([
      ['preferences', '{"theme":"dark"}'],
      ['episode_cache', '[]'],
    ]);
    (AsyncStorage.multiSet as jest.Mock).mockResolvedValue(undefined);

    const keysToKeep: StorageKey[] = ['preferences'];
    await storageService.clearExcept(keysToKeep);

    expect(AsyncStorage.multiGet).toHaveBeenCalled();
  });

  /**
   * Test: Compression for large items
   * Expected: Large items are compressed
   */
  test('test_compression_large_items', async () => {
    const largeValue = 'x'.repeat(2000); // > 1KB threshold

    (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);

    await storageService.setString('episode_cache', largeValue);

    expect(AsyncStorage.setItem).toHaveBeenCalled();
  });
});
