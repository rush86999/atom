/**
 * Offline Sync Service
 *
 * Manages offline action queuing and synchronization for mobile devices.
 *
 * Features:
 * - Queue actions when device is offline
 * - Automatic sync when connection restored
 * - Conflict resolution (last-write-wins, manual)
 * - Priority-based execution
 * - Retry logic with exponential backoff
 *
 * Uses MMKV for fast, reliable storage of offline actions.
 */

import NetInfo from '@react-native-community/netinfo';
import { storageService, StorageKey } from './storageService';
import { storageService as mmkvStorage } from './storageService';
import { apiService } from './api';

// Types
export type OfflineActionType =
  | 'agent_message'
  | 'workflow_trigger'
  | 'form_submit'
  | 'feedback'
  | 'canvas_update'
  | 'device_command'
  | 'agent_sync'
  | 'workflow_sync'
  | 'canvas_sync'
  | 'episode_sync';

export type OfflineActionStatus = 'pending' | 'syncing' | 'completed' | 'failed';

export type ConflictResolution =
  | 'last_write_wins'
  | 'manual'
  | 'server_wins'
  | 'client_wins'
  | 'merge';

export type SyncPriority = 'critical' | 'high' | 'normal' | 'low';
export type EntityType = 'agents' | 'workflows' | 'canvases' | 'episodes';

export interface OfflineAction {
  id: string;
  type: OfflineActionType;
  payload: any;
  priority: number; // 0-10, higher = more important
  priorityLevel: SyncPriority;
  status: OfflineActionStatus;
  createdAt: Date;
  syncAttempts: number;
  lastSyncError?: string;
  conflictResolution?: ConflictResolution;
  userId: string;
  deviceId: string;
  entityType?: EntityType;
  entityId?: string;
  deltaHash?: string; // For delta sync
  sizeBytes?: number; // Track storage size
}

export interface SyncResult {
  cycleId?: string;
  success: boolean;
  skipped?: number;
  cancelled?: boolean;
  synced: number;
  failed: number;
  conflicts: number;
  duration: number;
  entities: {
    agents: number;
    workflows: number;
    canvases: number;
    episodes: number;
  };
  bytesTransferred: number;
}

/** Local pass bookkeeping, not a receipt certifying an external business effect. */
export interface SyncEntityProgress {
  type: EntityType | 'other';
  total: number;
  synced: number;
  failed: number;
  conflicts: number;
  skipped: number;
}

export interface SyncCycleSnapshot {
  id: string;
  startedAt: number;
  actionIds: string[];
  entityProgress: SyncEntityProgress[];
  result: (SyncResult & { cycleId: string }) | null;
}

export interface SyncState {
  cycle?: SyncCycleSnapshot;
  lastSyncAt: Date | null;
  lastSuccessfulSyncAt: Date | null;
  pendingCount: number;
  syncInProgress: boolean;
  consecutiveFailures: number;
  currentOperation: string;
  syncProgress: number; // 0-100
  cancelled: boolean;
}

export interface SyncQualityMetrics {
  totalSyncs: number;
  successfulSyncs: number;
  failedSyncs: number;
  conflictRate: number;
  avgSyncDuration: number;
  avgBytesTransferred: number;
  lastQualityCheck: Date;
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

// Configuration
const MAX_SYNC_ATTEMPTS = 5;
const BASE_RETRY_DELAY = 1000; // 1 second
const MAX_RETRY_DELAY = 60000; // 1 minute
const SYNC_BATCH_SIZE = 10; // Process up to 10 actions per sync
const STORAGE_QUOTA_BYTES = 50 * 1024 * 1024; // 50MB default quota
const WARNING_THRESHOLD = 0.8; // 80%
const ENFORCEMENT_THRESHOLD = 0.95; // 95%
const DELTA_SYNC_ENABLED = true;

// Priority level mappings
const PRIORITY_LEVELS: Record<SyncPriority, number> = {
  critical: 10,
  high: 7,
  normal: 5,
  low: 2,
};

/**
 * Offline Sync Service
 */
class OfflineSyncService {
  private isOnline: boolean = true;
  private syncInProgress: boolean = false;
  private queueMutationTail: Promise<void> = Promise.resolve();
  private syncTimer: NodeJS.Timeout | null = null;
  private listeners: Set<(state: SyncState) => void> = new Set();
  private progressListeners: Set<(progress: number, operation: string) => void> = new Set();
  private conflictListeners: Set<(conflict: OfflineAction) => void> = new Set();
  private cycleSequence = 0;
  private qualityMetrics: SyncQualityMetrics = {
    totalSyncs: 0, successfulSyncs: 0, failedSyncs: 0, conflictRate: 0,
    avgSyncDuration: 0, avgBytesTransferred: 0, lastQualityCheck: new Date(),
  };
  private cancelRequested: boolean = false;

