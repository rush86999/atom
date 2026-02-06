/**
 * Storage Service
 *
 * Fast local storage wrapper using MMKV for critical data and AsyncStorage for fallback.
 * Provides a unified interface for storing and retrieving data on mobile devices.
 *
 * MMKV Benefits:
 * - Synchronous (no async/await needed for reads)
 * - Extremely fast (1MB read in ~0.3ms)
 * - Efficient storage (smaller footprint than AsyncStorage)
 *
 * AsyncStorage Fallback:
 * - Used when MMKV is not available
 * - Good for less critical data
 */

import { MMKV } from 'react-native-mmkv';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Types
export type StorageKey =
  | 'auth_token'
  | 'refresh_token'
  | 'user_id'
  | 'device_id'
  | 'biometric_enabled'
  | 'offline_queue'
  | 'sync_state'
  | 'episode_cache'
  | 'canvas_cache'
  | 'preferences';

export interface StorageStats {
  mmkvSize: number;
  asyncStorageSize: number;
  totalItems: number;
}

// Initialize MMKV
const mmkv = new MMKV({
  id: 'atom-storage',
  encryptionKey: 'atom-encryption-key', // In production, get from secure storage
});

// Keys that should use MMKV (fast access, critical data)
const MMKV_KEYS: Set<StorageKey> = new Set([
  'auth_token',
  'refresh_token',
  'user_id',
  'device_id',
  'biometric_enabled',
  'offline_queue',
  'sync_state',
]);

// Keys that should use AsyncStorage (larger data, less critical)
const ASYNC_STORAGE_KEYS: Set<StorageKey> = new Set([
  'episode_cache',
  'canvas_cache',
  'preferences',
]);

/**
 * Storage Service Class
 */
class StorageService {
  /**
   * Store a string value
   */
  async setString(key: StorageKey, value: string): Promise<boolean> {
    try {
      if (MMKV_KEYS.has(key)) {
        mmkv.set(key, value);
        return true;
      } else {
        await AsyncStorage.setItem(key, value);
        return true;
      }
    } catch (error) {
      console.error(`StorageService: Failed to set ${key}:`, error);
      return false;
    }
  }

  /**
   * Get a string value
   */
  getString(key: StorageKey): string | null {
    try {
      if (MMKV_KEYS.has(key)) {
        return mmkv.getString(key);
      } else {
        // AsyncStorage is async, but we need sync here
        // Return null and use getStringAsync for async storage keys
        console.warn(`StorageService: Key ${key} is in AsyncStorage, use getStringAsync`);
        return null;
      }
    } catch (error) {
      console.error(`StorageService: Failed to get ${key}:`, error);
      return null;
    }
  }

  /**
   * Get a string value (async version for AsyncStorage keys)
   */
  async getStringAsync(key: StorageKey): Promise<string | null> {
    try {
      if (MMKV_KEYS.has(key)) {
        return mmkv.getString(key);
      } else {
        return await AsyncStorage.getItem(key);
      }
    } catch (error) {
      console.error(`StorageService: Failed to get ${key}:`, error);
      return null;
    }
  }

  /**
   * Store a JSON object
   */
  async setObject<T>(key: StorageKey, value: T): Promise<boolean> {
    try {
      const json = JSON.stringify(value);
      return await this.setString(key, json);
    } catch (error) {
      console.error(`StorageService: Failed to set object ${key}:`, error);
      return false;
    }
  }

  /**
   * Get a JSON object
   */
  async getObject<T>(key: StorageKey): Promise<T | null> {
    try {
      const json = await this.getStringAsync(key);
      return json ? JSON.parse(json) : null;
    } catch (error) {
      console.error(`StorageService: Failed to get object ${key}:`, error);
      return null;
    }
  }

  /**
   * Store a number value
   */
  async setNumber(key: StorageKey, value: number): Promise<boolean> {
    try {
      if (MMKV_KEYS.has(key)) {
        mmkv.set(key, value);
        return true;
      } else {
        return await this.setString(key, value.toString());
      }
    } catch (error) {
      console.error(`StorageService: Failed to set number ${key}:`, error);
      return false;
    }
  }

  /**
   * Get a number value
   */
  async getNumber(key: StorageKey): Promise<number | null> {
    try {
      if (MMKV_KEYS.has(key)) {
        return mmkv.getNumber(key);
      } else {
        const str = await this.getStringAsync(key);
        return str !== null ? parseFloat(str) : null;
      }
    } catch (error) {
      console.error(`StorageService: Failed to get number ${key}:`, error);
      return null;
    }
  }

