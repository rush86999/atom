// Google API Caching Service
import { readTextFile, writeTextFile, exists, createDir } from '@tauri-apps/api/fs';
import { appCacheDir, join } from '@tauri-apps/api/path';
import type { GoogleEmail, GoogleCalendarEvent, GoogleDriveFile, GoogleConnectionStatus } from '../types/googleTypes';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  expiresAt: number;
  key: string;
  userId: string;
}

interface CacheConfig {
  defaultTTL: number; // Default time to live in seconds
  maxCacheSize: number; // Max cache size in MB
  cleanupInterval: number; // Cleanup interval in seconds
  compressionEnabled: boolean;
}

export class GoogleCacheManager {
  private static instance: GoogleCacheManager;
  private cacheDir: string = '';
  private config: CacheConfig;
  private cleanupTimer: NodeJS.Timeout | null = null;
  private memoryCache: Map<string, any> = new Map();

  private constructor() {
    this.config = {
      defaultTTL: 300, // 5 minutes
      maxCacheSize: 50, // 50MB
      cleanupInterval: 600, // 10 minutes
      compressionEnabled: true
    };
  }

  static getInstance(): GoogleCacheManager {
    if (!GoogleCacheManager.instance) {
      GoogleCacheManager.instance = new GoogleCacheManager();
    }
    return GoogleCacheManager.instance;
  }

  // Initialize cache manager
  async initialize(): Promise<void> {
    try {
      this.cacheDir = await appCacheDir();
      await createDir(this.cacheDir);
      
      // Start cleanup timer
      this.startCleanupTimer();
      
      // Perform initial cleanup
      await this.cleanup();
    } catch (error) {
      console.error('Failed to initialize Google cache:', error);
    }
  }

  // Generate cache key
  private generateCacheKey(userId: string, action: string, params: any): string {
    const paramString = JSON.stringify(params || {});
    const hash = this.simpleHash(`${userId}:${action}:${paramString}`);
    return `google_${userId}_${action}_${hash}`;
  }

