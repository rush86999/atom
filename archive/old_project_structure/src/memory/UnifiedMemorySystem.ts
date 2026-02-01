/**
 * Unified Memory System for ATOM Platform
 *
 * Provides consistent memory management across desktop and web platforms:
 * - Desktop: Uses localStorage for offline capability
 * - Web: Uses AWS S3 for cloud storage
 *
 * Maintains full UI and feature parity between platforms
 */

import { EventEmitter } from 'events';
import {
  MemoryStorageAdapter,
  StorageFactory,
  StorageConfig,
  MemoryQuery,
  MemoryStorageResult
} from './storage/StorageAdapter';

// Memory system interfaces
export interface UnifiedMemoryData {
  id: string;
  type: 'workflow' | 'automation' | 'user_pattern' | 'entity' | 'context' | 'insight' | 'conversation';
  content: any;
  embedding?: number[];
  metadata: UnifiedMemoryMetadata;
  timestamp: Date;
  expires?: Date;
  platform: 'desktop' | 'web';
  storageLocation: 'localStorage' | 's3';
}

export interface UnifiedMemoryMetadata {
  userId?: string;
  workspaceId?: string;
  platforms?: string[];
  tags?: string[];
  importance: number;
  accessCount: number;
  lastAccessed: Date;
  confidence?: number;
  relationships?: UnifiedMemoryRelationship[];
  size?: number;
}

export interface UnifiedMemoryRelationship {
  type: 'contains' | 'precedes' | 'follows' | 'related_to' | 'triggers' | 'depends_on';
  targetId: string;
  strength: number;
  metadata?: Record<string, any>;
}

export interface UnifiedMemoryQuery {
  type?: UnifiedMemoryData['type'];
  userId?: string;
  workspaceId?: string;
  tags?: string[];
  platform?: 'desktop' | 'web' | 'all';
  limit?: number;
  offset?: number;
  dateRange?: {
    start: Date;
    end: Date;
  };
  includeExpired?: boolean;
}

export interface UnifiedMemoryRetrieval {
  data: UnifiedMemoryData[];
  scores: number[];
  query: UnifiedMemoryQuery;
  processingTime: number;
  totalFound: number;
  platform: 'desktop' | 'web' | 'mixed';
}

export interface UnifiedMemoryStats {
  totalMemories: number;
  desktopMemories: number;
  webMemories: number;
  totalSize: number;
  desktopSize: number;
  webSize: number;
  storageUsage: {
    desktop: {
      usagePercentage: number;
      maxSize: number;
    };
    web: {
      usagePercentage: number;
      bucketName?: string;
    };
  };
  memoryTypes: Record<string, number>;
  lastSync?: Date;
}

export interface UnifiedMemorySystemConfig {
  platform: 'desktop' | 'web';
  userId: string;
  workspaceId?: string;
  storage: {
    useLocalStorage: boolean;
    offlineCapable: boolean;
    encryptionEnabled: boolean;
    localDataPath?: string;
    s3Config?: {
      bucketName: string;
      region: string;
      accessKeyId?: string;
      secretAccessKey?: string;
    };
  };
  memory: {
    maxAge?: number;
    maxSize?: number;
    cleanupInterval?: number;
    syncInterval?: number;
  };
}

/**
 * Unified Memory System
 *
 * Provides feature parity between desktop and web platforms with:
 * - Consistent API for memory operations
 * - Platform-appropriate storage backend
 * - Synchronization capabilities
 * - Memory lifecycle management
 */
export class UnifiedMemorySystem extends EventEmitter {
  private config: UnifiedMemorySystemConfig;
  private storageAdapter: MemoryStorageAdapter;
  private isInitialized: boolean = false;
  private memoryCache: Map<string, UnifiedMemoryData> = new Map();
  private cleanupInterval?: NodeJS.Timeout;
  private syncInterval?: NodeJS.Timeout;

  constructor(config: UnifiedMemorySystemConfig) {
    super();
    this.config = config;

    // Create appropriate storage adapter based on platform
    const storageConfig: StorageConfig = {
      platform: config.platform,
      useLocalStorage: config.storage.useLocalStorage,
      offlineCapable: config.storage.offlineCapable,
      encryptionEnabled: config.storage.encryptionEnabled,
      localDataPath: config.storage.localDataPath,
      s3Config: config.storage.s3Config
    };

    this.storageAdapter = StorageFactory.createStorageAdapter(storageConfig, this.getLogger());
  }