  /**
   * Initialize the sync service
   */
  async initialize(): Promise<void> {
    // Check initial network state
    const netInfo = await NetInfo.fetch();
    this.isOnline = netInfo.isConnected ?? false;

    // Listen for network changes
    NetInfo.addEventListener((state) => {
      const wasOnline = this.isOnline;
      this.isOnline = state.isConnected ?? false;

      if (!wasOnline && this.isOnline) {
        // Connection restored, trigger sync
        console.log('OfflineSync: Connection restored, triggering sync');
        this.triggerSync();
      }

      this.notifyListeners();
    });

    // Load sync state
    await this.loadSyncState();

    // Load quality metrics
    await this.loadQualityMetrics();

    // Initialize storage quota
    await this.initializeStorageQuota();

    // Start periodic sync (every 5 minutes)
    this.startPeriodicSync();

    // Start cleanup task (every hour)
    this.startCleanupTask();
  }

  /**
   * Add an action to the offline queue
   */
  async queueAction(
    type: OfflineActionType,
    payload: any,
    priorityLevel: SyncPriority = 'normal',
    userId: string,
    deviceId: string,
    conflictResolution: ConflictResolution = 'last_write_wins',
    entityType?: EntityType,
    entityId?: string
  ): Promise<string> {
    const priority = PRIORITY_LEVELS[priorityLevel];
    const sizeBytes = this.calculateActionSize(payload);

    const action: OfflineAction = {
      id: `action_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type,
      payload,
      priority,
      priorityLevel,
      status: 'pending',
      createdAt: new Date(),
      syncAttempts: 0,
      conflictResolution,
      userId,
      deviceId,
      entityType,
      entityId,
      sizeBytes,
      deltaHash: DELTA_SYNC_ENABLED ? this.generateDeltaHash(payload) : undefined,
    };

    try {
      return await this.withQueueMutation(async () => {
        // Check storage quota before adding
        const quotaOk = await this.checkStorageQuota(sizeBytes);
        if (!quotaOk) {
          throw new Error('Offline storage quota reached. Resolve or explicitly remove queued work before adding more.');
        }

        // Get existing queue
        const queue = await this.getQueue();

        // Add new action (sorted by priority, then by creation time)
        queue.push(action);
        queue.sort((a, b) => {
          if (a.priority !== b.priority) {
            return b.priority - a.priority; // Higher priority first
          }
          return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
        });

        // Save queue
        await this.saveQueue(queue);

        console.log(`OfflineSync: Queued action ${action.id} (type: ${type}, priority: ${priorityLevel})`);

        // If online, trigger immediate sync for high-priority actions
        if (this.isOnline && priority >= 7) {
          this.triggerSync();
        }

        return action.id;
      });
    } catch (error) {
      console.error('OfflineSync: Failed to queue action:', error);
      throw error;
    }
  }

  /**
   * Trigger sync (public method)
   */
  async triggerSync(): Promise<SyncResult> {
    if (this.syncInProgress) {
      console.log('OfflineSync: Sync already in progress');
      return {
        success: false,
        synced: 0,
        failed: 0,
        conflicts: 0,
        duration: 0,
        entities: { agents: 0, workflows: 0, canvases: 0, episodes: 0 },
        bytesTransferred: 0,
      };
    }

    if (!this.isOnline) {
      console.log('OfflineSync: Device is offline, skipping sync');
      return {
        success: false,
        synced: 0,
        failed: 0,
        conflicts: 0,
        duration: 0,
        entities: { agents: 0, workflows: 0, canvases: 0, episodes: 0 },
        bytesTransferred: 0,
      };
    }

    this.syncInProgress = true;
    this.cancelRequested = false;

    const startTime = Date.now();
    let synced = 0;
    let failed = 0;
    let conflicts = 0;
    let skipped = 0;
    let bytesTransferred = 0;
    const entities = { agents: 0, workflows: 0, canvases: 0, episodes: 0 };
    // Identity is local to this service lifetime; no provider-operation guarantee.
    let cycle: SyncCycleSnapshot = {
      id: `sync_${startTime}_${++this.cycleSequence}`, startedAt: startTime,
      actionIds: [], entityProgress: [], result: null,
    };
    const finalize = async (result: SyncResult): Promise<SyncResult> => {
      const bound = { ...result, cycleId: cycle.id };
      cycle = { ...cycle, result: bound };
      try {
        await this.updateSyncState({ cycle, syncInProgress: false, cancelled: !!result.cancelled });
        return bound;
      } catch {
        console.warn('OfflineSync: Observed result could not be recorded; no completion certified.');
        return { ...bound, success: false };
      }
    };

    try {
      // Get pending actions
      const queue = await this.getQueue();
      const pendingActions = queue.filter((a) => a.status === 'pending');
      const kinds: Array<EntityType | 'other'> = ['agents', 'workflows', 'canvases', 'episodes', 'other'];
      cycle.actionIds = pendingActions.map(action => action.id);
      cycle.entityProgress = kinds.map(type => ({
        type, total: pendingActions.filter(action => (action.entityType || 'other') === type).length,
        synced: 0, failed: 0, conflicts: 0, skipped: 0,
      })).filter(row => row.total > 0);
      await this.updateSyncState({ cycle, syncInProgress: true, cancelled: false, syncProgress: 0, currentOperation: 'Preparing sync' });
      this.notifyListeners();

      if (pendingActions.length === 0) {
        console.log('OfflineSync: No pending actions to sync');
        return await finalize({
          success: !this.cancelRequested && queue.every(action => action.status === 'completed'),
          cancelled: this.cancelRequested,
          synced: 0,
          failed: 0,
          conflicts: 0,
          duration: Date.now() - startTime,
          entities,
          bytesTransferred,
        });
      }

      console.log(`OfflineSync: Syncing ${pendingActions.length} actions`);

      // Process in batches
      for (let i = 0; i < pendingActions.length; i += SYNC_BATCH_SIZE) {
        // Check for cancellation
        if (this.cancelRequested) {
          console.log('OfflineSync: Sync cancelled by user');
          break;
        }

        const batch = pendingActions.slice(i, i + SYNC_BATCH_SIZE);
        const progress = Math.floor((i / pendingActions.length) * 100);

        await this.updateSyncState({
          syncProgress: progress,
          currentOperation: `Syncing batch ${Math.floor(i / SYNC_BATCH_SIZE) + 1}`,
        });
        this.notifyProgressListeners(progress, `Syncing batch ${Math.floor(i / SYNC_BATCH_SIZE) + 1}`);

        for (const action of batch) {
          // Check for cancellation
          if (this.cancelRequested) {
            break;
          }

          const row = cycle.entityProgress.find(item => item.type === (action.entityType || 'other'));
          let attemptRecorded = false;
          try {
            const result = await this.syncAction(action);
            if (result.skipped) { skipped++; if (row) row.skipped++; continue; }

            if (result.success) {
              await this.updateActionStatus(action.id, 'completed');
              synced++;
              if (row) row.synced++;
              bytesTransferred += action.sizeBytes || 0;

              // Track entity types
              if (action.entityType && entities[action.entityType] !== undefined) {
                entities[action.entityType]++;
              }

            } else if (result.conflict) {
              await this.updateActionStatus(action.id, 'pending');
              conflicts++;
              if (row) row.conflicts++;
              this.notifyConflictListeners(action);
            } else {
              await this.incrementSyncAttempts(action.id);
              attemptRecorded = true;
              // Retry below the limit; retain exhausted intent as failed for
              // an explicit owner retry/removal instead of silently dropping it.
              if (action.syncAttempts + 1 >= MAX_SYNC_ATTEMPTS) {
                await this.updateActionStatus(action.id, 'failed');
              } else {
                await this.updateActionStatus(action.id, 'pending');
              }
              failed++;
              if (row) row.failed++;
            }
          } catch (error) {
            console.error(`OfflineSync: Failed to sync action ${action.id}:`, error);
            failed++;
            if (row) row.failed++;
            if (!attemptRecorded) await this.incrementSyncAttempts(action.id);
            if (action.syncAttempts + 1 >= MAX_SYNC_ATTEMPTS) {
              await this.updateActionStatus(action.id, 'failed');
            } else {
              await this.updateActionStatus(action.id, 'pending');
            }
          }
        }
        await this.updateSyncState({ cycle: { ...cycle, result: null } });
        this.notifyListeners();
      }

      // Remove completed actions
      await this.removeCompletedActions();

      // Update sync state
      const newQueue = await this.getQueue();
      const now = new Date();
      const successfulCount = synced > 0 ? synced : 0;
      const cancelled = this.cancelRequested;
      const satisfactory = !cancelled && failed === 0 && conflicts === 0 && skipped === 0 && synced === pendingActions.length;

      await this.updateSyncState({
        lastSyncAt: now,
        lastSuccessfulSyncAt: successfulCount > 0 ? now : null,
        pendingCount: newQueue.filter((a) => a.status === 'pending').length,
        consecutiveFailures: failed === 0 ? 0 : (await this.getSyncState()).consecutiveFailures + 1,
        syncProgress: satisfactory ? 100 : Math.floor(((synced + failed + conflicts + skipped) / pendingActions.length) * 100),
        currentOperation: satisfactory ? 'Sync complete' : cancelled ? 'Sync cancelled' : 'Sync incomplete',
      });

      const duration = Date.now() - startTime;

      // Update quality metrics
      await this.updateQualityMetrics({
        totalSyncs: this.qualityMetrics.totalSyncs + 1,
        successfulSyncs: this.qualityMetrics.successfulSyncs + (satisfactory ? 1 : 0),
        failedSyncs: this.qualityMetrics.failedSyncs + (satisfactory ? 0 : 1),
        conflictRate: conflicts / (synced + conflicts || 1),
        avgSyncDuration: (this.qualityMetrics.avgSyncDuration * this.qualityMetrics.totalSyncs + duration) / (this.qualityMetrics.totalSyncs + 1),
        avgBytesTransferred: (this.qualityMetrics.avgBytesTransferred * this.qualityMetrics.totalSyncs + bytesTransferred) / (this.qualityMetrics.totalSyncs + 1),
        lastQualityCheck: now,
      });

      console.log(`OfflineSync: Sync complete - ${synced} synced, ${failed} failed, ${conflicts} conflicts, ${duration}ms, ${bytesTransferred} bytes`);

      return await finalize({
        success: satisfactory,
        synced,
        failed,
        conflicts,
        skipped,
        cancelled,
        duration,
        entities,
        bytesTransferred,
      });
    } catch (error) {
      console.error('OfflineSync: Sync failed:', error);
      await this.updateQualityMetrics({
        totalSyncs: this.qualityMetrics.totalSyncs + 1,
        failedSyncs: this.qualityMetrics.failedSyncs + 1,
        lastQualityCheck: new Date(),
      });
      return await finalize({
        success: false,
        cancelled: this.cancelRequested,
        synced,
        failed,
        conflicts,
        duration: Date.now() - startTime,
        entities,
        bytesTransferred,
      });
    } finally {
      this.syncInProgress = false;
      this.cancelRequested = false;
      try { await this.updateSyncState({ syncInProgress: false }); } catch {
        console.warn('OfflineSync: Terminal state unavailable; no completion certified.');
      }
      this.notifyListeners();
    }
  }

  /**
   * Cancel ongoing sync
   */
  async cancelSync(): Promise<void> {
    if (this.syncInProgress) {
      console.log('OfflineSync: Cancelling sync...');
      this.cancelRequested = true;
      await this.updateSyncState({ cancelled: true });
    }
  }

  /**
   * Subscribe to sync progress updates
   */
  subscribeToProgress(callback: (progress: number, operation: string) => void): () => void {
    this.progressListeners.add(callback);
    return () => {
      this.progressListeners.delete(callback);
    };
  }

  /**
   * Subscribe to conflict notifications
   */
  subscribeToConflicts(callback: (conflict: OfflineAction) => void): () => void {
    this.conflictListeners.add(callback);
    return () => {
      this.conflictListeners.delete(callback);
    };
  }

  /**
   * Get quality metrics
   */
  async getQualityMetrics(): Promise<SyncQualityMetrics> {
    return this.qualityMetrics;
  }

  /**
   * Get storage quota information
   */
  async getStorageQuota(): Promise<StorageQuota> {
    return this.deriveQueueQuota(await this.getQueue());
  }

  /**
   * Sync a single action
   */
  private async syncAction(action: OfflineAction): Promise<{ success: boolean; conflict?: boolean; skipped?: boolean }> {
    let admitted = false;
    try {
      // Apply exponential backoff for retries
      if (action.syncAttempts > 0) {
        const delay = Math.min(
          BASE_RETRY_DELAY * Math.pow(2, action.syncAttempts),
          MAX_RETRY_DELAY
        );
        await new Promise(resolve => setTimeout(resolve, delay));
      }

      // Check if max attempts reached
      if (action.syncAttempts >= MAX_SYNC_ATTEMPTS) {
        console.error(`OfflineSync: Max sync attempts reached for action ${action.id}`);
        return { success: false };
      }

      admitted = await this.claimAction(action);
      if (!admitted) return { success: false, skipped: true };

      switch (action.type) {
        case 'agent_message':
          return await this.syncAgentMessage(action);
        case 'workflow_trigger':
          return await this.syncWorkflowTrigger(action);
        case 'form_submit':
          return await this.syncFormSubmit(action);
        case 'feedback':
          return await this.syncFeedback(action);
        case 'canvas_update':
          return await this.syncCanvasUpdate(action);
        case 'agent_sync':
          return await this.syncAgentEntity(action);
        case 'workflow_sync':
          return await this.syncWorkflowEntity(action);
        case 'canvas_sync':
          return await this.syncCanvasEntity(action);
        case 'episode_sync':
          return await this.syncEpisodeEntity(action);
        default:
          console.warn(`OfflineSync: Unknown action type: ${action.type}`);
          return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Failed to sync action ${action.id}:`, error);
      return { success: false, skipped: !admitted };
    }
  }

