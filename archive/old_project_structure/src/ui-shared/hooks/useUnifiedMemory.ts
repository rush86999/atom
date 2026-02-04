/**
 * React Hook for Unified Memory System
 *
 * Provides consistent memory management across desktop and web platforms:
 * - Desktop: Uses localStorage for offline capability
 * - Web: Uses AWS S3 for cloud storage
 * - Maintains full UI and feature parity between platforms
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  UnifiedMemorySystem,
  UnifiedMemoryData,
  UnifiedMemoryQuery,
  UnifiedMemoryRetrieval,
  UnifiedMemoryStats,
  UnifiedMemorySystemConfig,
} from "../../memory/UnifiedMemorySystem";

export interface UseUnifiedMemoryConfig {
  platform: "desktop" | "web";
  userId: string;
  workspaceId?: string;
  enableMemory?: boolean;
  autoInitialize?: boolean;
  storage?: {
    useLocalStorage?: boolean;
    offlineCapable?: boolean;
    encryptionEnabled?: boolean;
    localDataPath?: string;
    s3Config?: {
      bucketName: string;
      region: string;
      accessKeyId?: string;
      secretAccessKey?: string;
    };
  };
  memory?: {
    maxAge?: number;
    maxSize?: number;
    cleanupInterval?: number;
    syncInterval?: number;
  };
}

export interface UseUnifiedMemoryReturn {
  // State
  memories: UnifiedMemoryData[];
  memoryStats: UnifiedMemoryStats | null;
  isLoading: boolean;
  isInitializing: boolean;
  error: string | null;
  isOnline: boolean;

  // Core memory operations
  storeMemory: (
    data: Omit<
      UnifiedMemoryData,
      "id" | "timestamp" | "platform" | "storageLocation"
    >,
  ) => Promise<string>;
  retrieveMemory: (memoryId: string) => Promise<UnifiedMemoryData | null>;
  queryMemories: (query: UnifiedMemoryQuery) => Promise<UnifiedMemoryRetrieval>;
  deleteMemory: (memoryId: string) => Promise<boolean>;

  // Memory management
  getMemoryStats: () => Promise<UnifiedMemoryStats>;
  cleanupExpiredMemories: () => Promise<number>;
  exportMemories: (query?: UnifiedMemoryQuery) => Promise<UnifiedMemoryData[]>;
  importMemories: (memories: UnifiedMemoryData[]) => Promise<number>;

  // System operations
  initialize: () => Promise<boolean>;
  shutdown: () => Promise<void>;
  refresh: () => Promise<void>;

  // Platform information
  platform: "desktop" | "web";
  storageLocation: "localStorage" | "s3";
  isOfflineCapable: boolean;
}

/**
 * React hook for unified memory system
 * Provides consistent memory management across desktop and web platforms
 */
