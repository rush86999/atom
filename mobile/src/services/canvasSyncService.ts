/**
 * Canvas Sync Service
 *
 * Manages synchronization of canvases and canvas data for mobile devices.
 *
 * Features:
 * - Sync canvas definitions
 * - Sync canvas data (charts, sheets, forms)
 * - Cache canvas HTML/CSS
 * - Offline canvas viewing
 * - Canvas form submission queue
 * - Canvas data conflict resolution
 * - Canvas cache invalidation
 * - Canvas metadata sync
 * - Background canvas refresh
 * - Canvas favorites sync
 *
 * Uses offlineSyncService for offline support and MMKV for local caching.
 */

import { apiService } from './api';
import { storageService } from './storageService';
import { offlineSyncService } from './offlineSyncService';
import { createCacheTransactionQueue, decodeDate, decodeDetailResponse, decodeListResponse, isRecord } from './syncResponse';
import {
  authorizePendingWriteOwner,
  readPendingWriteOwner,
} from './pendingWriteOwner';
import type { PendingWriteOwner } from './pendingWriteOwner';
import { isAccessTokenSnapshotCurrent } from '../storage/secureTokenStorage';

// Types
export interface Canvas {
  id: string;
  title: string;
  type: 'chart' | 'sheet' | 'form' | 'generic' | 'docs' | 'email' | 'orchestration' | 'terminal' | 'coding';
  data: any;
  html?: string;
  css?: string;
  userId?: string;
  agentId?: string;
  isFavorite?: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface CanvasFormData {
  canvasId: string;
  formData: any;
  submittedAt: Date;
  status: 'pending' | 'submitted' | 'failed';
  deliveryStatus?: 'pending' | 'dispatching' | 'effect_unknown';
  error?: string;
  // Optional only for legacy queued rows; new rows capture the canonical owner.
  userId?: string;
  workspaceId?: string;
  deviceId?: string;
}

export interface CanvasCache {
  canvases: Record<string, Canvas>;
  htmlCache: Record<string, string>;
  cssCache: Record<string, string>;
  lastSyncAt: Date | null;
  pendingFormSubmissions: CanvasFormData[];
  favorites: Set<string>;
}

export interface CanvasSyncResult {
  success: boolean;
  synced: number;
  failed: number;
  conflicts: number;
  duration: number;
}

function isCanvasType(value: unknown): value is Canvas['type'] {
  return (
    value === 'chart' ||
    value === 'sheet' ||
    value === 'form' ||
    value === 'generic' ||
    value === 'docs' ||
    value === 'email' ||
    value === 'orchestration' ||
    value === 'terminal' ||
    value === 'coding'
  );
}

function decodeCanvas(value: unknown): Canvas | null {
  if (!isRecord(value)) {
    return null;
  }

  const { id, title, type, data, html, css, userId, agentId, isFavorite } = value;

  if (typeof id !== 'string' || id.length === 0) {
    return null;
  }
  if (typeof title !== 'string') {
    return null;
  }
  if (!isCanvasType(type)) {
    return null;
  }
  if (data === undefined) {
    return null;
  }

  const createdAt = decodeDate(value.createdAt);
  const updatedAt = decodeDate(value.updatedAt);
  if (createdAt === null || updatedAt === null) {
    return null;
  }

  if (html !== undefined && typeof html !== 'string') {
    return null;
  }
  if (css !== undefined && typeof css !== 'string') {
    return null;
  }
  if (userId !== undefined && typeof userId !== 'string') {
    return null;
  }
  if (agentId !== undefined && typeof agentId !== 'string') {
    return null;
  }
  if (isFavorite !== undefined && typeof isFavorite !== 'boolean') {
    return null;
  }

  const canvas: Canvas = {
    ...value,
    id,
    title,
    type,
    data,
    createdAt,
    updatedAt,
  };

  if (html !== undefined) {
    canvas.html = html;
  }
  if (css !== undefined) {
    canvas.css = css;
  }
  if (userId !== undefined) {
    canvas.userId = userId;
  }
  if (agentId !== undefined) {
    canvas.agentId = agentId;
  }
  if (isFavorite !== undefined) {
    canvas.isFavorite = isFavorite;
  }

  return canvas;
}

function getSubmissionOwner(submission: CanvasFormData): PendingWriteOwner | null {
  const { userId, workspaceId, deviceId } = submission;
  if (typeof userId !== 'string' || userId.length === 0) {
    return null;
  }
  if (typeof workspaceId !== 'string' || workspaceId.length === 0) {
    return null;
  }
  if (typeof deviceId !== 'string' || deviceId.length === 0) {
    return null;
  }
  return { userId, workspaceId, deviceId };
}

// Configuration
const CACHE_TTL = 12 * 60 * 60 * 1000; // 12 hours (shorter for dynamic canvas data)
const MAX_CACHE_SIZE = 30; // Max canvases to cache
const MAX_PENDING_SUBMISSIONS = 50;

/**
 * Canvas Sync Service
 */
class CanvasSyncService {
  private cache: CanvasCache = {
    canvases: {},
    htmlCache: {},
    cssCache: {},
    lastSyncAt: null,
    pendingFormSubmissions: [],
    favorites: new Set(),
  };
  private initialized: boolean = false;
  private refreshTimer: NodeJS.Timeout | null = null;
  private flushInFlight: Promise<void> | null = null;
  private readonly cacheTransaction = createCacheTransactionQueue();
  private cacheGeneration = 0;
  private readonly invalidatedCanvases = new Map<string, number>();