  /**
   * Sync agent message
   */
  private async syncAgentMessage(action: OfflineAction): Promise<{ success: boolean; conflict?: boolean }> {
    console.log(`OfflineSync: Syncing agent message ${action.id}`);

    try {
      const { agentId, message, sessionId } = action.payload;

      // Call the menubar quick chat endpoint (which works for all platforms)
      const response = await apiService.post('/api/menubar/quick/chat', {
        agent_id: agentId,
        message: message,
        session_id: sessionId,
      });

      if (response.success) {
        console.log(`OfflineSync: Successfully synced agent message ${action.id}`);
        return { success: true, conflict: false };
      } else {
        console.error(`OfflineSync: Failed to sync agent message ${action.id}:`, response.error);
        return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Error syncing agent message ${action.id}:`, error);
      return { success: false };
    }
  }

  /**
   * Sync workflow trigger
   */
  private async syncWorkflowTrigger(action: OfflineAction): Promise<{ success: boolean; conflict?: boolean }> {
    console.log(`OfflineSync: Syncing workflow trigger ${action.id}`);

    try {
      const { workflowId, input } = action.payload;

      // Call the workflow trigger endpoint
      const response = await apiService.post(`/api/workflows/${workflowId}/trigger`, input);

      if (response.success) {
        console.log(`OfflineSync: Successfully synced workflow trigger ${action.id}`);
        return { success: true, conflict: false };
      } else {
        console.error(`OfflineSync: Failed to sync workflow trigger ${action.id}:`, response.error);
        return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Error syncing workflow trigger ${action.id}:`, error);
      return { success: false };
    }
  }

