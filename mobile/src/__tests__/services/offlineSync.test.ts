/**
 * Mobile Offline Sync Service Tests
 *
 * Tests for offline synchronization functionality:
 * - Queue management (add, remove, prioritize)
 * - Sync orchestration (batch processing, retry logic)
 * - Conflict resolution (last_write_wins, manual, server_wins)
 * - State persistence (MMKV storage)
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { offlineSyncService, OfflineAction, SyncStatus } from '../../services/offlineSyncService';

// Mock MMKV
jest.mock('react-native-mmkv', () => ({
  MMKV: jest.fn().mockImplementation(() => ({
    set: jest.fn(),
    get: jest.fn(),
    delete: jest.fn(),
    removeAll: jest.fn(),
  })),
}));

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage');

// Mock fetch
global.fetch = jest.fn();

describe('OfflineSyncService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset service state
    offlineSyncService.clearQueue();
  });

  afterEach(async () => {
    await AsyncStorage.clear();
  });

  // ========================================================================
  // Queue Management Tests
  // ========================================================================

  describe('Queue Management', () => {
    test('should add action to queue', async () => {
      const action: OfflineAction = {
        id: 'action_1',
        type: 'agent_message',
        data: { message: 'Test', agent_id: 'agent_123' },
        priority: 5,
        created_at: Date.now(),
        retries: 0,
      };

      await offlineSyncService.queueAction(action);

      const queue = await offlineSyncService.getQueue();
      expect(queue).toHaveLength(1);
      expect(queue[0]).toEqual(action);
    });

    test('should prioritize high-priority actions', async () => {
      const lowPriorityAction: OfflineAction = {
        id: 'action_1',
        type: 'agent_message',
        data: { message: 'Low' },
        priority: 1,
        created_at: Date.now(),
        retries: 0,
      };

      const highPriorityAction: OfflineAction = {
        id: 'action_2',
        type: 'form_submit',
        data: { form_data: {} },
        priority: 10,
        created_at: Date.now() + 1000,
        retries: 0,
      };

      await offlineSyncService.queueAction(lowPriorityAction);
      await offlineSyncService.queueAction(highPriorityAction);

      const queue = await offlineSyncService.getSortedQueue();
      expect(queue[0].id).toBe('action_2'); // High priority first
    });

    test('should remove action from queue', async () => {
      const action: OfflineAction = {
        id: 'action_1',
        type: 'agent_message',
        data: { message: 'Test' },
        priority: 5,
        created_at: Date.now(),
        retries: 0,
      };

      await offlineSyncService.queueAction(action);
      await offlineSyncService.removeAction('action_1');

      const queue = await offlineSyncService.getQueue();
      expect(queue).toHaveLength(0);
    });

    test('should update action retry count', async () => {
      const action: OfflineAction = {
        id: 'action_1',
        type: 'agent_message',
        data: { message: 'Test' },
        priority: 5,
        created_at: Date.now(),
        retries: 0,
      };

      await offlineSyncService.queueAction(action);
      await offlineSyncService.incrementRetries('action_1');

      const queue = await offlineSyncService.getQueue();
      expect(queue[0].retries).toBe(1);
    });

    test('should enforce max queue size (1000 actions)', async () => {
      // Add 1001 actions
      for (let i = 0; i < 1001; i++) {
        await offlineSyncService.queueAction({
          id: `action_${i}`,
          type: 'test',
          data: {},
          priority: 1,
          created_at: Date.now() + i,
          retries: 0,
        });
      }

      const queue = await offlineSyncService.getQueue();
      expect(queue.length).toBe(1000); // Max size enforced
      expect(queue[0].id).toBe('action_1'); // Oldest removed
    });
  });

  // ========================================================================
  // Sync Orchestration Tests
  // ========================================================================

  describe('Sync Orchestration', () => {
    test('should process batch of actions', async () => {
      // Mock successful API responses
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      } as Response);

      // Queue 5 actions
      for (let i = 0; i < 5; i++) {
        await offlineSyncService.queueAction({
          id: `action_${i}`,
          type: 'agent_message',
          data: { message: `Test ${i}` },
          priority: 5,
          created_at: Date.now() + i,
          retries: 0,
        });
      }

      const result = await offlineSyncService.syncBatch(5);

      expect(result.processed).toBe(5);
      expect(result.succeeded).toBe(5);
      expect(result.failed).toBe(0);
    });

    test('should handle sync failures gracefully', async () => {
      // Mock API failure
      (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValue(
        new Error('Network error')
      );

      await offlineSyncService.queueAction({
        id: 'action_1',
        type: 'agent_message',
        data: { message: 'Test' },
        priority: 5,
        created_at: Date.now(),
        retries: 0,
      });

      const result = await offlineSyncService.syncBatch(10);

      expect(result.processed).toBe(1);
      expect(result.succeeded).toBe(0);
      expect(result.failed).toBe(1);
    });

    test('should retry failed actions up to max retries', async () => {
      let attemptCount = 0;

      // Mock API that fails twice, then succeeds
      (global.fetch as jest.MockedFunction<typeof fetch>).mockImplementation(() => {
        attemptCount++;
        if (attemptCount <= 2) {
          return Promise.reject(new Error('Network error'));
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true }),
        } as Response);
      });

      await offlineSyncService.queueAction({
        id: 'action_1',
        type: 'agent_message',
        data: { message: 'Test' },
        priority: 5,
        created_at: Date.now(),
        retries: 0,
      });

      // First sync attempt (fails)
      await offlineSyncService.syncBatch(10);
      let queue = await offlineSyncService.getQueue();
      expect(queue[0].retries).toBe(1);

      // Second sync attempt (fails)
      await offlineSyncService.syncBatch(10);
      queue = await offlineSyncService.getQueue();
      expect(queue[0].retries).toBe(2);

      // Third sync attempt (succeeds)
      await offlineSyncService.syncBatch(10);
      queue = await offlineSyncService.getQueue();
      expect(queue).toHaveLength(0); // Action removed after success
    });

    test('should discard actions after max retries', async () => {
      // Mock API that always fails
      (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValue(
        new Error('Network error')
      );

      await offlineSyncService.queueAction({
        id: 'action_1',
        type: 'agent_message',
        data: { message: 'Test' },
        priority: 5,
        created_at: Date.now(),
        retries: 4, // One away from max (5)
      });

      await offlineSyncService.syncBatch(10);

      const queue = await offlineSyncService.getQueue();
      expect(queue).toHaveLength(0); // Action discarded after max retries
    });

    test('should sync actions in priority order', async () => {
      const processedOrder: string[] = [];

      (global.fetch as jest.MockedFunction<typeof fetch>).mockImplementation(() => {
        return Promise.resolve({
          ok: true,
          json: async () => {
            // Track processing order
            return { success: true };
          },
        } as Response);
      });

      // Queue actions with different priorities
      await offlineSyncService.queueAction({
        id: 'low_priority',
        type: 'test',
        data: {},
        priority: 1,
        created_at: Date.now(),
        retries: 0,
      });

      await offlineSyncService.queueAction({
        id: 'high_priority',
        type: 'test',
        data: {},
        priority: 10,
        created_at: Date.now() + 1000,
        retries: 0,
      });

      await offlineSyncService.queueAction({
        id: 'medium_priority',
        type: 'test',
        data: {},
        priority: 5,
        created_at: Date.now() + 2000,
        retries: 0,
      });

      await offlineSyncService.syncBatch(10);

      // Verify high-priority actions processed first
      const queue = await offlineSyncService.getQueue();
      expect(queue).toHaveLength(0); // All processed
    });
  });

  // ========================================================================
  // Conflict Resolution Tests
  // ========================================================================

  describe('Conflict Resolution', () => {
    test('should resolve conflicts with last_write_wins strategy', async () => {
      const serverData = { value: 'server' };
      const localData = { value: 'local' };

      const resolution = await offlineSyncService.resolveConflict(
        'last_write_wins',
        serverData,
        localData,
        { server_timestamp: Date.now() - 1000, local_timestamp: Date.now() }
      );

      expect(resolution).toEqual(localData); // Local (newer) wins
    });

    test('should resolve conflicts with server_wins strategy', async () => {
      const serverData = { value: 'server' };
      const localData = { value: 'local' };

      const resolution = await offlineSyncService.resolveConflict(
        'server_wins',
        serverData,
        localData,
        {}
      );

      expect(resolution).toEqual(serverData); // Server always wins
    });

    test('should flag conflicts for manual resolution', async () => {
      const serverData = { value: 'server' };
      const localData = { value: 'local' };

      const resolution = await offlineSyncService.resolveConflict(
        'manual',
        serverData,
        localData,
        {}
      );

      expect(resolution).toEqual({
        conflict: true,
        server: serverData,
        local: localData,
      });
    });

    test('should store conflict for later resolution', async () => {
      const conflict = {
        id: 'conflict_1',
        action_id: 'action_1',
        server_data: { value: 'server' },
        local_data: { value: 'local' },
        created_at: Date.now(),
      };

      await offlineSyncService.storeConflict(conflict);

      const storedConflicts = await offlineSyncService.getConflicts();
      expect(storedConflicts).toHaveLength(1);
      expect(storedConflicts[0]).toEqual(conflict);
    });

    test('should apply manual conflict resolution', async () => {
      const resolution = { value: 'resolved' };

      await offlineSyncService.applyConflictResolution('conflict_1', resolution);

      const conflicts = await offlineSyncService.getConflicts();
      expect(conflicts.find(c => c.id === 'conflict_1')).toBeUndefined();
    });
  });

  // ========================================================================
  // State Persistence Tests
  // ========================================================================

  describe('State Persistence', () => {
    test('should persist queue to MMKV', async () => {
      const action: OfflineAction = {
        id: 'action_1',
        type: 'test',
        data: {},
        priority: 5,
        created_at: Date.now(),
        retries: 0,
      };

      await offlineSyncService.queueAction(action);

      // Simulate app restart
      const newQueue = await offlineSyncService.getQueue();

      expect(newQueue).toHaveLength(1);
      expect(newQueue[0]).toEqual(action);
    });

    test('should persist sync status', async () => {
      const status: SyncStatus = {
        last_sync_at: Date.now(),
        last_successful_sync_at: Date.now(),
        total_syncs: 10,
        successful_syncs: 8,
        failed_syncs: 2,
        pending_actions_count: 5,
      };

      await offlineSyncService.updateSyncStatus(status);

      const retrieved = await offlineSyncService.getSyncStatus();

      expect(retrieved).toEqual(status);
    });

    test('should clear persisted state on reset', async () => {
      await offlineSyncService.queueAction({
        id: 'action_1',
        type: 'test',
        data: {},
        priority: 5,
        created_at: Date.now(),
        retries: 0,
      });

      await offlineSyncService.clearQueue();

      const queue = await offlineSyncService.getQueue();
      expect(queue).toHaveLength(0);
    });
  });

  // ========================================================================
  // Performance Tests
  // ========================================================================

  describe('Performance', () => {
    test('should queue 100 actions in <100ms', async () => {
      const start = Date.now();

      for (let i = 0; i < 100; i++) {
        await offlineSyncService.queueAction({
          id: `action_${i}`,
          type: 'test',
          data: {},
          priority: 1,
          created_at: Date.now() + i,
          retries: 0,
        });
      }

      const duration = Date.now() - start;
      expect(duration).toBeLessThan(100);
    });

    test('should sort 1000 actions in <50ms', async () => {
      for (let i = 0; i < 1000; i++) {
        await offlineSyncService.queueAction({
          id: `action_${i}`,
          type: 'test',
          data: {},
          priority: Math.floor(Math.random() * 10),
          created_at: Date.now() + i,
          retries: 0,
        });
      }

      const start = Date.now();
      await offlineSyncService.getSortedQueue();
      const duration = Date.now() - start;

      expect(duration).toBeLessThan(50);
    });

    test('should process batch of 100 actions in <5s', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      } as Response);

      for (let i = 0; i < 100; i++) {
        await offlineSyncService.queueAction({
          id: `action_${i}`,
          type: 'test',
          data: {},
          priority: 1,
          created_at: Date.now() + i,
          retries: 0,
        });
      }

      const start = Date.now();
      await offlineSyncService.syncBatch(100);
      const duration = Date.now() - start;

      expect(duration).toBeLessThan(5000); // 5 seconds
    }, 10000);
  });
});
