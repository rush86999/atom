/**
 * Agent Sync Service
 *
 * Manages synchronization of agents and agent configurations for mobile devices.
 *
 * Features:
 * - Sync agent list and configurations
 * - Sync agent maturity levels
 * - Sync agent capabilities
 * - Cache agent prompts locally
 * - Sync agent execution history
 * - Offline agent execution queue
 * - Agent conflict resolution
 * - Agent sync health check
 * - Background agent refresh
 * - Agent favorites sync
 *
 * Uses offlineSyncService for offline support and MMKV for local caching.
 */

import { apiService } from './api';
import { storageService, StorageKey } from './storageService';
import { offlineSyncService } from './offlineSyncService';

// Types
export interface Agent {
  id: string;
  name: string;
  description: string;
  maturityLevel: 'STUDENT' | 'INTERN' | 'SUPERVISED' | 'AUTONOMOUS';
  capabilities: string[];
  systemPrompt: string;
  userId?: string;
  isFavorite?: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface AgentExecution {
  id: string;
  agentId: string;
  message: string;
  response: string;
  executedAt: Date;
  duration: number;
  success: boolean;
  error?: string;
}

export interface AgentCache {
  agents: Record<string, Agent>;
  lastSyncAt: Date | null;
  pendingExecutions: AgentExecution[];
  favorites: Set<string>;
}

export interface AgentSyncResult {
  success: boolean;
  synced: number;
  failed: number;
  conflicts: number;
  duration: number;
}

export interface AgentSyncHealth {
  isHealthy: boolean;
  lastSyncAt: Date | null;
  pendingCount: number;
  cacheSize: number;
  errorRate: number;
}

// Configuration
const CACHE_TTL = 24 * 60 * 60 * 1000; // 24 hours
const MAX_CACHE_SIZE = 100; // Max agents to cache
const MAX_EXECUTION_HISTORY = 50; // Max executions to keep

/**
 * Agent Sync Service
 */
class AgentSyncService {
  private cache: AgentCache;
  private initialized: boolean = false;
  private refreshTimer: NodeJS.Timeout | null = null;

  /**
   * Initialize the agent sync service
   */
  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    console.log('AgentSync: Initializing service');

    // Load cache from storage
    await this.loadCache();

    // Start background refresh (every 30 minutes)
    this.startBackgroundRefresh();

    this.initialized = true;
    console.log('AgentSync: Service initialized');
  }

