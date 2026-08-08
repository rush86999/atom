/**
 * Agent Sync Service Tests
 *
 * Tests for agent synchronization:
 * - List sync (counts, conflicts, failure handling)
 * - Single agent fetch (fresh cache, stale cache, server fallback)
 * - Agent updates (online PUT, offline optimistic queue)
 * - Favorites (toggle, filter)
 * - Prompt caching
 * - Execution history (record, cap, filter, sync-to-server)
 * - Health status and cache lifecycle
 */

import { agentSyncService } from '../../services/agentSyncService';
import { apiService } from '../../services/api';
import { storageService } from '../../services/storageService';
import { offlineSyncService } from '../../services/offlineSyncService';

// Mock service dependencies
jest.mock('../../services/api', () => ({
  apiService: {
    get: jest.fn(),
    put: jest.fn(),
  },
}));

jest.mock('../../services/storageService', () => ({
  storageService: {
    getObject: jest.fn(),
    setObject: jest.fn(),
  },
  StorageKey: {},
}));

jest.mock('../../services/offlineSyncService', () => ({
  offlineSyncService: {
    getSyncState: jest.fn(),
    queueAction: jest.fn(),
  },
}));

// Type casts for mocked services
const mockApiService = apiService as jest.Mocked<typeof apiService>;
const mockStorageService = storageService as jest.Mocked<typeof storageService>;
const mockOfflineSyncService = offlineSyncService as jest.Mocked<typeof offlineSyncService>;

const mockAgent = (id: string, updatedAt: Date, overrides: Partial<any> = {}) => ({
  id,
  name: `Agent ${id}`,
  description: `Test agent ${id}`,
  maturityLevel: 'INTERN',
  capabilities: ['chat', 'camera'],
  systemPrompt: 'You are a helpful agent',
  userId: 'user-1',
  isFavorite: false,
  createdAt: new Date('2024-01-01'),
  updatedAt,
  ...overrides,
});

const onlineState = {
  lastSyncAt: null,
  lastSuccessfulSyncAt: null,
  pendingCount: 0,
  syncInProgress: false,
  consecutiveFailures: 0,
  currentOperation: '',
  syncProgress: 0,
  cancelled: false,
};

