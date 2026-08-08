/**
 * Canvas Service Tests
 *
 * Tests for offline canvas caching:
 * - Progressive loading (cache-first with background refresh)
 * - Cache CRUD (get/set/remove/clear)
 * - Cache expiration and LRU eviction
 * - Cache statistics
 * - Offline behavior (no network, no cache -> error)
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { NetInfo } from '@react-native-community/netinfo';
import { canvasService } from '../../services/canvasService';

// The global netinfo mock (jest.setup) only exports default/fetch/etc. — it
// omits the `NetInfo` named export that canvasService imports. Provide it.
jest.mock('@react-native-community/netinfo', () => {
  const fetch = jest.fn().mockResolvedValue({
    isConnected: true,
    isInternetReachable: true,
    type: 'wifi',
    details: { isConnectionExpensive: false, ssid: 'test' },
  });
  const mockModule = {
    fetch,
    addEventListener: jest.fn().mockReturnValue({ remove: jest.fn() }),
    useNetInfo: jest.fn().mockReturnValue({ isConnected: true }),
  };
  return { default: mockModule, ...mockModule, NetInfo: mockModule };
});

// The real AsyncStorage mock (jest.setup) is backed by an in-memory map —
// exercise the actual storage round-trip like the service does.
const resetStorage = () => {
  (global as any).__resetAsyncStorageMock?.();
};

const mockNetInfo = NetInfo as jest.Mocked<typeof NetInfo>;

const CACHE_PREFIX = '@atom_canvas_cache_';

const sampleCanvas = (id: string, overrides: Record<string, any> = {}) => ({
  id,
  title: `Canvas ${id}`,
  type: 'chart',
  data: { series: [1, 2, 3] },
  metadata: {
    id,
    title: `Canvas ${id}`,
    type: 'chart',
    agent_name: 'agent-1',
    agent_id: 'a1',
    governance_level: 'SUPERVISED',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    version: 1,
    component_count: 2,
  },
  ...overrides,
});

// Flush the fire-and-forget background refresh promise chain
const flushMicrotasks = async () => {
  for (let i = 0; i < 10; i++) {
    await Promise.resolve();
  }
};

describe('canvasService', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    resetStorage();

    // Default: online
    mockNetInfo.fetch.mockResolvedValue({
      isConnected: true,
      isInternetReachable: true,
      type: 'wifi',
      details: { isConnectionExpensive: false, ssid: 'test' },
    } as any);

    // The singleton is initialized once at import; reset its in-memory state
    // and storage so each test starts from a cold cache.
    await canvasService.clearCache();
  });

  // ========================================================================
  // Progressive Loading Tests
  // ========================================================================

  describe('Progressive Loading', () => {
    test('should fetch from network and cache on first load', async () => {
      const data = sampleCanvas('c1');
      const fetchFn = jest.fn().mockResolvedValue(data);

      const result = await canvasService.loadCanvas('c1', fetchFn);

      expect(result.fromCache).toBe(false);
      expect(result.data).toEqual(data);
      expect(fetchFn).toHaveBeenCalledTimes(1);
      // Canvas is persisted under its prefixed key
      const stored = await AsyncStorage.getItem(`${CACHE_PREFIX}c1`);
      expect(stored).not.toBeNull();
      expect(JSON.parse(stored as string).canvasId).toBe('c1');
      expect(JSON.parse(stored as string).metadata.id).toBe('c1');
    });

    test('should serve cached data and refresh in the background when online', async () => {
      const initial = sampleCanvas('c1', { title: 'Original' });
      const refreshed = sampleCanvas('c1', { title: 'Refreshed' });

      await canvasService.loadCanvas('c1', jest.fn().mockResolvedValue(initial));
      const fetchFn2 = jest.fn().mockResolvedValue(refreshed);

      const result = await canvasService.loadCanvas('c1', fetchFn2);

      // Cache hit returns the underlying canvas payload — not the cache envelope
      expect(result.fromCache).toBe(true);
      expect(result.data).toEqual(initial);
      expect(result.data).not.toHaveProperty('cachedAt');
      expect(result.data).not.toHaveProperty('expiresAt');

      // Background refresh eventually lands in the cache
      await flushMicrotasks();
      const cached = await canvasService.getCachedCanvas('c1');
      expect(cached?.data.title).toBe('Refreshed');
    });

    test('should return cache without network call when offline', async () => {
      const data = sampleCanvas('c1');
      await canvasService.loadCanvas('c1', jest.fn().mockResolvedValue(data));

      mockNetInfo.fetch.mockResolvedValue({
        isConnected: false,
        isInternetReachable: false,
        type: 'none',
      } as any);

      const fetchFn = jest.fn();
      const result = await canvasService.loadCanvas('c1', fetchFn);

      expect(result.fromCache).toBe(true);
      expect(result.data).toEqual(data);
      // No background refresh attempt while offline
      expect(fetchFn).not.toHaveBeenCalled();
    });

    test('should throw when offline with no cached version', async () => {
      mockNetInfo.fetch.mockResolvedValue({
        isConnected: false,
        isInternetReachable: false,
        type: 'none',
      } as any);

      const fetchFn = jest.fn();
      await expect(canvasService.loadCanvas('c1', fetchFn)).rejects.toThrow(
        'No internet connection and no cached version available'
      );
      expect(fetchFn).not.toHaveBeenCalled();
    });

    test('should not fetch twice when the fetchFn rejects during background refresh', async () => {
      const data = sampleCanvas('c1');
      await canvasService.loadCanvas('c1', jest.fn().mockResolvedValue(data));

      const fetchFn2 = jest.fn().mockRejectedValue(new Error('server down'));
      const result = await canvasService.loadCanvas('c1', fetchFn2);

      expect(result.fromCache).toBe(true);
      await flushMicrotasks();
      // Original cache is untouched after a failed refresh
      const cached = await canvasService.getCachedCanvas('c1');
      expect(cached?.data.title).toBe('Canvas c1');
    });
  });

  // ========================================================================
  // Cache CRUD Tests
  // ========================================================================

  describe('Cache CRUD', () => {
    test('should cache a canvas with metadata and size', async () => {
      await canvasService.cacheCanvas('c1', sampleCanvas('c1'));

      const cached = await canvasService.getCachedCanvas('c1');
      expect(cached).not.toBeNull();
      expect(cached?.canvasId).toBe('c1');
      expect(cached?.metadata.id).toBe('c1');
      expect(cached?.size).toBeGreaterThan(0);
      expect(cached?.expiresAt).toBeGreaterThan(cached?.cachedAt ?? 0);
    });

    test('should return null for a missing canvas', async () => {
      expect(await canvasService.getCachedCanvas('nope')).toBeNull();
    });

    test('should return null for corrupt cache data without throwing', async () => {
      await AsyncStorage.setItem(`${CACHE_PREFIX}bad`, '{not valid json');

      expect(await canvasService.getCachedCanvas('bad')).toBeNull();
    });

    test('should remove a cached canvas and update stats', async () => {
      await canvasService.cacheCanvas('c1', sampleCanvas('c1'));
      await canvasService.cacheCanvas('c2', sampleCanvas('c2'));

      await canvasService.removeCachedCanvas('c1');

      expect(await canvasService.getCachedCanvas('c1')).toBeNull();
      expect(await canvasService.getCachedCanvas('c2')).not.toBeNull();
      expect(canvasService.getCacheStats().canvasCount).toBe(1);
    });

    test('should clear all cached canvases and reset stats', async () => {
      await canvasService.cacheCanvas('c1', sampleCanvas('c1'));
      await canvasService.cacheCanvas('c2', sampleCanvas('c2'));

      await canvasService.clearCache();

      expect(await AsyncStorage.getItem(`${CACHE_PREFIX}c1`)).toBeNull();
      expect(await AsyncStorage.getItem(`${CACHE_PREFIX}c2`)).toBeNull();
      const stats = canvasService.getCacheStats();
      expect(stats.canvasCount).toBe(0);
      expect(stats.totalSize).toBe(0);
    });

    test('should update cache via refreshCanvas', async () => {
      await canvasService.cacheCanvas('c1', sampleCanvas('c1', { title: 'Old' }));

      await canvasService.refreshCanvas('c1', jest.fn().mockResolvedValue(
        sampleCanvas('c1', { title: 'New' })
      ));

      const cached = await canvasService.getCachedCanvas('c1');
      expect(cached?.data.title).toBe('New');
    });

    test('should rethrow refresh errors', async () => {
      await expect(
        canvasService.refreshCanvas('c1', jest.fn().mockRejectedValue(new Error('boom')))
      ).rejects.toThrow('boom');
    });
  });

  // ========================================================================
  // Expiration Tests
  // ========================================================================

  describe('Expiration', () => {
    test('should evict expired entries on read', async () => {
      // Write an entry that expired yesterday
      const expired = {
        canvasId: 'expired',
        data: { id: 'expired' },
        metadata: {},
        cachedAt: Date.now() - 2 * 24 * 60 * 60 * 1000,
        expiresAt: Date.now() - 24 * 60 * 60 * 1000,
        size: 10,
      };
      await AsyncStorage.setItem(`${CACHE_PREFIX}expired`, JSON.stringify(expired));

      expect(await canvasService.getCachedCanvas('expired')).toBeNull();
      expect(await AsyncStorage.getItem(`${CACHE_PREFIX}expired`)).toBeNull();
    });

    test('should keep fresh entries', async () => {
      await canvasService.cacheCanvas('c1', sampleCanvas('c1'));

      const cached = await canvasService.getCachedCanvas('c1');
      expect(cached).not.toBeNull();
    });

    test('should not drive stats negative when removing an unknown entry', async () => {
      await AsyncStorage.setItem(
        `${CACHE_PREFIX}orphan`,
        JSON.stringify({
          canvasId: 'orphan',
          data: {},
          metadata: {},
          cachedAt: Date.now(),
          expiresAt: Date.now() + 1000,
          size: 5,
        })
      );

      await canvasService.removeCachedCanvas('orphan');

      const stats = canvasService.getCacheStats();
      expect(stats.canvasCount).toBeGreaterThanOrEqual(0);
      expect(stats.totalSize).toBeGreaterThanOrEqual(0);
    });
  });

  // ========================================================================
  // LRU Eviction Tests
  // ========================================================================

  describe('LRU Eviction', () => {
    test('should evict the oldest canvas when cache is full', async () => {
      // Seed two canvases in the cache, the second one being older
      const oldEntry = {
        canvasId: 'old',
        data: { id: 'old' },
        metadata: {},
        cachedAt: 1000,
        expiresAt: Date.now() + 24 * 60 * 60 * 1000,
        size: 10,
      };
      const newerEntry = {
        canvasId: 'newer',
        data: { id: 'newer' },
        metadata: {},
        cachedAt: 2000,
        expiresAt: Date.now() + 24 * 60 * 60 * 1000,
        size: 10,
      };
      await AsyncStorage.setItem(`${CACHE_PREFIX}old`, JSON.stringify(oldEntry));
      await AsyncStorage.setItem(`${CACHE_PREFIX}newer`, JSON.stringify(newerEntry));

      // Drive the in-memory state to full so cacheCanvas triggers eviction
      const service = canvasService as any;
      service.cacheIndex = new Set(['old', 'newer']);
      service.cacheStats = {
        totalSize: 50 * 1024 * 1024, // at the 50MB cap
        canvasCount: 2,
        oldestCache: 1000,
        newestCache: 2000,
      };

      await canvasService.cacheCanvas('third', sampleCanvas('third'));

      // Oldest entry ('old') was evicted, newest + new one remain
      expect(await AsyncStorage.getItem(`${CACHE_PREFIX}old`)).toBeNull();
      expect(await AsyncStorage.getItem(`${CACHE_PREFIX}newer`)).not.toBeNull();
      expect(await AsyncStorage.getItem(`${CACHE_PREFIX}third`)).not.toBeNull();
    });
  });

  // ========================================================================
  // Error Handling Tests
  // ========================================================================

  describe('Error Handling', () => {
    test('should not throw when the cache index fails to load', async () => {
      const getItem = AsyncStorage.getItem as jest.Mock;
      getItem.mockRejectedValueOnce(new Error('storage error'));

      // Force a re-init so loadCacheIndex runs again with the failing read
      (canvasService as any).initialized = false;
      await expect(canvasService.init()).resolves.toBeUndefined();
    });

    test('should not throw when stats fail to load', async () => {
      const getItem = AsyncStorage.getItem as jest.Mock;
      getItem.mockRejectedValueOnce(new Error('storage error'));

      const stats = await (canvasService as any).loadCacheStats();
      expect(stats).toBeUndefined();
    });

    test('should swallow storage failures when caching a canvas', async () => {
      const setItem = AsyncStorage.setItem as jest.Mock;
      setItem.mockRejectedValueOnce(new Error('storage error'));

      await expect(
        canvasService.cacheCanvas('c1', sampleCanvas('c1'))
      ).resolves.toBeUndefined();
    });

    test('should swallow storage failures when removing a canvas', async () => {
      const getItem = AsyncStorage.getItem as jest.Mock;
      getItem.mockRejectedValueOnce(new Error('storage error'));

      await expect(canvasService.removeCachedCanvas('c1')).resolves.toBeUndefined();
    });

    test('should rethrow clearCache storage failures', async () => {
      const getAllKeys = AsyncStorage.getAllKeys as jest.Mock;
      getAllKeys.mockRejectedValueOnce(new Error('storage error'));

      await expect(canvasService.clearCache()).rejects.toThrow('storage error');
    });

    test('should keep caching the new canvas when LRU eviction read fails', async () => {
      (canvasService as any).cacheIndex = new Set(['old']);
      (canvasService as any).cacheStats = {
        totalSize: 50 * 1024 * 1024, // full -> eviction attempted
        canvasCount: 1,
        oldestCache: 1000,
        newestCache: 1000,
      };

      const getItem = AsyncStorage.getItem as jest.Mock;
      getItem.mockRejectedValueOnce(new Error('storage error'));

      await canvasService.cacheCanvas('c1', sampleCanvas('c1'));

      const cached = await canvasService.getCachedCanvas('c1');
      expect(cached?.canvasId).toBe('c1');
    });
  });

    test('should swallow storage failures when persisting the cache index', async () => {
      const setItem = AsyncStorage.setItem as jest.Mock;
      setItem.mockRejectedValueOnce(new Error('storage error'));

      await expect((canvasService as any).saveCacheIndex()).resolves.toBeUndefined();
    });

    test('should swallow storage failures when persisting cache stats', async () => {
      const setItem = AsyncStorage.setItem as jest.Mock;
      setItem.mockRejectedValueOnce(new Error('storage error'));

      await expect((canvasService as any).saveCacheStats()).resolves.toBeUndefined();
    });

    test('should clean up expired caches during init', async () => {
      const expired = {
        canvasId: 'expired',
        data: { id: 'expired' },
        metadata: {},
        cachedAt: Date.now() - 2 * 24 * 60 * 60 * 1000,
        expiresAt: Date.now() - 24 * 60 * 60 * 1000,
        size: 10,
      };
      await AsyncStorage.setItem(`${CACHE_PREFIX}expired`, JSON.stringify(expired));
      (canvasService as any).cacheIndex = new Set(['expired']);

      await (canvasService as any).cleanupExpiredCache();

      expect(await AsyncStorage.getItem(`${CACHE_PREFIX}expired`)).toBeNull();
      expect((canvasService as any).cacheIndex.has('expired')).toBe(false);
    });

    test('should keep fresh caches during cleanup', async () => {
      await canvasService.cacheCanvas('c1', sampleCanvas('c1'));
      (canvasService as any).cacheIndex = new Set(['c1']);

      await (canvasService as any).cleanupExpiredCache();

      expect(await AsyncStorage.getItem(`${CACHE_PREFIX}c1`)).not.toBeNull();
    });

    test('should swallow storage failures during cache cleanup', async () => {
      // Seed the index so the cleanup loop actually reads storage — otherwise
      // the mockRejectedValueOnce below would leak unconsumed into the next test.
      await canvasService.cacheCanvas('c1', sampleCanvas('c1'));
      (canvasService as any).cacheIndex = new Set(['c1']);

      const getItem = AsyncStorage.getItem as jest.Mock;
      getItem.mockRejectedValueOnce(new Error('storage error'));

      await expect((canvasService as any).cleanupExpiredCache()).resolves.toBeUndefined();
      expect(getItem).toHaveBeenCalled();
    });

  // ========================================================================
  // Cache Statistics Tests
  // ========================================================================

  describe('Cache Statistics', () => {
    test('should track canvas count and total size across adds/removes', async () => {
      await canvasService.cacheCanvas('c1', sampleCanvas('c1'));
      const statsAfterAdd = canvasService.getCacheStats();
      expect(statsAfterAdd.canvasCount).toBe(1);
      expect(statsAfterAdd.totalSize).toBeGreaterThan(0);
      expect(statsAfterAdd.oldestCache).toBeGreaterThan(0);
      expect(statsAfterAdd.newestCache).toBeGreaterThan(0);

      await canvasService.cacheCanvas('c2', sampleCanvas('c2'));
      expect(canvasService.getCacheStats().canvasCount).toBe(2);

      await canvasService.removeCachedCanvas('c1');
      const statsAfterRemove = canvasService.getCacheStats();
      expect(statsAfterRemove.canvasCount).toBe(1);
      expect(statsAfterRemove.totalSize).toBeLessThan(statsAfterAdd.totalSize * 2);
    });
  });
});
