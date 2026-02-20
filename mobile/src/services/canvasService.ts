/**
 * Canvas Service
 *
 * Service for managing canvas data with offline caching support.
 * Features cache expiration, LRU eviction, and progressive loading.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { NetInfo } from '@react-native-community/netinfo';

interface CachedCanvas {
  canvasId: string;
  data: any;
  metadata: CanvasMetadata;
  cachedAt: number;
  expiresAt: number;
  size: number;
}

interface CanvasMetadata {
  id: string;
  title: string;
  type: string;
  agent_name: string;
  agent_id: string;
  governance_level: string;
  created_at: string;
  updated_at: string;
  version: number;
  component_count: number;
}

interface CacheStats {
  totalSize: number;
  canvasCount: number;
  oldestCache: number;
  newestCache: number;
}

const CACHE_PREFIX = '@atom_canvas_cache_';
const CACHE_INDEX_KEY = '@atom_canvas_index';
const CACHE_STATS_KEY = '@atom_canvas_stats';

// Cache configuration
const CACHE_EXPIRATION_MS = 24 * 60 * 60 * 1000; // 24 hours
const MAX_CACHE_SIZE = 50 * 1024 * 1024; // 50 MB
const CACHE_CHECK_INTERVAL = 60 * 60 * 1000; // 1 hour

/**
 * Canvas Service
 *
 * Manages canvas data loading with offline caching.
 */
export class CanvasService {
  private cacheIndex: Set<string> = new Set();
  private cacheStats: CacheStats = {
    totalSize: 0,
    canvasCount: 0,
    oldestCache: Date.now(),
    newestCache: 0,
  };
  private initialized = false;

  /**
   * Initialize service
   */
  async init(): Promise<void> {
    if (this.initialized) return;

    try {
      await this.loadCacheIndex();
      await this.loadCacheStats();
      await this.cleanupExpiredCache();
      this.initialized = true;
    } catch (error) {
      console.error('Failed to initialize CanvasService:', error);
    }
  }

  /**
   * Load canvas with cache support
   */
  async loadCanvas(canvasId: string, fetchFn: () => Promise<any>): Promise<{
    data: any;
    fromCache: boolean;
  }> {
    await this.init();

    const netInfo = await NetInfo.fetch();
    const isOnline = netInfo.isConnected ?? true;

    // Try cache first (progressive loading)
    const cached = await this.getCachedCanvas(canvasId);
    if (cached) {
      // If online, refresh in background
      if (isOnline) {
        this.refreshCanvas(canvasId, fetchFn).catch(error => {
          console.error('Background refresh failed:', error);
        });
      }

      return { data: cached, fromCache: true };
    }

    // If offline and no cache, throw
    if (!isOnline) {
      throw new Error('No internet connection and no cached version available');
    }

    // Fetch from network
    const data = await fetchFn();
    await this.cacheCanvas(canvasId, data);

    return { data, fromCache: false };
  }

  /**
   * Get cached canvas
   */
  async getCachedCanvas(canvasId: string): Promise<CachedCanvas | null> {
    try {
      const key = CACHE_PREFIX + canvasId;
      const data = await AsyncStorage.getItem(key);

      if (!data) return null;

      const cached: CachedCanvas = JSON.parse(data);

      // Check expiration
      if (Date.now() > cached.expiresAt) {
        await this.removeCachedCanvas(canvasId);
        return null;
      }

      return cached;
    } catch (error) {
      console.error('Failed to get cached canvas:', error);
      return null;
    }
  }

  /**
   * Cache canvas data
   */
  async cacheCanvas(canvasId: string, data: any): Promise<void> {
    try {
      // Check cache size
      if (this.cacheStats.totalSize >= MAX_CACHE_SIZE) {
        await this.evictLRU();
      }

      const cached: CachedCanvas = {
        canvasId,
        data,
        metadata: data.metadata || {},
        cachedAt: Date.now(),
        expiresAt: Date.now() + CACHE_EXPIRATION_MS,
        size: JSON.stringify(data).length,
      };

      const key = CACHE_PREFIX + canvasId;
      const serialized = JSON.stringify(cached);

      await AsyncStorage.setItem(key, serialized);
      this.cacheIndex.add(canvasId);
      this.updateCacheStats(cached.size, true);

      // Save index and stats
      await this.saveCacheIndex();
      await this.saveCacheStats();
    } catch (error) {
      console.error('Failed to cache canvas:', error);
    }
  }

  /**
   * Remove cached canvas
   */
  async removeCachedCanvas(canvasId: string): Promise<void> {
    try {
      const key = CACHE_PREFIX + canvasId;
      const data = await AsyncStorage.getItem(key);

      if (data) {
        const cached: CachedCanvas = JSON.parse(data);
        this.updateCacheStats(cached.size, false);
      }

      await AsyncStorage.removeItem(key);
      this.cacheIndex.delete(canvasId);

      await this.saveCacheIndex();
      await this.saveCacheStats();
    } catch (error) {
      console.error('Failed to remove cached canvas:', error);
    }
  }