export function useUnifiedMemory(
  config: UseUnifiedMemoryConfig,
): UseUnifiedMemoryReturn {
  const {
    platform,
    userId,
    workspaceId,
    enableMemory = true,
    autoInitialize = true,
    storage = {},
    memory = {},
  } = config;

  // State
  const [memories, setMemories] = useState<UnifiedMemoryData[]>([]);
  const [memoryStats, setMemoryStats] = useState<UnifiedMemoryStats | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState(true);

  // Refs
  const memorySystemRef = useRef<UnifiedMemorySystem | null>(null);
  const isMountedRef = useRef(true);

  // Platform-specific configuration
  const storageLocation = storage.useLocalStorage ? "localStorage" : "s3";
  const isOfflineCapable =
    platform === "desktop" || storage.offlineCapable === true;

  // Initialize memory system
  const initialize = useCallback(async (): Promise<boolean> => {
    if (!enableMemory) {
      return false;
    }

    try {
      setIsInitializing(true);
      setError(null);

      // Create memory system configuration
      const systemConfig: UnifiedMemorySystemConfig = {
        platform,
        userId,
        workspaceId,
        storage: {
          useLocalStorage:
            platform === "desktop" || storage.useLocalStorage === true,
          offlineCapable:
            platform === "desktop" || storage.offlineCapable === true,
          encryptionEnabled: storage.encryptionEnabled !== false,
          localDataPath: storage.localDataPath,
          s3Config: storage.s3Config,
        },
        memory: {
          maxAge: memory.maxAge,
          maxSize: memory.maxSize,
          cleanupInterval: memory.cleanupInterval,
          syncInterval: memory.syncInterval,
        },
      };

      // Create memory system instance
      const memorySystem = new UnifiedMemorySystem(systemConfig);
      memorySystemRef.current = memorySystem;

      // Set up event listeners
      memorySystem.on("memory-stored", handleMemoryStored);
      memorySystem.on("memory-deleted", handleMemoryDeleted);
      memorySystem.on("memory-query", handleMemoryQuery);
      memorySystem.on("memory-stats-retrieved", handleMemoryStatsRetrieved);
      memorySystem.on("memory-system-error", handleSystemError);

      // Initialize the system
      const initialized = await memorySystem.initialize();

      if (initialized && isMountedRef.current) {
        // Load initial memory stats
        await memorySystem.getMemoryStats();

        // Load recent memories
        const recentMemories = await memorySystem.queryMemories({
          limit: 50,
          platform: "all",
        });

        setMemories(recentMemories.data);
      }

      return initialized;
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to initialize memory system";
      setError(errorMessage);
      console.error("Failed to initialize unified memory system:", err);
      return false;
    } finally {
      if (isMountedRef.current) {
        setIsInitializing(false);
      }
    }
  }, [platform, userId, workspaceId, enableMemory, storage, memory]);

  // Auto-initialize on mount if enabled
  useEffect(() => {
    isMountedRef.current = true;

    if (autoInitialize && enableMemory) {
      initialize();
    }

    // Set up online/offline detection
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      isMountedRef.current = false;
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);

      // Cleanup memory system
      if (memorySystemRef.current) {
        memorySystemRef.current.shutdown().catch(console.error);
        memorySystemRef.current = null;
      }
    };
  }, [autoInitialize, enableMemory, initialize]);

  // Event handlers
  const handleMemoryStored = useCallback(
    ({ memory }: { memory: UnifiedMemoryData }) => {
      if (isMountedRef.current) {
        setMemories((prev: UnifiedMemoryData[]) => {
          const existingIndex = prev.findIndex(
            (m: UnifiedMemoryData) => m.id === memory.id,
          );
          if (existingIndex >= 0) {
            // Update existing memory
            const updated = [...prev];
            updated[existingIndex] = memory;
            return updated;
          } else {
            // Add new memory (limit to 100 most recent)
            return [memory, ...prev.slice(0, 99)];
          }
        });
      }
    },
    [],
  );

  const handleMemoryDeleted = useCallback(
    ({ memoryId }: { memoryId: string }) => {
      if (isMountedRef.current) {
        setMemories((prev: UnifiedMemoryData[]) =>
          prev.filter((m: UnifiedMemoryData) => m.id !== memoryId),
        );
      }
    },
    [],
  );

  const handleMemoryQuery = useCallback(
    ({ results }: { results: UnifiedMemoryRetrieval }) => {
      if (isMountedRef.current) {
        setMemories(results.data);
      }
    },
    [],
  );

  const handleMemoryStatsRetrieved = useCallback(
    ({ stats }: { stats: UnifiedMemoryStats }) => {
      if (isMountedRef.current) {
        setMemoryStats(stats);
      }
    },
    [],
  );

  const handleSystemError = useCallback(
    ({ error: systemError }: { error: Error }) => {
      if (isMountedRef.current) {
        setError(systemError.message);
      }
    },
    [],
  );

  // Core memory operations
  const storeMemory = useCallback(
    async (
      data: Omit<
        UnifiedMemoryData,
        "id" | "timestamp" | "platform" | "storageLocation"
      >,
    ): Promise<string> => {
      if (!memorySystemRef.current) {
        throw new Error("Memory system not initialized");
      }

      try {
        setIsLoading(true);
        setError(null);
        const memoryId = await memorySystemRef.current.storeMemory(data);
        return memoryId;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to store memory";
        setError(errorMessage);
        throw err;
      } finally {
        if (isMountedRef.current) {
          setIsLoading(false);
        }
      }
    },
    [],
  );

  const retrieveMemory = useCallback(
    async (memoryId: string): Promise<UnifiedMemoryData | null> => {
      if (!memorySystemRef.current) {
        throw new Error("Memory system not initialized");
      }

      try {
        setIsLoading(true);
        setError(null);
        const memory = await memorySystemRef.current.retrieveMemory(memoryId);
        return memory;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to retrieve memory";
        setError(errorMessage);
        throw err;
      } finally {
        if (isMountedRef.current) {
          setIsLoading(false);
        }
      }
    },
    [],
  );

  const queryMemories = useCallback(
    async (query: UnifiedMemoryQuery): Promise<UnifiedMemoryRetrieval> => {
      if (!memorySystemRef.current) {
        throw new Error("Memory system not initialized");
      }

      try {
        setIsLoading(true);
        setError(null);
        const results = await memorySystemRef.current.queryMemories(query);
        return results;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to query memories";
        setError(errorMessage);
        throw err;
      } finally {
        if (isMountedRef.current) {
          setIsLoading(false);
        }
      }
    },
    [],
  );

  const deleteMemory = useCallback(
    async (memoryId: string): Promise<boolean> => {
      if (!memorySystemRef.current) {
        throw new Error("Memory system not initialized");
      }

      try {
        setIsLoading(true);
        setError(null);
        const success = await memorySystemRef.current.deleteMemory(memoryId);
        return success;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to delete memory";
        setError(errorMessage);
        throw err;
      } finally {
        if (isMountedRef.current) {
          setIsLoading(false);
        }
      }
    },
    [],
  );

  // Memory management operations
  const getMemoryStats = useCallback(async (): Promise<UnifiedMemoryStats> => {
    if (!memorySystemRef.current) {
      throw new Error("Memory system not initialized");
    }

    try {
      setIsLoading(true);
      setError(null);
      const stats = await memorySystemRef.current.getMemoryStats();
      return stats;
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to get memory stats";
      setError(errorMessage);
      throw err;
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  const cleanupExpiredMemories = useCallback(async (): Promise<number> => {
    if (!memorySystemRef.current) {
      throw new Error("Memory system not initialized");
    }

    try {
      setIsLoading(true);
      setError(null);
      const cleanedCount =
        await memorySystemRef.current.cleanupExpiredMemories();
      return cleanedCount;
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to cleanup expired memories";
      setError(errorMessage);
      throw err;
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  const exportMemories = useCallback(
    async (query?: UnifiedMemoryQuery): Promise<UnifiedMemoryData[]> => {
      if (!memorySystemRef.current) {
        throw new Error("Memory system not initialized");
      }

      try {
        setIsLoading(true);
        setError(null);
        const exportedMemories =
          await memorySystemRef.current.exportMemories(query);
        return exportedMemories;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to export memories";
        setError(errorMessage);
        throw err;
      } finally {
        if (isMountedRef.current) {
          setIsLoading(false);
        }
      }
    },
    [],
  );

  const importMemories = useCallback(
    async (memories: UnifiedMemoryData[]): Promise<number> => {
      if (!memorySystemRef.current) {
        throw new Error("Memory system not initialized");
      }

      try {
        setIsLoading(true);
        setError(null);
        const importedCount =
          await memorySystemRef.current.importMemories(memories);
        return importedCount;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to import memories";
        setError(errorMessage);
        throw err;
      } finally {
        if (isMountedRef.current) {
          setIsLoading(false);
        }
      }
    },
    [],
  );

  // System operations
  const shutdown = useCallback(async (): Promise<void> => {
    if (memorySystemRef.current) {
      await memorySystemRef.current.shutdown();
      memorySystemRef.current = null;
    }
  }, []);

  const refresh = useCallback(async (): Promise<void> => {
    if (!memorySystemRef.current) {
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      // Refresh memory stats
      await getMemoryStats();

      // Refresh recent memories
      const recentMemories = await queryMemories({
        limit: 50,
        platform: "all",
      });

      setMemories(recentMemories.data);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to refresh memories";
      setError(errorMessage);
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [getMemoryStats, queryMemories]);

  return {
    // State
    memories,
    memoryStats,
    isLoading,
    isInitializing,
    error,
    isOnline,

    // Core memory operations
    storeMemory,
    retrieveMemory,
    queryMemories,
    deleteMemory,

    // Memory management
    getMemoryStats,
    cleanupExpiredMemories,
    exportMemories,
    importMemories,

    // System operations
    initialize,
    shutdown,
    refresh,

    // Platform information
    platform,
    storageLocation,
    isOfflineCapable,
  };
}

// Export default configuration helpers
export const createDesktopMemoryConfig = (
  userId: string,
  workspaceId?: string,
): UseUnifiedMemoryConfig => ({
  platform: "desktop",
  userId,
  workspaceId,
  enableMemory: true,
  autoInitialize: true,
  storage: {
    useLocalStorage: true,
    offlineCapable: true,
    encryptionEnabled: true,
  },
  memory: {
    maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
    maxSize: 50 * 1024 * 1024, // 50MB
    cleanupInterval: 24 * 60 * 60 * 1000, // 24 hours
  },
});

export const createWebMemoryConfig = (
  userId: string,
  s3Config: {
    bucketName: string;
    region: string;
    accessKeyId?: string;
    secretAccessKey?: string;
  },
  workspaceId?: string,
): UseUnifiedMemoryConfig => ({
  platform: "web",
  userId,
  workspaceId,
  enableMemory: true,
  autoInitialize: true,
  storage: {
    useLocalStorage: false,
    offlineCapable: false,
    encryptionEnabled: true,
    s3Config,
  },
  memory: {
    maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
    cleanupInterval: 24 * 60 * 60 * 1000, // 24 hours
  },
});