  // Simple hash function
  private simpleHash(str: string): string {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash).toString(36);
  }

  // Get cached data
  async get<T>(userId: string, action: string, params: any = {}): Promise<T | null> {
    const key = this.generateCacheKey(userId, action, params);
    
    // Check memory cache first
    if (this.memoryCache.has(key)) {
      const entry: CacheEntry<T> = this.memoryCache.get(key);
      if (Date.now() < entry.expiresAt) {
        return entry.data;
      } else {
        this.memoryCache.delete(key);
      }
    }

    // Check file cache
    try {
      const cacheFile = await join(this.cacheDir, `${key}.json`);
      
      if (await exists(cacheFile)) {
        const cacheData = await readTextFile(cacheFile);
        const entry: CacheEntry<T> = JSON.parse(cacheData);
        
        if (Date.now() < entry.expiresAt) {
          // Store in memory cache for faster access
          this.memoryCache.set(key, entry);
          return entry.data;
        } else {
          // Remove expired file
          await this.deleteCacheFile(key);
        }
      }
    } catch (error) {
      console.warn(`Cache read error for key ${key}:`, error);
    }

    return null;
  }

  // Set cached data
  async set<T>(
    userId: string, 
    action: string, 
    data: T, 
    params: any = {},
    ttl?: number
  ): Promise<void> {
    const key = this.generateCacheKey(userId, action, params);
    const now = Date.now();
    const cacheTTL = ttl || this.config.defaultTTL;
    
    const entry: CacheEntry<T> = {
      data,
      timestamp: now,
      expiresAt: now + (cacheTTL * 1000),
      key,
      userId
    };

    // Store in memory cache
    this.memoryCache.set(key, entry);

    // Store in file cache
    try {
      const cacheFile = await join(this.cacheDir, `${key}.json`);
      const cacheData = JSON.stringify(entry);
      await writeTextFile(cacheFile, cacheData);
    } catch (error) {
      console.warn(`Cache write error for key ${key}:`, error);
    }
  }

  // Invalidate cache entries
  async invalidate(userId: string, action?: string, params?: any): Promise<void> {
    if (action && params) {
      // Invalidate specific entry
      const key = this.generateCacheKey(userId, action, params);
      await this.deleteCacheEntry(key);
    } else if (action) {
      // Invalidate all entries for action
      await this.invalidatePattern(userId, action);
    } else {
      // Invalidate all entries for user
      await this.invalidateUser(userId);
    }
  }

  // Delete specific cache entry
  private async deleteCacheEntry(key: string): Promise<void> {
    this.memoryCache.delete(key);
    await this.deleteCacheFile(key);
  }

  // Delete cache file
  private async deleteCacheFile(key: string): Promise<void> {
    try {
      const cacheFile = await join(this.cacheDir, `${key}.json`);
      if (await exists(cacheFile)) {
        // Tauri doesn't have a direct delete function, so we write empty content
        await writeTextFile(cacheFile, '');
      }
    } catch (error) {
      // Ignore deletion errors
    }
  }

  // Invalidate cache entries by pattern
  private async invalidatePattern(userId: string, action: string): Promise<void> {
    const pattern = `google_${userId}_${action}_`;
    
    // Remove from memory cache
    for (const key of this.memoryCache.keys()) {
      if (key.startsWith(pattern)) {
        this.memoryCache.delete(key);
      }
    }

    // Remove from file cache
    // Note: Tauri doesn't provide directory listing, so we'd need to track keys
    // For now, we'll skip file invalidation by pattern
  }

  // Invalidate all entries for user
  private async invalidateUser(userId: string): Promise<void> {
    const pattern = `google_${userId}_`;
    
    // Remove from memory cache
    for (const key of this.memoryCache.keys()) {
      if (key.startsWith(pattern)) {
        this.memoryCache.delete(key);
      }
    }

    // Remove from file cache
    // Note: Tauri doesn't provide directory listing, so we'd need to track keys
    // For now, we'll skip file invalidation by user
  }

  // Cleanup expired cache entries
  async cleanup(): Promise<void> {
    const now = Date.now();
    const expiredKeys: string[] = [];

    // Check memory cache
    for (const [key, entry] of this.memoryCache.entries()) {
      if (now >= entry.expiresAt) {
        expiredKeys.push(key);
      }
    }

    // Remove expired entries from memory
    for (const key of expiredKeys) {
      this.memoryCache.delete(key);
    }

    // Note: File cache cleanup would require directory listing
    // For Tauri, we'd need to maintain a separate cache index
  }

  // Start cleanup timer
  private startCleanupTimer(): void {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
    }

    this.cleanupTimer = setInterval(() => {
      this.cleanup();
    }, this.config.cleanupInterval * 1000);
  }

  // Stop cleanup timer
  stopCleanupTimer(): void {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
      this.cleanupTimer = null;
    }
  }

  // Get cache statistics
  async getStats(userId: string): Promise<{
    memoryEntries: number;
    totalCacheSize: number;
    lastCleanup: number;
  }> {
    const pattern = `google_${userId}_`;
    let memoryEntries = 0;

    for (const key of this.memoryCache.keys()) {
      if (key.startsWith(pattern)) {
        memoryEntries++;
      }
    }

    return {
      memoryEntries,
      totalCacheSize: 0, // Would need to calculate from file sizes
      lastCleanup: Date.now()
    };
  }

  // Configure cache settings
  updateConfig(config: Partial<CacheConfig>): void {
    this.config = { ...this.config, ...config };
  }

  // Export cache data
  async exportCache(userId: string): Promise<string> {
    const pattern = `google_${userId}_`;
    const exportData: any = {};

    for (const [key, entry] of this.memoryCache.entries()) {
      if (key.startsWith(pattern)) {
        exportData[key] = entry;
      }
    }

    return JSON.stringify(exportData, null, 2);
  }

  // Import cache data
  async importCache(data: string): Promise<void> {
    try {
      const importData = JSON.parse(data);
      
      for (const [key, entry] of Object.entries(importData)) {
        const cacheEntry = entry as CacheEntry<any>;
        
        // Only import non-expired entries
        if (Date.now() < cacheEntry.expiresAt) {
          this.memoryCache.set(key, cacheEntry);
        }
      }
    } catch (error) {
      console.error('Failed to import cache data:', error);
    }
  }

  // Clear all cache
  async clear(): Promise<void> {
    this.memoryCache.clear();
    
    // Note: Clearing file cache would require directory listing
    // For now, we'll stop the cleanup timer
    this.stopCleanupTimer();
  }
}

// Export singleton instance
export const googleCache = GoogleCacheManager.getInstance();

// Cache decorators for API calls
export function cached(ttl?: number) {
  return function (target: any, propertyName: string, descriptor: PropertyDescriptor) {
    const method = descriptor.value;

    descriptor.value = async function (...args: any[]) {
      const userId = args[0]; // First argument is typically userId
      const action = propertyName;
      const params = args.slice(1); // Rest of the arguments

      // Try to get from cache first
      const cachedResult = await googleCache.get(userId, action, params);
      if (cachedResult !== null) {
        return cachedResult;
      }

      // Execute the original method
      const result = await method.apply(this, args);

      // Cache the result
      await googleCache.set(userId, action, result, params, ttl);

      return result;
    };

    return descriptor;
  };
}

// Predefined cache configurations for different data types
export const CACHE_TTL = {
  EMAIL_LIST: 60, // 1 minute - emails change frequently
  EMAIL_CONTENT: 300, // 5 minutes - email content is stable
  CALENDAR_EVENTS: 120, // 2 minutes - calendar events can change
  CALENDAR_LIST: 3600, // 1 hour - calendars don't change often
  DRIVE_FILES: 180, // 3 minutes - file list can change
  DRIVE_METADATA: 600, // 10 minutes - file metadata is stable
  USER_INFO: 3600, // 1 hour - user info doesn't change often
  CONNECTION_STATUS: 30, // 30 seconds - connection status is volatile
};

// Export types
export type { CacheConfig, CacheEntry };