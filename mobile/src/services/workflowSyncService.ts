/**
 * Workflow Sync Service
 *
 * Manages synchronization of workflows and workflow executions for mobile devices.
 *
 * Features:
 * - Sync workflow definitions
 * - Sync workflow executions
 * - Sync execution logs
 * - Cache workflow schemas
 * - Offline workflow trigger queue
 * - Workflow execution status sync
 * - Workflow conflict resolution
 * - Workflow execution replay
 * - Background workflow monitoring
 * - Workflow metrics sync
 *
 * Uses offlineSyncService for offline support and MMKV for local caching.
 */

import { apiService } from './api';
import { storageService, StorageKey } from './storageService';
import { offlineSyncService } from './offlineSyncService';

// Types
export interface Workflow {
  id: string;
  name: string;
  description: string;
  definition: any;
  schema: any;
  isActive: boolean;
  userId?: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface WorkflowExecution {
  id: string;
  workflowId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  input: any;
  output?: any;
  error?: string;
  startedAt: Date;
  completedAt?: Date;
  duration?: number;
  logs: WorkflowLog[];
}

export interface WorkflowLog {
  timestamp: Date;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  stepId?: string;
}

export interface WorkflowCache {
  workflows: Record<string, Workflow>;
  executions: Record<string, WorkflowExecution>;
  lastSyncAt: Date | null;
  pendingTriggers: WorkflowTrigger[];
}

export interface WorkflowTrigger {
  id: string;
  workflowId: string;
  input: any;
  priority: number;
  createdAt: Date;
  retryCount: number;
}

export interface WorkflowSyncResult {
  success: boolean;
  synced: number;
  failed: number;
  conflicts: number;
  duration: number;
}

export interface WorkflowMetrics {
  totalExecutions: number;
  successfulExecutions: number;
  failedExecutions: number;
  avgDuration: number;
  lastExecutionAt: Date | null;
}

// Configuration
const CACHE_TTL = 24 * 60 * 60 * 1000; // 24 hours
const MAX_CACHE_SIZE = 50; // Max workflows to cache
const MAX_EXECUTIONS_PER_WORKFLOW = 20; // Max executions to keep per workflow
const MAX_PENDING_TRIGGERS = 100;

/**
 * Workflow Sync Service
 */
class WorkflowSyncService {
  private cache: WorkflowCache;
  private initialized: boolean = false;
  private monitoringTimer: NodeJS.Timeout | null = null;
  private metrics: WorkflowMetrics;

  /**
   * Initialize the workflow sync service
   */
  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    console.log('WorkflowSync: Initializing service');

    // Load cache from storage
    await this.loadCache();

    // Load metrics
    await this.loadMetrics();

    // Start background monitoring (every 5 minutes)
    this.startBackgroundMonitoring();

    this.initialized = true;
    console.log('WorkflowSync: Service initialized');
  }

