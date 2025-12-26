import { useState, useCallback, useEffect } from 'react';

export interface ConversationMemory {
  id: string;
  userId: string;
  sessionId: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  metadata: {
    messageType: 'text' | 'voice' | 'command';
    workflowId?: string;
    intent?: string;
    entities?: string[];
    sentiment?: number;
    importance: number;
    accessCount: number;
    lastAccessed: Date;
  };
}

export interface MemoryContext {
  shortTermMemories: ConversationMemory[];
  longTermMemories: ConversationMemory[];
  userPatterns: any[];
  conversationSummary: string;
  relevanceScore: number;
}

export interface MemoryStats {
  shortTermMemoryCount: number;
  userPatternCount: number;
  activeSessions: number;
  totalMemoryAccesses: number;
  lancedbAvailable: boolean;
}

export interface UseChatMemoryReturn {
  // State
  memories: ConversationMemory[];
  memoryContext: MemoryContext | null;
  memoryStats: MemoryStats | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  storeMemory: (memory: Omit<ConversationMemory, 'id' | 'timestamp'>) => Promise<void>;
  getMemoryContext: (currentMessage: string) => Promise<MemoryContext>;
  clearSessionMemory: () => Promise<void>;
  refreshMemoryStats: () => Promise<void>;

  // Utilities
  hasRelevantContext: boolean;
  contextRelevanceScore: number;
}

export interface UseChatMemoryConfig {
  userId: string;
  sessionId: string;
  enableMemory?: boolean;
  autoStoreMessages?: boolean;
  contextWindow?: number;
}

/**
 * React hook for integrating chat interface with memory system
 * Provides short-term and long-term memory capabilities for conversations
 */
export function useChatMemory(config: UseChatMemoryConfig): UseChatMemoryReturn {
  const {
    userId,
    sessionId,
    enableMemory = true,
    autoStoreMessages = true,
    contextWindow = 10
  } = config;

  const [memories, setMemories] = useState<ConversationMemory[]>([]);
  const [memoryContext, setMemoryContext] = useState<MemoryContext | null>(null);
  const [memoryStats, setMemoryStats] = useState<MemoryStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load initial memory stats
  useEffect(() => {
    if (enableMemory) {
      refreshMemoryStats();
    }
  }, [enableMemory, userId]);

  /**
   * Store a conversation memory
   */
  const storeMemory = useCallback(async (
    memory: Omit<ConversationMemory, 'id' | 'timestamp'>
  ): Promise<void> => {
    if (!enableMemory) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/chat/memory/store', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...memory,
          userId,
          sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to store memory: ${response.statusText}`);
      }

      const result = await response.json();

      if (result.status === 'success') {
        // Update local state
        const newMemory: ConversationMemory = {
          ...memory,
          id: result.memory_id,
          timestamp: new Date(),
        };

        setMemories(prev => [newMemory, ...prev].slice(0, contextWindow));

        // Refresh stats
        await refreshMemoryStats();
      } else {
        throw new Error(result.message || 'Failed to store memory');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      console.error('Error storing memory:', err);
    } finally {
      setIsLoading(false);
    }
  }, [enableMemory, userId, sessionId, contextWindow]);

  /**
   * Get memory context for current conversation
   */
  const getMemoryContext = useCallback(async (
    currentMessage: string
  ): Promise<MemoryContext> => {
    if (!enableMemory) {
      return {
        shortTermMemories: [],
        longTermMemories: [],
        userPatterns: [],
        conversationSummary: 'Memory system disabled',
        relevanceScore: 0
      };
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/chat/memory/context', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userId,
          sessionId,
          currentMessage,
          contextWindow,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to get memory context: ${response.statusText}`);
      }

      const result = await response.json();

      if (result.status === 'success') {
        const context = result.context;
        setMemoryContext(context);
        return context;
      } else {
        throw new Error(result.message || 'Failed to get memory context');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      console.error('Error getting memory context:', err);

      // Return empty context on error
      return {
        shortTermMemories: [],
        longTermMemories: [],
        userPatterns: [],
        conversationSummary: 'Memory context unavailable',
        relevanceScore: 0
      };
    } finally {
      setIsLoading(false);
    }
  }, [enableMemory, userId, sessionId, contextWindow]);

  /**
   * Clear session memory
   */
  const clearSessionMemory = useCallback(async (): Promise<void> => {
    if (!enableMemory) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/chat/memory/session/${sessionId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`Failed to clear session memory: ${response.statusText}`);
      }

      const result = await response.json();

      if (result.status === 'success') {
        // Clear local state
        setMemories([]);
        setMemoryContext(null);

        // Refresh stats
        await refreshMemoryStats();
      } else {
        throw new Error(result.message || 'Failed to clear session memory');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      console.error('Error clearing session memory:', err);
    } finally {
      setIsLoading(false);
    }
  }, [enableMemory, sessionId]);

  /**
   * Refresh memory statistics
   */
  const refreshMemoryStats = useCallback(async (): Promise<void> => {
    if (!enableMemory) return;

    try {
      const response = await fetch(`/api/chat/memory/stats?user_id=${userId}`);

      if (!response.ok) {
        throw new Error(`Failed to get memory stats: ${response.statusText}`);
      }

      const result = await response.json();

      if (result.status === 'success') {
        setMemoryStats(result);
      } else {
        throw new Error(result.message || 'Failed to get memory stats');
      }
    } catch (err) {
      console.error('Error refreshing memory stats:', err);
      // Don't set error state for stats refresh to avoid disrupting UX
    }
  }, [enableMemory, userId]);

  /**
   * Auto-store messages when autoStoreMessages is enabled
   */
  const autoStoreMessage = useCallback(async (
    role: 'user' | 'assistant',
    content: string,
    metadata?: Partial<ConversationMemory['metadata']>
  ): Promise<void> => {
    if (!autoStoreMessages || !enableMemory) return;

    await storeMemory({
      userId,
      sessionId,
      role,
      content,
      metadata: {
        messageType: 'text',
        importance: 0.5,
        accessCount: 0,
        lastAccessed: new Date(),
        ...metadata,
      },
    });
  }, [autoStoreMessages, enableMemory, storeMemory, userId, sessionId]);

  // Derived state
  const hasRelevantContext = Boolean(
    memoryContext &&
    memoryContext.relevanceScore > 0.3 &&
    (memoryContext.shortTermMemories.length > 0 || memoryContext.longTermMemories.length > 0)
  );

  const contextRelevanceScore = memoryContext?.relevanceScore || 0;

  return {
    // State
    memories,
    memoryContext,
    memoryStats,
    isLoading,
    error,

    // Actions
    storeMemory,
    getMemoryContext,
    clearSessionMemory,
    refreshMemoryStats,

    // Utilities
    hasRelevantContext,
    contextRelevanceScore,

    // Expose auto-store for external use
    // Note: This is not in the public interface but available internally
  } as UseChatMemoryReturn & { autoStoreMessage: typeof autoStoreMessage };
}

// Default export for convenience
export default useChatMemory;
