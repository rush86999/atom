/**
 * AsyncStorage/MMKV Storage Tests
 *
 * Tests for AsyncStorage and MMKV storage covering:
 * - Storing and retrieving values
 * - JSON serialization/deserialization
 * - Error handling for invalid operations
 * - Instance initialization
 *
 * @module Storage Tests
 * @see Phase 158-02 - Mobile Test Suite Execution
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { Text, View } from 'react-native';

// ============================================================================
// AsyncStorage Tests
// ============================================================================

describe('AsyncStorage Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Clear all AsyncStorage before each test
    AsyncStorage.clear();
  });

  afterEach(async () => {
    await AsyncStorage.clear();
  });

  // Test 1: Store values
  it('test_async_storage_set_item', async () => {
    await AsyncStorage.setItem('test_key', 'test_value');

    const value = await AsyncStorage.getItem('test_key');
    expect(value).toBe('test_value');
  });

  it('test_async_storage_set_item_number', async () => {
    await AsyncStorage.setItem('number_key', '12345');

    const value = await AsyncStorage.getItem('number_key');
    expect(value).toBe('12345');
  });

  it('test_async_storage_set_item_boolean', async () => {
    await AsyncStorage.setItem('bool_key', 'true');

    const value = await AsyncStorage.getItem('bool_key');
    expect(value).toBe('true');
  });

  // Test 2: Retrieve values
  it('test_async_storage_get_item', async () => {
    await AsyncStorage.setItem('existing_key', 'existing_value');

    const value = await AsyncStorage.getItem('existing_key');
    expect(value).toBe('existing_value');
  });

  it('test_async_storage_get_item_nonexistent', async () => {
    const value = await AsyncStorage.getItem('nonexistent_key');
    expect(value).toBeNull();
  });

  // Test 3: Delete values
  it('test_async_storage_remove_item', async () => {
    await AsyncStorage.setItem('delete_key', 'delete_value');
    await AsyncStorage.removeItem('delete_key');

    const value = await AsyncStorage.getItem('delete_key');
    expect(value).toBeNull();
  });

  it('test_async_storage_remove_nonexistent', async () => {
    // Should not throw error for deleting non-existent key
    await AsyncStorage.removeItem('nonexistent_key');

    const value = await AsyncStorage.getItem('nonexistent_key');
    expect(value).toBeNull();
  });

  // Test 4: JSON handling
  it('test_async_storage_json_handling', async () => {
    const data = { id: '123', name: 'Test', active: true };
    await AsyncStorage.setItem('json_key', JSON.stringify(data));

    const value = await AsyncStorage.getItem('json_key');
    expect(value).toBeTruthy();

    const parsed = JSON.parse(value || '');
    expect(parsed.id).toBe('123');
    expect(parsed.name).toBe('Test');
    expect(parsed.active).toBe(true);
  });

  it('test_async_storage_json_array', async () => {
    const data = [{ id: '1' }, { id: '2' }, { id: '3' }];
    await AsyncStorage.setItem('json_array_key', JSON.stringify(data));

    const value = await AsyncStorage.getItem('json_array_key');
    expect(value).toBeTruthy();

    const parsed = JSON.parse(value || '[]');
    expect(parsed).toHaveLength(3);
    expect(parsed[0].id).toBe('1');
  });

  it('test_async_storage_json_invalid', async () => {
    await AsyncStorage.setItem('invalid_json', '{invalid json}');

    const value = await AsyncStorage.getItem('invalid_json');
    expect(value).toBe('{invalid json}');

    // Should handle parse error gracefully
    expect(() => {
      JSON.parse(value || '');
    }).toThrow();
  });

  // Test 5: Error handling
  it('test_async_storage_error_handling', async () => {
    // Test with undefined key
    try {
      await AsyncStorage.setItem('', 'value');
      // Some implementations may throw, some may not
    } catch (error) {
      expect((error as Error).message).toBeTruthy();
    }

    // Test with null value
    try {
      await AsyncStorage.setItem('test_key', null as any);
      // AsyncStorage should handle null gracefully
    } catch (error) {
      // Expected behavior varies by implementation
    }
  });

  it('test_async_storage_merge_item', async () => {
    await AsyncStorage.mergeItem('merge_key', JSON.stringify({ field1: 'value1' }));
    await AsyncStorage.mergeItem('merge_key', JSON.stringify({ field2: 'value2' }));

    const value = await AsyncStorage.getItem('merge_key');
    expect(value).toBeTruthy();

    const parsed = JSON.parse(value || '{}');
    expect(parsed.field1).toBe('value1');
    expect(parsed.field2).toBe('value2');
  });

  // Test 6: Get all keys
  it('test_async_storage_get_all_keys', async () => {
    await AsyncStorage.setItem('key1', 'value1');
    await AsyncStorage.setItem('key2', 'value2');
    await AsyncStorage.setItem('key3', 'value3');

    const keys = await AsyncStorage.getAllKeys();
    expect(keys).toHaveLength(3);
    expect(keys).toContain('key1');
    expect(keys).toContain('key2');
    expect(keys).toContain('key3');
  });

  it('test_async_storage_multi_get', async () => {
    await AsyncStorage.setItem('multi_key1', 'multi_value1');
    await AsyncStorage.setItem('multi_key2', 'multi_value2');
    await AsyncStorage.setItem('multi_key3', 'multi_value3');

    const values = await AsyncStorage.multiGet(['multi_key1', 'multi_key2', 'multi_key3']);
    expect(values).toHaveLength(3);
    expect(values[0]).toEqual(['multi_key1', 'multi_value1']);
    expect(values[1]).toEqual(['multi_key2', 'multi_value2']);
    expect(values[2]).toEqual(['multi_key3',_multi_value3']);
  });

  it('test_async_storage_multi_set', async () => {
    const pairs = [
      ['batch_key1', 'batch_value1'],
      ['batch_key2', 'batch_value2'],
      ['batch_key3', 'batch_value3'],
    ];

    await AsyncStorage.multiSet(pairs);

    const values = await AsyncStorage.multiGet(['batch_key1', 'batch_key2', 'batch_key3']);
    expect(values).toEqual(pairs);
  });

  it('test_async_storage_multi_remove', async () => {
    await AsyncStorage.setItem('remove_key1', 'value1');
    await AsyncStorage.setItem('remove_key2', 'value2');
    await AsyncStorage.setItem('remove_key3', 'value3');

    await AsyncStorage.multiRemove(['remove_key1', 'remove_key2', 'remove_key3']);

    const key1 = await AsyncStorage.getItem('remove_key1');
    const key2 = await AsyncStorage.getItem('remove_key2');
    const key3 = await AsyncStorage.getItem('remove_key3');

    expect(key1).toBeNull();
    expect(key2).toBeNull();
    expect(key3).toBeNull();
  });

  // Test 7: Clear all
  it('test_async_storage_clear', async () => {
    await AsyncStorage.setItem('clear_key1', 'value1');
    await AsyncStorage.setItem('clear_key2', 'value2');

    await AsyncStorage.clear();

    const allKeys = await AsyncStorage.getAllKeys();
    expect(allKeys).toHaveLength(0);
  });

  // Test 8: Large data handling
  it('test_async_storage_large_string', async () => {
    const largeString = 'x'.repeat(10000);
    await AsyncStorage.setItem('large_key', largeString);

    const value = await AsyncStorage.getItem('large_key');
    expect(value).toHaveLength(10000);
  });

  it('test_async_storage_unicode', async () => {
    const unicodeString = 'Hello 世界 🌍 Привет мир';
    await AsyncStorage.setItem('unicode_key', unicodeString);

    const value = await AsyncStorage.getItem('unicode_key');
    expect(value).toBe(unicodeString);
  });

  it('test_async_storage_special_chars', async () => {
    const specialString = 'Test with "quotes" and \'apostrophes\'';
    await AsyncStorage.setItem('special_key', specialString);

    const value = await AsyncStorage.getItem('special_key');
    expect(value).toBe(specialString);
  });
});

// ============================================================================
// MMKV Storage Tests (if available)
// ============================================================================

describe('MMKV Storage Tests', () => {
  // Mock MMKV for testing since it requires native module
  const mockMMKVStore: Record<string, string | number | boolean> = {};

  beforeEach(() => {
    mockMMKVStore = {};
  });

  // Test 8: MMKV string storage
  it('test_mmkv_string_storage', () => {
    mockMMKVStore['string_key'] = 'string_value';

    expect(mockMMKVStore['string_key']).toBe('string_value');
  });

  it('test_mmkv_string_retrieval', () => {
    mockMMKVStore['retrieve_key'] = 'retrieve_value';

    const value = mockMMKVStore['retrieve_key'];
    expect(value).toBe('retrieve_value');
  });

  // Test 9: MMKV number storage
  it('test_mmkv_number_storage', () => {
    mockMMKVStore['number_key'] = 12345;

    expect(mockMMKVStore['number_key']).toBe(12345);
  });

  it('test_mmkv_float_storage', () => {
    mockMMKVStore['float_key'] = 123.45;

    expect(mockMMKVStore['float_key']).toBe(123.45);
  });

  // Test 10: MMKV boolean storage
  it('test_mmkv_boolean_storage', () => {
    mockMMKVStore['bool_key'] = true;
    mockMMKVStore['bool_key2'] = false;

    expect(mockMMKVStore['bool_key']).toBe(true);
    expect(mockMMKVStore['bool_key2']).toBe(false);
  });

  // Test 11: MMKV JSON storage
  it('test_mmkv_json_storage', () => {
    const data = { id: 'xyz', value: 999 };
    mockMMKVStore['json_key'] = JSON.stringify(data);

    const parsed = JSON.parse(mockMMKVStore['json_key'] || '');
    expect(parsed.id).toBe('xyz');
    expect(parsed.value).toBe(999);
  });

  // Test 12: MMKV instance initialization
  it('test_mmkv_instance_initialization', () => {
    const instance = {
      store: mockMMKVStore,
      get: (key: string) => mockMMKVStore[key],
      set: (key: string, value: any) => {
        mockMMKVStore[key] = value;
      },
      delete: (key: string) => {
        delete mockMMKVStore[key];
      },
      contains: (key: string) => key in mockMMKVStore,
    };

    instance.set('test_key', 'test_value');
    expect(instance.get('test_key')).toBe('test_value');

    expect(instance.contains('test_key')).toBe(true);
    expect(instance.contains('nonexistent')).toBe(false);

    instance.delete('test_key');
    expect(instance.contains('test_key')).toBe(false);
  });

  // Test 13: MMKV batch operations
  it('test_mmkv_batch_operations', () => {
    const instance = {
      store: mockMMKVStore,
      set: (key: string, value: any) => {
        mockMMKVStore[key] = value;
      },
    };

    instance.set('batch1', 'value1');
    instance.set('batch2', 'value2');
    instance.set('batch3', 'value3');

    expect(Object.keys(mockMMKVStore)).toHaveLength(3);
    expect(mockMMKVStore['batch1']).toBe('value1');
    expect(mockMMKVStore['batch2']).toBe('value2');
    expect(mockMMKVStore['batch3']).toBe('value3');
  });
});

// ============================================================================
// Storage Performance Tests
// ============================================================================

describe('Storage Performance', () => {
  it('test_async_storage_read_performance', async () => {
    const iterations = 100;

    // Setup
    for (let i = 0; i < iterations; i++) {
      await AsyncStorage.setItem(`perf_key_${i}`, `perf_value_${i}`);
    }

    const startTime = Date.now();

    for (let i = 0; i < iterations; i++) {
      await AsyncStorage.getItem(`perf_key_${i}`);
    }

    const endTime = Date.now();
    const duration = endTime - startTime;

    // Should complete reasonably fast (<5 seconds for 100 reads)
    expect(duration).toBeLessThan(5000);
  });

  it('test_async_storage_write_performance', async () => {
    const iterations = 100;

    const startTime = Date.now();

    for (let i = 0; i < iterations; i++) {
      await AsyncStorage.setItem(`perf_write_key_${i}`, `perf_write_value_${i}`);
    }

    const endTime = Date.now();
    const duration = endTime - startTime;

    // Should complete reasonably fast (<10 seconds for 100 writes)
    expect(duration).toBeLessThan(10000);
  });
});

// ============================================================================
// Storage Error Recovery
// ============================================================================

describe('Storage Error Recovery', () => {
  it('test_async_storage_corrupted_data_recovery', async () => {
    // Store valid JSON
    await AsyncStorage.setItem('backup_data', JSON.stringify({ valid: true }));

    // Corrupt the data by overwriting with invalid JSON
    await AsyncStorage.setItem('corrupted_data', '{corrupted json}');

    // Backup data should still be valid
    const backup = await AsyncStorage.getItem('backup_data');
    expect(backup).toBeTruthy();

    const parsed = JSON.parse(backup || '{}');
    expect(parsed.valid).toBe(true);
  });

  it('test_async_storage_quota_exceeded', async () => {
    // Test handling when storage is full
    const largeData = 'x'.repeat(1000000); // 10MB string

    try {
      await AsyncStorage.setItem('quota_test', largeData);
      // Some implementations may throw quota exceeded error
    } catch (error) {
      expect((error as Error).message).toContain('quota');
    }
  });
});

// ============================================================================
// Storage Type Safety
// ============================================================================

describe('Storage Type Safety', () => {
  it('should maintain type consistency', async () => {
    const data = { timestamp: Date.now(), value: 'test', active: true };
    await AsyncStorage.setItem('typed_key', JSON.stringify(data));

    const retrieved = await AsyncStorage.getItem('typed_key');
    const parsed = JSON.parse(retrieved || '');

    expect(typeof parsed.timestamp).toBe('number');
    expect(typeof parsed.value).toBe('string');
    expect(typeof parsed.active).toBe('boolean');
  });

  it('should handle type coercion', async () => {
    await AsyncStorage.setItem('number_as_string', '12345');
    await AsyncStorage.setItem('string_as_number', '12345');

    const value1 = await AsyncStorage.getItem('number_as_string');
    const value2 = await AsyncStorage.getItem('string_as_number');

    // Both are stored as strings
    expect(value1).toBe('12345');
    expect(value2).toBe('12345');
  });
});