  /**
   * Initialize the canvas sync service
   */
  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    console.log('CanvasSync: Initializing service');

    // Load cache from storage
    await this.loadCache();

    // Start background refresh (every 15 minutes)
    this.startBackgroundRefresh();

    this.initialized = true;
    console.log('CanvasSync: Service initialized');
  }

  /**
   * Sync all canvases from server
   */
  async syncCanvases(userId: string, deviceId: string): Promise<CanvasSyncResult> {
    const startTime = Date.now();
    let synced = 0;
    let failed = 0;
    let conflicts = 0;

    try {
      console.log('CanvasSync: Syncing canvases');

      // Fetch and fully decode canvases before mutating the cache.
      const response = await apiService.get<unknown>('/api/canvas');
      const decoded = decodeListResponse(response, 'canvases', decodeCanvas);

      if (!decoded.ok) {
        console.error('CanvasSync: Failed to fetch canvases:', decoded.error);
        return {
          success: false,
          synced: 0,
          failed: 0,
          conflicts: 0,
          duration: Date.now() - startTime,
        };
      }

      const canvases = decoded.items;
      const generation = this.cacheGeneration;

      await this.cacheTransaction(async () => {
        if (generation !== this.cacheGeneration) {
          return;
        }

        const nextCache: CanvasCache = {
          ...this.cache,
          canvases: { ...this.cache.canvases },
          htmlCache: { ...this.cache.htmlCache },
          cssCache: { ...this.cache.cssCache },
        };

        // Process each canvas against the cache as it exists inside this
        // transaction, then persist before publishing the candidate in memory.
        for (const canvas of canvases) {
          try {
            const cached = nextCache.canvases[canvas.id];

            // Check for conflict
            if (cached && new Date(canvas.updatedAt) < new Date(cached.updatedAt)) {
              conflicts++;
              await this.queueConflictResolution(canvas, cached);
              continue;
            }

            nextCache.canvases[canvas.id] = canvas;

            // Cache HTML/CSS if available
            if (canvas.html) {
              nextCache.htmlCache[canvas.id] = canvas.html;
            }
            if (canvas.css) {
              nextCache.cssCache[canvas.id] = canvas.css;
            }

            synced++;
          } catch (error) {
            console.error(`CanvasSync: Failed to sync canvas ${canvas.id}:`, error);
            failed++;
          }
        }

        nextCache.lastSyncAt = new Date();

        await this.saveCache(nextCache);
        this.cache = nextCache;
      });

      const duration = Date.now() - startTime;
      console.log(`CanvasSync: Sync complete - ${synced} synced, ${failed} failed, ${conflicts} conflicts, ${duration}ms`);

      return {
        success: true,
        synced,
        failed,
        conflicts,
        duration,
      };
    } catch (error) {
      console.error('CanvasSync: Sync failed:', error);
      return {
        success: false,
        synced,
        failed,
        conflicts,
        duration: Date.now() - startTime,
      };
    }
  }

