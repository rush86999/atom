/**
 * useChatMemory Hook Comprehensive Tests
 *
 * The real useChatMemory hook (hooks/useChatMemory.ts) takes a config object
 * ({ userId, sessionId, enableMemory, autoStoreMessages, contextWindow }) and
 * returns { memories, memoryContext, memoryStats, isLoading, error,
 * storeMemory, getMemoryContext, clearSessionMemory, refreshMemoryStats,
 * hasRelevantContext, contextRelevanceScore }.
 *
 * Important: when enableMemory is true the hook fetches /api/chat/memory/stats
 * on mount (a useEffect). That mount call consumes the first queued fetch mock,
 * so every test that queues a mockResolvedValueOnce for a later call must also
 * queue a leading mount-stats mock.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatMemory } from '../useChatMemory';

const statsOk = (overrides: Record<string, unknown> = {}) => ({
  ok: true,
  json: async () => ({
    status: 'success',
    shortTermMemoryCount: 0,
    userPatternCount: 0,
    activeSessions: 0,
    totalMemoryAccesses: 0,
    lancedbAvailable: true,
    ...overrides,
  }),
});

const storeOk = (memoryId = 'mem-1') => ({
  ok: true,
  json: async () => ({
    status: 'success',
    memory_id: memoryId,
  }),
});

const baseMemory = {
  userId: 'user-1',
  sessionId: 'session-1',
  role: 'user' as const,
  content: 'Test message',
  metadata: {
    messageType: 'text' as const,
    importance: 0.5,
    accessCount: 0,
    lastAccessed: new Date(),
  },
};

describe('useChatMemory Hook (comprehensive)', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
    global.mockFetch = global.fetch;
    jest.clearAllMocks();
  });

  describe('Memory Initialization', () => {
    it('initializes with empty memories array', () => {
      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      expect(result.current.memories).toEqual([]);
    });

    it('initializes with null memoryContext', () => {
      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      expect(result.current.memoryContext).toBeNull();
    });

    it('initializes with null memoryStats', () => {
      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      expect(result.current.memoryStats).toBeNull();
    });

    it('initializes with isLoading false', () => {
      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      expect(result.current.isLoading).toBe(false);
    });

    it('initializes with error null', () => {
      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      expect(result.current.error).toBeNull();
    });

    it('fetches memory stats on mount when enableMemory is true', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce(statsOk());

      renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/chat/memory/stats?user_id=user-1'
        );
      });
    });

    it('does not fetch stats on mount when enableMemory is false', () => {
      renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: false })
      );

      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('handles different chat sessions independently', () => {
      const { result: result1 } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: false })
      );
      const { result: result2 } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-2', enableMemory: false })
      );

      expect(result1.current.memories).not.toBe(result2.current.memories);
    });
  });

  describe('Memory Storage', () => {
    it('stores a memory via the backend API', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockResolvedValueOnce(storeOk());

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.storeMemory(baseMemory);
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/chat/memory/store',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('Test message'),
        })
      );
    });

    it('adds the stored memory to the local memories array', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockResolvedValueOnce(storeOk('mem-1'))
        .mockResolvedValueOnce(statsOk({ shortTermMemoryCount: 1 }));

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true, contextWindow: 10 })
      );

      await act(async () => {
        await result.current.storeMemory(baseMemory);
      });

      expect(result.current.memories.length).toBe(1);
      expect(result.current.memories[0].content).toBe('Test message');
      expect(result.current.memories[0].id).toBe('mem-1');
    });

    it('limits memories to contextWindow size', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValue(storeOk(`mem-${Math.random()}`))
        .mockResolvedValueOnce(statsOk());

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true, contextWindow: 3 })
      );

      for (let i = 0; i < 5; i++) {
        await act(async () => {
          await result.current.storeMemory({
            ...baseMemory,
            content: `Message ${i}`,
          });
        });
      }

      expect(result.current.memories.length).toBe(3);
    });

    it('sets error when the store call fails', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.storeMemory(baseMemory);
      });

      expect(result.current.error).toBe('Network error');
    });

    it('does not store when enableMemory is false', async () => {
      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: false })
      );

      await act(async () => {
        await result.current.storeMemory(baseMemory);
      });

      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('refreshes stats after a successful store', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockResolvedValueOnce(storeOk())
        .mockResolvedValueOnce(statsOk({ shortTermMemoryCount: 1 }));

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.storeMemory(baseMemory);
      });

      // mount stats + store + post-store stats
      expect(global.fetch).toHaveBeenCalledTimes(3);
    });
  });

  describe('Memory Context', () => {
    const contextResponse = (overrides: Record<string, unknown>) => ({
      ok: true,
      json: async () => ({
        status: 'success',
        context: {
          shortTermMemories: [],
          longTermMemories: [],
          userPatterns: [],
          conversationSummary: 'Summary',
          relevanceScore: 0.5,
          ...overrides,
        },
      }),
    });

    it('retrieves memory context via the backend API', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockResolvedValueOnce(contextResponse({}));

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.getMemoryContext('Current message');
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/chat/memory/context',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('Current message'),
        })
      );
    });

    it('sets memoryContext from the API response', async () => {
      const mockMemories = [
        { id: 'mem-1', content: 'Message 1', role: 'user' },
        { id: 'mem-2', content: 'Message 2', role: 'assistant' },
      ];

      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockResolvedValueOnce(
          contextResponse({ shortTermMemories: mockMemories, relevanceScore: 0.8 })
        );

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.getMemoryContext('Test');
      });

      expect(result.current.memoryContext?.shortTermMemories).toEqual(mockMemories);
      expect(result.current.memoryContext?.relevanceScore).toBe(0.8);
    });

    it('returns a disabled context when enableMemory is false', async () => {
      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: false })
      );

      let context: any;
      await act(async () => {
        context = await result.current.getMemoryContext('Test');
      });

      expect(context.shortTermMemories).toEqual([]);
      expect(context.conversationSummary).toBe('Memory system disabled');
      expect(context.relevanceScore).toBe(0);
    });

    it('returns an empty context (not null) on error', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockRejectedValueOnce(new Error('API error'));

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      let context: any;
      await act(async () => {
        context = await result.current.getMemoryContext('Test');
      });

      expect(context).not.toBeNull();
      expect(context.shortTermMemories).toEqual([]);
      expect(context.conversationSummary).toBe('Memory context unavailable');
    });
  });

  describe('Session Management', () => {
    it('clears session memory via the backend API', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success' }) })
        .mockResolvedValueOnce(statsOk({ shortTermMemoryCount: 0 }));

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.clearSessionMemory();
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/chat/memory/session/session-1',
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('clears the local memories array on clear', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk()) // mount stats
        .mockResolvedValueOnce(storeOk()) // store
        .mockResolvedValueOnce(statsOk({ shortTermMemoryCount: 1 })) // post-store stats
        .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success' }) }) // clear
        .mockResolvedValueOnce(statsOk({ shortTermMemoryCount: 0 })); // post-clear stats

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.storeMemory(baseMemory);
      });

      expect(result.current.memories.length).toBe(1);

      await act(async () => {
        await result.current.clearSessionMemory();
      });

      expect(result.current.memories).toEqual([]);
    });

    it('clears memoryContext on clear', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'success' }),
      });

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      // Set context (mockResolvedValue serves every call; context payload has no
      // `context` field so memoryContext becomes undefined, which is not null).
      await act(async () => {
        await result.current.getMemoryContext('Test');
      });

      expect(result.current.memoryContext).not.toBeNull();

      await act(async () => {
        await result.current.clearSessionMemory();
      });

      expect(result.current.memoryContext).toBeNull();
    });

    it('refreshes stats after clear', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk()) // mount stats
        .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success' }) }) // clear
        .mockResolvedValueOnce(statsOk({ shortTermMemoryCount: 0 })); // post-clear stats

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.clearSessionMemory();
      });

      // mount stats + clear + post-clear stats
      expect(global.fetch).toHaveBeenCalledTimes(3);
    });

    it('does nothing when enableMemory is false', async () => {
      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: false })
      );

      await act(async () => {
        await result.current.clearSessionMemory();
      });

      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('Memory Stats', () => {
    it('retrieves stats via the backend API', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockResolvedValueOnce(
          statsOk({
            shortTermMemoryCount: 10,
            userPatternCount: 5,
            activeSessions: 2,
            totalMemoryAccesses: 100,
            lancedbAvailable: true,
          })
        );

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.refreshMemoryStats();
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/chat/memory/stats?user_id=user-1'
      );
      expect(result.current.memoryStats).toEqual({
        status: 'success',
        shortTermMemoryCount: 10,
        userPatternCount: 5,
        activeSessions: 2,
        totalMemoryAccesses: 100,
        lancedbAvailable: true,
      });
    });

    it('updates memoryStats state on success', async () => {
      const mockStats = {
        shortTermMemoryCount: 15,
        userPatternCount: 7,
        activeSessions: 3,
        totalMemoryAccesses: 150,
        lancedbAvailable: true,
      };

      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockResolvedValueOnce(statsOk(mockStats));

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.refreshMemoryStats();
      });

      expect(result.current.memoryStats).toEqual({ status: 'success', ...mockStats });
    });

    it('does not set error when a stats refresh fails', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(
        new Error('Stats error')
      );

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      const errorBefore = result.current.error;

      await act(async () => {
        await result.current.refreshMemoryStats();
      });

      expect(result.current.error).toBe(errorBefore);
    });

    it('does not fetch stats when enableMemory is false', async () => {
      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: false })
      );

      await act(async () => {
        await result.current.refreshMemoryStats();
      });

      expect(result.current.memoryStats).toBeNull();
      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('Derived State', () => {
    const contextResponse = (overrides: Record<string, unknown>) => ({
      ok: true,
      json: async () => ({
        status: 'success',
        context: {
          shortTermMemories: [],
          longTermMemories: [],
          userPatterns: [],
          conversationSummary: 'Summary',
          relevanceScore: 0.5,
          ...overrides,
        },
      }),
    });

    it('hasRelevantContext is true when relevanceScore > 0.3 and there are memories', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockResolvedValueOnce(
          contextResponse({
            shortTermMemories: [{ id: 'mem-1', content: 'Test', role: 'user' }],
            relevanceScore: 0.8,
          })
        );

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.getMemoryContext('Test');
      });

      expect(result.current.hasRelevantContext).toBe(true);
    });

    it('hasRelevantContext is false when relevanceScore <= 0.3', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(statsOk())
        .mockResolvedValueOnce(
          contextResponse({
            shortTermMemories: [{ id: 'mem-1', content: 'Test', role: 'user' }],
            relevanceScore: 0.2,
          })
        );

      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      await act(async () => {
        await result.current.getMemoryContext('Test');
      });

      expect(result.current.hasRelevantContext).toBe(false);
    });

    it('contextRelevanceScore defaults to 0 when memoryContext is null', () => {
      const { result } = renderHook(() =>
        useChatMemory({ userId: 'user-1', sessionId: 'session-1', enableMemory: true })
      );

      expect(result.current.contextRelevanceScore).toBe(0);
    });
  });
});