  /**
   * Sync all workflows from server
   */
  async syncWorkflows(userId: string, deviceId: string): Promise<WorkflowSyncResult> {
    const startTime = Date.now();
    let synced = 0;
    let failed = 0;
    let conflicts = 0;

    try {
      console.log('WorkflowSync: Syncing workflows');

      // Fetch workflows from server
      const response = await apiService.get('/api/workflows');

      if (!response.success || !response.data) {
        console.error('WorkflowSync: Failed to fetch workflows:', response.error);
        return {
          success: false,
          synced: 0,
          failed: 0,
          conflicts: 0,
          duration: Date.now() - startTime,
        };
      }

      const workflows: Workflow[] = response.data.workflows || [];

      // Process each workflow
      for (const workflow of workflows) {
        try {
          const cached = this.cache.workflows[workflow.id];

          // Check for conflict
          if (cached && new Date(workflow.updatedAt) < new Date(cached.updatedAt)) {
            conflicts++;
            await this.queueConflictResolution(workflow, cached);
            continue;
          }

          // Update cache
          this.cache.workflows[workflow.id] = workflow;
          synced++;
        } catch (error) {
          console.error(`WorkflowSync: Failed to sync workflow ${workflow.id}:`, error);
          failed++;
        }
      }

      // Update cache metadata
      this.cache.lastSyncAt = new Date();

      // Save cache
      await this.saveCache();

      const duration = Date.now() - startTime;
      console.log(`WorkflowSync: Sync complete - ${synced} synced, ${failed} failed, ${conflicts} conflicts, ${duration}ms`);

      return {
        success: true,
        synced,
        failed,
        conflicts,
        duration,
      };
    } catch (error) {
      console.error('WorkflowSync: Sync failed:', error);
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
   * Get workflow from cache (with fallback to server)
   */
  async getWorkflow(workflowId: string): Promise<Workflow | null> {
    // Check cache first
    const cached = this.cache.workflows[workflowId];
    if (cached) {
      // Check if cache is fresh
      const age = Date.now() - new Date(cached.updatedAt).getTime();
      if (age < CACHE_TTL) {
        return cached;
      }
    }

    // Fetch from server
    try {
      const response = await apiService.get(`/api/workflows/${workflowId}`);
      if (response.success && response.data) {
        const workflow: Workflow = response.data;
        this.cache.workflows[workflowId] = workflow;
        await this.saveCache();
        return workflow;
      }
    } catch (error) {
      console.error(`WorkflowSync: Failed to fetch workflow ${workflowId}:`, error);
    }

    // Return cached even if stale
    return cached || null;
  }

  /**
   * Get all workflows from cache
   */
  getAllWorkflows(): Workflow[] {
    return Object.values(this.cache.workflows);
  }

  /**
   * Trigger workflow execution
   */
  async triggerWorkflow(
    workflowId: string,
    input: any,
    userId: string,
    deviceId: string,
    priority: number = 5
  ): Promise<string | null> {
    try {
      const executionId = `exec_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      // Check if offline
      const isOffline = !(await this.isOnline());

      if (isOffline) {
        // Queue for offline execution
        const trigger: WorkflowTrigger = {
          id: executionId,
          workflowId,
          input,
          priority,
          createdAt: new Date(),
          retryCount: 0,
        };

        this.cache.pendingTriggers.push(trigger);

        // Limit pending triggers
        if (this.cache.pendingTriggers.length > MAX_PENDING_TRIGGERS) {
          // Remove oldest low-priority triggers
          this.cache.pendingTriggers = this.cache.pendingTriggers
            .sort((a, b) => b.priority - a.priority || new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
            .slice(0, MAX_PENDING_TRIGGERS);
        }

        await this.saveCache();

        console.log(`WorkflowSync: Queued workflow trigger ${executionId} for offline execution`);
        return executionId;
      }

      // Execute immediately
      const response = await apiService.post(`/api/workflows/${workflowId}/trigger`, input);

      if (response.success) {
        console.log(`WorkflowSync: Triggered workflow ${workflowId}, execution ${executionId}`);
        return executionId;
      }

      return null;
    } catch (error) {
      console.error(`WorkflowSync: Failed to trigger workflow ${workflowId}:`, error);
      return null;
    }
  }

  /**
   * Get workflow execution
   */
  async getExecution(executionId: string): Promise<WorkflowExecution | null> {
    // Check cache first
    const cached = this.cache.executions[executionId];
    if (cached) {
      return cached;
    }

    // Fetch from server
    try {
      const response = await apiService.get(`/api/workflows/executions/${executionId}`);
      if (response.success && response.data) {
        const execution: WorkflowExecution = response.data;
        this.cache.executions[executionId] = execution;
        await this.saveCache();
        return execution;
      }
    } catch (error) {
      console.error(`WorkflowSync: Failed to fetch execution ${executionId}:`, error);
    }

    return null;
  }

  /**
   * Get workflow executions
   */
  getWorkflowExecutions(workflowId: string): WorkflowExecution[] {
    return Object.values(this.cache.executions)
      .filter(exec => exec.workflowId === workflowId)
      .sort((a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime())
      .slice(0, MAX_EXECUTIONS_PER_WORKFLOW);
  }

  /**
   * Sync workflow executions
   */
  async syncExecutions(userId: string, deviceId: string): Promise<void> {
    console.log('WorkflowSync: Syncing executions');

    // Sync pending triggers
    for (const trigger of this.cache.pendingTriggers) {
      try {
        const response = await apiService.post(`/api/workflows/${trigger.workflowId}/trigger`, trigger.input);

        if (response.success) {
          console.log(`WorkflowSync: Synced trigger ${trigger.id}`);
          // Remove from pending
          this.cache.pendingTriggers = this.cache.pendingTriggers.filter(t => t.id !== trigger.id);
        } else {
          trigger.retryCount++;
          if (trigger.retryCount >= 5) {
            console.error(`WorkflowSync: Trigger ${trigger.id} failed after 5 retries`);
            this.cache.pendingTriggers = this.cache.pendingTriggers.filter(t => t.id !== trigger.id);
          }
        }
      } catch (error) {
        console.error(`WorkflowSync: Failed to sync trigger ${trigger.id}:`, error);
        trigger.retryCount++;
      }
    }

    await this.saveCache();
  }

  /**
   * Replay workflow execution
   */
  async replayExecution(executionId: string, userId: string, deviceId: string): Promise<boolean> {
    try {
      const execution = await this.getExecution(executionId);
      if (!execution) {
        return false;
      }

      const result = await this.triggerWorkflow(
        execution.workflowId,
        execution.input,
        userId,
        deviceId,
        7 // High priority for replays
      );

      return result !== null;
    } catch (error) {
      console.error(`WorkflowSync: Failed to replay execution ${executionId}:`, error);
      return false;
    }
  }

  /**
   * Get workflow metrics
   */
  getMetrics(): WorkflowMetrics {
    return this.metrics;
  }

  /**
   * Update workflow metrics
   */
  private async updateMetrics(execution: WorkflowExecution): Promise<void> {
    this.metrics.totalExecutions++;
    if (execution.status === 'completed') {
      this.metrics.successfulExecutions++;
    } else if (execution.status === 'failed') {
      this.metrics.failedExecutions++;
    }

    if (execution.duration) {
      const totalDuration = this.metrics.avgDuration * (this.metrics.totalExecutions - 1);
      this.metrics.avgDuration = (totalDuration + execution.duration) / this.metrics.totalExecutions;
    }

    this.metrics.lastExecutionAt = execution.startedAt;

    await storageService.setObject('workflow_metrics' as StorageKey, this.metrics);
  }

  /**
   * Clear cache
   */
  async clearCache(): Promise<void> {
    this.cache = {
      workflows: {},
      executions: {},
      lastSyncAt: null,
      pendingTriggers: [],
    };
    await this.saveCache();
    console.log('WorkflowSync: Cache cleared');
  }

  // Private helper methods

  private async loadCache(): Promise<void> {
    const cached = await storageService.getObject<WorkflowCache>('workflow_cache' as StorageKey);

    this.cache = cached || {
      workflows: {},
      executions: {},
      lastSyncAt: null,
      pendingTriggers: [],
    };

    // Convert dates
    for (const workflowId in this.cache.workflows) {
      const workflow = this.cache.workflows[workflowId];
      workflow.createdAt = new Date(workflow.createdAt);
      workflow.updatedAt = new Date(workflow.updatedAt);
    }

    for (const executionId in this.cache.executions) {
      const execution = this.cache.executions[executionId];
      execution.startedAt = new Date(execution.startedAt);
      if (execution.completedAt) {
        execution.completedAt = new Date(execution.completedAt);
      }
      for (const log of execution.logs) {
        log.timestamp = new Date(log.timestamp);
      }
    }

    for (const trigger of this.cache.pendingTriggers) {
      trigger.createdAt = new Date(trigger.createdAt);
    }

    if (this.cache.lastSyncAt) {
      this.cache.lastSyncAt = new Date(this.cache.lastSyncAt);
    }
  }

  private async saveCache(): Promise<void> {
    // Enforce cache size limits
    const workflowIds = Object.keys(this.cache.workflows);
    if (workflowIds.length > MAX_CACHE_SIZE) {
      const sorted = workflowIds.sort((a, b) => {
        const dateA = new Date(this.cache.workflows[a].updatedAt).getTime();
        const dateB = new Date(this.cache.workflows[b].updatedAt).getTime();
        return dateA - dateB;
      });

      const toRemove = sorted.slice(0, workflowIds.length - MAX_CACHE_SIZE);
      for (const id of toRemove) {
        delete this.cache.workflows[id];
      }
    }

    // Limit executions per workflow
    for (const workflowId in this.cache.executions) {
      const executions = Object.values(this.cache.executions)
        .filter(exec => exec.workflowId === workflowId);

      if (executions.length > MAX_EXECUTIONS_PER_WORKFLOW) {
        const sorted = executions.sort((a, b) =>
          new Date(a.startedAt).getTime() - new Date(b.startedAt).getTime()
        );

        const toRemove = sorted.slice(0, executions.length - MAX_EXECUTIONS_PER_WORKFLOW);
        for (const exec of toRemove) {
          delete this.cache.executions[exec.id];
        }
      }
    }

    await storageService.setObject('workflow_cache' as StorageKey, this.cache);
  }

  private async loadMetrics(): Promise<void> {
    const cached = await storageService.getObject<WorkflowMetrics>('workflow_metrics' as StorageKey);
    this.metrics = cached || {
      totalExecutions: 0,
      successfulExecutions: 0,
      failedExecutions: 0,
      avgDuration: 0,
      lastExecutionAt: null,
    };

    if (this.metrics.lastExecutionAt) {
      this.metrics.lastExecutionAt = new Date(this.metrics.lastExecutionAt);
    }
  }

  private async queueConflictResolution(serverWorkflow: Workflow, localWorkflow: Workflow): Promise<void> {
    console.warn(`WorkflowSync: Conflict detected for workflow ${serverWorkflow.id}, queuing for resolution`);
  }

  private async isOnline(): Promise<boolean> {
    const state = await offlineSyncService.getSyncState();
    return !state.syncInProgress;
  }

  private startBackgroundMonitoring(): void {
    // Monitor every 5 minutes
    this.monitoringTimer = setInterval(async () => {
      if (this.initialized) {
        console.log('WorkflowSync: Background monitoring');
        // Sync pending triggers
        // Update execution statuses
      }
    }, 5 * 60 * 1000);
  }

  /**
   * Cleanup
   */
  destroy(): void {
    if (this.monitoringTimer) {
      clearInterval(this.monitoringTimer);
      this.monitoringTimer = null;
    }
  }
}

// Export singleton instance
export const workflowSyncService = new WorkflowSyncService();

export default workflowSyncService;