  /**
   * Sync form submit
   */
  private async syncFormSubmit(action: OfflineAction): Promise<{ success: boolean; conflict?: boolean }> {
    console.log(`OfflineSync: Syncing form submit ${action.id}`);

    try {
      const { canvasId, formData } = action.payload;

      // Check for conflict by comparing timestamps
      const localTimestamp = new Date(action.createdAt);
      const response = await apiService.get(`/api/canvas/${canvasId}`);

      if (response.success && response.data) {
        const serverTimestamp = new Date(response.data.updated_at);
        // If server version is newer, mark as conflict
        if (serverTimestamp > localTimestamp) {
          console.warn(`OfflineSync: Conflict detected for form submit ${action.id}`);
          return { success: false, conflict: true };
        }
      }

      // Submit the form
      const submitResponse = await apiService.post(`/api/canvas/${canvasId}/submit`, {
        form_data: formData,
        submitted_at: action.createdAt,
      });

      if (submitResponse.success) {
        console.log(`OfflineSync: Successfully synced form submit ${action.id}`);
        return { success: true, conflict: false };
      } else {
        console.error(`OfflineSync: Failed to sync form submit ${action.id}:`, submitResponse.error);
        return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Error syncing form submit ${action.id}:`, error);
      return { success: false };
    }
  }

  /**
   * Sync feedback
   */
  private async syncFeedback(action: OfflineAction): Promise<{ success: boolean; conflict?: boolean }> {
    console.log(`OfflineSync: Syncing feedback ${action.id}`);

    try {
      const { agentId, feedbackType, rating, comment } = action.payload;

      // Call the feedback endpoint
      const response = await apiService.post('/api/feedback', {
        agent_id: agentId,
        feedback_type: feedbackType,
        rating: rating,
        comment: comment,
        created_at: action.createdAt,
      });

      if (response.success) {
        console.log(`OfflineSync: Successfully synced feedback ${action.id}`);
        return { success: true, conflict: false };
      } else {
        console.error(`OfflineSync: Failed to sync feedback ${action.id}:`, response.error);
        return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Error syncing feedback ${action.id}:`, error);
      return { success: false };
    }
  }