  /**
   * Initialize the memory system
   */
  async initialize(): Promise<boolean> {
    try {
      if (this.isInitialized) {
        return true;
      }

      console.log(`Initializing UnifiedMemorySystem for ${this.config.platform} platform...`);

      // Initialize storage adapter
      const storageInitialized = await this.storageAdapter.initialize();
      if (!storageInitialized) {
        throw new Error('Failed to initialize storage adapter');
      }

      // Load existing memories into cache
      await this.loadMemoriesIntoCache();

      // Setup periodic cleanup
      this.setupPeriodicCleanup();

      // Setup periodic sync (if applicable)
      this.setupPeriodicSync();

      this.isInitialized = true;
      console.log('UnifiedMemorySystem initialized successfully');
      this.emit('memory-system-initialized', { platform: this.config.platform });

      return true;
    } catch (error) {
      console.error('Failed to initialize UnifiedMemorySystem:', error);
      this.emit('memory-system-error', { error, platform: this.config.platform });
      return false;
    }
  }

  /**
   * Store a memory with platform-appropriate storage
   */
  async storeMemory(
    data: Omit<UnifiedMemoryData, 'id' | 'timestamp' | 'platform' | 'storageLocation'>
  ): Promise<string> {
    try {
      this.ensureInitialized();

      const memoryId = this.generateMemoryId();
      const now = new Date();

      // Create unified memory data
      const memoryData: UnifiedMemoryData = {
        ...data,
        id: memoryId,
        timestamp: now,
        platform: this.config.platform,
        storageLocation: this.config.storage.useLocalStorage ? 'localStorage' : 's3',
        metadata: {
          ...data.metadata,
          lastAccessed: now,
          accessCount: 0,
          size: this.calculateMemorySize(data)
        }
      };

      // Store using the appropriate storage adapter
      const result = await this.storageAdapter.storeMemory(memoryData);

      if (!result.success) {
        throw new Error(result.error || 'Failed to store memory');
      }

      // Update cache
      this.memoryCache.set(memoryId, memoryData);

      console.log(`Memory stored with ID: ${memoryId} on ${this.config.platform}`);
      this.emit('memory-stored', {
        memory: memoryData,
        platform: this.config.platform,
        storageLocation: memoryData.storageLocation
      });

      return memoryId;
    } catch (error) {
      console.error('Failed to store memory:', error);
      this.emit('memory-store-error', { error, platform: this.config.platform });
      throw error;
    }
  }

  /**
   * Retrieve a memory by ID
   */
  async retrieveMemory(memoryId: string): Promise<UnifiedMemoryData | null> {
    try {
      this.ensureInitialized();

      // Check cache first
      const cachedMemory = this.memoryCache.get(memoryId);
      if (cachedMemory) {
        // Update access metadata
        cachedMemory.metadata.lastAccessed = new Date();
        cachedMemory.metadata.accessCount = (cachedMemory.metadata.accessCount || 0) + 1;

        this.emit('memory-accessed', {
          memory: cachedMemory,
          platform: this.config.platform
        });

        return cachedMemory;
      }

      // Retrieve from storage
      const result = await this.storageAdapter.retrieveMemory(memoryId);

      if (!result.success || !result.data) {
        return null;
      }

      const memoryData = result.data as UnifiedMemoryData;

      // Update cache
      this.memoryCache.set(memoryId, memoryData);

      // Update access metadata
      memoryData.metadata.lastAccessed = new Date();
      memoryData.metadata.accessCount = (memoryData.metadata.accessCount || 0) + 1;

      this.emit('memory-accessed', {
        memory: memoryData,
        platform: this.config.platform
      });

      return memoryData;
    } catch (error) {
      console.error('Failed to retrieve memory:', error);
      this.emit('memory-retrieve-error', { error, memoryId, platform: this.config.platform });
      return null;
    }
  }

