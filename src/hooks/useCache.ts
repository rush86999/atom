import { useState, useEffect, useCallback, useRef } from 'react';
import lzString from 'lz-string';
import { Timer } from '../utils/timer';

// Cache interfaces and class
interface CacheOptions {
  ttl?: number;
  backgroundRefresh?: boolean;
}

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

class Cache {
  private cache: Map<string, CacheEntry<any>> = new Map();
  public hits: number = 0;
  public misses: number = 0;

  constructor(private options: { enablePersistence?: boolean } = {}) {
    if (this.options.enablePersistence) {
      this.loadFromPersistence();
    }
  }

  get<T>(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) {
      this.misses++;
      return null;
    }

    if (Date.now() - entry.timestamp > entry.ttl) {
      this.cache.delete(key);
      this.misses++;
      return null;
    }

    this.hits++;
    return entry.data;
  }

  set<T>(key: string, data: T, ttl: number = 300000): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl,
    });

    if (this.options.enablePersistence) {
      try {
        const compressedData = lzString.compressToUTF16(JSON.stringify({
          data,
          timestamp: Date.now(),
          ttl,
        }));
        localStorage.setItem(`cache_${key}`, compressedData);
      } catch (e) {
        console.warn('Failed to persist cache entry:', e);
      }
    }
  }

  delete(key: string): void {
    this.cache.delete(key);
    if (this.options.enablePersistence) {
      try {
        localStorage.removeItem(`cache_${key}`);
      } catch (e) {
        console.warn('Failed to remove persisted cache entry:', e);
      }
    }
  }

  clear(): void {
    this.cache.clear();
    if (this.options.enablePersistence) {
      try {
        Object.keys(localStorage).forEach(key => {
          if (key.startsWith('cache_')) {
            localStorage.removeItem(key);
          }
        });
      } catch (e) {
        console.warn('Failed to clear persisted cache:', e);
      }
    }
  }

  size(): number {
    return this.cache.size;
  }

  prefetch<T>(key: string, fetcher: () => Promise<T>): void {
    // Prefetch data in the background
    fetcher().then(data => {
      this.set(key, data);
    }).catch(err => {
      console.warn('Prefetch failed:', err);
    });
  }

  private loadFromPersistence(): void {
    try {
      Object.keys(localStorage).forEach(key => {
        if (key.startsWith('cache_')) {
          const compressedData = localStorage.getItem(key);
          if (compressedData) {
            const decompressedData = lzString.decompressFromUTF16(compressedData);
            if (decompressedData) {
              const entry = JSON.parse(decompressedData);
              if (Date.now() - entry.timestamp < entry.ttl) {
                this.cache.set(key.replace('cache_', ''), entry);
              } else {
                localStorage.removeItem(key);
              }
            }
          }
        }
      });
    } catch (e) {
      console.warn('Failed to load persisted cache:', e);
    }
  }
}

// Global cache instance
const globalCache = new Cache({
  enablePersistence: true,
});

const backgroundRefreshTimers = new Map<string, Timer>();