  /**
   * Sync canvas update
   */
  private async syncCanvasUpdate(action: OfflineAction): Promise<{ success: boolean; conflict?: boolean }> {
    console.log(`OfflineSync: Syncing canvas update ${action.id}`);

    try {
      const { canvasId, updates } = action.payload;

      // Check for conflict by comparing timestamps
      const localTimestamp = new Date(action.createdAt);
      const response = await apiService.get(`/api/canvas/${canvasId}`);

      if (response.success && response.data) {
        const serverTimestamp = new Date(response.data.updated_at);
        // If server version is newer, mark as conflict
        if (serverTimestamp > localTimestamp) {
          console.warn(`OfflineSync: Conflict detected for canvas update ${action.id}`);

          // Apply conflict resolution strategy
          if (action.conflictResolution === 'server_wins') {
            return { success: true, conflict: false }; // Skip update
          } else if (action.conflictResolution === 'client_wins') {
            // Proceed with update below
          } else if (action.conflictResolution === 'merge') {
            return await this.mergeCanvasUpdate(canvasId, updates, response.data);
          } else {
            return { success: false, conflict: true };
          }
        }
      }

      // Update the canvas
      const updateResponse = await apiService.put(`/api/canvas/${canvasId}`, {
        ...updates,
        updated_at: action.createdAt,
      });

      if (updateResponse.success) {
        console.log(`OfflineSync: Successfully synced canvas update ${action.id}`);
        return { success: true, conflict: false };
      } else {
        console.error(`OfflineSync: Failed to sync canvas update ${action.id}:`, updateResponse.error);
        return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Error syncing canvas update ${action.id}:`, error);
      return { success: false };
    }
  }

  /**
   * Sync agent entity
   */
  private async syncAgentEntity(action: OfflineAction): Promise<{ success: boolean; conflict?: boolean }> {
    console.log(`OfflineSync: Syncing agent entity ${action.id}`);

    try {
      const { agentId, agentData } = action.payload;
      const response = await apiService.put(`/api/agents/${agentId}`, agentData);

      if (response.success) {
        console.log(`OfflineSync: Successfully synced agent entity ${action.id}`);
        return { success: true, conflict: false };
      } else {
        console.error(`OfflineSync: Failed to sync agent entity ${action.id}:`, response.error);
        return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Error syncing agent entity ${action.id}:`, error);
      return { success: false };
    }
  }

  /**
   * Sync workflow entity
   */
  private async syncWorkflowEntity(action: OfflineAction): Promise<{ success: boolean; conflict?: boolean }> {
    console.log(`OfflineSync: Syncing workflow entity ${action.id}`);

    try {
      const { workflowId, workflowData } = action.payload;
      const response = await apiService.put(`/api/workflows/${workflowId}`, workflowData);

      if (response.success) {
        console.log(`OfflineSync: Successfully synced workflow entity ${action.id}`);
        return { success: true, conflict: false };
      } else {
        console.error(`OfflineSync: Failed to sync workflow entity ${action.id}:`, response.error);
        return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Error syncing workflow entity ${action.id}:`, error);
      return { success: false };
    }
  }

  /**
   * Sync canvas entity
   */
  private async syncCanvasEntity(action: OfflineAction): Promise<{ success: boolean; conflict?: boolean }> {
    console.log(`OfflineSync: Syncing canvas entity ${action.id}`);

    try {
      const { canvasId, canvasData } = action.payload;
      const response = await apiService.put(`/api/canvas/${canvasId}`, canvasData);

      if (response.success) {
        console.log(`OfflineSync: Successfully synced canvas entity ${action.id}`);
        return { success: true, conflict: false };
      } else {
        console.error(`OfflineSync: Failed to sync canvas entity ${action.id}:`, response.error);
        return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Error syncing canvas entity ${action.id}:`, error);
      return { success: false };
    }
  }