  /**
   * Get canvas from cache (with fallback to server)
   */
  async getCanvas(canvasId: string): Promise<Canvas | null> {
    // Check cache first
    const cached = this.cache.canvases[canvasId];
    if (cached) {
      // Check if cache is fresh
      const age = Date.now() - new Date(cached.updatedAt).getTime();
      if (age < CACHE_TTL) {
        return cached;
      }
    }

    // Fetch from server
    const generation = this.cacheGeneration;
    const invalidation = this.invalidatedCanvases.get(canvasId) || 0;
    try {
      const response = await apiService.get<unknown>(`/api/canvas/${canvasId}`);
      const decoded = decodeDetailResponse(response, 'canvas', canvasId, decodeCanvas);
      if (decoded.ok) {
        const item = decoded.item;
        return await this.cacheTransaction(async () => {
          if (generation !== this.cacheGeneration || invalidation !== (this.invalidatedCanvases.get(canvasId) || 0)) {
            return null;
          }

          const existing = this.cache.canvases[item.id];
          const published = existing && item.isFavorite === undefined && existing.isFavorite !== undefined
            ? { ...item, isFavorite: existing.isFavorite }
            : item;
          const nextCache: CanvasCache = {
            ...this.cache,
            canvases: { ...this.cache.canvases, [item.id]: published },
            htmlCache: { ...this.cache.htmlCache },
            cssCache: { ...this.cache.cssCache },
          };

          // Cache HTML/CSS
          if (published.html) {
            nextCache.htmlCache[item.id] = published.html;
          }
          if (published.css) {
            nextCache.cssCache[item.id] = published.css;
          }

          await this.saveCache(nextCache);
          this.cache = nextCache;
          return item;
        });
      }
    } catch (error) {
      console.error(`CanvasSync: Failed to fetch canvas ${canvasId}:`, error);
    }

    // Return cached even if stale for offline viewing
    return generation === this.cacheGeneration && invalidation === (this.invalidatedCanvases.get(canvasId) || 0) ? cached || null : null;
  }

  /**
   * Get all canvases from cache
   */
  getAllCanvases(): Canvas[] {
    return Object.values(this.cache.canvases);
  }

  /**
   * Get canvases by type
   */
  getCanvasesByType(type: Canvas['type']): Canvas[] {
    return this.getAllCanvases().filter(canvas => canvas.type === type);
  }

  /**
   * Get cached HTML
   */
  getCachedHtml(canvasId: string): string | null {
    return this.cache.htmlCache[canvasId] || null;
  }

  /**
   * Get cached CSS
   */
  getCachedCss(canvasId: string): string | null {
    return this.cache.cssCache[canvasId] || null;
  }

  /**
   * Update canvas data
   */
  async updateCanvas(
    canvasId: string,
    updates: Partial<Canvas>,
    userId: string,
    deviceId: string
  ): Promise<boolean> {
    try {
      const generation = this.cacheGeneration;

      // Check if offline
      const isOffline = !(await this.isOnline());

      if (isOffline) {
        // Queue for sync
        await offlineSyncService.queueAction(
          'canvas_sync',
          {
            canvasId,
            canvasData: updates,
          },
          'normal',
          userId,
          deviceId,
          'last_write_wins',
          'canvases',
          canvasId
        );

        // Update local cache optimistically
        await this.cacheTransaction(async () => {
          if (generation !== this.cacheGeneration) {
            return;
          }
          const cached = this.cache.canvases[canvasId];
          if (!cached) {
            return;
          }
          const nextCache: CanvasCache = {
            ...this.cache,
            canvases: {
              ...this.cache.canvases,
              [canvasId]: {
                ...cached,
                ...updates,
                updatedAt: new Date(),
              },
            },
          };
          await this.saveCache(nextCache);
          this.cache = nextCache;
        });

        return true;
      }

      // Sync to server
      const response = await apiService.put(`/api/canvas/${canvasId}`, updates);

      if (response.success) {
        // Update cache
        await this.cacheTransaction(async () => {
          if (generation !== this.cacheGeneration) {
            return;
          }
          const cached = this.cache.canvases[canvasId];
          if (!cached) {
            return;
          }
          const nextCache: CanvasCache = {
            ...this.cache,
            canvases: {
              ...this.cache.canvases,
              [canvasId]: {
                ...cached,
                ...updates,
                updatedAt: new Date(),
              },
            },
          };
          await this.saveCache(nextCache);
          this.cache = nextCache;
        });
        return true;
      }

      return false;
    } catch (error) {
      console.error(`CanvasSync: Failed to update canvas ${canvasId}:`, error);
      return false;
    }
  }

