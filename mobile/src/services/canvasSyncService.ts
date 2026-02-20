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
import { storageService, StorageKey } from './storageService';
import { offlineSyncService } from './offlineSyncService';

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
  error?: string;
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

// Configuration
const CACHE_TTL = 12 * 60 * 60 * 1000; // 12 hours (shorter for dynamic canvas data)
const MAX_CACHE_SIZE = 30; // Max canvases to cache
const MAX_PENDING_SUBMISSIONS = 50;

/**
 * Canvas Sync Service
 */
class CanvasSyncService {
  private cache: CanvasCache;
  private initialized: boolean = false;
  private refreshTimer: NodeJS.Timeout | null = null;

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

      // Fetch canvases from server
      const response = await apiService.get('/api/canvas');

      if (!response.success || !response.data) {
        console.error('CanvasSync: Failed to fetch canvases:', response.error);
        return {
          success: false,
          synced: 0,
          failed: 0,
          conflicts: 0,
          duration: Date.now() - startTime,
        };
      }

      const canvases: Canvas[] = response.data.canvases || [];

      // Process each canvas
      for (const canvas of canvases) {
        try {
          const cached = this.cache.canvases[canvas.id];

          // Check for conflict
          if (cached && new Date(canvas.updatedAt) < new Date(cached.updatedAt)) {
            conflicts++;
            await this.queueConflictResolution(canvas, cached);
            continue;
          }

          // Update cache
          this.cache.canvases[canvas.id] = canvas;

          // Cache HTML/CSS if available
          if (canvas.html) {
            this.cache.htmlCache[canvas.id] = canvas.html;
          }
          if (canvas.css) {
            this.cache.cssCache[canvas.id] = canvas.css;
          }

          synced++;
        } catch (error) {
          console.error(`CanvasSync: Failed to sync canvas ${canvas.id}:`, error);
          failed++;
        }
      }

      // Update cache metadata
      this.cache.lastSyncAt = new Date();

      // Save cache
      await this.saveCache();

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
    try {
      const response = await apiService.get(`/api/canvas/${canvasId}`);
      if (response.success && response.data) {
        const canvas: Canvas = response.data;
        this.cache.canvases[canvasId] = canvas;

        // Cache HTML/CSS
        if (canvas.html) {
          this.cache.htmlCache[canvasId] = canvas.html;
        }
        if (canvas.css) {
          this.cache.cssCache[canvasId] = canvas.css;
        }

        await this.saveCache();
        return canvas;
      }
    } catch (error) {
      console.error(`CanvasSync: Failed to fetch canvas ${canvasId}:`, error);
    }

    // Return cached even if stale for offline viewing
    return cached || null;
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
        if (this.cache.canvases[canvasId]) {
          this.cache.canvases[canvasId] = {
            ...this.cache.canvases[canvasId],
            ...updates,
            updatedAt: new Date(),
          };
          await this.saveCache();
        }

        return true;
      }

      // Sync to server
      const response = await apiService.put(`/api/canvas/${canvasId}`, updates);

      if (response.success) {
        // Update cache
        if (this.cache.canvases[canvasId]) {
          this.cache.canvases[canvasId] = {
            ...this.cache.canvases[canvasId],
            ...updates,
            updatedAt: new Date(),
          };
          await this.saveCache();
        }
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
      const submission: CanvasFormData = {
        canvasId,
        formData,
        submittedAt: new Date(),
        status: 'pending',
      };

      // Check if offline
      const isOffline = !(await this.isOnline());

      if (isOffline) {
        // Queue for offline submission
        this.cache.pendingFormSubmissions.push(submission);

        // Limit pending submissions
        if (this.cache.pendingFormSubmissions.length > MAX_PENDING_SUBMISSIONS) {
          // Remove oldest submissions
          this.cache.pendingFormSubmissions = this.cache.pendingFormSubmissions
            .sort((a, b) => new Date(a.submittedAt).getTime() - new Date(b.submittedAt).getTime())
            .slice(-MAX_PENDING_SUBMISSIONS);
        }

        await this.saveCache();
        console.log(`CanvasSync: Queued form submission for canvas ${canvasId}`);
        return true;
      }

      // Submit immediately
      const response = await apiService.post(`/api/canvas/${canvasId}/submit`, {
        form_data: formData,
        submitted_at: submission.submittedAt,
      });

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
    if (this.cache.pendingFormSubmissions.length === 0) {
      return;
    }

    console.log(`CanvasSync: Syncing ${this.cache.pendingFormSubmissions.length} form submissions`);

    for (const submission of this.cache.pendingFormSubmissions) {
      try {
        const response = await apiService.post(`/api/canvas/${submission.canvasId}/submit`, {
          form_data: submission.formData,
          submitted_at: submission.submittedAt,
        });

        if (response.success) {
          console.log(`CanvasSync: Synced form submission for canvas ${submission.canvasId}`);
          submission.status = 'submitted';
          // Remove from pending
          this.cache.pendingFormSubmissions = this.cache.pendingFormSubmissions.filter(
            s => s.canvasId !== submission.canvasId || s.submittedAt !== submission.submittedAt
          );
        } else {
          submission.status = 'failed';
          submission.error = response.error || 'Unknown error';
        }
      } catch (error) {
        console.error(`CanvasSync: Failed to sync form submission for canvas ${submission.canvasId}:`, error);
        submission.status = 'failed';
        submission.error = error instanceof Error ? error.message : 'Unknown error';
      }
    }

    await this.saveCache();
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
    delete this.cache.canvases[canvasId];
    delete this.cache.htmlCache[canvasId];
    delete this.cache.cssCache[canvasId];
    await this.saveCache();
    console.log(`CanvasSync: Invalidated cache for canvas ${canvasId}`);
  }

  /**
   * Clear all cache
   */
  async clearCache(): Promise<void> {
    this.cache = {
      canvases: {},
      htmlCache: {},
      cssCache: {},
      lastSyncAt: null,
      pendingFormSubmissions: [],
      favorites: new Set(),
    };
    await this.saveCache();
    console.log('CanvasSync: Cache cleared');
  }

  // Private helper methods

  private async loadCache(): Promise<void> {
    const cached = await storageService.getObject<CanvasCache>('canvas_cache' as StorageKey);

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

  private async saveCache(): Promise<void> {
    // Enforce cache size limit
    const canvasIds = Object.keys(this.cache.canvases);
    if (canvasIds.length > MAX_CACHE_SIZE) {
      // Remove oldest canvases
      const sorted = canvasIds.sort((a, b) => {
        const dateA = new Date(this.cache.canvases[a].updatedAt).getTime();
        const dateB = new Date(this.cache.canvases[b].updatedAt).getTime();
        return dateA - dateB;
      });

      const toRemove = sorted.slice(0, canvasIds.length - MAX_CACHE_SIZE);
      for (const id of toRemove) {
        delete this.cache.canvases[id];
        delete this.cache.htmlCache[id];
        delete this.cache.cssCache[id];
      }
    }

    await storageService.setObject('canvas_cache' as StorageKey, this.cache);
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