  /**
   * Query memories with filters
   */
  async queryMemories(query: UnifiedMemoryQuery): Promise<UnifiedMemoryRetrieval> {
    try {
      this.ensureInitialized();
      const startTime = Date.now();

      // Convert unified query to storage query
      const storageQuery: MemoryQuery = {
        type: query.type,
        userId: query.userId || this.config.userId,
        workspaceId: query.workspaceId || this.config.workspaceId,
        tags: query.tags,
        limit: query.limit,
        offset: query.offset,
        dateRange: query.dateRange
      };

      const result = await this.storageAdapter.queryMemories(storageQuery);

      if (!result.success) {
        throw new Error(result.error || 'Failed to query memories');
      }

      const memories = (result.data?.memories || []) as UnifiedMemoryData[];

      // Filter out expired memories unless explicitly requested
      const filteredMemories = query.includeExpired
        ? memories
        : memories.filter(memory => !memory.expires || new Date(memory.expires) > new Date());

      const processingTime = Date.now() - startTime;

      const retrieval: UnifiedMemoryRetrieval = {
        data: filteredMemories,
        scores: filteredMemories.map(() => 1.0), // Simple relevance scoring
        query,
        processingTime,
        totalFound: filteredMemories.length,
        platform: this.config.platform
      };

      this.emit('memory-query', {
        query,
        results: retrieval,
        platform: this.config.platform
      });

      return retrieval;
    } catch (error) {
      console.error('Failed to query memories:', error);
      this.emit('memory-query-error', { error, query, platform: this.config.platform });
      throw error;
    }
  }

  /**
   * Delete a memory by ID
   */
  async deleteMemory(memoryId: string): Promise<boolean> {
    try {
      this.ensureInitialized();

      const result = await this.storageAdapter.deleteMemory(memoryId);

      if (!result.success) {
        throw new Error(result.error || 'Failed to delete memory');
      }

      // Remove from cache
      this.memoryCache.delete(memoryId);

      console.log(`Memory deleted with ID: ${memoryId}`);
      this.emit('memory-deleted', {
        memoryId,
        platform: this.config.platform
      });

      return true;
    } catch (error) {
      console.error('Failed to delete memory:', error);
      this.emit('memory-delete-error', { error, memoryId, platform: this.config.platform });
      return false;
    }
  }

  /**
   * Get memory system statistics
   */
  async getMemoryStats(): Promise<UnifiedMemoryStats> {
    try {
      this.ensureInitialized();

      const storageStats = await this.storageAdapter.getMemoryStats();

      if (!storageStats.success) {
        throw new Error(storageStats.error || 'Failed to get memory stats');
      }

      // Calculate memory type distribution
      const memoryTypes: Record<string, number> = {};
      this.memoryCache.forEach(memory => {
        memoryTypes[memory.type] = (memoryTypes[memory.type] || 0) + 1;
      });

      const stats: UnifiedMemoryStats = {
        totalMemories: this.memoryCache.size,
        desktopMemories: this.config.platform === 'desktop' ? this.memoryCache.size : 0,
        webMemories: this.config.platform === 'web' ? this.memoryCache.size : 0,
        totalSize: storageStats.data?.totalSize || 0,
        desktopSize: this.config.platform === 'desktop' ? (storageStats.data?.totalSize || 0) : 0,
        webSize: this.config.platform === 'web' ? (storageStats.data?.totalSize || 0) : 0,
        storageUsage: {
          desktop: {
            usagePercentage: this.config.platform === 'desktop' ? (storageStats.data?.usagePercentage || 0) : 0,
            maxSize: this.config.platform === 'desktop' ? (storageStats.data?.maxSize || 0) : 0
          },
          web: {
            usagePercentage: this.config.platform === 'web' ? (storageStats.data?.usagePercentage || 0) : 0,
            bucketName: this.config.storage.s3Config?.bucketName
          }
        },
        memoryTypes,
        lastSync: new Date()
      };

      this.emit('memory-stats-retrieved', {
        stats,
        platform: this.config.platform
      });

      return stats;
    } catch (error) {
      console.error('Failed to get memory stats:', error);
      this.emit('memory-stats-error', { error, platform: this.config.platform });
      throw error;
    }
  }

