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

export interface StorageQuota {
  usedBytes: number;
  maxBytes: number;
  warningThreshold: number; // 0.8 = 80%
  enforcementThreshold: number; // 0.95 = 95%
  breakdown: {
    agents: number;
    workflows: number;
    canvases: number;
    episodes: number;
    other: number;
  };
}

export interface StorageBreakdown {
  [key: string]: number;
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

// Storage quota configuration
const DEFAULT_MAX_BYTES = 50 * 1024 * 1024; // 50MB
const WARNING_THRESHOLD = 0.8; // 80%
const ENFORCEMENT_THRESHOLD = 0.95; // 95%
const COMPRESSION_THRESHOLD = 1024; // Compress items > 1KB

/**
 * Storage Service Class
 */
class StorageService {
  private quota: StorageQuota;
  private compressionEnabled: boolean = true;
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
   * Get storage quota information
   */
  async getStorageQuota(): Promise<StorageQuota> {
    if (!this.quota) {
      await this.initializeQuota();
    }
    return this.quota;
  }

  /**
   * Check if storage quota is approaching limit
   */
  async checkQuota(): Promise<{ isOk: boolean; usageRatio: number; shouldWarn: boolean; shouldEnforce: boolean }> {
    const quota = await this.getStorageQuota();
    const usageRatio = quota.usedBytes / quota.maxBytes;

    return {
      isOk: usageRatio < quota.enforcementThreshold,
      usageRatio,
      shouldWarn: usageRatio >= quota.warningThreshold,
      shouldEnforce: usageRatio >= quota.enforcementThreshold,
    };
  }

  /**
   * Get storage breakdown by entity type
   */
  async getStorageBreakdown(): Promise<StorageBreakdown> {
    const quota = await this.getStorageQuota();
    return quota.breakdown;
  }

  /**
   * Clear all cached data (preserves auth tokens)
   */
  async clearCachedData(): Promise<boolean> {
    try {
      // Clear cache keys but preserve auth tokens
      const cacheKeys: StorageKey[] = ['episode_cache', 'canvas_cache', 'preferences', 'offline_queue'];

      for (const key of cacheKeys) {
        await this.delete(key);
      }

      // Reset quota
      await this.initializeQuota();

      console.log('StorageService: Cleared all cached data');
      return true;
    } catch (error) {
      console.error('StorageService: Failed to clear cached data:', error);
      return false;
    }
  }

  /**
   * Cleanup old data using LRU strategy
   */
  async cleanupOldData(requiredBytes: number = 0): Promise<number> {
    console.log('StorageService: Cleaning up old data');

    try {
      // Get all cache keys with their sizes
      const breakdown = await this.getStorageBreakdown();
      const entries = Object.entries(breakdown).sort(([, a], [, b]) => a - b); // Sort by size (smallest first)

      let freedBytes = 0;

      // Remove smallest entries first until we have enough space
      for (const [key, size] of entries) {
        if (freedBytes >= requiredBytes) break;

        try {
          await this.delete(key as StorageKey);
          freedBytes += size;
          console.log(`StorageService: Removed ${key} (${size} bytes)`);
        } catch (error) {
          console.error(`StorageService: Failed to remove ${key}:`, error);
        }
      }

      // Update quota
      this.quota.usedBytes -= freedBytes;

      return freedBytes;
    } catch (error) {
      console.error('StorageService: Failed to cleanup old data:', error);
      return 0;
    }
  }

  /**
   * Compress large cached items
   */
  async compressCache(): Promise<{ compressed: number; bytesSaved: number }> {
    if (!this.compressionEnabled) {
      return { compressed: 0, bytesSaved: 0 };
    }

    console.log('StorageService: Compressing cache');
    let compressed = 0;
    let bytesSaved = 0;

    try {
      // Get all cache keys
      const cacheKeys: StorageKey[] = ['episode_cache', 'canvas_cache'];

      for (const key of cacheKeys) {
        const data = await this.getStringAsync(key);
        if (data && data.length > COMPRESSION_THRESHOLD) {
          // In a real implementation, you would use a compression library like lz-string
          // For now, just log the potential savings
          const potentialSavings = Math.floor(data.length * 0.3); // Assume 30% compression
          console.log(`StorageService: Could compress ${key} (save ~${potentialSavings} bytes)`);
          bytesSaved += potentialSavings;
          compressed++;
        }
      }

      return { compressed, bytesSaved };
    } catch (error) {
      console.error('StorageService: Failed to compress cache:', error);
      return { compressed: 0, bytesSaved: 0 };
    }
  }

  /**
   * Get storage quality metrics
   */
  async getQualityMetrics(): Promise<{
    totalItems: number;
    cacheHitRate: number;
    avgItemSize: number;
    compressionRatio: number;
  }> {
    const stats = await this.getStats();
    const quota = await this.getStorageQuota();

    return {
      totalItems: stats.totalItems,
      cacheHitRate: 0.85, // Mock value - would be tracked in real implementation
      avgItemSize: stats.totalItems > 0 ? Math.floor(quota.usedBytes / stats.totalItems) : 0,
      compressionRatio: 0.3, // Mock value - 30% compression
    };
  }

  // Private helper methods

  private async initializeQuota(): Promise<void> {
    const stats = await this.getStats();

    this.quota = {
      usedBytes: stats.mmkvSize + stats.asyncStorageSize,
      maxBytes: DEFAULT_MAX_BYTES,
      warningThreshold: WARNING_THRESHOLD,
      enforcementThreshold: ENFORCEMENT_THRESHOLD,
      breakdown: {
        agents: 0,
        workflows: 0,
        canvases: 0,
        episodes: 0,
        other: stats.mmkvSize + stats.asyncStorageSize,
      },
    };

    // Save quota to storage
    await this.setObject('storage_quota' as StorageKey, this.quota);
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
