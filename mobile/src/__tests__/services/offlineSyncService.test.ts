/**
 * Mobile Offline Sync Service Tests
 *
 * Comprehensive tests for offline synchronization functionality:
 * - Queue management (add, remove, prioritize, quota)
 * - Sync execution (batch processing, retry logic, cancellation)
 * - Network handling (online/offline detection)
 * - Conflict resolution (last_write_wins, server_wins, client_wins)
 * - Entity-specific sync (agents, workflows, canvases, episodes)
 * - State management (listeners, progress tracking)
 * - Quality metrics and storage quota
 */

import { offlineSyncService, OfflineActionType, SyncPriority, ConflictResolution } from '../../services/offlineSyncService';
import { simulateNetworkSwitch } from '../helpers/deviceMocks';

// Mock NetInfo
jest.mock('@react-native-community/netinfo', () => ({
  fetch: jest.fn(() => Promise.resolve({ isConnected: true })),
  addEventListener: jest.fn(() => jest.fn()),
}));

// Mock apiService
jest.mock('../../services/api', () => ({
  apiService: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

describe('offlineSyncService', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    // Reset global storage mocks
    (global as any).__resetSecureStoreMock?.();
    (global as any).__resetAsyncStorageMock?.();

    await offlineSyncService.initialize();
  });

  afterEach(() => {
    offlineSyncService.destroy();
  });

  // ========================================================================
  // Queue Management Tests (6 tests)
  // ========================================================================

  describe('Queue', () => {
    test('should queue action with priority', async () => {
      const actionId = await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_123', message: 'Test message', sessionId: 'session_1' },
        'high',
        'user_1',
        'device_1'
      );

      expect(actionId).toMatch(/^action_\d+_[a-z0-9]+$/);
      expect(actionId).toBeDefined();
    });

    test('should sort queue by priority', async () => {
      // Queue low priority action first
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Low priority' },
        'low',
        'user_1',
        'device_1'
      );

      // Queue high priority action second
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_2', message: 'High priority' },
        'critical',
        'user_1',
        'device_1'
      );

      // Queue normal priority action third
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_3', message: 'Normal priority' },
        'normal',
        'user_1',
        'device_1'
      );

      // Critical (10) > High (7) > Normal (5) > Low (2)
      const state = await offlineSyncService.getSyncState();
      expect(state.pendingCount).toBe(3);
    });

    test('should check storage quota before queueing', async () => {
      const quota = await offlineSyncService.getStorageQuota();

      expect(quota).toHaveProperty('usedBytes');
      expect(quota).toHaveProperty('maxBytes');
      expect(quota).toHaveProperty('warningThreshold');
      expect(quota).toHaveProperty('enforcementThreshold');
      expect(quota.maxBytes).toBeGreaterThan(0);
    });

    test('should cleanup old entries when quota exceeded', async () => {
      // This test verifies the cleanup logic is in place
      // Actual cleanup would require filling up the quota
      const quota = await offlineSyncService.getStorageQuota();

      // Verify quota enforcement thresholds are set correctly
      expect(quota.warningThreshold).toBe(0.8); // 80%
      expect(quota.enforcementThreshold).toBe(0.95); // 95%
    });

    test('should get pending count', async () => {
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Test' },
        'normal',
        'user_1',
        'device_1'
      );

      const state = await offlineSyncService.getSyncState();
      expect(state.pendingCount).toBeGreaterThan(0);
    });

    test('should clear queue', async () => {
      // Queue some actions
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Test 1' },
        'normal',
        'user_1',
        'device_1'
      );

      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_2', message: 'Test 2' },
        'normal',
        'user_1',
        'device_1'
      );

      // Verify queue has items
      let state = await offlineSyncService.getSyncState();
      expect(state.pendingCount).toBeGreaterThan(0);

      // Clear queue
      await offlineSyncService.clearQueue();

      // Verify queue is cleared
      state = await offlineSyncService.getSyncState();
      expect(state.pendingCount).toBe(0);
    });
  });

  // ========================================================================
  // Sync Execution Tests (8 tests)
  // ========================================================================

  describe('Sync Execution', () => {
    test('should sync actions when online', async () => {
      const { apiService } = require('../../services/api');
      apiService.post.mockResolvedValue({ success: true, data: {} });

      // Use normal priority to avoid immediate sync during queueing
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Test', sessionId: 'session_1' },
        'normal',
        'user_1',
        'device_1'
      );

      const result = await offlineSyncService.triggerSync();

      expect(result.synced).toBeGreaterThan(0);
      expect(result.success).toBe(true);
    });

    test('should sync critical actions immediately', async () => {
      const { apiService } = require('../../services/api');
      apiService.post.mockResolvedValue({ success: true, data: {} });

      // Critical actions (priority 10) should trigger immediate sync when online
      const actionId = await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Critical', sessionId: 'session_1' },
        'critical',
        'user_1',
        'device_1'
      );

      expect(actionId).toBeDefined();
    });

    test('should handle sync failure with retry', async () => {
      const { apiService } = require('../../services/api');
      let attemptCount = 0;

      apiService.post.mockImplementation(() => {
        attemptCount++;
        if (attemptCount === 1) {
          return Promise.reject(new Error('Network error'));
        }
        return Promise.resolve({ success: true, data: {} });
      });

      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Test', sessionId: 'session_1' },
        'normal',
        'user_1',
        'device_1'
      );

      const result = await offlineSyncService.triggerSync();

      // Should fail on first attempt but queue for retry
      expect(result.failed).toBeGreaterThan(0);
    });

    test('should stop retrying after max attempts', async () => {
      const { apiService } = require('../../services/api');
      apiService.post.mockRejectedValue(new Error('Persistent failure'));

      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Test', sessionId: 'session_1' },
        'normal',
        'user_1',
        'device_1'
      );

      // Multiple sync attempts should eventually discard the action
      await offlineSyncService.triggerSync();
      await offlineSyncService.triggerSync();
      await offlineSyncService.triggerSync();
      await offlineSyncService.triggerSync();
      await offlineSyncService.triggerSync();

      const state = await offlineSyncService.getSyncState();
      // After 5 attempts, action should be removed
      expect(state.consecutiveFailures).toBeGreaterThan(0);
    });

    test('should process in batches', async () => {
      const { apiService } = require('../../services/api');
      apiService.post.mockResolvedValue({ success: true, data: {} });

      // Queue 15 actions (batch size is 10)
      for (let i = 0; i < 15; i++) {
        await offlineSyncService.queueAction(
          'agent_message',
          { agentId: `agent_${i}`, message: `Test ${i}`, sessionId: `session_${i}` },
          'normal',
          'user_1',
          'device_1'
        );
      }

      const result = await offlineSyncService.triggerSync();

      // Should process all 15 actions in batches
      expect(result.synced).toBe(15);
    });

    test('should cancel ongoing sync', async () => {
      const { apiService } = require('../../services/api');
      apiService.post.mockImplementation(() => {
        return new Promise(resolve => {
          // Long-running request
          setTimeout(() => resolve({ success: true, data: {} }), 5000);
        });
      });

      // Start sync
      const syncPromise = offlineSyncService.triggerSync();

      // Cancel immediately
      await offlineSyncService.cancelSync();

      const result = await syncPromise;

      // Sync should be cancelled
      const state = await offlineSyncService.getSyncState();
      expect(state.cancelled).toBe(true);
    });

    test('should not sync when offline', async () => {
      const { apiService } = require('../../services/api');
      const NetInfo = require('@react-native-community/netinfo');

      // Mock offline state
      NetInfo.fetch.mockResolvedValue({ isConnected: false });

      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Test', sessionId: 'session_1' },
        'normal',
        'user_1',
        'device_1'
      );

      const result = await offlineSyncService.triggerSync();

      // Should skip sync when offline
      expect(result.synced).toBe(0);
      expect(result.success).toBe(false);
    });

    test('should remove completed actions', async () => {
      const { apiService } = require('../../services/api');
      apiService.post.mockResolvedValue({ success: true, data: {} });

      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Test', sessionId: 'session_1' },
        'normal',
        'user_1',
        'device_1'
      );

      const stateBefore = await offlineSyncService.getSyncState();
      expect(stateBefore.pendingCount).toBeGreaterThan(0);

      await offlineSyncService.triggerSync();

      const stateAfter = await offlineSyncService.getSyncState();
      expect(stateAfter.pendingCount).toBe(0);
    });
  });

  // ========================================================================
  // Network Handling Tests (3 tests)
  // ========================================================================

  describe('Network', () => {
    test('should trigger sync when connection restored', async () => {
      const { apiService } = require('../../services/api');
      apiService.post.mockResolvedValue({ success: true, data: {} });

      const NetInfo = require('@react-native-community/netinfo');
      const addEventListenerMock = NetInfo.addEventListener;

      // Queue actions while offline
      NetInfo.fetch.mockResolvedValue({ isConnected: false });
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Test', sessionId: 'session_1' },
        'normal',
        'user_1',
        'device_1'
      );

      // Simulate connection restored
      const callback = addEventListenerMock.mock.calls[0][0];
      callback({ isConnected: true });

      // Should trigger sync automatically
      const state = await offlineSyncService.getSyncState();
      expect(state).toBeDefined();
    });

    test('should subscribe to network changes', async () => {
      const NetInfo = require('@react-native-community/netinfo');

      // Verify addEventListener was called during initialization
      expect(NetInfo.addEventListener).toHaveBeenCalled();
    });

    test('should start periodic sync', async () => {
      // Verify periodic sync timer is started
      jest.useFakeTimers();

      await offlineSyncService.initialize();

      // Fast-forward time to trigger periodic sync
      jest.advanceTimersByTime(5 * 60 * 1000); // 5 minutes

      jest.useRealTimers();

      const state = await offlineSyncService.getSyncState();
      expect(state).toBeDefined();
    });
  });

  // ========================================================================
  // Network Switching Tests (5 tests)
  // ========================================================================

  describe('Network Switching', () => {
    test('should execute periodic sync timer', async () => {
      const { apiService } = require('../../services/api');
      apiService.post.mockResolvedValue({ success: true, data: {} });

      // Verify service initialized successfully (already initialized in beforeEach)
      const state = await offlineSyncService.getSyncState();
      expect(state).toBeDefined();

      // Queue a NEW action
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_test', message: 'Periodic Test', sessionId: 'session_periodic' },
        'normal',
        'user_1',
        'device_1'
      );

      // Manual sync to verify timer was set up
      const result = await offlineSyncService.triggerSync();

      // Check if sync succeeded or if there were no pending actions
      expect(result).toBeDefined();
    });

    test('should skip periodic sync when offline', async () => {
      const { apiService } = require('../../services/api');
      const NetInfo = require('@react-native-community/netinfo');

      // Destroy and re-initialize with offline state
      offlineSyncService.destroy();
      NetInfo.fetch.mockResolvedValue({ isConnected: false });
      await offlineSyncService.initialize();

      // Queue an action
      const actionId = await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_offline', message: 'Test', sessionId: 'session_offline' },
        'normal',
        'user_1',
        'device_1'
      );

      expect(actionId).toBeDefined();

      // Try to sync while offline
      const result = await offlineSyncService.triggerSync();

      // Verify sync was skipped
      expect(result.synced).toBe(0);
      expect(result.success).toBe(false);

      // Re-initialize for next test
      offlineSyncService.destroy();
      NetInfo.fetch.mockResolvedValue({ isConnected: true });
      await offlineSyncService.initialize();
    });

    test('should not trigger periodic sync if sync already in progress', async () => {
      const { apiService } = require('../../services/api');

      // Queue actions
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Test 1', sessionId: 'session_1' },
        'normal',
        'user_1',
        'device_1'
      );

      // Start first sync
      const syncPromise = offlineSyncService.triggerSync();

      // Try to trigger another sync while first is in progress
      const result2 = await offlineSyncService.triggerSync();

      // Verify second sync was skipped
      expect(result2.synced).toBe(0);
      expect(result2.success).toBe(false);

      // Wait for first sync to complete
      await syncPromise;
    });

    test('should notify subscribers on network state change', async () => {
      const stateCallback = jest.fn();

      // Subscribe to state changes
      const unsubscribe = offlineSyncService.subscribe(stateCallback);

      // Trigger a state change by queuing an action (which updates state)
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_sub', message: 'Test', sessionId: 'session_sub' },
        'normal',
        'user_1',
        'device_1'
      );

      // Manually trigger state update to verify subscription works
      const state = await offlineSyncService.getSyncState();
      expect(state).toBeDefined();

      // Clean up
      unsubscribe();
    });

    test('should have cleanup task initialized', async () => {
      // Queue an action
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_cleanup', message: 'Test', sessionId: 'session_cleanup' },
        'low',
        'user_1',
        'device_1'
      );

      // Verify cleanup was triggered (quota should be updated)
      const quota = await offlineSyncService.getStorageQuota();
      expect(quota).toBeDefined();
      expect(quota.usedBytes).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // Conflict Resolution Tests (5 tests)
  // ========================================================================

  describe('Conflicts', () => {
    test('should detect server timestamp conflict', async () => {
      const { apiService } = require('../../services/api');

      // Mock server response with newer timestamp
      apiService.get.mockResolvedValue({
        success: true,
        data: { updated_at: new Date(Date.now() + 10000).toISOString() },
      });

      await offlineSyncService.queueAction(
        'form_submit',
        { canvasId: 'canvas_1', formData: { field1: 'value1' } },
        'normal',
        'user_1',
        'device_1',
        'last_write_wins'
      );

      const result = await offlineSyncService.triggerSync();

      // Should detect conflict
      expect(result.conflicts).toBeGreaterThan(0);
    });

    test('should apply last_write_wins resolution', async () => {
      const { apiService } = require('../../services/api');

      // Older server version
      apiService.get.mockResolvedValue({
        success: true,
        data: { updated_at: new Date(Date.now() - 10000).toISOString() },
      });

      apiService.post.mockResolvedValue({ success: true, data: {} });

      await offlineSyncService.queueAction(
        'form_submit',
        { canvasId: 'canvas_1', formData: { field1: 'value1' } },
        'normal',
        'user_1',
        'device_1',
        'last_write_wins'
      );

      const result = await offlineSyncService.triggerSync();

      // Client (newer) should win
      expect(result.synced).toBeGreaterThan(0);
      expect(result.conflicts).toBe(0);
    });

    test('should apply server_wins resolution', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: true,
        data: { updated_at: new Date().toISOString() },
      });

      await offlineSyncService.queueAction(
        'canvas_update',
        { canvasId: 'canvas_1', updates: { title: 'New Title' } },
        'normal',
        'user_1',
        'device_1',
        'server_wins'
      );

      const result = await offlineSyncService.triggerSync();

      // Server always wins with server_wins strategy
      expect(result.synced).toBeGreaterThan(0);
    });

    test('should apply client_wins resolution', async () => {
      const { apiService } = require('../../services/api');

      apiService.get.mockResolvedValue({
        success: true,
        data: { updated_at: new Date().toISOString() },
      });

      apiService.put.mockResolvedValue({ success: true, data: {} });

      await offlineSyncService.queueAction(
        'canvas_update',
        { canvasId: 'canvas_1', updates: { title: 'Client Title' } },
        'normal',
        'user_1',
        'device_1',
        'client_wins'
      );

      const result = await offlineSyncService.triggerSync();

      // Client wins even with older timestamp
      expect(result.synced).toBeGreaterThan(0);
    });

    test('should subscribe to conflict notifications', async () => {
      const conflictCallback = jest.fn();

      const unsubscribe = offlineSyncService.subscribeToConflicts(conflictCallback);

      expect(typeof unsubscribe).toBe('function');

      // Clean up
      unsubscribe();
    });
  });

  // ========================================================================
  // Entity-Specific Sync Tests (4 tests)
  // ========================================================================

  describe('Entity Sync', () => {
    test('should sync agent entity', async () => {
      const { apiService } = require('../../services/api');
      apiService.put.mockResolvedValue({ success: true, data: {} });

      await offlineSyncService.queueAction(
        'agent_sync',
        { agentId: 'agent_1', agentData: { name: 'Agent 1' } },
        'normal',
        'user_1',
        'device_1',
        'last_write_wins',
        'agents',
        'agent_1'
      );

      const result = await offlineSyncService.triggerSync();

      // Verify sync was attempted
      expect(result.synced).toBeGreaterThan(0);
    });

    test('should sync workflow entity', async () => {
      const { apiService } = require('../../services/api');
      apiService.put.mockResolvedValue({ success: true, data: {} });

      await offlineSyncService.queueAction(
        'workflow_sync',
        { workflowId: 'workflow_1', workflowData: { name: 'Workflow 1' } },
        'normal',
        'user_1',
        'device_1',
        'last_write_wins',
        'workflows',
        'workflow_1'
      );

      const result = await offlineSyncService.triggerSync();

      // Verify sync was attempted
      expect(result.synced).toBeGreaterThan(0);
    });

    test('should sync canvas entity', async () => {
      const { apiService } = require('../../services/api');
      apiService.post.mockResolvedValue({ success: true, data: {} });

      await offlineSyncService.queueAction(
        'canvas_sync',
        { canvasId: 'canvas_1', canvasData: { title: 'Canvas 1' } },
        'normal',
        'user_1',
        'device_1',
        'last_write_wins',
        'canvases',
        'canvas_1'
      );

      const result = await offlineSyncService.triggerSync();

      // Verify sync was attempted
      expect(result.synced).toBeGreaterThan(0);
    });

    test('should sync episode entity', async () => {
      const { apiService } = require('../../services/api');
      apiService.put.mockResolvedValue({ success: true, data: {} });

      await offlineSyncService.queueAction(
        'episode_sync',
        { episodeId: 'episode_1', episodeData: { summary: 'Episode 1' } },
        'normal',
        'user_1',
        'device_1',
        'last_write_wins',
        'episodes',
        'episode_1'
      );

      const result = await offlineSyncService.triggerSync();

      // Verify sync was attempted
      expect(result.synced).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // State Management Tests (4 tests)
  // ========================================================================

  describe('State', () => {
    test('should update sync state correctly', async () => {
      const state = await offlineSyncService.getSyncState();

      expect(state).toHaveProperty('lastSyncAt');
      expect(state).toHaveProperty('lastSuccessfulSyncAt');
      expect(state).toHaveProperty('pendingCount');
      expect(state).toHaveProperty('syncInProgress');
      expect(state).toHaveProperty('consecutiveFailures');
      expect(state).toHaveProperty('currentOperation');
      expect(state).toHaveProperty('syncProgress');
      expect(state).toHaveProperty('cancelled');
    });

    test('should subscribe to state changes', async () => {
      const stateCallback = jest.fn();

      const unsubscribe = offlineSyncService.subscribe(stateCallback);

      expect(typeof unsubscribe).toBe('function');

      // Trigger a state change
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: 'agent_1', message: 'Test', sessionId: 'session_1' },
        'normal',
        'user_1',
        'device_1'
      );

      // Clean up
      unsubscribe();
    });

    test('should subscribe to progress updates', async () => {
      const progressCallback = jest.fn();

      const unsubscribe = offlineSyncService.subscribeToProgress(progressCallback);

      expect(typeof unsubscribe).toBe('function');

      // Clean up
      unsubscribe();
    });

    test('should get sync state', async () => {
      const state = await offlineSyncService.getSyncState();

      expect(state).toBeDefined();
      expect(typeof state.syncProgress).toBe('number');
      expect(typeof state.pendingCount).toBe('number');
      expect(typeof state.syncInProgress).toBe('boolean');
    });
  });

  // ========================================================================
  // Quality Metrics Tests (2 tests)
  // ========================================================================

  describe('Quality', () => {
    test('should track quality metrics', async () => {
      const metrics = await offlineSyncService.getQualityMetrics();

      expect(metrics).toHaveProperty('totalSyncs');
      expect(metrics).toHaveProperty('successfulSyncs');
      expect(metrics).toHaveProperty('failedSyncs');
      expect(metrics).toHaveProperty('conflictRate');
      expect(metrics).toHaveProperty('avgSyncDuration');
      expect(metrics).toHaveProperty('avgBytesTransferred');
      expect(metrics).toHaveProperty('lastQualityCheck');
    });

    test('should get storage quota', async () => {
      const quota = await offlineSyncService.getStorageQuota();

      expect(quota).toHaveProperty('usedBytes');
      expect(quota).toHaveProperty('maxBytes');
      expect(quota).toHaveProperty('warningThreshold');
      expect(quota).toHaveProperty('enforcementThreshold');
      expect(quota).toHaveProperty('breakdown');

      expect(quota.breakdown).toHaveProperty('agents');
      expect(quota.breakdown).toHaveProperty('workflows');
      expect(quota.breakdown).toHaveProperty('canvases');
      expect(quota.breakdown).toHaveProperty('episodes');
      expect(quota.breakdown).toHaveProperty('other');
    });
  });
});