  /**
   * Cleanup expired memories
   */
  async cleanupExpiredMemories(): Promise<number> {
    try {
      this.ensureInitialized();

      const result = await this.storageAdapter.cleanupExpiredMemories();

      if (!result.success) {
        throw new Error(result.error || 'Failed to cleanup expired memories');
      }

      const cleanedCount = result.data?.cleanedCount || 0;

      // Update cache by removing expired memories
      for (const [memoryId, memory] of this.memoryCache.entries()) {
        if (memory.expires && new Date(memory.expires) < new Date()) {
          this.memoryCache.delete(memoryId);
        }
      }

      console.log(`Cleaned up ${cleanedCount} expired memories`);
      this.emit('memory-cleanup-completed', {
        cleanedCount,
        platform: this.config.platform
      });

      return cleanedCount;
    } catch (error) {
      console.error('Failed to cleanup expired memories:', error);
      this.emit('memory-cleanup-error', { error, platform: this.config.platform });
      return 0;
    }
  }

  /**
   * Export memories for backup or transfer
   */
  async exportMemories(query?: UnifiedMemoryQuery): Promise<UnifiedMemoryData[]> {
    try {
      this.ensureInitialized();

      const retrieval = await this.queryMemories({
        ...query,
        includeExpired: false
      });

      this.emit('memory-export', {
        count: retrieval.data.length,
        platform: this.config.platform
      });

      return retrieval.data;
    } catch (error) {
      console.error('Failed to export memories:', error);
      this.emit('memory-export-error', { error, platform: this.config.platform });
      throw error;
    }
  }

  /**
   * Import memories from backup or transfer
   */
  async importMemories(memories: UnifiedMemoryData[]): Promise<number> {
    try {
      this.ensureInitialized();

      let importedCount = 0;

      for (const memory of memories) {
        try {
          // Convert imported memory to current platform format
          const importedMemory: Omit<UnifiedMemoryData, 'id' | 'timestamp' | 'platform' | 'storageLocation'> = {
            type: memory.type,
            content: memory.content,
            embedding: memory.embedding,
            metadata: {
              ...memory.metadata,
              // Reset access metadata for imported memories
              accessCount: 0,
              lastAccessed: new Date()
            },
            expires: memory.expires
          };

          await this.storeMemory(importedMemory);
          importedCount++;
        } catch (error) {
          console.warn(`Failed to import memory: ${memory.id}`, error);
        }
      }

      console.log(`Imported ${importedCount} memories`);
      this.emit('memory-import-completed', {
        importedCount,
        platform: this.config.platform
      });

      return importedCount;
    } catch (error) {
      console.error('Failed to import memories:', error);
      this.emit('memory-import-error', { error, platform: this.config.platform });
      throw error;
    }
  }

  /**
   * Shutdown the memory system
   */
  async shutdown(): Promise<void> {
    try {
      if (this.cleanupInterval) {
        clearInterval(this.cleanupInterval);
      }
      if (this.syncInterval) {
        clearInterval(this.syncInterval);
      }

      this.memoryCache.clear();
      this.isInitialized = false;

      console.log('UnifiedMemorySystem shutdown completed');
      this.emit('memory-system-shutdown', { platform: this.config.platform });
    } catch (error) {
      console.error('Failed to shutdown memory system:', error);
      this.emit('memory-system-shutdown-error', { error, platform: this.config.platform });
    }
  }

  // Private helper methods

  private ensureInitialized(): void {
    if (!this.isInitialized) {
      throw new Error('Memory system not initialized. Call initialize() first.');
    }
  }

  private getLogger(): any {
    return {
      info: (message: string, ...args: any[]) => console.log(`[UnifiedMemorySystem] ${message}`, ...args),
      error: (message: string, ...args: any[]) => console.error(`[UnifiedMemorySystem] ${message}`, ...args),
      debug: (message: string, ...args: any[]) => console.debug(`[UnifiedMemorySystem] ${message}`, ...args),
      warn: (message: string, ...args: any[]) => console.warn(`[UnifiedMemorySystem] ${message}`, ...args)
    };
  }

  private generateMemoryId(): string {
    return `memory_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private calculateMemorySize(memoryData: any): number {
    return JSON.stringify(memoryData).length;
  }

  private async loadMemoriesIntoCache(): Promise<void> {
    try {
      // Load recent memories into cache for faster access
      const recentQuery: UnifiedMemoryQuery = {
        limit: 1000, // Load up to 1000 recent memories
        dateRange: {
          start: new Date(Date.now() - 30 * 24 *
