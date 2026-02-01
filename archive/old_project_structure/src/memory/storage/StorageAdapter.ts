/**
 * Unified Storage Adapter for ATOM Memory System
 *
 * Provides a consistent interface for memory storage across different platforms:
 * - Desktop app: Uses localStorage for offline capability
 * - Web app: Uses AWS S3 for cloud storage
 */

export interface StorageConfig {
  platform: "desktop" | "web";
  useLocalStorage: boolean;
  offlineCapable: boolean;
  encryptionEnabled: boolean;
  localDataPath?: string;
  s3Config?: S3StorageConfig;
}

export interface S3StorageConfig {
  bucketName: string;
  region: string;
  accessKeyId?: string;
  secretAccessKey?: string;
  endpoint?: string;
}

export interface MemoryStorageResult {
  success: boolean;
  data?: any;
  error?: string;
  metadata?: {
    size?: number;
    timestamp?: Date;
    location?: string;
  };
}

export interface MemoryQuery {
  type?: string;
  userId?: string;
  workspaceId?: string;
  tags?: string[];
  limit?: number;
  offset?: number;
  dateRange?: {
    start: Date;
    end: Date;
  };
}

/**
 * Abstract base class for memory storage adapters
 */
export abstract class MemoryStorageAdapter {
  protected config: StorageConfig;
  protected logger: any;

  constructor(config: StorageConfig, logger?: any) {
    this.config = config;
    this.logger = logger || console;
  }

  abstract initialize(): Promise<boolean>;
  abstract storeMemory(memoryData: any): Promise<MemoryStorageResult>;
  abstract retrieveMemory(memoryId: string): Promise<MemoryStorageResult>;
  abstract queryMemories(query: MemoryQuery): Promise<MemoryStorageResult>;
  abstract deleteMemory(memoryId: string): Promise<MemoryStorageResult>;
  abstract getMemoryStats(): Promise<MemoryStorageResult>;
  abstract cleanupExpiredMemories(): Promise<MemoryStorageResult>;
}

/**
 * Local Storage Adapter for Desktop App
 * Uses localStorage for persistent offline storage
 */
export class LocalStorageAdapter extends MemoryStorageAdapter {
  private storageKey = "atom_memory_system";
  private maxStorageSize = 50 * 1024 * 1024; // 50MB limit for localStorage

  async initialize(): Promise<boolean> {
    try {
      if (typeof window === "undefined" || !window.localStorage) {
        throw new Error("localStorage is not available in this environment");
      }

      // Initialize memory storage structure
      const existingData = localStorage.getItem(this.storageKey);
      if (!existingData) {
        const initialStructure = {
          memories: {},
          metadata: {
            totalMemories: 0,
            totalSize: 0,
            lastCleanup: new Date().toISOString(),
            storageVersion: "1.0.0",
          },
          indexes: {
            byType: {},
            byUserId: {},
            byTimestamp: {},
            byTags: {},
          },
        };
        localStorage.setItem(this.storageKey, JSON.stringify(initialStructure));
      }

      this.logger.info("LocalStorageAdapter initialized successfully");
      return true;
    } catch (error) {
      this.logger.error("Failed to initialize LocalStorageAdapter:", error);
      return false;
    }
  }

