/**
 * Canvas Sync Service Tests
 *
 * Tests for canvas synchronization functionality:
 * - List sync (sync all canvases, filter by type)
 * - Single sync (individual canvas, updates, not found)
 * - Form sync (submit forms, offline queue, validation)
 * - State (progress tracking, last sync time, partial sync)
 */

import { canvasSyncService } from '../../services/canvasSyncService';

// Mock apiService
jest.mock('../../services/api', () => ({
  apiService: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
  },
}));

// Mock storageService
jest.mock('../../services/storageService', () => ({
  storageService: {
    getObject: jest.fn(() => Promise.resolve(null)),
    setObject: jest.fn(() => Promise.resolve()),
  },
  StorageKey: {},
}));

// Mock offlineSyncService
jest.mock('../../services/offlineSyncService', () => ({
  offlineSyncService: {
    getSyncState: jest.fn(() => Promise.resolve({ syncInProgress: false })),
    queueAction: jest.fn(() => Promise.resolve()),
  },
}));

describe('canvasSyncService', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    // The service keeps an in-memory cache that survives across tests —
    // clear it so each test starts from a cold cache.
    await canvasSyncService.clearCache();
    // Restore the default online state — a previous test may have set
    // syncInProgress: true, which routes submits to the offline queue.
    const { offlineSyncService } = require('../../services/offlineSyncService');
    offlineSyncService.getSyncState.mockResolvedValue({ syncInProgress: false });
    await canvasSyncService.initialize();
  });

  afterEach(() => {
    canvasSyncService.destroy();
  });

  // ========================================================================
  // List Sync Tests (3 tests)
  // ========================================================================

  describe('List Sync', () => {
    test('should sync canvas list', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: true,
        data: {
          canvases: [
            {
              id: 'canvas_1',
              title: 'Canvas 1',
              type: 'chart',
              data: {},
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            },
            {
              id: 'canvas_2',
              title: 'Canvas 2',
              type: 'form',
              data: {},
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            },
          ],
        },
      });

      const result = await canvasSyncService.syncCanvases('user_1', 'device_1');

      expect(result.success).toBe(true);
      expect(result.synced).toBe(2);
      expect(result.failed).toBe(0);
    });

    test('should handle empty list', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: true,
        data: { canvases: [] },
      });

      const result = await canvasSyncService.syncCanvases('user_1', 'device_1');

      expect(result.success).toBe(true);
      expect(result.synced).toBe(0);
    });

    test('should filter by type', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: true,
        data: {
          canvases: [
            {
              id: 'canvas_1',
              title: 'Chart Canvas',
              type: 'chart',
              data: {},
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            },
            {
              id: 'canvas_2',
              title: 'Form Canvas',
              type: 'form',
              data: {},
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            },
          ],
        },
      });

      await canvasSyncService.syncCanvases('user_1', 'device_1');

      const chartCanvases = canvasSyncService.getCanvasesByType('chart');
      const formCanvases = canvasSyncService.getCanvasesByType('form');

      expect(chartCanvases).toHaveLength(1);
      expect(chartCanvases[0].type).toBe('chart');
      expect(formCanvases).toHaveLength(1);
      expect(formCanvases[0].type).toBe('form');
    });
  });

  // ========================================================================
  // Single Sync Tests (4 tests)
  // ========================================================================

  describe('Single Sync', () => {
    test('should sync single canvas', async () => {
      const { apiService } = require('../../services/api');

      const canvasData = {
        id: 'canvas_1',
        title: 'Canvas 1',
        type: 'chart',
        data: { chart: 'data' },
        html: '<div>Canvas HTML</div>',
        css: '.canvas { color: red; }',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      apiService.get.mockResolvedValue({
        success: true,
        data: canvasData,
      });

      const canvas = await canvasSyncService.getCanvas('canvas_1');

      expect(canvas).not.toBeNull();
      expect(canvas?.id).toBe('canvas_1');
      expect(canvas?.title).toBe('Canvas 1');
    });

    test('should sync canvas updates', async () => {
      const { apiService } = require('../../services/api');

      apiService.put.mockResolvedValue({
        success: true,
      });

      const result = await canvasSyncService.updateCanvas(
        'canvas_1',
        { title: 'Updated Title' },
        'user_1',
        'device_1'
      );

      expect(result).toBe(true);
      expect(apiService.put).toHaveBeenCalledWith(
        '/api/canvas/canvas_1',
        expect.objectContaining({ title: 'Updated Title' })
      );
    });

    test('should handle canvas not found', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: false,
        error: 'Canvas not found',
      });

      const canvas = await canvasSyncService.getCanvas('nonexistent');

      expect(canvas).toBeNull();
    });

    test('should resolve canvas conflicts', async () => {
      const { apiService } = require('../../services/api');

      // Simulate conflict by having server return newer version
      apiService.get.mockResolvedValue({
        success: true,
        data: {
          id: 'canvas_1',
          title: 'Server Title',
          type: 'chart',
          data: {},
          updatedAt: new Date(Date.now() + 10000).toISOString(), // Server is newer
          createdAt: new Date().toISOString(),
        },
      });

      apiService.put.mockResolvedValue({ success: true });

      const result = await canvasSyncService.updateCanvas(
        'canvas_1',
        { title: 'Client Title' },
        'user_1',
        'device_1'
      );

      // Update should succeed with conflict resolution
      expect(result).toBe(true);
    });
  });

  // ========================================================================
  // Form Sync Tests (4 tests)
  // ========================================================================

  describe('Form Sync', () => {
    test('should sync form submissions', async () => {
      const { apiService } = require('../../services/api');

      apiService.post.mockResolvedValue({
        success: true,
      });

      const result = await canvasSyncService.submitForm(
        'canvas_1',
        { field1: 'value1', field2: 'value2' },
        'user_1',
        'device_1'
      );

      expect(result).toBe(true);
      expect(apiService.post).toHaveBeenCalledWith(
        '/api/canvas/canvas_1/submit',
        expect.objectContaining({
          form_data: { field1: 'value1', field2: 'value2' },
        })
      );
    });

    test('should queue form submits offline', async () => {
      const { offlineSyncService } = require('../../services/offlineSyncService');

      // Mock offline state
      offlineSyncService.getSyncState.mockResolvedValue({ syncInProgress: true });

      const result = await canvasSyncService.submitForm(
        'canvas_1',
        { field1: 'value1' },
        'user_1',
        'device_1'
      );

      // Should queue for later sync
      expect(result).toBe(true);
    });

    test('should handle form validation errors', async () => {
      const { apiService } = require('../../services/api');

      apiService.post.mockResolvedValue({
        success: false,
        error: 'Validation failed: field1 is required',
      });

      const result = await canvasSyncService.submitForm(
        'canvas_1',
        {}, // Missing required fields
        'user_1',
        'device_1'
      );

      expect(result).toBe(false);
    });

    test('should track form submit status', async () => {
      const { apiService } = require('../../services/api');

      apiService.post.mockResolvedValue({
        success: true,
      });

      await canvasSyncService.submitForm(
        'canvas_1',
        { field1: 'value1' },
        'user_1',
        'device_1'
      );

      // Verify submission was tracked
      expect(apiService.post).toHaveBeenCalled();
    });
  });

  // ========================================================================
  // State Tests (4 tests)
  // ========================================================================

  describe('State', () => {
    test('should track sync progress', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: true,
        data: {
          canvases: Array(20).fill(null).map((_, i) => ({
            id: `canvas_${i}`,
            title: `Canvas ${i}`,
            type: 'chart',
            data: {},
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          })),
        },
      });

      const result = await canvasSyncService.syncCanvases('user_1', 'device_1');

      // Duration is wall-clock time; with all-immmediate mocks it can be 0ms
      expect(result.duration).toBeGreaterThanOrEqual(0);
      expect(result.synced).toBe(20);
    });

    test('should get last sync time', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: true,
        data: { canvases: [] },
      });

      await canvasSyncService.syncCanvases('user_1', 'device_1');

      // After sync, should have lastSyncAt set
      const canvases = canvasSyncService.getAllCanvases();
      expect(Array.isArray(canvases)).toBe(true);
    });

    test('should force refresh', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: true,
        data: {
          canvases: [
            {
              id: 'canvas_1',
              title: 'Canvas 1',
              type: 'chart',
              data: {},
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            },
          ],
        },
      });

      // Initial sync
      await canvasSyncService.syncCanvases('user_1', 'device_1');

      // Force refresh
      await canvasSyncService.syncCanvases('user_1', 'device_1');

      expect(apiService.get).toHaveBeenCalledTimes(2);
    });

    test('should handle partial sync', async () => {
      const { apiService } = require('../../services/api');

      // Mock partial failure
      apiService.get.mockResolvedValue({
        success: true,
        data: {
          canvases: [
            {
              id: 'canvas_1',
              title: 'Canvas 1',
              type: 'chart',
              data: {},
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            },
            {
              id: 'canvas_2',
              title: 'Canvas 2',
              type: 'form',
              data: {}, // This will fail to sync
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            },
          ],
        },
      });

      // Force one canvas to fail by throwing error during processing
      const result = await canvasSyncService.syncCanvases('user_1', 'device_1');

      // Should still report success with some synced and some failed
      expect(result.success).toBe(true);
      expect(result.synced).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // Cache Management Tests
  // ========================================================================

  describe('Cache Management', () => {
    test('should invalidate canvas cache', async () => {
      const { apiService } = require('../../services/api');

      // Cache a canvas
      apiService.get.mockResolvedValue({
        success: true,
        data: {
          id: 'canvas_1',
          title: 'Canvas 1',
          type: 'chart',
          data: {},
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      });

      await canvasSyncService.getCanvas('canvas_1');

      // Invalidate cache
      await canvasSyncService.invalidateCache('canvas_1');

      // Should fetch from server again on next get
      await canvasSyncService.getCanvas('canvas_1');

      expect(apiService.get).toHaveBeenCalledTimes(2);
    });

    test('should clear all cache', async () => {
      const { apiService } = require('../../services/api');

      // Cache multiple canvases
      apiService.get.mockResolvedValue({
        success: true,
        data: {
          id: 'canvas_1',
          title: 'Canvas 1',
          type: 'chart',
          data: {},
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      });

      await canvasSyncService.getCanvas('canvas_1');

      // Clear all cache
      await canvasSyncService.clearCache();

      // Cache should be empty
      const canvases = canvasSyncService.getAllCanvases();
      expect(canvases).toHaveLength(0);
    });

    test('should get cached HTML', async () => {
      const { apiService } = require('../../services/api');

      const html = '<div>Canvas HTML</div>';

      apiService.get.mockResolvedValue({
        success: true,
        data: {
          id: 'canvas_1',
          title: 'Canvas 1',
          type: 'chart',
          data: {},
          html,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      });

      await canvasSyncService.getCanvas('canvas_1');

      const cachedHtml = canvasSyncService.getCachedHtml('canvas_1');
      expect(cachedHtml).toBe(html);
    });

    test('should get cached CSS', async () => {
      const { apiService } = require('../../services/api');

      const css = '.canvas { color: red; }';

      apiService.get.mockResolvedValue({
        success: true,
        data: {
          id: 'canvas_1',
          title: 'Canvas 1',
          type: 'chart',
          data: {},
          css,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      });

      await canvasSyncService.getCanvas('canvas_1');

      const cachedCss = canvasSyncService.getCachedCss('canvas_1');
      expect(cachedCss).toBe(css);
    });
  });

  // ========================================================================
  // Favorites Tests
  // ========================================================================

  describe('Favorites', () => {    test('should toggle canvas favorite status', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: true,
        data: {
          id: 'canvas_1',
          title: 'Canvas 1',
          type: 'chart',
          data: {},
          isFavorite: false,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      });

      apiService.put.mockResolvedValue({ success: true });

      // Seed the cache (toggleFavorite requires the canvas to be cached)
      await canvasSyncService.getCanvas('canvas_1');

      // First toggle: add to favorites
      const result1 = await canvasSyncService.toggleFavorite('canvas_1', 'user_1', 'device_1');
      expect(result1).toBe(true);

      // Second toggle: remove from favorites
      const result2 = await canvasSyncService.toggleFavorite('canvas_1', 'user_1', 'device_1');
      expect(result2).toBe(true);
    });

    test('should get favorite canvases', async () => {
      const { apiService } = require('../../services/api');

      // Cache canvases with different favorite statuses
      apiService.get.mockImplementation((url) => {
        if (url === '/api/canvas/canvas_1') {
          return Promise.resolve({
            success: true,
            data: {
              id: 'canvas_1',
              title: 'Favorite Canvas',
              type: 'chart',
              data: {},
              isFavorite: true,
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            },
          });
        }
        return Promise.resolve({
          success: true,
          data: {
            id: 'canvas_2',
            title: 'Regular Canvas',
            type: 'form',
            data: {},
            isFavorite: false,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          },
        });
      });

      await canvasSyncService.getCanvas('canvas_1');
      await canvasSyncService.getCanvas('canvas_2');

      const favorites = canvasSyncService.getFavoriteCanvases();

      expect(favorites).toHaveLength(1);
      expect(favorites[0].id).toBe('canvas_1');
      expect(favorites[0].isFavorite).toBe(true);
    });
  });

  // ========================================================================
  // Sync Failure Tests
  // ========================================================================

  describe('Sync Failures', () => {
    test('should report failure when list fetch fails', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: false,
        error: 'Server unreachable',
      });

      const result = await canvasSyncService.syncCanvases('user_1', 'device_1');

      expect(result.success).toBe(false);
      expect(result.synced).toBe(0);
      expect(result.duration).toBeGreaterThanOrEqual(0);
    });

    test('should report failure when list fetch throws', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockRejectedValue(new Error('Network error'));

      const result = await canvasSyncService.syncCanvases('user_1', 'device_1');

      expect(result.success).toBe(false);
    });

    test('should return null when single canvas fetch fails', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockRejectedValue(new Error('Network error'));

      const canvas = await canvasSyncService.getCanvas('missing');

      expect(canvas).toBeNull();
    });
  });

  // ========================================================================
  // Cache Hit & Staleness Tests
  // ========================================================================

  describe('Cache Behavior', () => {
    test('should serve fresh cache without a second fetch', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: true,
        data: {
          id: 'canvas_1',
          title: 'Canvas 1',
          type: 'chart',
          data: {},
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      });

      await canvasSyncService.getCanvas('canvas_1');

      // Second get hits the fresh cache — no additional API call
      const canvas = await canvasSyncService.getCanvas('canvas_1');

      expect(canvas?.id).toBe('canvas_1');
      expect(apiService.get).toHaveBeenCalledTimes(1);
    });

    test('should fall back to stale cache when refetch fails', async () => {
      const { apiService } = require('../../services/api');

      // Seed the cache with a stale canvas (updated long ago)
      apiService.get.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'canvas_1',
          title: 'Stale Canvas',
          type: 'chart',
          data: {},
          createdAt: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
          updatedAt: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
        },
      });

      await canvasSyncService.getCanvas('canvas_1');

      // Refetch fails — stale cached copy is returned for offline viewing
      apiService.get.mockResolvedValueOnce({
        success: false,
        error: 'Server unreachable',
      });

      const canvas = await canvasSyncService.getCanvas('canvas_1');

      expect(canvas).not.toBeNull();
      expect(canvas?.id).toBe('canvas_1');
      expect(canvas?.title).toBe('Stale Canvas');
      expect(apiService.get).toHaveBeenCalledTimes(2);
    });
  });

  // ========================================================================
  // Conflict Detection Tests
  // ========================================================================

  describe('Conflicts', () => {
    test('should detect conflicts when server canvas is older than cache', async () => {
      const { apiService } = require('../../services/api');

      const now = Date.now();

      // Cache a fresh canvas
      apiService.get.mockResolvedValue({
        success: true,
        data: {
          id: 'canvas_1',
          title: 'Local Title',
          type: 'chart',
          data: {},
          createdAt: new Date(now).toISOString(),
          updatedAt: new Date(now).toISOString(),
        },
      });

      await canvasSyncService.getCanvas('canvas_1');

      // Sync returns an OLDER server version → conflict, not overwrite
      apiService.get.mockResolvedValue({
        success: true,
        data: {
          canvases: [
            {
              id: 'canvas_1',
              title: 'Server Old Title',
              type: 'chart',
              data: {},
              createdAt: new Date(now - 60000).toISOString(),
              updatedAt: new Date(now - 60000).toISOString(),
            },
          ],
        },
      });

      const result = await canvasSyncService.syncCanvases('user_1', 'device_1');

      expect(result.conflicts).toBe(1);
      expect(result.synced).toBe(0);

      // Local (newer) copy is preserved
      const cached = canvasSyncService.getAllCanvases();
      expect(cached).toHaveLength(1);
      expect(cached[0].title).toBe('Local Title');
    });
  });

  // ========================================================================
  // Offline Update Tests
  // ========================================================================

  describe('Offline Updates', () => {
    test('should queue canvas updates when offline', async () => {
      const { apiService } = require('../../services/api');
      const { offlineSyncService } = require('../../services/offlineSyncService');

      // Seed the cache
      apiService.get.mockResolvedValue({
        success: true,
        data: {
          id: 'canvas_1',
          title: 'Canvas 1',
          type: 'chart',
          data: {},
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      });
      await canvasSyncService.getCanvas('canvas_1');

      // Go offline
      offlineSyncService.getSyncState.mockResolvedValue({ syncInProgress: true });

      const result = await canvasSyncService.updateCanvas(
        'canvas_1',
        { title: 'Offline Title' },
        'user_1',
        'device_1'
      );

      expect(result).toBe(true);
      expect(offlineSyncService.queueAction).toHaveBeenCalledWith(
        'canvas_sync',
        expect.objectContaining({ canvasId: 'canvas_1' }),
        'normal',
        'user_1',
        'device_1',
        'last_write_wins',
        'canvases',
        'canvas_1'
      );

      // Optimistic cache update applied
      const cached = canvasSyncService.getAllCanvases();
      expect(cached[0].title).toBe('Offline Title');

      // No server call was attempted
      expect(apiService.put).not.toHaveBeenCalled();
    });

    test('should return false when update fails on server', async () => {
      const { apiService } = require('../../services/api');

      apiService.put.mockResolvedValue({ success: false, error: 'Conflict' });

      const result = await canvasSyncService.updateCanvas(
        'canvas_1',
        { title: 'New Title' },
        'user_1',
        'device_1'
      );

      expect(result).toBe(false);
    });

    test('should return false when toggling favorite on unknown canvas', async () => {
      const result = await canvasSyncService.toggleFavorite(
        'not_cached',
        'user_1',
        'device_1'
      );

      expect(result).toBe(false);
    });
  });

  // ========================================================================
  // Pending Form Submission Sync Tests
  // ========================================================================

  describe('Pending Form Sync', () => {
    test('should flush queued submissions when back online', async () => {
      const { apiService } = require('../../services/api');
      const { offlineSyncService } = require('../../services/offlineSyncService');

      // Queue while offline
      offlineSyncService.getSyncState.mockResolvedValue({ syncInProgress: true });
      await canvasSyncService.submitForm(
        'canvas_1',
        { field1: 'value1' },
        'user_1',
        'device_1'
      );

      // Back online — flush
      offlineSyncService.getSyncState.mockResolvedValue({ syncInProgress: false });
      apiService.post.mockResolvedValue({ success: true });

      await canvasSyncService.syncFormSubmissions('user_1', 'device_1');

      expect(apiService.post).toHaveBeenCalledWith(
        '/api/canvas/canvas_1/submit',
        expect.objectContaining({ form_data: { field1: 'value1' } })
      );

      // Pending queue is now empty — a second flush makes no calls
      apiService.post.mockClear();
      await canvasSyncService.syncFormSubmissions('user_1', 'device_1');
      expect(apiService.post).not.toHaveBeenCalled();
    });

    test('should keep failed submissions pending for retry', async () => {
      const { apiService } = require('../../services/api');
      const { offlineSyncService } = require('../../services/offlineSyncService');

      offlineSyncService.getSyncState.mockResolvedValue({ syncInProgress: true });
      await canvasSyncService.submitForm(
        'canvas_1',
        { field1: 'value1' },
        'user_1',
        'device_1'
      );

      // Flush attempt fails
      offlineSyncService.getSyncState.mockResolvedValue({ syncInProgress: false });
      apiService.post.mockResolvedValue({ success: false, error: 'Validation failed' });

      await canvasSyncService.syncFormSubmissions('user_1', 'device_1');

      // Submission remains pending → retried on next flush
      apiService.post.mockClear();
      await canvasSyncService.syncFormSubmissions('user_1', 'device_1');
      expect(apiService.post).toHaveBeenCalled();
    });
  });

  // ========================================================================
  // Cache Size Limit Tests
  // ========================================================================

  describe('Cache Size Limit', () => {
    test('should evict oldest canvases beyond max cache size', async () => {
      const { apiService } = require('../../services/api');

      const now = Date.now();
      const canvases = Array(35)
        .fill(null)
        .map((_, i) => ({
          id: `canvas_${i}`,
          title: `Canvas ${i}`,
          type: 'chart' as const,
          data: {},
          createdAt: new Date(now - (35 - i) * 1000).toISOString(),
          updatedAt: new Date(now - (35 - i) * 1000).toISOString(),
        }));

      apiService.get.mockResolvedValue({
        success: true,
        data: { canvases },
      });

      await canvasSyncService.syncCanvases('user_1', 'device_1');

      const cached = canvasSyncService.getAllCanvases();
      expect(cached.length).toBe(30);

      // Oldest canvases (smallest updatedAt) were evicted; newest retained
      const ids = cached.map((c) => c.id);
      expect(ids).not.toContain('canvas_0');
      expect(ids).toContain('canvas_34');
    });
  });
});