  /**
   * Refresh canvas (update cache)
   */
  async refreshCanvas(canvasId: string, fetchFn: () => Promise<any>): Promise<void> {
    try {
      const data = await fetchFn();
      await this.cacheCanvas(canvasId, data);
    } catch (error) {
      console.error('Failed to refresh canvas:', error);
      throw error;
    }
  }

  /**
   * Clear all cache
   */
  async clearCache(): Promise<void> {
    try {
      const keys = await AsyncStorage.getAllKeys();
      const canvasKeys = keys.filter(key => key.startsWith(CACHE_PREFIX));

      await AsyncStorage.multiRemove(canvasKeys);
      this.cacheIndex.clear();
      this.cacheStats = {
        totalSize: 0,
        canvasCount: 0,
        oldestCache: Date.now(),
        newestCache: 0,
      };

      await this.saveCacheIndex();
      await this.saveCacheStats();
    } catch (error) {
      console.error('Failed to clear cache:', error);
      throw error;
    }
  }

  /**
   * Get cache statistics
   */
  getCacheStats(): CacheStats {
    return { ...this.cacheStats };
  }

  /**
   * Evict least recently used canvas
   */
  private async evictLRU(): Promise<void> {
    try {
      let oldestCanvasId: string | null = null;
      let oldestTimestamp = Infinity;

      for (const canvasId of this.cacheIndex) {
        const key = CACHE_PREFIX + canvasId;
        const data = await AsyncStorage.getItem(key);

        if (data) {
          const cached: CachedCanvas = JSON.parse(data);
          if (cached.cachedAt < oldestTimestamp) {
            oldestTimestamp = cached.cachedAt;
            oldestCanvasId = canvasId;
          }
        }
      }

      if (oldestCanvasId) {
        await this.removeCachedCanvas(oldestCanvasId);
        console.log('Evicted LRU canvas:', oldestCanvasId);
      }
    } catch (error) {
      console.error('Failed to evict LRU:', error);
    }
  }

  /**
   * Cleanup expired cache
   */
  private async cleanupExpiredCache(): Promise<void> {
    try {
      const now = Date.now();
      const expiredCanvasIds: string[] = [];

      for (const canvasId of this.cacheIndex) {
        const key = CACHE_PREFIX + canvasId;
        const data = await AsyncStorage.getItem(key);

        if (data) {
          const cached: CachedCanvas = JSON.parse(data);
          if (now > cached.expiresAt) {
            expiredCanvasIds.push(canvasId);
          }
        }
      }

      for (const canvasId of expiredCanvasIds) {
        await this.removeCachedCanvas(canvasId);
      }

      if (expiredCanvasIds.length > 0) {
        console.log(`Cleaned up ${expiredCanvasIds.length} expired caches`);
      }
    } catch (error) {
      console.error('Failed to cleanup expired cache:', error);
    }
  }

  /**
   * Load cache index from storage
   */
  private async loadCacheIndex(): Promise<void> {
    try {
      const data = await AsyncStorage.getItem(CACHE_INDEX_KEY);
      if (data) {
        const index = JSON.parse(data);
        this.cacheIndex = new Set(index);
      }
    } catch (error) {
      console.error('Failed to load cache index:', error);
    }
  }

  /**
   * Save cache index to storage
   */
  private async saveCacheIndex(): Promise<void> {
    try {
      const index = Array.from(this.cacheIndex);
      await AsyncStorage.setItem(CACHE_INDEX_KEY, JSON.stringify(index));
    } catch (error) {
      console.error('Failed to save cache index:', error);
    }
  }

  /**
   * Load cache stats from storage
   */
  private async loadCacheStats(): Promise<void> {
    try {
      const data = await AsyncStorage.getItem(CACHE_STATS_KEY);
      if (data) {
        this.cacheStats = JSON.parse(data);
      }
    } catch (error) {
      console.error('Failed to load cache stats:', error);
    }
  }

  /**
   * Save cache stats to storage
   */
  private async saveCacheStats(): Promise<void> {
    try {
      await AsyncStorage.setItem(CACHE_STATS_KEY, JSON.stringify(this.cacheStats));
    } catch (error) {
      console.error('Failed to save cache stats:', error);
    }
  }

  /**
   * Update cache stats
   */
  private updateCacheStats(size: number, isAdd: boolean): void {
    if (isAdd) {
      this.cacheStats.totalSize += size;
      this.cacheStats.canvasCount += 1;
      this.cacheStats.newestCache = Date.now();
      if (this.cacheStats.canvasCount === 1) {
        this.cacheStats.oldestCache = Date.now();
      }
    } else {
      this.cacheStats.totalSize -= size;
      this.cacheStats.canvasCount -= 1;
    }
  }
}

// Singleton instance
export const canvasService = new CanvasService();

// Initialize on import
canvasService.init().catch(error => {
  console.error('Failed to initialize canvas service:', error);
});
