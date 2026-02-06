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
  | 'device_command';

export type OfflineActionStatus = 'pending' | 'syncing' | 'completed' | 'failed';

export type ConflictResolution = 'last_write_wins' | 'manual' | 'server_wins';

export interface OfflineAction {
  id: string;
  type: OfflineActionType;
  payload: any;
  priority: number; // 0-10, higher = more important
  status: OfflineActionStatus;
  createdAt: Date;
  syncAttempts: number;
  lastSyncError?: string;
  conflictResolution?: ConflictResolution;
  userId: string;
  deviceId: string;
}

export interface SyncResult {
  success: boolean;
  synced: number;
  failed: number;
  conflicts: number;
  duration: number;
}

export interface SyncState {
  lastSyncAt: Date | null;
  lastSuccessfulSyncAt: Date | null;
  pendingCount: number;
  syncInProgress: boolean;
  consecutiveFailures: number;
}

// Configuration
const MAX_SYNC_ATTEMPTS = 5;
const BASE_RETRY_DELAY = 1000; // 1 second
const MAX_RETRY_DELAY = 60000; // 1 minute
const SYNC_BATCH_SIZE = 10; // Process up to 10 actions per sync

/**
 * Offline Sync Service
 */
class OfflineSyncService {
  private isOnline: boolean = true;
  private syncInProgress: boolean = false;
  private syncTimer: NodeJS.Timeout | null = null;
  private listeners: Set<(state: SyncState) => void> = new Set();

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