  /**
   * Sync episode entity
   */
  private async syncEpisodeEntity(action: OfflineAction): Promise<{ success: boolean; conflict?: boolean }> {
    console.log(`OfflineSync: Syncing episode entity ${action.id}`);

    try {
      const { episodeId, episodeData } = action.payload;
      const response = await apiService.put(`/api/episodes/${episodeId}`, episodeData);

      if (response.success) {
        console.log(`OfflineSync: Successfully synced episode entity ${action.id}`);
        return { success: true, conflict: false };
      } else {
        console.error(`OfflineSync: Failed to sync episode entity ${action.id}:`, response.error);
        return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Error syncing episode entity ${action.id}:`, error);
      return { success: false };
    }
  }

  /**
   * Merge canvas update (smart merge for compatible changes)
   */
  private async mergeCanvasUpdate(
    canvasId: string,
    localUpdates: any,
    serverData: any
  ): Promise<{ success: boolean; conflict?: boolean }> {
    console.log(`OfflineSync: Merging canvas update for ${canvasId}`);

    try {
      // Merge compatible fields (e.g., tags, metadata)
      const mergedData = {
        ...serverData,
        tags: [...new Set([...(serverData.tags || []), ...(localUpdates.tags || [])])],
        metadata: { ...(serverData.metadata || {}), ...(localUpdates.metadata || {}) },
      };

      const response = await apiService.put(`/api/canvas/${canvasId}`, mergedData);

      if (response.success) {
        console.log(`OfflineSync: Successfully merged canvas update for ${canvasId}`);
        return { success: true, conflict: false };
      } else {
        console.error(`OfflineSync: Failed to merge canvas update for ${canvasId}:`, response.error);
        return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Error merging canvas update for ${canvasId}:`, error);
      return { success: false };
    }
  }

  /**
   * Get sync state
   */
  async getSyncState(): Promise<SyncState> {
    const state = await mmkvStorage.getObject<SyncState>('sync_state');
    const queue = await this.getQueue();
    if (queue.some(action => !['pending', 'syncing', 'completed', 'failed'].includes(action.status))) {
      throw new Error('Offline queue status is unreadable; original data has been retained.');
    }
    // Cached progress is advisory; durable unresolved work owns this count.
    const pendingCount = queue.filter(action => action.status !== 'completed').length;
    return {
      ...(state ?? {
        lastSyncAt: null,
        lastSuccessfulSyncAt: null,
        syncInProgress: false,
        consecutiveFailures: 0,
        currentOperation: '',
        syncProgress: 0,
        cancelled: false,
      }),
      pendingCount,
    };
  }

  /**
   * Subscribe to sync state changes
   */
  subscribe(callback: (state: SyncState) => void): () => void {
    this.listeners.add(callback);
    return () => {
      this.listeners.delete(callback);
    };
  }

  /**
   * Get pending action count
   */
  async getPendingCount(): Promise<number> {
    const queue = await this.getQueue();
    return queue.filter((a) => a.status === 'pending').length;
  }

  /** Return fresh serialized pending/failed rows, never shared UI references. */
  async getPendingActions(): Promise<OfflineAction[]> {
    return (await this.getQueue()).filter((a) => a.status === 'pending' || a.status === 'failed');
  }

  async retryActions(ids: readonly string[]): Promise<number> {
    return this.withQueueMutation(async () => {
      const queue = await this.getQueue();
      const selected = queue.filter((a) => ids.includes(a.id));
      if (selected.some((a) => a.status === 'syncing')) throw new Error('An action is already being synchronized.');
      const retryable = selected.filter((a) => a.status === 'pending' || a.status === 'failed');
      if (!retryable.length) return 0;
      for (const action of retryable) {
        action.syncAttempts = 0;
        action.status = 'pending';
        delete action.lastSyncError;
      }
      await this.saveQueue(queue);
      return retryable.length;
    });
  }

  async prioritizeAction(id: string): Promise<boolean> {
    return this.withQueueMutation(async () => {
      const queue = await this.getQueue();
      const action = queue.find((a) => a.id === id);
      if (!action || action.status === 'completed') return false;
      if (action.status === 'syncing') throw new Error('An action is already being synchronized.');
      action.priority = Math.min(action.priority + 2, 10);
      action.priorityLevel = action.priority >= 10 ? 'critical' : action.priority >= 7 ? 'high' : action.priority >= 5 ? 'normal' : 'low';
      queue.sort((a, b) => b.priority - a.priority || new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());
      await this.saveQueue(queue);
      return true;
    });
  }