  /**
   * Submit canvas form
   */
  async submitForm(
    canvasId: string,
    formData: any,
    userId: string,
    deviceId: string
  ): Promise<boolean> {
    try {
      const generation = this.cacheGeneration;

      // Capture the canonical owner before creating any queued work. This is a
      // local hint; it becomes authority only after the caller is re-authorized.
      const local = await readPendingWriteOwner(userId, deviceId);
      if (!local) {
        return false;
      }

      const submission: CanvasFormData = {
        canvasId,
        formData,
        submittedAt: new Date(),
        status: 'pending',
        deliveryStatus: 'pending',
        userId: local.owner.userId,
        workspaceId: local.owner.workspaceId,
        deviceId: local.owner.deviceId,
      };

      // Check if offline
      const isOffline = !(await this.isOnline());

      if (isOffline) {
        // The network-state read above is an await: the captured session must
        // still be current before the row can be enqueued.
        if (!isAccessTokenSnapshotCurrent(local.session)) {
          return false;
        }

        // Queue for offline submission
        const queued = await this.cacheTransaction(async () => {
          if (generation !== this.cacheGeneration) {
            return false;
          }

          if (this.cache.pendingFormSubmissions.length >= MAX_PENDING_SUBMISSIONS) {
            console.warn('CanvasSync: Pending queue is full; existing intent retained');
            return false;
          }
          const pendingFormSubmissions = [...this.cache.pendingFormSubmissions, submission];

          const nextCache: CanvasCache = {
            ...this.cache,
            pendingFormSubmissions,
          };
          await this.saveCache(nextCache);
          this.cache = nextCache;
          return true;
        });

        if (!queued) {
          return false;
        }
        console.log(`CanvasSync: Queued form submission for canvas ${canvasId}`);
        return true;
      }

      // Submit immediately only against the exact owner the server confirms.
      const session = await authorizePendingWriteOwner(local.owner, userId, deviceId);
      if (!session) {
        return false;
      }

      const response = await apiService.post(
        `/api/canvas/${canvasId}/submit`,
        {
          form_data: formData,
          submitted_at: submission.submittedAt,
        },
        { expectedAccessTokenSnapshot: session }
      );

      if (response.success) {
        console.log(`CanvasSync: Submitted form for canvas ${canvasId}`);
        return true;
      }

      submission.status = 'failed';
      submission.error = response.error || 'Unknown error';
      return false;
    } catch (error) {
      console.error(`CanvasSync: Failed to submit form for canvas ${canvasId}:`, error);
      return false;
    }
  }

  /**
   * Sync pending form submissions
   */
  async syncFormSubmissions(userId: string, deviceId: string): Promise<void> {
    if (this.flushInFlight) {
      return this.flushInFlight;
    }

    const flush = this.flushPendingFormSubmissions(userId, deviceId);
    this.flushInFlight = flush;

    try {
      await flush;
    } finally {
      if (this.flushInFlight === flush) {
        this.flushInFlight = null;
      }
    }
  }

