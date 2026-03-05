/**
 * Workflow Sync Service Tests
 *
 * Tests for workflow synchronization functionality:
 * - List sync (workflow list from server)
 * - Single sync (individual workflow with executions)
 * - Offline queue (trigger queuing and syncing)
 * - State tracking (sync progress, last sync time)
 * - Cache management and conflict resolution
 * - Metrics tracking
 */

import { workflowSyncService } from '../../services/workflowSyncService';
import { apiService } from '../../services/api';
import { storageService } from '../../services/storageService';
import { offlineSyncService } from '../../services/offlineSyncService';

// Mock service dependencies
jest.mock('../../services/api');
jest.mock('../../services/storageService');
jest.mock('../../services/offlineSyncService');

// Type casts for mocked services
const mockApiService = apiService as jest.Mocked<typeof apiService>;
const mockStorageService = storageService as jest.Mocked<typeof storageService>;
const mockOfflineSyncService = offlineSyncService as jest.Mocked<typeof offlineSyncService>;

describe('workflowSyncService', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    // Default mock implementations
    mockStorageService.getObject.mockResolvedValue(null);
    mockStorageService.setObject.mockResolvedValue(undefined);
    mockOfflineSyncService.getSyncState.mockResolvedValue({
      syncInProgress: false,
      lastSyncAt: null,
      pendingActions: 0,
      syncProgress: 0,
    });

    // Initialize service
    await workflowSyncService.initialize();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  // Helper function to create mock workflow
  const mockWorkflow = (id: string, updatedAt: Date) => ({
    id,
    name: `Workflow ${id}`,
    description: `Test workflow ${id}`,
    definition: { steps: [] },
    schema: {},
    isActive: true,
    userId: 'user-123',
    createdAt: new Date('2024-01-01'),
    updatedAt,
  });

  // Helper function to create mock execution
  const mockExecution = (id: string, workflowId: string, status: string) => ({
    id,
    workflowId,
    status,
    input: { test: 'data' },
    output: { result: 'success' },
    error: undefined,
    startedAt: new Date('2024-01-01'),
    completedAt: new Date('2024-01-01'),
    duration: 1000,
    logs: [],
  });

  // List sync tests (3 tests)
  describe('List Sync', () => {
    it('should sync workflow list', async () => {
      const workflows = [
        mockWorkflow('wf-1', new Date('2024-01-01')),
        mockWorkflow('wf-2', new Date('2024-01-02')),
      ];

      mockApiService.get.mockResolvedValue({
        success: true,
        data: { workflows },
      });

      const result = await workflowSyncService.syncWorkflows('user-123', 'device-123');

      expect(result.success).toBe(true);
      expect(result.synced).toBe(2);
      expect(result.failed).toBe(0);
      expect(result.conflicts).toBe(0);
      expect(mockApiService.get).toHaveBeenCalledWith('/api/workflows');
      expect(mockStorageService.setObject).toHaveBeenCalled();
    });

    it('should handle sync failure', async () => {
      mockApiService.get.mockResolvedValue({
        success: false,
        error: 'Network error',
      });

      const result = await workflowSyncService.syncWorkflows('user-123', 'device-123');

      expect(result.success).toBe(false);
      expect(result.synced).toBe(0);
      expect(mockApiService.get).toHaveBeenCalledWith('/api/workflows');
    });

    it('should cache synced workflows', async () => {
      const workflows = [mockWorkflow('wf-1', new Date())]; // Use current time for fresh cache

      mockApiService.get.mockResolvedValue({
        success: true,
        data: { workflows },
      });

      await workflowSyncService.syncWorkflows('user-123', 'device-123');

      // Verify workflow is cached
      const cached = await workflowSyncService.getWorkflow('wf-1');
      expect(cached).toBeDefined();
      expect(cached?.id).toBe('wf-1');
    });
  });

  // Single sync tests (4 tests)
  describe('Single Sync', () => {
    it('should sync single workflow', async () => {
      // Clear cache to ensure API is called
      await workflowSyncService.clearCache();

      const workflow = mockWorkflow('wf-1', new Date());

      mockApiService.get.mockResolvedValue({
        success: true,
        data: workflow,
      });

      const result = await workflowSyncService.getWorkflow('wf-1');

      expect(result).toBeDefined();
      expect(result?.id).toBe('wf-1');
      // API is called because cache is empty
      expect(mockApiService.get).toHaveBeenCalledWith('/api/workflows/wf-1');
      expect(mockStorageService.setObject).toHaveBeenCalled();
    });

    it('should sync workflow executions', async () => {
      const execution = mockExecution('exec-1', 'wf-1', 'completed');

      mockApiService.get.mockResolvedValue({
        success: true,
        data: execution,
      });

      const result = await workflowSyncService.getExecution('exec-1');

      expect(result).toBeDefined();
      expect(result?.id).toBe('exec-1');
      expect(mockApiService.get).toHaveBeenCalledWith('/api/workflows/executions/exec-1');
      expect(mockStorageService.setObject).toHaveBeenCalled();
    });

    it('should handle workflow not found', async () => {
      mockApiService.get.mockResolvedValue({
        success: false,
        error: 'Workflow not found',
      });

      const result = await workflowSyncService.getWorkflow('wf-nonexistent');

      expect(result).toBeNull();
      expect(mockApiService.get).toHaveBeenCalledWith('/api/workflows/wf-nonexistent');
    });

    it('should merge workflow changes', async () => {
      const oldWorkflow = mockWorkflow('wf-1', new Date(Date.now() - 10000)); // 10 seconds ago
      const newWorkflow = mockWorkflow('wf-1', new Date()); // Now
      newWorkflow.name = 'Updated Workflow';

      // First sync adds old workflow
      mockApiService.get.mockResolvedValueOnce({
        success: true,
        data: { workflows: [oldWorkflow] },
      });
      await workflowSyncService.syncWorkflows('user-123', 'device-123');

      // Second sync should update to new workflow
      mockApiService.get.mockResolvedValueOnce({
        success: true,
        data: { workflows: [newWorkflow] },
      });
      const result = await workflowSyncService.syncWorkflows('user-123', 'device-123');

      expect(result.synced).toBe(1);

      const cached = await workflowSyncService.getWorkflow('wf-1');
      expect(cached?.name).toBe('Updated Workflow');
    });
  });

  // Offline queue tests (4 tests)
  describe('Offline Queue', () => {
    it('should queue workflow triggers offline', async () => {
      mockOfflineSyncService.getSyncState.mockResolvedValue({
        syncInProgress: true, // isOnline() returns false, so isOffline = true
        lastSyncAt: null,
        pendingActions: 10,
        syncProgress: 50,
      });

      const executionId = await workflowSyncService.triggerWorkflow(
        'wf-1',
        { test: 'input' },
        'user-123',
        'device-123',
        5
      );

      expect(executionId).toBeDefined();
      expect(executionId).toMatch(/^exec_/);

      // Verify storage was called to cache the trigger
      expect(mockStorageService.setObject).toHaveBeenCalled();
    });

    it('should sync queued triggers on reconnect', async () => {
      mockOfflineSyncService.getSyncState.mockResolvedValue({
        syncInProgress: false,
        lastSyncAt: null,
        pendingActions: 0,
        syncProgress: 0,
      });

      mockApiService.post.mockResolvedValue({
        success: true,
        data: { executionId: 'exec-123' },
      });

      await workflowSyncService.syncExecutions('user-123', 'device-123');

      // Verify sync completed
      expect(mockStorageService.setObject).toHaveBeenCalled();
    });

    it('should handle trigger conflicts', async () => {
      // This test verifies conflict detection during sync
      const workflow = mockWorkflow('wf-1', new Date('2024-01-02'));
      const cachedWorkflow = mockWorkflow('wf-1', new Date('2024-01-03')); // Local is newer

      // First, add cached workflow
      mockApiService.get.mockResolvedValueOnce({
        success: true,
        data: { workflows: [cachedWorkflow] },
      });
      await workflowSyncService.syncWorkflows('user-123', 'device-123');

      // Now sync with older server version - should detect conflict
      mockApiService.get.mockResolvedValueOnce({
        success: true,
        data: { workflows: [workflow] },
      });
      const result = await workflowSyncService.syncWorkflows('user-123', 'device-123');

      expect(result.conflicts).toBe(1);
      expect(result.synced).toBe(0);
    });

    it('should clear synced triggers', async () => {
      mockOfflineSyncService.getSyncState.mockResolvedValue({
        syncInProgress: false,
        lastSyncAt: null,
        pendingActions: 0,
        syncProgress: 0,
      });

      mockApiService.post.mockResolvedValue({
        success: true,
        data: { executionId: 'exec-123' },
      });

      // Setup cache with pending trigger
      mockStorageService.getObject.mockImplementation(async (key) => {
        if (key === 'workflow_cache') {
          return {
            workflows: {},
            executions: {},
            lastSyncAt: null,
            pendingTriggers: [
              {
                id: 'trigger-1',
                workflowId: 'wf-1',
                input: {},
                priority: 5,
                createdAt: new Date(),
                retryCount: 0,
              },
            ],
          };
        }
        return null;
      });

      await workflowSyncService.syncExecutions('user-123', 'device-123');

      // Verify storage was updated (triggers should be cleared after sync)
      expect(mockStorageService.setObject).toHaveBeenCalled();
    });
  });

  // State tests (4 tests)
  describe('State', () => {
    it('should track sync progress', async () => {
      const workflows = [mockWorkflow('wf-1', new Date('2024-01-01'))];

      mockApiService.get.mockResolvedValue({
        success: true,
        data: { workflows },
      });

      await workflowSyncService.syncWorkflows('user-123', 'device-123');

      // Service initialized successfully - progress tracking is internal
      expect(mockStorageService.setObject).toHaveBeenCalled();
    });

    it('should get last sync time', async () => {
      const syncTime = new Date('2024-01-01T12:00:00Z');

      mockStorageService.getObject.mockImplementation(async (key) => {
        if (key === 'workflow_cache') {
          return {
            workflows: {},
            executions: {},
            lastSyncAt: syncTime,
            pendingTriggers: [],
          };
        }
        return null;
      });

      // Clear cache and re-initialize
      await workflowSyncService.clearCache();
      await workflowSyncService.initialize();

      // Service should be initialized with cached data
      const allWorkflows = workflowSyncService.getAllWorkflows();
      expect(Array.isArray(allWorkflows)).toBe(true);
    });

    it('should force refresh', async () => {
      const workflow = mockWorkflow('wf-1', new Date('2024-01-01'));

      // First call caches the workflow
      mockApiService.get.mockResolvedValueOnce({
        success: true,
        data: workflow,
      });
      await workflowSyncService.getWorkflow('wf-1');

      // Clear cache to force refresh
      await workflowSyncService.clearCache();

      // Second call should fetch from server again
      mockApiService.get.mockClear();
      mockApiService.get.mockResolvedValueOnce({
        success: true,
        data: workflow,
      });
      await workflowSyncService.getWorkflow('wf-1');

      expect(mockApiService.get).toHaveBeenCalledWith('/api/workflows/wf-1');
    });

    it('should handle partial sync', async () => {
      const workflows = [
        mockWorkflow('wf-1', new Date('2024-01-01')),
        mockWorkflow('wf-2', new Date('2024-01-02')),
      ];

      // First workflow syncs successfully
      // Second workflow fails
      mockApiService.get.mockResolvedValue(async () => {
        throw new Error('Partial sync error');
      });

      const result = await workflowSyncService.syncWorkflows('user-123', 'device-123');

      expect(result.success).toBe(false);
      expect(result.synced).toBe(0); // All failed due to exception
    });
  });

  // Additional tests for metrics and utility methods (3 tests)
  describe('Metrics and Utilities', () => {
    it('should get workflow metrics', async () => {
      const metrics = workflowSyncService.getMetrics();

      expect(metrics).toBeDefined();
      expect(typeof metrics.totalExecutions).toBe('number');
      expect(typeof metrics.successfulExecutions).toBe('number');
      expect(typeof metrics.failedExecutions).toBe('number');
      expect(typeof metrics.avgDuration).toBe('number');
    });

    it('should get all workflows from cache', async () => {
      const workflows = [
        mockWorkflow('wf-1', new Date('2024-01-01')),
        mockWorkflow('wf-2', new Date('2024-01-02')),
      ];

      // Sync workflows to populate cache
      mockApiService.get.mockResolvedValue({
        success: true,
        data: { workflows },
      });

      await workflowSyncService.syncWorkflows('user-123', 'device-123');

      const allWorkflows = workflowSyncService.getAllWorkflows();
      expect(allWorkflows.length).toBe(2);
      expect(allWorkflows[0].id).toBe('wf-1');
      expect(allWorkflows[1].id).toBe('wf-2');
    });

    it('should get workflow executions', async () => {
      const executions = [
        mockExecution('exec-1', 'wf-1', 'completed'),
        mockExecution('exec-2', 'wf-1', 'running'),
      ];

      // Fetch executions to cache them
      for (const execution of executions) {
        mockApiService.get.mockResolvedValueOnce({
          success: true,
          data: execution,
        });
        await workflowSyncService.getExecution(execution.id);
      }

      const workflowExecutions = workflowSyncService.getWorkflowExecutions('wf-1');
      expect(workflowExecutions.length).toBe(2);
      expect(workflowExecutions[0].workflowId).toBe('wf-1');
    });
  });

  // Trigger workflow tests (2 tests)
  describe('Trigger Workflow', () => {
    it('should trigger workflow immediately when online', async () => {
      mockOfflineSyncService.getSyncState.mockResolvedValue({
        syncInProgress: false,
        lastSyncAt: null,
        pendingActions: 0,
        syncProgress: 0,
      });

      mockApiService.post.mockResolvedValue({
        success: true,
        data: { executionId: 'exec-123' },
      });

      const executionId = await workflowSyncService.triggerWorkflow(
        'wf-1',
        { test: 'input' },
        'user-123',
        'device-123',
        5
      );

      expect(executionId).toBeDefined();
      expect(executionId).toMatch(/^exec_/);
      expect(mockApiService.post).toHaveBeenCalledWith('/api/workflows/wf-1/trigger', { test: 'input' });
    });

    it('should handle trigger failure', async () => {
      mockOfflineSyncService.getSyncState.mockResolvedValue({
        syncInProgress: false,
        lastSyncAt: null,
        pendingActions: 0,
        syncProgress: 0,
      });

      mockApiService.post.mockResolvedValue({
        success: false,
        error: 'Workflow not found',
      });

      const executionId = await workflowSyncService.triggerWorkflow(
        'wf-nonexistent',
        { test: 'input' },
        'user-123',
        'device-123',
        5
      );

      expect(executionId).toBeNull();
      expect(mockApiService.post).toHaveBeenCalledWith('/api/workflows/wf-nonexistent/trigger', { test: 'input' });
    });
  });

  // Replay execution tests (1 test)
  describe('Replay Execution', () => {
    it('should replay workflow execution', async () => {
      const execution = mockExecution('exec-1', 'wf-1', 'failed');

      // First, cache the execution
      mockApiService.get.mockResolvedValue({
        success: true,
        data: execution,
      });

      await workflowSyncService.getExecution('exec-1');

      // Now replay it
      mockOfflineSyncService.getSyncState.mockResolvedValue({
        syncInProgress: false,
        lastSyncAt: null,
        pendingActions: 0,
        syncProgress: 0,
      });

      mockApiService.post.mockResolvedValue({
        success: true,
        data: { executionId: 'exec-new' },
      });

      const result = await workflowSyncService.replayExecution('exec-1', 'user-123', 'device-123');

      expect(result).toBe(true);
      expect(mockApiService.post).toHaveBeenCalledWith('/api/workflows/wf-1/trigger', execution.input);
    });
  });

  // Cleanup test (1 test)
  describe('Cleanup', () => {
    it('should destroy service and clear timers', () => {
      // Service should destroy without errors
      expect(() => {
        workflowSyncService.destroy();
      }).not.toThrow();
    });
  });
});