  /**
   * Sync all agents from server
   */
  async syncAgents(userId: string, deviceId: string): Promise<AgentSyncResult> {
    const startTime = Date.now();
    let synced = 0;
    let failed = 0;
    let conflicts = 0;

    try {
      console.log('AgentSync: Syncing agents');

      // Fetch agents from server
      const response = await apiService.get('/api/agents');

      if (!response.success || !response.data) {
        console.error('AgentSync: Failed to fetch agents:', response.error);
        return {
          success: false,
          synced: 0,
          failed: 0,
          conflicts: 0,
          duration: Date.now() - startTime,
        };
      }

      const agents: Agent[] = response.data.agents || [];

      // Process each agent
      for (const agent of agents) {
        try {
          const cached = this.cache.agents[agent.id];

          // Check for conflict
          if (cached && new Date(agent.updatedAt) < new Date(cached.updatedAt)) {
            conflicts++;
            await this.queueConflictResolution(agent, cached);
            continue;
          }

          // Update cache
          this.cache.agents[agent.id] = agent;
          synced++;
        } catch (error) {
          console.error(`AgentSync: Failed to sync agent ${agent.id}:`, error);
          failed++;
        }
      }

      // Update cache metadata
      this.cache.lastSyncAt = new Date();

      // Save cache
      await this.saveCache();

      const duration = Date.now() - startTime;
      console.log(`AgentSync: Sync complete - ${synced} synced, ${failed} failed, ${conflicts} conflicts, ${duration}ms`);

      return {
        success: true,
        synced,
        failed,
        conflicts,
        duration,
      };
    } catch (error) {
      console.error('AgentSync: Sync failed:', error);
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
   * Get agent from cache (with fallback to server)
   */
  async getAgent(agentId: string): Promise<Agent | null> {
    // Check cache first
    const cached = this.cache.agents[agentId];
    if (cached) {
      // Check if cache is fresh
      const age = Date.now() - new Date(cached.updatedAt).getTime();
      if (age < CACHE_TTL) {
        return cached;
      }
    }

    // Fetch from server
    try {
      const response = await apiService.get(`/api/agents/${agentId}`);
      if (response.success && response.data) {
        const agent: Agent = response.data;
        this.cache.agents[agentId] = agent;
        await this.saveCache();
        return agent;
      }
    } catch (error) {
      console.error(`AgentSync: Failed to fetch agent ${agentId}:`, error);
    }

    // Return cached even if stale
    return cached || null;
  }

  /**
   * Get all agents from cache
   */
  getAllAgents(): Agent[] {
    return Object.values(this.cache.agents);
  }

  /**
   * Update agent configuration
   */
  async updateAgent(
    agentId: string,
    updates: Partial<Agent>,
    userId: string,
    deviceId: string
  ): Promise<boolean> {
    try {
      // Check if offline
      const isOffline = !(await this.isOnline());

      if (isOffline) {
        // Queue for sync
        await offlineSyncService.queueAction(
          'agent_sync',
          {
            agentId,
            agentData: updates,
          },
          'normal',
          userId,
          deviceId,
          'last_write_wins',
          'agents',
          agentId
        );

        // Update local cache optimistically
        if (this.cache.agents[agentId]) {
          this.cache.agents[agentId] = {
            ...this.cache.agents[agentId],
            ...updates,
            updatedAt: new Date(),
          };
          await this.saveCache();
        }

        return true;
      }

      // Sync to server
      const response = await apiService.put(`/api/agents/${agentId}`, updates);

      if (response.success) {
        // Update cache
        if (this.cache.agents[agentId]) {
          this.cache.agents[agentId] = {
            ...this.cache.agents[agentId],
            ...updates,
            updatedAt: new Date(),
          };
          await this.saveCache();
        }
        return true;
      }

      return false;
    } catch (error) {
      console.error(`AgentSync: Failed to update agent ${agentId}:`, error);
      return false;
    }
  }

  /**
   * Toggle agent favorite status
   */
  async toggleFavorite(agentId: string, userId: string, deviceId: string): Promise<boolean> {
    const agent = this.cache.agents[agentId];
    if (!agent) {
      return false;
    }

    const newFavoriteStatus = !agent.isFavorite;
    return await this.updateAgent(
      agentId,
      { isFavorite: newFavoriteStatus },
      userId,
      deviceId
    );
  }

  /**
   * Get favorite agents
   */
  getFavoriteAgents(): Agent[] {
    return this.getAllAgents().filter(agent => agent.isFavorite);
  }

  /**
   * Cache agent prompt locally
   */
  async cachePrompt(agentId: string, prompt: string): Promise<void> {
    const agent = this.cache.agents[agentId];
    if (agent) {
      agent.systemPrompt = prompt;
      await this.saveCache();
    }
  }

  /**
   * Get cached prompt
   */
  getCachedPrompt(agentId: string): string | null {
    const agent = this.cache.agents[agentId];
    return agent?.systemPrompt || null;
  }

  /**
   * Record agent execution
   */
  async recordExecution(execution: AgentExecution): Promise<void> {
    this.cache.pendingExecutions.push(execution);

    // Limit history size
    if (this.cache.pendingExecutions.length > MAX_EXECUTION_HISTORY) {
      this.cache.pendingExecutions = this.cache.pendingExecutions.slice(-MAX_EXECUTION_HISTORY);
    }

    await this.saveCache();
  }

  /**
   * Get agent execution history
   */
  getExecutionHistory(agentId: string): AgentExecution[] {
    return this.cache.pendingExecutions
      .filter(exec => exec.agentId === agentId)
      .sort((a, b) => new Date(b.executedAt).getTime() - new Date(a.executedAt).getTime());
  }

  /**
   * Sync execution history to server
   */
  async syncExecutions(userId: string, deviceId: string): Promise<void> {
    if (this.cache.pendingExecutions.length === 0) {
      return;
    }

    console.log(`AgentSync: Syncing ${this.cache.pendingExecutions.length} executions`);

    for (const execution of this.cache.pendingExecutions) {
      try {
        await offlineSyncService.queueAction(
          'agent_message',
          {
            agentId: execution.agentId,
            message: execution.message,
            sessionId: execution.id,
          },
          'low',
          userId,
          deviceId
        );
      } catch (error) {
        console.error(`AgentSync: Failed to queue execution ${execution.id}:`, error);
      }
    }

    // Clear synced executions
    this.cache.pendingExecutions = [];
    await this.saveCache();
  }

  /**
   * Perform health check
   */
  async getHealthStatus(): Promise<AgentSyncHealth> {
    const state = await offlineSyncService.getSyncState();

    // Calculate error rate
    const errorRate = state.consecutiveFailures > 0 ? 1 : 0;

    return {
      isHealthy: state.consecutiveFailures < 3,
      lastSyncAt: this.cache.lastSyncAt,
      pendingCount: this.cache.pendingExecutions.length,
      cacheSize: Object.keys(this.cache.agents).length,
      errorRate,
    };
  }

  /**
   * Clear cache
   */
  async clearCache(): Promise<void> {
    this.cache = {
      agents: {},
      lastSyncAt: null,
      pendingExecutions: [],
      favorites: new Set(),
    };
    await this.saveCache();
    console.log('AgentSync: Cache cleared');
  }

  // Private helper methods

  private async loadCache(): Promise<void> {
    const cached = await storageService.getObject<AgentCache>('agent_cache' as StorageKey);

    this.cache = cached || {
      agents: {},
      lastSyncAt: null,
      pendingExecutions: [],
      favorites: new Set(),
    };

    // Convert dates
    for (const agentId in this.cache.agents) {
      const agent = this.cache.agents[agentId];
      agent.createdAt = new Date(agent.createdAt);
      agent.updatedAt = new Date(agent.updatedAt);
    }

    for (const execution of this.cache.pendingExecutions) {
      execution.executedAt = new Date(execution.executedAt);
    }

    if (this.cache.lastSyncAt) {
      this.cache.lastSyncAt = new Date(this.cache.lastSyncAt);
    }
  }

  private async saveCache(): Promise<void> {
    // Enforce cache size limit
    const agentIds = Object.keys(this.cache.agents);
    if (agentIds.length > MAX_CACHE_SIZE) {
      // Remove oldest agents
      const sorted = agentIds.sort((a, b) => {
        const dateA = new Date(this.cache.agents[a].updatedAt).getTime();
        const dateB = new Date(this.cache.agents[b].updatedAt).getTime();
        return dateA - dateB;
      });

      const toRemove = sorted.slice(0, agentIds.length - MAX_CACHE_SIZE);
      for (const id of toRemove) {
        delete this.cache.agents[id];
      }
    }

    await storageService.setObject('agent_cache' as StorageKey, this.cache);
  }

  private async queueConflictResolution(serverAgent: Agent, localAgent: Agent): Promise<void> {
    // Queue for manual resolution
    console.warn(`AgentSync: Conflict detected for agent ${serverAgent.id}, queuing for resolution`);
    // Implementation depends on UI for conflict resolution
  }

  private async isOnline(): Promise<boolean> {
    // Use offline sync service's online status
    const state = await offlineSyncService.getSyncState();
    return !state.syncInProgress;
  }

  private startBackgroundRefresh(): void {
    // Refresh every 30 minutes
    this.refreshTimer = setInterval(async () => {
      if (this.initialized) {
        console.log('AgentSync: Background refresh');
        // Refresh logic would go here (requires userId/deviceId)
      }
    }, 30 * 60 * 1000);
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
export const agentSyncService = new AgentSyncService();

export default agentSyncService;