  async storeMemory(memoryData: any): Promise<MemoryStorageResult> {
    try {
      const storageData = this.getStorageData();
      const memoryId = memoryData.id || this.generateMemoryId();

      // Check storage limits
      const memorySize = this.calculateMemorySize(memoryData);
      if (storageData.metadata.totalSize + memorySize > this.maxStorageSize) {
        await this.cleanupOldMemories();
      }

      // Store memory
      storageData.memories[memoryId] = {
        ...memoryData,
        id: memoryId,
        timestamp: new Date().toISOString(),
        size: memorySize,
      };

      // Update indexes
      this.updateIndexes(storageData, memoryId, memoryData);

      // Update metadata
      storageData.metadata.totalMemories++;
      storageData.metadata.totalSize += memorySize;

      // Save back to localStorage
      localStorage.setItem(this.storageKey, JSON.stringify(storageData));

      this.logger.debug(`Memory stored with ID: ${memoryId}`);

      return {
        success: true,
        data: { id: memoryId },
        metadata: {
          size: memorySize,
          timestamp: new Date(),
          location: "localStorage",
        },
      };
    } catch (error) {
      this.logger.error("Failed to store memory:", error);
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  async retrieveMemory(memoryId: string): Promise<MemoryStorageResult> {
    try {
      const storageData = this.getStorageData();
      const memory = storageData.memories[memoryId];

      if (!memory) {
        return {
          success: false,
          error: `Memory not found: ${memoryId}`,
        };
      }

      // Update access metadata
      memory.lastAccessed = new Date().toISOString();
      memory.accessCount = (memory.accessCount || 0) + 1;
      localStorage.setItem(this.storageKey, JSON.stringify(storageData));

      return {
        success: true,
        data: memory,
        metadata: {
          size: memory.size,
          timestamp: new Date(memory.timestamp),
          location: "localStorage",
        },
      };
    } catch (error) {
      this.logger.error("Failed to retrieve memory:", error);
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  async queryMemories(query: MemoryQuery): Promise<MemoryStorageResult> {
    try {
      const storageData = this.getStorageData();
      let memories = Object.values(storageData.memories);

      // Apply filters
      if (query.type) {
        memories = memories.filter((m: any) => m.type === query.type);
      }
      if (query.userId) {
        memories = memories.filter(
          (m: any) => m.metadata?.userId === query.userId,
        );
      }
      if (query.tags && query.tags.length > 0) {
        memories = memories.filter((m: any) =>
          query.tags!.some((tag) => m.metadata?.tags?.includes(tag)),
        );
      }
      if (query.dateRange) {
        memories = memories.filter((m: any) => {
          const memoryDate = new Date(m.timestamp);
          return (
            memoryDate >= query.dateRange!.start &&
            memoryDate <= query.dateRange!.end
          );
        });
      }

      // Apply pagination
      const offset = query.offset || 0;
      const limit = query.limit || 50;
      const paginatedMemories = memories.slice(offset, offset + limit);

      return {
        success: true,
        data: {
          memories: paginatedMemories,
          total: memories.length,
          offset,
          limit,
        },
        metadata: {
          timestamp: new Date(),
          location: "localStorage",
        },
      };
    } catch (error) {
      this.logger.error("Failed to query memories:", error);
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  async deleteMemory(memoryId: string): Promise<MemoryStorageResult> {
    try {
      const storageData = this.getStorageData();

      if (!storageData.memories[memoryId]) {
        return {
          success: false,
          error: `Memory not found: ${memoryId}`,
        };
      }

      const memorySize = storageData.memories[memoryId].size || 0;

      // Remove from memory store
      delete storageData.memories[memoryId];

      // Remove from indexes
      this.removeFromIndexes(storageData, memoryId);

      // Update metadata
      storageData.metadata.totalMemories--;
      storageData.metadata.totalSize -= memorySize;

      // Save back to localStorage
      localStorage.setItem(this.storageKey, JSON.stringify(storageData));

      this.logger.debug(`Memory deleted with ID: ${memoryId}`);

      return {
        success: true,
        metadata: {
          timestamp: new Date(),
          location: "localStorage",
        },
      };
    } catch (error) {
      this.logger.error("Failed to delete memory:", error);
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  async getMemoryStats(): Promise<MemoryStorageResult> {
    try {
      const storageData = this.getStorageData();

      return {
        success: true,
        data: {
          totalMemories: storageData.metadata.totalMemories,
          totalSize: storageData.metadata.totalSize,
          maxSize: this.maxStorageSize,
          usagePercentage:
            (storageData.metadata.totalSize / this.maxStorageSize) * 100,
          lastCleanup: storageData.metadata.lastCleanup,
          storageVersion: storageData.metadata.storageVersion,
        },
        metadata: {
          timestamp: new Date(),
          location: "localStorage",
        },
      };
    } catch (error) {
      this.logger.error("Failed to get memory stats:", error);
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  async cleanupExpiredMemories(): Promise<MemoryStorageResult> {
    try {
      const storageData = this.getStorageData();
      const now = new Date();
      let cleanedCount = 0;
      let freedSize = 0;

      for (const [memoryId, memory] of Object.entries(storageData.memories)) {
        const memoryData = memory as any;
        if (memoryData.expires && new Date(memoryData.expires) < now) {
          // Memory has expired
          freedSize += memoryData.size || 0;
          delete storageData.memories[memoryId];
          this.removeFromIndexes(storageData, memoryId);
          cleanedCount++;
        }
      }

      // Update metadata
      storageData.metadata.totalMemories -= cleanedCount;
      storageData.metadata.totalSize -= freedSize;
      storageData.metadata.lastCleanup = now.toISOString();

      localStorage.setItem(this.storageKey, JSON.stringify(storageData));

      this.logger.info(
        `Cleaned up ${cleanedCount} expired memories, freed ${freedSize} bytes`,
      );

      return {
        success: true,
        data: {
          cleanedCount,
          freedSize,
        },
        metadata: {
          timestamp: now,
          location: "localStorage",
        },
      };
    } catch (error) {
      this.logger.error("Failed to cleanup expired memories:", error);
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  private getStorageData(): any {
    const data = localStorage.getItem(this.storageKey);
    if (!data) {
      throw new Error("Storage data not initialized");
    }
    return JSON.parse(data);
  }

  private generateMemoryId(): string {
    return `memory_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private calculateMemorySize(memoryData: any): number {
    return JSON.stringify(memoryData).length;
  }

  private updateIndexes(
    storageData: any,
    memoryId: string,
    memoryData: any,
  ): void {
    // Index by type
    if (!storageData.indexes.byType[memoryData.type]) {
      storageData.indexes.byType[memoryData.type] = [];
    }
    storageData.indexes.byType[memoryData.type].push(memoryId);

    // Index by user ID
    if (memoryData.metadata?.userId) {
      const userId = memoryData.metadata.userId;
      if (!storageData.indexes.byUserId[userId]) {
        storageData.indexes.byUserId[userId] = [];
      }
      storageData.indexes.byUserId[userId].push(memoryId);
    }

    // Index by timestamp
    const timestampKey = new Date(memoryData.timestamp)
      .toISOString()
      .split("T")[0];
    if (!storageData.indexes.byTimestamp[timestampKey]) {
      storageData.indexes.byTimestamp[timestampKey] = [];
    }
    storageData.indexes.byTimestamp[timestampKey].push(memoryId);

    // Index by tags
    if (memoryData.metadata?.tags) {
      for (const tag of memoryData.metadata.tags) {
        if (!storageData.indexes.byTags[tag]) {
          storageData.indexes.byTags[tag] = [];
        }
        storageData.indexes.byTags[tag].push(memoryId);
      }
    }
  }

  private removeFromIndexes(storageData: any, memoryId: string): void {
    // Remove from all indexes
    Object.keys(storageData.indexes.byType).forEach((type) => {
      storageData.indexes.byType[type] = storageData.indexes.byType[
        type
      ].filter((id: string) => id !== memoryId);
    });

    Object.keys(storageData.indexes.byUserId).forEach((userId) => {
      storageData.indexes.byUserId[userId] = storageData.indexes.byUserId[
        userId
      ].filter((id: string) => id !== memoryId);
    });

    Object.keys(storageData.indexes.byTimestamp).forEach((timestamp) => {
      storageData.indexes.byTimestamp[timestamp] =
        storageData.indexes.byTimestamp[timestamp].filter(
          (id: string) => id !== memoryId,
        );
    });

    Object.keys(storageData.indexes.byTags).forEach((tag) => {
      storageData.indexes.byTags[tag] = storageData.indexes.byTags[tag].filter(
        (id: string) => id !== memoryId,
      );
    });
  }

  private async cleanupOldMemories(): Promise<void> {
    const storageData = this.getStorageData();
    const memories = Object.entries(storageData.memories)
      .map(([id, memory]: [string, any]) => ({ id, ...memory }))
      .sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
      );

    let freedSize = 0;
    const targetFreeSpace = this.maxStorageSize * 0.2; // Free up 20% of space

    for (const memory of memories) {
      if (freedSize >= targetFreeSpace) break;

      freedSize += memory.size || 0;
      delete storageData.memories[memory.id];
      this.removeFromIndexes(storageData, memory.id);
    }

    storageData.metadata.totalMemories = Object.keys(
      storageData.memories,
    ).length;
    storageData.metadata.totalSize -= freedSize;

    localStorage.setItem(this.storageKey, JSON.stringify(storageData));
    this.logger.info(`Cleaned up old memories, freed ${freedSize} bytes`);
  }
}

/**
 * S3 Storage Adapter for Web App
 * Uses AWS S3 for cloud-based storage
 */
export class S3StorageAdapter extends MemoryStorageAdapter {
  private s3Client: any = null;

  async initialize(): Promise<boolean> {
    try {
      // In a real implementation, this would initialize the AWS S3 client
      // For now, we'll simulate the initialization
      this.logger.info("S3StorageAdapter initialized (simulated)");
      return true;
    } catch (error) {
      this.logger.error("Failed to initialize S3StorageAdapter:", error);
      return false;
    }
  }

  async storeMemory(memoryData: any): Promise<MemoryStorageResult> {
    // Simulated S3 storage implementation
    this.logger.info(`Simulating S3 storage for memory: ${memoryData.id}`);

    return {
      success: true,
      data: { id: memoryData.id },
      metadata: {
        size: JSON.stringify(memoryData).length,
        timestamp: new Date(),
        location: "s3",
      },
    };
  }

  async retrieveMemory(memoryId: string): Promise<MemoryStorageResult> {
    // Simulated S3 retrieval implementation
    this.logger.info(`Simulating S3 retrieval for memory: ${memoryId}`);

    return {
      success: true,
      data: { id: memoryId, type: "simulated", content: "Simulated S3 data" },
      metadata: {
        timestamp: new Date(),
        location: "s3",
      },
    };
  }

  async queryMemories(query: MemoryQuery): Promise<MemoryStorageResult> {
    // Simulated S3 query implementation
    this.logger.info("Simulating S3 query");

    return {
      success: true,
      data: {
        memories: [],
        total: 0,
        offset: query.offset || 0,
        limit: query.limit || 50,
      },
      metadata: {
        timestamp: new Date(),
        location: "s3",
      },
    };
  }

  async deleteMemory(memoryId: string): Promise<MemoryStorageResult> {
    // Simulated S3 deletion implementation
    this.logger.info(`Simulating S3 deletion for memory: ${memoryId}`);

    return {
      success: true,
      metadata: {
        timestamp: new Date(),
        location: "s3",
      },
    };
  }

  async getMemoryStats(): Promise<MemoryStorageResult> {
    // Simulated S3 stats implementation
    this.logger.info("Simulating S3 stats retrieval");

    return {
      success: true,
      data: {
        totalMemories: 0,
        totalSize: 0,
        bucketName: this.config.s3Config?.bucketName || "unknown",
        region: this.config.s3Config?.region || "unknown",
      },
      metadata: {
        timestamp: new Date(),
        location: "s3",
      },
    };
  }

  async cleanupExpiredMemories(): Promise<MemoryStorageResult> {
    // Simulated S3 cleanup implementation
    this.logger.info("Simulating S3 cleanup");

    return {
      success: true,
      data: {
        cleanedCount: 0,
        freedSize: 0,
      },
      metadata: {
        timestamp: new Date(),
        location: "s3",
      },
    };
  }
}

/**
 * Storage Factory for creating appropriate storage adapters
 */
export class StorageFactory {
  static createStorageAdapter(
    config: StorageConfig,
    logger?: any,
  ): MemoryStorageAdapter {
    if (config.useLocalStorage && config.platform === "desktop") {
      return new LocalStorageAdapter(config, logger);
    } else {
      return new S3StorageAdapter(config, logger);
    }
  }

  static createDesktopStorage(logger?: any): MemoryStorageAdapter {
    const config: StorageConfig = {
      platform: "desktop",
      useLocalStorage: true,
      offlineCapable: true,
      encryptionEnabled: true,
    };
    return new LocalStorageAdapter(config, logger);
  }
}
