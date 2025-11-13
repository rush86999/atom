import { useState, useEffect, useCallback, useRef } from 'react';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

interface CacheOptions {
  ttl?: number; // Time to live in milliseconds
  maxSize?: number; // Maximum cache size
  strategy?: 'lru' | 'fifo' | 'lfu'; // Cache eviction strategy
  enablePersistence?: boolean; // Enable localStorage persistence
}

class Cache<T = any> {
  private cache = new Map<string, CacheEntry<T>>();
  private accessOrder = new Set<string>();
  private options: Required<CacheOptions>;

  constructor(options: CacheOptions = {}) {
    this.options = {
      ttl: options.ttl || 5 * 60 * 1000, // 5 minutes default
      maxSize: options.maxSize || 100,
      strategy: options.strategy || 'lru',
      enablePersistence: options.enablePersistence || false,
    };
  }

  get(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    // Check if expired
    if (Date.now() - entry.timestamp > entry.ttl) {
      this.cache.delete(key);
      this.accessOrder.delete(key);
      return null;
    }

    // Update access order for LRU
    if (this.options.strategy === 'lru') {
      this.accessOrder.delete(key);
      this.accessOrder.add(key);
    }

    return entry.data;
  }

  set(key: string, data: T, ttl?: number): void {
    // Evict if cache is full
    if (this.cache.size >= this.options.maxSize) {
      this.evict();
    }

    const entry: CacheEntry<T> = {
      data,
      timestamp: Date.now(),
      ttl: ttl || this.options.ttl,
    };

    this.cache.set(key, entry);
    this.accessOrder.add(key);
  }

  delete(key: string): void {
    this.cache.delete(key);
    this.accessOrder.delete(key);
  }

  clear(): void {
    this.cache.clear();
    this.accessOrder.clear();
  }

  private evict(): void {
    if (this.options.strategy === 'lru') {
      // Remove least recently used
      const firstKey = this.accessOrder.values().next().value;
      if (firstKey) {
        this.cache.delete(firstKey);
        this.accessOrder.delete(firstKey);
      }
    } else if (this.options.strategy === 'fifo') {
      // FIFO - remove oldest
      const firstKey = this.accessOrder.values().next().value;
      if (firstKey) {
        this.cache.delete(firstKey);
        this.accessOrder.delete(firstKey);
      }
    } else if (this.options.strategy === 'lfu') {
      // LFU - remove least frequently used
      let leastUsedKey: string | null = null;
      let minAccessCount = Infinity;

      for (const key of this.accessOrder) {
        const entry = this.cache.get(key);
        if (entry && (entry as any).accessCount < minAccessCount) {
          minAccessCount = (entry as any).accessCount || 0;
          leastUsedKey = key;
        }
      }

      if (leastUsedKey) {
        this.cache.delete(leastUsedKey);
        this.accessOrder.delete(leastUsedKey);
      }
    }
  }

  size(): number {
    return this.cache.size;
  }
}

// Global cache instance
const globalCache = new Cache({});

export const useCache = <T>(
  key: string,
  fetcher: () => Promise<T>,
  options: CacheOptions & {
    enabled?: boolean;
    refetchOnWindowFocus?: boolean;
    refetchInterval?: number;
  } = {}
) => {
  const {
    enabled = true,
    refetchOnWindowFocus = false,
    refetchInterval,
    ...cacheOptions
  } = options;

  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isStale, setIsStale] = useState(false);

  const fetchRef = useRef(fetcher);
  const intervalRef = useRef<NodeJS.Timeout | undefined>();
  const mountedRef = useRef(true);

  // Update fetcher ref when it changes
  useEffect(() => {
    fetchRef.current = fetcher;
  }, [fetcher]);

  const fetchData = useCallback(async (force = false) => {
    if (!enabled || !mountedRef.current) return;

    try {
      setIsLoading(true);
      setError(null);

      let cachedData = globalCache.get(key);

      if (!cachedData || force) {
        const freshData = await fetchRef.current();
        globalCache.set(key, freshData, cacheOptions.ttl);
        cachedData = freshData;
        setIsStale(false);
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
    } catch (err) {
      if (mountedRef.current) {
        setError(err as Error);
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [key, enabled, cacheOptions.ttl]);

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
    fetchData();
  }, [fetchData]);

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

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = undefined;
      }
    };
  }, []);

  return {
    data,
    isLoading,
    error,
    isStale,
    refetch,
    invalidate,
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
  });

  useEffect(() => {
    const updateStats = () => {
      setStats({
        size: globalCache.size(),
        hitRate: 0, // Would need to track this separately
        totalRequests: 0,
        cacheHits: 0,
      });
    };

    updateStats();
    const interval = setInterval(updateStats, 5000);
    return () => clearInterval(interval);
  }, []);

  return stats;
};