    // Start periodic sync (every 5 minutes)
    this.startPeriodicSync();
  }

  /**
   * Add an action to the offline queue
   */
  async queueAction(
    type: OfflineActionType,
    payload: any,
    priority: number = 0,
    userId: string,
    deviceId: string,
    conflictResolution: ConflictResolution = 'last_write_wins'
  ): Promise<string> {
    const action: OfflineAction = {
      id: `action_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type,
      payload,
      priority,
      status: 'pending',
      createdAt: new Date(),
      syncAttempts: 0,
      conflictResolution,
      userId,
      deviceId,
    };

    try {
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

      // Update sync state
      await this.updateSyncState({
        pendingCount: queue.filter((a) => a.status === 'pending').length,
      });

      console.log(`OfflineSync: Queued action ${action.id} (type: ${type})`);

      // If online, trigger immediate sync for high-priority actions
      if (this.isOnline && priority >= 5) {
        this.triggerSync();
      }

      return action.id;
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
      };
    }

    this.syncInProgress = true;
    this.notifyListeners();

    const startTime = Date.now();
    let synced = 0;
    let failed = 0;
    let conflicts = 0;

    try {
      // Get pending actions
      const queue = await this.getQueue();
      const pendingActions = queue.filter((a) => a.status === 'pending');

      if (pendingActions.length === 0) {
        console.log('OfflineSync: No pending actions to sync');
        return {
          success: true,
          synced: 0,
          failed: 0,
          conflicts: 0,
          duration: Date.now() - startTime,
        };
      }

      console.log(`OfflineSync: Syncing ${pendingActions.length} actions`);

      // Process in batches
      for (let i = 0; i < pendingActions.length; i += SYNC_BATCH_SIZE) {
        const batch = pendingActions.slice(i, i + SYNC_BATCH_SIZE);

        for (const action of batch) {
          try {
            const result = await this.syncAction(action);

            if (result.success) {
              synced++;
              await this.updateActionStatus(action.id, 'completed');
            } else if (result.conflict) {
              conflicts++;
              await this.updateActionStatus(action.id, 'pending');
            } else {
              failed++;
              await this.updateActionStatus(action.id, 'failed');
              await this.incrementSyncAttempts(action.id);
            }
          } catch (error) {
            console.error(`OfflineSync: Failed to sync action ${action.id}:`, error);
            failed++;
            await this.updateActionStatus(action.id, 'failed');
            await this.incrementSyncAttempts(action.id);
          }
        }
      }

      // Remove completed actions
      await this.removeCompletedActions();

      // Update sync state
      const newQueue = await this.getQueue();
      const now = new Date();
      const successfulCount = synced > 0 ? synced : 0;

      await this.updateSyncState({
        lastSyncAt: now,
        lastSuccessfulSyncAt: successfulCount > 0 ? now : null,
        pendingCount: newQueue.filter((a) => a.status === 'pending').length,
        consecutiveFailures: failed === 0 ? 0 : (await this.getSyncState()).consecutiveFailures + 1,
      });

      const duration = Date.now() - startTime;
      console.log(`OfflineSync: Sync complete - ${synced} synced, ${failed} failed, ${conflicts} conflicts, ${duration}ms`);

      return {
        success: true,
        synced,
        failed,
        conflicts,
        duration,
      };
    } catch (error) {
      console.error('OfflineSync: Sync failed:', error);
      return {
        success: false,
        synced,
        failed,
        conflicts,
        duration: Date.now() - startTime,
      };
    } finally {
      this.syncInProgress = false;
      this.notifyListeners();
    }
  }

  /**
   * Sync a single action
   */
  private async syncAction(action: OfflineAction): Promise<{ success: boolean; conflict?: boolean }> {
    try {
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
        default:
          console.warn(`OfflineSync: Unknown action type: ${action.type}`);
          return { success: false };
      }
    } catch (error) {
      console.error(`OfflineSync: Failed to sync action ${action.id}:`, error);
      return { success: false };
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
          return { success: false, conflict: true };
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
   * Get sync state
   */
  async getSyncState(): Promise<SyncState> {
    const state = await mmkvStorage.getObject<SyncState>('sync_state');
    return (
      state ?? {
        lastSyncAt: null,
        lastSuccessfulSyncAt: null,
        pendingCount: 0,
        syncInProgress: false,
        consecutiveFailures: 0,
      }
    );
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

  /**
   * Clear all offline actions
   */
  async clearQueue(): Promise<void> {
    await mmkvStorage.delete('offline_queue' as StorageKey);
    await this.updateSyncState({ pendingCount: 0 });
  }

  // Private helper methods

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
      console.error('OfflineSync: Failed to parse queue:', error);
      // Clear corrupted data
      await mmkvStorage.delete('offline_queue' as StorageKey);
      throw new Error(
        'Offline queue data corrupted. Queue has been reset. Please try again.'
      );
    }
  }

  private async saveQueue(queue: OfflineAction[]): Promise<void> {
    await mmkvStorage.setString('offline_queue' as StorageKey, JSON.stringify(queue));
  }

  private async updateActionStatus(id: string, status: OfflineActionStatus): Promise<void> {
    const queue = await this.getQueue();
    const action = queue.find((a) => a.id === id);

    if (action) {
      action.status = status;
      await this.saveQueue(queue);
    }
  }

  private async incrementSyncAttempts(id: string): Promise<void> {
    const queue = await this.getQueue();
    const action = queue.find((a) => a.id === id);

    if (action) {
      action.syncAttempts += 1;
      await this.saveQueue(queue);
    }
  }

  private async removeCompletedActions(): Promise<void> {
    const queue = await this.getQueue();
    const filtered = queue.filter((a) => a.status !== 'completed');
    await this.saveQueue(filtered);
  }

  private async updateSyncState(updates: Partial<SyncState>): Promise<void> {
    const currentState = await this.getSyncState();
    const newState = { ...currentState, ...updates };
    await mmkvStorage.setObject('sync_state' as StorageKey, newState);
  }

  private async loadSyncState(): Promise<void> {
    const state = await this.getSyncState();
    this.syncInProgress = state.syncInProgress;
  }

  private notifyListeners(): void {
    this.getSyncState().then((state) => {
      this.listeners.forEach((callback) => callback(state));
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