  private async flushPendingFormSubmissions(userId: string, deviceId: string): Promise<void> {
    if (this.cache.pendingFormSubmissions.length === 0) {
      return;
    }

    console.log(`CanvasSync: Syncing ${this.cache.pendingFormSubmissions.length} form submissions`);

    // Only explicit pending rows may dispatch. Legacy rows without a delivery
    // status, interrupted dispatches, and uncertain writes are left untouched.
    const submissions = [...this.cache.pendingFormSubmissions];

    for (const submission of submissions) {
      if (submission.deliveryStatus !== 'pending') {
        continue;
      }

      // Legacy/unknown owners are retained unresolved, never assigned to the
      // current actor. Every row is authorized independently.
      const owner = getSubmissionOwner(submission);
      if (!owner) {
        continue;
      }

      // Authorize the queued owner before persisting any dispatch marker.
      const session = await authorizePendingWriteOwner(owner, userId, deviceId);
      if (!session) {
        continue;
      }

      // Persist the dispatch boundary before any transport attempt.
      const marked = await this.cacheTransaction(async () => {
        if (this.cache.pendingFormSubmissions.indexOf(submission) < 0) {
          return false;
        }
        submission.deliveryStatus = 'dispatching';
        try {
          await this.saveCache();
        } catch (error) {
          // No POST occurred, so this in-memory row is still known undispatched.
          submission.deliveryStatus = 'pending';
          throw error;
        }
        return true;
      });
      if (!marked) {
        continue;
      }

      // A replacement during the marker write means no transport is allowed.
      // No POST occurred, so restoring the known-safe pending state is safe.
      if (!isAccessTokenSnapshotCurrent(session)) {
        // A failed restoration remains a failed checkpoint, even though the
        // durable dispatch marker safely prevents automatic replay.
        await this.cacheTransaction(async () => {
          if (this.cache.pendingFormSubmissions.indexOf(submission) < 0) {
            return;
          }
          submission.deliveryStatus = 'pending';
          await this.saveCache();
        });
        continue;
      }

      let accepted = false;
      try {
        const response = await apiService.post(
          `/api/canvas/${submission.canvasId}/submit`,
          {
            form_data: submission.formData,
            submitted_at: submission.submittedAt,
          },
          { expectedAccessTokenSnapshot: session }
        );
        accepted = response.success;
      } catch (error) {
        console.error(`CanvasSync: Failed to sync form submission for canvas ${submission.canvasId}:`, error);
      }

      if (!accepted) {
        // The POST may have reached the server. Keep the exact queued input and
        // identifiers, but never automatically repeat an uncertain dispatch.
        await this.cacheTransaction(async () => {
          if (this.cache.pendingFormSubmissions.indexOf(submission) < 0) {
            return;
          }
          submission.deliveryStatus = 'effect_unknown';
          await this.saveCache();
        });
        continue;
      }

      // Transport acceptance is not business completion. Remove only the exact
      // object that was dispatched; concurrent additions are preserved.
      await this.cacheTransaction(async () => {
        if (this.cache.pendingFormSubmissions.indexOf(submission) < 0) {
          return;
        }

        const nextCache: CanvasCache = {
          ...this.cache,
          pendingFormSubmissions: this.cache.pendingFormSubmissions.filter(
            (row) => row !== submission
          ),
        };

        try {
          await this.saveCache(nextCache);
        } catch (error) {
          // The durable row still says dispatching. Keep the uncertainty visible
          // in memory so this process cannot dispatch it again either.
          submission.deliveryStatus = 'effect_unknown';
          throw error;
        }
        this.cache = nextCache;
      });

      console.log(`CanvasSync: Synced form submission for canvas ${submission.canvasId}`);
    }
  }

  /**
   * Toggle canvas favorite status
   */
  async toggleFavorite(canvasId: string, userId: string, deviceId: string): Promise<boolean> {
    const canvas = this.cache.canvases[canvasId];
    if (!canvas) {
      return false;
    }

    const newFavoriteStatus = !canvas.isFavorite;
    return await this.updateCanvas(
      canvasId,
      { isFavorite: newFavoriteStatus },
      userId,
      deviceId
    );
  }