  /**
   * Store a boolean value
   */
  async setBoolean(key: StorageKey, value: boolean): Promise<boolean> {
    try {
      if (MMKV_KEYS.has(key)) {
        mmkv.set(key, value);
        return true;
      } else {
        return await this.setString(key, value.toString());
      }
    } catch (error) {
      console.error(`StorageService: Failed to set boolean ${key}:`, error);
      return false;
    }
  }

  /**
   * Get a boolean value
   */
  async getBoolean(key: StorageKey): Promise<boolean | null> {
    try {
      if (MMKV_KEYS.has(key)) {
        return mmkv.getBoolean(key);
      } else {
        const str = await this.getStringAsync(key);
        return str !== null ? str === 'true' : null;
      }
    } catch (error) {
      console.error(`StorageService: Failed to get boolean ${key}:`, error);
      return null;
    }
  }

  /**
   * Delete a value
   */
  async delete(key: StorageKey): Promise<boolean> {
    try {
      if (MMKV_KEYS.has(key)) {
        mmkv.delete(key);
        return true;
      } else {
        await AsyncStorage.removeItem(key);
        return true;
      }
    } catch (error) {
      console.error(`StorageService: Failed to delete ${key}:`, error);
      return false;
    }
  }

  /**
   * Check if a key exists
   */
  async has(key: StorageKey): Promise<boolean> {
    try {
      if (MMKV_KEYS.has(key)) {
        return mmkv.contains(key);
      } else {
        const value = await AsyncStorage.getItem(key);
        return value !== null;
      }
    } catch (error) {
      console.error(`StorageService: Failed to check ${key}:`, error);
      return false;
    }
  }

  /**
   * Clear all storage
   */
  async clear(): Promise<boolean> {
    try {
      // Clear MMKV
      const keys = mmkv.getAllKeys();
      keys.forEach((key) => mmkv.delete(key));

      // Clear AsyncStorage
      await AsyncStorage.clear();

      return true;
    } catch (error) {
      console.error('StorageService: Failed to clear storage:', error);
      return false;
    }
  }

  /**
   * Get all keys
   */
  async getAllKeys(): Promise<string[]> {
    try {
      const mmkvKeys = mmkv.getAllKeys();
      const asyncKeys = await AsyncStorage.getAllKeys();
      return [...mmkvKeys, ...asyncKeys];
    } catch (error) {
      console.error('StorageService: Failed to get all keys:', error);
      throw new Error(
        error instanceof Error
          ? `Failed to retrieve storage keys: ${error.message}`
          : 'Storage system is unavailable'
      );
    }
  }

  /**
   * Get storage statistics
   */
  async getStats(): Promise<StorageStats> {
    try {
      const mmkvSize = mmkv.getSizeInBytes();
      const asyncKeys = await AsyncStorage.getAllKeys();
      let asyncStorageSize = 0;

      for (const key of asyncKeys) {
        const value = await AsyncStorage.getItem(key);
        if (value) {
          asyncStorageSize += key.length + value.length;
        }
      }

      return {
        mmkvSize,
        asyncStorageSize,
        totalItems: mmkv.getAllKeys().length + asyncKeys.length,
      };
    } catch (error) {
      console.error('StorageService: Failed to get stats:', error);
      return {
        mmkvSize: 0,
        asyncStorageSize: 0,
        totalItems: 0,
      };
    }
  }

  /**
   * Migrate data from AsyncStorage to MMKV
   */
  async migrateToMMKV(keys: StorageKey[]): Promise<{ success: number; failed: number }> {
    let success = 0;
    let failed = 0;

    for (const key of keys) {
      if (MMKV_KEYS.has(key)) {
        try {
          const value = await AsyncStorage.getItem(key);
          if (value !== null) {
            mmkv.set(key, value);
            await AsyncStorage.removeItem(key);
            success++;
          }
        } catch (error) {
          console.error(`StorageService: Failed to migrate ${key}:`, error);
          failed++;
        }
      }
    }

    return { success, failed };
  }
}

// Export singleton instance
export const storageService = new StorageService();

// Export convenience functions
export const setString = (key: StorageKey, value: string) => storageService.setString(key, value);
export const getString = (key: StorageKey) => storageService.getStringAsync(key);
export const setObject = <T>(key: StorageKey, value: T) => storageService.setObject(key, value);
export const getObject = <T>(key: StorageKey) => storageService.getObject(key);
export const setNumber = (key: StorageKey, value: number) => storageService.setNumber(key, value);
export const getNumber = (key: StorageKey) => storageService.getNumber(key);
export const setBoolean = (key: StorageKey, value: boolean) => storageService.setBoolean(key, value);
export const getBoolean = (key: StorageKey) => storageService.getBoolean(key);
export const deleteKey = (key: StorageKey) => storageService.delete(key);
export const hasKey = (key: StorageKey) => storageService.has(key);
export const clearStorage = () => storageService.clear();

export default storageService;