  async removeActions(ids: readonly string[]): Promise<number> {
    return this.withQueueMutation(async () => {
      const queue = await this.getQueue();
      if (queue.some((a) => ids.includes(a.id) && a.status === 'syncing')) throw new Error('An in-flight action cannot be represented as stopped.');
      const remaining = queue.filter((a) => !ids.includes(a.id));
      if (remaining.length === queue.length) return 0;
      await this.saveQueue(remaining);
      return queue.length - remaining.length;
    });
  }

  /**
   * Clear all offline actions
   */
  async clearQueue(): Promise<void> {
    return this.withQueueMutation(async () => {
      if ((await this.getQueue()).some((a) => a.status === 'syncing')) throw new Error('In-flight actions cannot be represented as stopped.');
      if (!(await mmkvStorage.delete('offline_queue' as StorageKey))) {
        throw new Error('Offline queue deletion was not confirmed.');
      }
      await this.reconcileQueueMetadata([]);
    });
  }

  // Private helper methods

  /** Serialize participating queue writes in this JS runtime; not a native/process lock. */
  private withQueueMutation<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.queueMutationTail.then(operation);
    // Both outcomes release the next writer; a rejected write never poisons the tail.
    this.queueMutationTail = result.then(() => undefined, () => undefined);
    return result;
  }

  private async getQueue(): Promise<OfflineAction[]> {
    const queueData = await mmkvStorage.getString('offline_queue' as StorageKey);
    if (!queueData) return [];

    try {
      const parsed = JSON.parse(queueData);
      // Convert date strings back to Date objects
      return parsed.map((action: any) => ({
        ...action,
        createdAt: new Date(action.createdAt),
      }));
    } catch (error) {
      console.error('OfflineSync: Queue parsing failed; original bytes retained.');
      // Keep the original bytes for recovery. A parse error is not an empty queue.
      throw new Error('Offline queue data is unreadable; original data has been retained.');
    }
  }

  private async saveQueue(queue: OfflineAction[]): Promise<void> {
    if (!(await mmkvStorage.setString('offline_queue' as StorageKey, JSON.stringify(queue)))) {
      throw new Error('Offline queue write was not confirmed.');
    }
    await this.reconcileQueueMetadata(queue);
  }

  private async claimAction(expected: OfflineAction): Promise<boolean> {
    return this.withQueueMutation(async () => {
      const queue = await this.getQueue();
      const current = queue.find((a) => a.id === expected.id);
      if (!current || current.status !== 'pending') return false;
      const material = (a: OfflineAction) => JSON.stringify([a.type, a.payload, a.userId, a.deviceId, a.entityType, a.entityId, a.conflictResolution, a.deltaHash]);
      if (material(current) !== material(expected)) return false;
      current.status = 'syncing';
      await this.saveQueue(queue);
      return true;
    });
  }

  private async updateActionStatus(id: string, status: OfflineActionStatus): Promise<void> {
    return this.withQueueMutation(async () => {
      const queue = await this.getQueue();
      const action = queue.find((a) => a.id === id);

      if (action) {
        action.status = status;
        await this.saveQueue(queue);
      }
    });
  }

  private async incrementSyncAttempts(id: string): Promise<void> {
    return this.withQueueMutation(async () => {
      const queue = await this.getQueue();
      const action = queue.find((a) => a.id === id);

      if (action) {
        action.syncAttempts += 1;
        await this.saveQueue(queue);
      }
    });
  }

  private async removeActionFromQueue(id: string): Promise<void> {
    return this.withQueueMutation(async () => {
      const queue = await this.getQueue();
      await this.saveQueue(queue.filter((a) => a.id !== id));
    });
  }

  private async removeCompletedActions(): Promise<void> {
    return this.withQueueMutation(async () => {
      const queue = await this.getQueue();
      const filtered = queue.filter((a) => a.status !== 'completed');
      await this.saveQueue(filtered);
    });
  }

  private async updateSyncState(updates: Partial<SyncState>): Promise<void> {
    const currentState = await this.getSyncState();
    const newState = { ...currentState, ...updates };
    if (!(await mmkvStorage.setObject('sync_state' as StorageKey, newState))) {
      throw new Error('Sync state write was not confirmed.');
    }
  }

  private async loadSyncState(): Promise<void> {
    const state = await this.getSyncState();
    this.syncInProgress = state.syncInProgress;
  }

  private notifyListeners(): void {
    this.getSyncState().then((state) => {
      this.listeners.forEach((callback) => callback(state));
    }).catch(() => {
      // An unreadable authoritative queue is never published as an empty one.
      console.warn('OfflineSync: Sync state unavailable; retained work not certified.');
    });
  }

  private startPeriodicSync(): void {
    // Sync every 5 minutes when online
    this.syncTimer = setInterval(() => {
      if (this.isOnline && !this.syncInProgress) {
        this.triggerSync();
      }
    }, 5 * 60 * 1000);
  }

  /**
   * Start cleanup task (runs hourly)
   */
  private startCleanupTask(): void {
    setInterval(async () => {
      await this.cleanupOldEntries();
      await this.checkStorageQuota();
    }, 60 * 60 * 1000); // Every hour
  }

  /**
   * Calculate size of an action payload
   */
  private calculateActionSize(payload: any): number {
    return JSON.stringify(payload).length * 2; // Rough estimate (2 bytes per char)
  }

  /**
   * Generate delta hash for change detection
   */
  private generateDeltaHash(payload: any): string {
    const str = JSON.stringify(payload);
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    return hash.toString(36);
  }

  /**
   * Check storage quota
   */
  private async checkStorageQuota(additionalBytes: number = 0): Promise<boolean> {
    const { usedBytes, maxBytes } = this.deriveQueueQuota(await this.getQueue());
    const projectedUsage = usedBytes + additionalBytes;
    const usageRatio = projectedUsage / maxBytes;

    if (usageRatio >= ENFORCEMENT_THRESHOLD) {
      console.warn('OfflineSync: Storage quota exceeded, cleanup required');
      return false;
    }

    if (usageRatio >= WARNING_THRESHOLD) {
      console.warn('OfflineSync: Storage quota warning threshold reached');
    }

    return true;
  }

  /**
   * Update storage quota
   */
  private deriveQueueQuota(queue: readonly OfflineAction[]): StorageQuota {
    const quota: StorageQuota = {
      usedBytes: 0, maxBytes: STORAGE_QUOTA_BYTES,
      warningThreshold: WARNING_THRESHOLD, enforcementThreshold: ENFORCEMENT_THRESHOLD,
      breakdown: { agents: 0, workflows: 0, canvases: 0, episodes: 0, other: 0 },
    };
    for (const action of queue) {
      // Rebuild the existing payload-budget estimate; stored counters are projections.
      const bytes = this.calculateActionSize(action.payload);
      const entity = action.entityType;
      if (entity === 'agents' || entity === 'workflows' || entity === 'canvases' || entity === 'episodes') quota.breakdown[entity] += bytes;
      else quota.breakdown.other += bytes;
      quota.usedBytes += bytes;
    }
    return quota;
  }

  private async reconcileQueueMetadata(queue: readonly OfflineAction[]): Promise<void> {
    try {
      const state = await this.getSyncState();
      const stateSaved = await mmkvStorage.setObject('sync_state', { ...state, pendingCount: queue.filter((a) => a.status === 'pending').length });
      // Keep queue-derived metadata separate from StorageService's whole-store quota.
      const quotaSaved = await mmkvStorage.setObject('offline_storage_quota', this.deriveQueueQuota(queue));
      if (!stateSaved || !quotaSaved) console.warn('OfflineSync: Queue committed; metadata projection write not confirmed.');
    } catch {
      console.warn('OfflineSync: Queue committed; metadata projection unavailable.');
    }
  }

  private async initializeStorageQuota(): Promise<void> {
    await this.reconcileQueueMetadata(await this.getQueue());
  }

  /**
   * Cleanup old entries using LRU strategy
   */
  private async cleanupOldEntries(requiredBytes: number = 0): Promise<void> {
    return this.withQueueMutation(async () => {
      console.log('OfflineSync: Cleaning up old entries');

      const queue = await this.getQueue();

      // Sort by creation time (oldest first)
      const sorted = [...queue].sort((a, b) =>
        new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
      );

      let freedBytes = 0;
      const toRemove: string[] = [];

      for (const action of sorted) {
        // Only terminal completed entries are disposable, regardless of priority.
        if (action.status !== 'completed') continue;

        // Remove until we have enough space
        toRemove.push(action.id);
        freedBytes += action.sizeBytes || 0;

        if (freedBytes >= requiredBytes) break;
      }

      if (toRemove.length > 0) {
        const filtered = queue.filter(a => !toRemove.includes(a.id));
        await this.saveQueue(filtered);

        console.log(`OfflineSync: Cleaned up ${toRemove.length} entries, freed ${freedBytes} bytes`);
      }
    });
  }

  /**
   * Load quality metrics
   */
  private async loadQualityMetrics(): Promise<void> {
    const saved = await mmkvStorage.getObject<SyncQualityMetrics>('sync_quality_metrics' as StorageKey);
    this.qualityMetrics = saved || {
      totalSyncs: 0,
      successfulSyncs: 0,
      failedSyncs: 0,
      conflictRate: 0,
      avgSyncDuration: 0,
      avgBytesTransferred: 0,
      lastQualityCheck: new Date(),
    };
  }

  /**
   * Update quality metrics
   */
  private async updateQualityMetrics(updates: Partial<SyncQualityMetrics>): Promise<void> {
    this.qualityMetrics = { ...this.qualityMetrics, ...updates };
    await mmkvStorage.setObject('sync_quality_metrics' as StorageKey, this.qualityMetrics);
  }

  /**
   * Notify progress listeners
   */
  private notifyProgressListeners(progress: number, operation: string): void {
    this.progressListeners.forEach(callback => callback(progress, operation));
  }

  /**
   * Notify conflict listeners
   */
  private notifyConflictListeners(conflict: OfflineAction): void {
    this.conflictListeners.forEach(callback => callback(conflict));
  }

  /**
   * Cleanup
   */
  destroy(): void {
    if (this.syncTimer) {
      clearInterval(this.syncTimer);
      this.syncTimer = null;
    }
    this.listeners.clear();
  }
}

// Export singleton instance
export const offlineSyncService = new OfflineSyncService();

export default offlineSyncService;