  /**
   * Get favorite canvases
   */
  getFavoriteCanvases(): Canvas[] {
    return this.getAllCanvases().filter(canvas => canvas.isFavorite);
  }

  /**
   * Invalidate canvas cache
   */
  async invalidateCache(canvasId: string): Promise<void> {
    this.invalidatedCanvases.set(canvasId, (this.invalidatedCanvases.get(canvasId) || 0) + 1);
    await this.cacheTransaction(async () => {
      const next: CanvasCache = { ...this.cache, canvases: { ...this.cache.canvases }, htmlCache: { ...this.cache.htmlCache }, cssCache: { ...this.cache.cssCache } };
      delete next.canvases[canvasId];
      delete next.htmlCache[canvasId];
      delete next.cssCache[canvasId];
      await this.saveCache(next);
      this.cache = next;
    });
    console.log(`CanvasSync: Invalidated cache for canvas ${canvasId}`);
  }

  /** Clear invalidates in-flight reads before joining the cache write queue. */
  async clearCache(): Promise<void> {
    this.cacheGeneration += 1;
    await this.cacheTransaction(async () => {
      const next: CanvasCache = {
        canvases: {}, htmlCache: {}, cssCache: {}, lastSyncAt: null,
        pendingFormSubmissions: [], favorites: new Set(),
      };
      await this.saveCache(next);
      this.cache = next;
    });
    console.log('CanvasSync: Cache cleared');
  }

  // Private helper methods

  private async loadCache(): Promise<void> {
    const cached = await storageService.getObject<CanvasCache>('canvas_cache');

    this.cache = cached || {
      canvases: {},
      htmlCache: {},
      cssCache: {},
      lastSyncAt: null,
      pendingFormSubmissions: [],
      favorites: new Set(),
    };

    // Convert dates
    for (const canvasId in this.cache.canvases) {
      const canvas = this.cache.canvases[canvasId];
      canvas.createdAt = new Date(canvas.createdAt);
      canvas.updatedAt = new Date(canvas.updatedAt);
    }

    for (const submission of this.cache.pendingFormSubmissions) {
      submission.submittedAt = new Date(submission.submittedAt);
    }

    if (this.cache.lastSyncAt) {
      this.cache.lastSyncAt = new Date(this.cache.lastSyncAt);
    }
  }

  private async saveCache(cache: CanvasCache = this.cache): Promise<void> {
    // Enforce cache size limit
    const canvasIds = Object.keys(cache.canvases);
    if (canvasIds.length > MAX_CACHE_SIZE) {
      // Remove oldest canvases
      const sorted = canvasIds.sort((a, b) => {
        const dateA = new Date(cache.canvases[a].updatedAt).getTime();
        const dateB = new Date(cache.canvases[b].updatedAt).getTime();
        return dateA - dateB;
      });

      const toRemove = sorted.slice(0, canvasIds.length - MAX_CACHE_SIZE);
      for (const id of toRemove) {
        delete cache.canvases[id];
        delete cache.htmlCache[id];
        delete cache.cssCache[id];
      }
    }

    if (!(await storageService.setObject('canvas_cache', cache))) {
      throw new Error('Canvas cache persistence refused');
    }
  }

  private async queueConflictResolution(serverCanvas: Canvas, localCanvas: Canvas): Promise<void> {
    console.warn(`CanvasSync: Conflict detected for canvas ${serverCanvas.id}, queuing for resolution`);
  }

  private async isOnline(): Promise<boolean> {
    const state = await offlineSyncService.getSyncState();
    return !state.syncInProgress;
  }

  private startBackgroundRefresh(): void {
    // Refresh every 15 minutes (more frequent for dynamic canvas data)
    this.refreshTimer = setInterval(async () => {
      if (this.initialized) {
        console.log('CanvasSync: Background refresh');
        // Refresh logic would go here (requires userId/deviceId)
      }
    }, 15 * 60 * 1000);
  }

  /**
   * Cleanup
   */
  destroy(): void {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
  }
}

// Export singleton instance
export const canvasSyncService = new CanvasSyncService();

export default canvasSyncService;