export const useCache = <T>(
  key: string,
  fetcher: () => Promise<T>,
  options: CacheOptions & {
    enabled?: boolean;
    refetchOnWindowFocus?: boolean;
    refetchInterval?: number;
    optimisticUpdate?: (currentData: T | null) => T;
    initialData?: T;
  } = {}
) => {
  const {
    enabled = true,
    refetchOnWindowFocus = false,
    refetchInterval,
    optimisticUpdate,
    initialData,
    ...cacheOptions
  } = options;

  const [data, setData] = useState<T | null>(initialData || null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isStale, setIsStale] = useState(false);

  const fetchRef = useRef(fetcher);
  const intervalRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const mountedRef = useRef(true);
  const previousDataRef = useRef<T | null>(null);
  const initializedRef = useRef(false);

  // Update fetcher ref when it changes
  useEffect(() => {
    fetchRef.current = fetcher;
  }, [fetcher]);

  const fetchData = useCallback(async (force = false) => {
    if (!enabled || !mountedRef.current) return;

    let startTime = 0;
    try {
      startTime = performance.now();
    } catch (e) {
      console.warn('Performance monitoring not available:', e);
    }

    // Store previous data for potential reversion
    previousDataRef.current = data;

    try {
      setIsLoading(true);
      setError(null);

      // Apply optimistic update if provided and force
      if (optimisticUpdate && force) {
        const optimisticData = optimisticUpdate(previousDataRef.current);
        if (mountedRef.current) {
          setData(optimisticData);
        }
      }

      let cachedData = globalCache.get<T>(key);

      if (!cachedData || force) {
        const freshData = await fetchRef.current();
        globalCache.set(key, freshData, cacheOptions.ttl);
        cachedData = freshData;
        setIsStale(false);

        // Background refresh if enabled
        if (cacheOptions.backgroundRefresh && !force) {
          if (backgroundRefreshTimers.has(key)) {
            backgroundRefreshTimers.get(key)!.stop();
          }
          const callback = () => {
            fetchRef.current().then(newData => {
              globalCache.set(key, newData, cacheOptions.ttl);
              if (mountedRef.current) {
                setData(newData);
              }
            }).catch(e => {
              console.warn('Background refresh failed:', e);
            });
          };
          const timer = new Timer(callback, (cacheOptions.ttl || 300000) * 0.9);
          backgroundRefreshTimers.set(key, timer);
        }
      } else {
        // Check if data is stale (close to expiration)
        const entry = (globalCache as any).cache.get(key);
        if (entry && Date.now() - entry.timestamp > (entry.ttl * 0.8)) {
          setIsStale(true);
        }
      }

      if (mountedRef.current) {
        setData(cachedData);
      }

      if (startTime > 0) {
        try {
          const duration = performance.now() - startTime;
          console.log(`Cache operation for ${key}: ${duration.toFixed(2)}ms`);
        } catch (e) {
          // Performance API not available
        }
      }
    } catch (err) {
      // Revert optimistic update on error
      if (optimisticUpdate && force && mountedRef.current && previousDataRef.current !== undefined) {
        setData(previousDataRef.current);
      }
      if (mountedRef.current) {
        const error = err instanceof Error ? err : new Error(String(err));
        setError(error);
      }
      console.warn(`Cache error for ${key}:`, err);
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [key, enabled, cacheOptions.ttl, cacheOptions.backgroundRefresh, optimisticUpdate]);

  const refetch = useCallback(() => {
    return fetchData(true);
  }, [fetchData]);

  const invalidate = useCallback(() => {
    globalCache.delete(key);
    setData(null);
    setIsStale(false);
  }, [key]);

  // Initial fetch
  useEffect(() => {
    if (!initializedRef.current) {
      initializedRef.current = true;
      fetchData();
    }
  }, [key]); // Only depend on key, not fetchData

  // Refetch on window focus
  useEffect(() => {
    if (!refetchOnWindowFocus) return;

    const handleFocus = () => fetchData(true);
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [fetchData, refetchOnWindowFocus]);

  // Refetch interval
  useEffect(() => {
    if (!refetchInterval) return;

    intervalRef.current = setInterval(() => {
      fetchData(true);
    }, refetchInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = undefined;
      }
    };
  }, [fetchData, refetchInterval]);

  // Pause and resume background refresh on window focus/blur
  useEffect(() => {
    const handleFocus = () => {
      if (backgroundRefreshTimers.has(key)) {
        backgroundRefreshTimers.get(key)!.resume();
      }
    };
    const handleBlur = () => {
      if (backgroundRefreshTimers.has(key)) {
        backgroundRefreshTimers.get(key)!.pause();
      }
    };
    window.addEventListener('focus', handleFocus);
    window.addEventListener('blur', handleBlur);
    return () => {
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('blur', handleBlur);
    };
  }, [key]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = undefined;
      }
      if (backgroundRefreshTimers.has(key)) {
        backgroundRefreshTimers.get(key)!.stop();
        backgroundRefreshTimers.delete(key);
      }
    };
  }, [key]);

  const mutate = useCallback(async (updater: (currentData: T | null) => T, options: { optimistic?: boolean } = {}) => {
    const { optimistic = true } = options;
    const previousData = data;
    let updatedData: T;
    
    try {
      updatedData = updater(previousData);
      
      // Update cache and state with optimistic data
      globalCache.set(key, updatedData, cacheOptions.ttl);
      if (optimistic && mountedRef.current) {
        setData(updatedData);
      }
      
      // Fetch actual data from server
      const serverData = await fetchRef.current();
      globalCache.set(key, serverData, cacheOptions.ttl);
      if (mountedRef.current) {
        setData(serverData);
        setError(null);
      }
    } catch (err) {
      // Revert to previous data on error
      if (mountedRef.current) {
        setData(previousData);
      }
      const error = err instanceof Error ? err : new Error(String(err));
      if (mountedRef.current) {
        setError(error);
      }
      console.warn(`Mutation error for ${key}:`, err);
      throw error;
    }
  }, [key, data, cacheOptions.ttl]);

  return {
    data,
    isLoading,
    error,
    isStale,
    refetch,
    invalidate,
    mutate,
  };
};

// Cache utilities
export const cacheUtils = {
  get: <T>(key: string): T | null => globalCache.get(key),
  set: <T>(key: string, data: T, ttl?: number) => globalCache.set(key, data, ttl),
  delete: (key: string) => globalCache.delete(key),
  clear: () => globalCache.clear(),
  size: () => globalCache.size(),
};

// Cache statistics hook
export const useCacheStats = () => {
  const [stats, setStats] = useState({
    size: 0,
    hitRate: 0,
    totalRequests: 0,
    cacheHits: 0,
    cacheMisses: 0,
  });

  useEffect(() => {
    const updateStats = () => {
      const totalRequests = globalCache.hits + globalCache.misses;
      setStats({
        size: globalCache.size(),
        hitRate: totalRequests > 0 ? globalCache.hits / totalRequests : 0,
        totalRequests,
        cacheHits: globalCache.hits,
        cacheMisses: globalCache.misses,
      });
    };

    updateStats();
    const interval = setInterval(updateStats, 5000);
    return () => clearInterval(interval);
  }, []);

  return stats;
};