describe('agentSyncService', () => {
  beforeEach(async () => {
    // mockReset clears implementations (clearAllMocks leaves them), which is
    // essential — the singleton's cache and mock implementations otherwise
    // leak between tests.
    mockApiService.get.mockReset();
    mockApiService.put.mockReset();
    mockStorageService.getObject.mockReset();
    mockStorageService.setObject.mockReset();
    mockOfflineSyncService.getSyncState.mockReset();
    mockOfflineSyncService.queueAction.mockReset();

    // Default mock implementations
    mockStorageService.getObject.mockResolvedValue(null);
    mockStorageService.setObject.mockResolvedValue(undefined);
    mockOfflineSyncService.getSyncState.mockResolvedValue(onlineState);
    mockOfflineSyncService.queueAction.mockResolvedValue('action-1');

    // Reset the singleton's in-memory cache between tests
    await agentSyncService.clearCache();

    await agentSyncService.initialize();

    // clearCache() above persists the empty cache — drop that write so tests
    // can assert on writes caused by their own actions.
    mockStorageService.setObject.mockClear();
  });

  afterEach(() => {
    agentSyncService.destroy();
  });

  // ========================================================================
  // List Sync Tests
  // ========================================================================

  describe('List Sync', () => {
    test('should sync agent list and report counts', async () => {
      mockApiService.get.mockResolvedValue({
        success: true,
        data: {
          agents: [
            mockAgent('a1', new Date('2024-01-01')),
            mockAgent('a2', new Date('2024-01-02')),
          ],
        },
      });

      const result = await agentSyncService.syncAgents('user-1', 'device-1');

      expect(mockApiService.get).toHaveBeenCalledWith('/api/agents');
      expect(result.success).toBe(true);
      expect(result.synced).toBe(2);
      expect(result.failed).toBe(0);
      expect(result.conflicts).toBe(0);
      expect(result.duration).toBeGreaterThanOrEqual(0);
      // Cache is persisted after sync
      expect(mockStorageService.setObject).toHaveBeenCalled();
    });

    test('should handle failed sync response', async () => {
      mockApiService.get.mockResolvedValue({
        success: false,
        error: 'Network error',
      });

      const result = await agentSyncService.syncAgents('user-1', 'device-1');

      expect(result.success).toBe(false);
      expect(result.synced).toBe(0);
      expect(result.failed).toBe(0);
      // Failed sync must not touch the cache
      expect(mockStorageService.setObject).not.toHaveBeenCalled();
    });

    test('should handle network exception during sync', async () => {
      mockApiService.get.mockRejectedValue(new Error('Request failed'));

      const result = await agentSyncService.syncAgents('user-1', 'device-1');

      expect(result.success).toBe(false);
      expect(result.synced).toBe(0);
    });

    test('should cache synced agents for offline reads', async () => {
      mockApiService.get.mockResolvedValue({
        success: true,
        data: { agents: [mockAgent('a1', new Date())] },
      });

      await agentSyncService.syncAgents('user-1', 'device-1');

      const agents = agentSyncService.getAllAgents();
      expect(agents).toHaveLength(1);
      expect(agents[0].id).toBe('a1');
    });

    test('should detect conflict when server version is older than cached', async () => {
      // Seed cache with a newer version
      mockApiService.get.mockResolvedValueOnce({
        success: true,
        data: { agents: [mockAgent('a1', new Date('2024-06-01'))] },
      });
      await agentSyncService.syncAgents('user-1', 'device-1');

      // Server now returns an older version -> conflict, cache must win
      mockApiService.get.mockResolvedValueOnce({
        success: true,
        data: { agents: [mockAgent('a1', new Date('2024-01-01'), { name: 'Stale Name' })] },
      });
      const result = await agentSyncService.syncAgents('user-1', 'device-1');

      expect(result.conflicts).toBe(1);
      expect(result.synced).toBe(0);
      // Local (newer) version is preserved
      expect(agentSyncService.getAllAgents()[0].name).toBe('Agent a1');
    });
  });

  // ========================================================================
  // Single Agent Tests
  // ========================================================================

  describe('Single Agent', () => {
    test('should return agent from fresh cache without hitting the server', async () => {
      mockApiService.get.mockResolvedValue({
        success: true,
        data: { agents: [mockAgent('a1', new Date())] },
      });
      await agentSyncService.syncAgents('user-1', 'device-1');

      mockApiService.get.mockClear();
      const agent = await agentSyncService.getAgent('a1');

      expect(agent).not.toBeNull();
      expect(agent?.id).toBe('a1');
      expect(mockApiService.get).not.toHaveBeenCalled();
    });

    test('should refetch stale cached agent and update the cache', async () => {
      // 25h old -> beyond the 24h TTL
      const stale = mockAgent('a1', new Date(Date.now() - 25 * 60 * 60 * 1000), {
        name: 'Stale Name',
      });
      mockApiService.get.mockResolvedValueOnce({
        success: true,
        data: { agents: [stale] },
      });
      await agentSyncService.syncAgents('user-1', 'device-1');

      const fresh = mockAgent('a1', new Date(), { name: 'Fresh Name' });
      mockApiService.get.mockResolvedValueOnce({ success: true, data: fresh });
      mockApiService.get.mockClear();

      const agent = await agentSyncService.getAgent('a1');

      expect(mockApiService.get).toHaveBeenCalledWith('/api/agents/a1');
      expect(agent?.name).toBe('Fresh Name');
      expect(agentSyncService.getAllAgents()[0].name).toBe('Fresh Name');
    });

    test('should fall back to stale cache when server fetch fails', async () => {
      const stale = mockAgent('a1', new Date(Date.now() - 25 * 60 * 60 * 1000));
      mockApiService.get.mockResolvedValueOnce({
        success: true,
        data: { agents: [stale] },
      });
      await agentSyncService.syncAgents('user-1', 'device-1');

      mockApiService.get.mockRejectedValueOnce(new Error('offline'));

      const agent = await agentSyncService.getAgent('a1');
      expect(agent?.id).toBe('a1');
    });

    test('should return null when agent is not cached and server has no data', async () => {
      mockApiService.get.mockResolvedValue({ success: true, data: null });

      const agent = await agentSyncService.getAgent('missing');
      expect(agent).toBeNull();
    });
  });

  // ========================================================================
  // Update Agent Tests
  // ========================================================================

  describe('Update Agent', () => {
    test('should PUT updates to server and refresh the cache', async () => {
      mockApiService.get.mockResolvedValue({
        success: true,
        data: { agents: [mockAgent('a1', new Date('2024-01-01'), { name: 'Old' })] },
      });
      await agentSyncService.syncAgents('user-1', 'device-1');

      mockApiService.put.mockResolvedValue({ success: true });

      const result = await agentSyncService.updateAgent(
        'a1',
        { name: 'New Name' },
        'user-1',
        'device-1'
      );

      expect(result).toBe(true);
      expect(mockApiService.put).toHaveBeenCalledWith('/api/agents/a1', { name: 'New Name' });
      expect(agentSyncService.getAllAgents()[0].name).toBe('New Name');
    });

    test('should queue offline updates and apply optimistically', async () => {
      mockApiService.get.mockResolvedValue({
        success: true,
        data: { agents: [mockAgent('a1', new Date('2024-01-01'), { name: 'Old' })] },
      });
      await agentSyncService.syncAgents('user-1', 'device-1');

      mockOfflineSyncService.getSyncState.mockResolvedValue({
        ...onlineState,
        syncInProgress: true,
      });

      const result = await agentSyncService.updateAgent(
        'a1',
        { name: 'Queued Name' },
        'user-1',
        'device-1'
      );

      expect(result).toBe(true);
      expect(mockOfflineSyncService.queueAction).toHaveBeenCalledWith(
        'agent_sync',
        { agentId: 'a1', agentData: { name: 'Queued Name' } },
        'normal',
        'user-1',
        'device-1',
        'last_write_wins',
        'agents',
        'a1'
      );
      // Optimistic cache update visible immediately
      expect(agentSyncService.getAllAgents()[0].name).toBe('Queued Name');
      // No server call while offline
      expect(mockApiService.put).not.toHaveBeenCalled();
    });

    test('should return false when server update fails', async () => {
      mockApiService.get.mockResolvedValue({
        success: true,
        data: { agents: [mockAgent('a1', new Date('2024-01-01'), { name: 'Old' })] },
      });
      await agentSyncService.syncAgents('user-1', 'device-1');

      mockApiService.put.mockResolvedValue({ success: false, error: 'Rejected' });

      const result = await agentSyncService.updateAgent('a1', { name: 'X' }, 'user-1', 'device-1');

      expect(result).toBe(false);
      expect(agentSyncService.getAllAgents()[0].name).toBe('Old');
    });
  });

  // ========================================================================
  // Favorites Tests
  // ========================================================================

  describe('Favorites', () => {
    test('should return false when toggling an uncached agent', async () => {
      const result = await agentSyncService.toggleFavorite('missing', 'user-1', 'device-1');
      expect(result).toBe(false);
      expect(mockApiService.put).not.toHaveBeenCalled();
    });

    test('should toggle favorite status via updateAgent', async () => {
      mockApiService.get.mockResolvedValue({
        success: true,
        data: {
          agents: [mockAgent('a1', new Date(), { isFavorite: false })],
        },
      });
      await agentSyncService.syncAgents('user-1', 'device-1');
      mockApiService.put.mockResolvedValue({ success: true });

      const result = await agentSyncService.toggleFavorite('a1', 'user-1', 'device-1');

      expect(result).toBe(true);
      expect(mockApiService.put).toHaveBeenCalledWith(
        '/api/agents/a1',
        { isFavorite: true }
      );
      expect(agentSyncService.getFavoriteAgents()).toHaveLength(1);
    });

    test('should filter favorite agents', async () => {
      mockApiService.get.mockResolvedValue({
        success: true,
        data: {
          agents: [
            mockAgent('a1', new Date('2024-01-01'), { isFavorite: true }),
            mockAgent('a2', new Date('2024-01-02'), { isFavorite: false }),
          ],
        },
      });
      await agentSyncService.syncAgents('user-1', 'device-1');

      const favorites = agentSyncService.getFavoriteAgents();
      expect(favorites).toHaveLength(1);
      expect(favorites[0].id).toBe('a1');
    });
  });

  // ========================================================================
  // Prompt Caching Tests
  // ========================================================================

  describe('Prompt Caching', () => {
    test('should cache and retrieve agent prompts', async () => {
      mockApiService.get.mockResolvedValue({
        success: true,
        data: { agents: [mockAgent('a1', new Date('2024-01-01'))] },
      });
      await agentSyncService.syncAgents('user-1', 'device-1');

      await agentSyncService.cachePrompt('a1', 'Custom prompt');
      expect(agentSyncService.getCachedPrompt('a1')).toBe('Custom prompt');
    });

    test('should return null for prompts of uncached agents', async () => {
      await agentSyncService.cachePrompt('missing', 'nope');
      expect(agentSyncService.getCachedPrompt('missing')).toBeNull();
    });
  });

  // ========================================================================
  // Execution History Tests
  // ========================================================================

  describe('Execution History', () => {
    const mockExecution = (id: string, agentId: string, executedAt: Date) => ({
      id,
      agentId,
      message: `msg ${id}`,
      response: 'response',
      executedAt,
      duration: 100,
      success: true,
    });

    test('should record executions and cap history at 50 entries', async () => {
      for (let i = 0; i < 55; i++) {
        await agentSyncService.recordExecution(mockExecution(`e${i}`, 'a1', new Date()));
      }

      expect(agentSyncService.getExecutionHistory('a1')).toHaveLength(50);
    });

    test('should filter by agent and sort newest first', async () => {
      await agentSyncService.recordExecution(
        mockExecution('e1', 'a1', new Date('2024-01-01T10:00:00Z'))
      );
      await agentSyncService.recordExecution(
        mockExecution('e2', 'a2', new Date('2024-01-01T11:00:00Z'))
      );
      await agentSyncService.recordExecution(
        mockExecution('e3', 'a1', new Date('2024-01-01T12:00:00Z'))
      );

      const history = agentSyncService.getExecutionHistory('a1');
      expect(history).toHaveLength(2);
      expect(history[0].id).toBe('e3');
      expect(history[1].id).toBe('e1');
    });

    test('should queue executions to offline sync and clear the queue', async () => {
      await agentSyncService.recordExecution(mockExecution('e1', 'a1', new Date()));
      await agentSyncService.recordExecution(mockExecution('e2', 'a1', new Date()));

      await agentSyncService.syncExecutions('user-1', 'device-1');

      expect(mockOfflineSyncService.queueAction).toHaveBeenCalledTimes(2);
      expect(mockOfflineSyncService.queueAction).toHaveBeenCalledWith(
        'agent_message',
        { agentId: 'a1', message: 'msg e1', sessionId: 'e1' },
        'low',
        'user-1',
        'device-1'
      );
      // Queue cleared after sync
      expect(agentSyncService.getExecutionHistory('a1')).toHaveLength(0);
    });

    test('should no-op syncExecutions when queue is empty', async () => {
      await agentSyncService.syncExecutions('user-1', 'device-1');
      expect(mockOfflineSyncService.queueAction).not.toHaveBeenCalled();
    });
  });

  // ========================================================================
  // Health Status Tests
  // ========================================================================

  describe('Health Status', () => {
    test('should report healthy when failures are below threshold', async () => {
      mockOfflineSyncService.getSyncState.mockResolvedValue({
        ...onlineState,
        consecutiveFailures: 2,
      });

      const health = await agentSyncService.getHealthStatus();

      expect(health.isHealthy).toBe(true);
      expect(health.errorRate).toBe(1);
      expect(health.cacheSize).toBe(0);
      expect(health.pendingCount).toBe(0);
    });

    test('should report unhealthy after 3 consecutive failures', async () => {
      mockOfflineSyncService.getSyncState.mockResolvedValue({
        ...onlineState,
        consecutiveFailures: 3,
      });

      const health = await agentSyncService.getHealthStatus();
      expect(health.isHealthy).toBe(false);
    });
  });

  // ========================================================================
  // Cache Lifecycle Tests
  // ========================================================================

  describe('Cache Lifecycle', () => {
    test('should clear the cache and persist the empty state', async () => {
      mockApiService.get.mockResolvedValue({
        success: true,
        data: { agents: [mockAgent('a1', new Date())] },
      });
      await agentSyncService.syncAgents('user-1', 'device-1');

      await agentSyncService.clearCache();

      expect(agentSyncService.getAllAgents()).toHaveLength(0);
      expect(mockStorageService.setObject).toHaveBeenCalled();
    });

    test('should load cached agents and executions from storage on initialize', async () => {
      mockStorageService.getObject.mockResolvedValue({
        agents: {
          a1: {
            ...mockAgent('a1', new Date('2024-01-01')),
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z',
          },
        },
        lastSyncAt: '2024-01-02T00:00:00Z',
        pendingExecutions: [
          {
            id: 'e1',
            agentId: 'a1',
            message: 'hi',
            response: 'yo',
            executedAt: '2024-01-03T00:00:00Z',
            duration: 5,
            success: true,
          },
        ],
        favorites: [],
      });

      let fresh: typeof agentSyncService;
      jest.isolateModules(() => {
        fresh = require('../../services/agentSyncService').agentSyncService;
      });
      await fresh.initialize();

      expect(fresh.getAllAgents()).toHaveLength(1);
      expect(fresh.getAllAgents()[0].id).toBe('a1');
      // Dates are hydrated from ISO strings
      expect(fresh.getAllAgents()[0].updatedAt).toBeInstanceOf(Date);
      expect(fresh.getExecutionHistory('a1')).toHaveLength(1);
      expect(fresh.getExecutionHistory('a1')[0].executedAt).toBeInstanceOf(Date);

      fresh.destroy();
    });
  });
});
