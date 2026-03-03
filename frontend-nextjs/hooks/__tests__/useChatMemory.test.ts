/**
 * useChatMemory Hook Unit Tests
 *
 * Tests for useChatMemory hook managing conversation context and persistence.
 * Verifies memory storage, context retrieval, session management, stats,
 * derived state, and auto-store functionality.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatMemory } from '../useChatMemory';

// Mock fetch API
global.fetch = jest.fn();

describe('useChatMemory Hook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('1. Hook Initialization Tests', () => {
    test('initializes with empty memories array', () => {
      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      expect(result.current.memories).toEqual([]);
    });

    test('initializes with null memoryContext', () => {
      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      expect(result.current.memoryContext).toBeNull();
    });

    test('initializes with null memoryStats', () => {
      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      expect(result.current.memoryStats).toBeNull();
    });

    test('initializes with isLoading false', () => {
      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      expect(result.current.isLoading).toBe(false);
    });

    test('initializes with error null', () => {
      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      expect(result.current.error).toBeNull();
    });

    test('calls refreshMemoryStats on mount when enableMemory is true', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          shortTermMemoryCount: 5,
          userPatternCount: 3,
          activeSessions: 2,
          totalMemoryAccesses: 10,
          lancedbAvailable: true,
        }),
      });

      renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/chat/memory/stats?user_id=user-1'
        );
      });
    });
  });

  describe('2. Memory Storage Tests', () => {
    test('stores memory via API call', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          memory_id: 'mem-1',
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.storeMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          role: 'user',
          content: 'Test message',
          metadata: {
            messageType: 'text',
            importance: 0.5,
            accessCount: 0,
            lastAccessed: new Date(),
          },
        });
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/chat/memory/store',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: expect.stringContaining('Test message'),
        })
      );
    });

    test('adds new memory to local memories array', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            status: 'success',
            memory_id: 'mem-1',
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            status: 'success',
            shortTermMemoryCount: 1,
          }),
        });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
          contextWindow: 10,
        })
      );

      await act(async () => {
        await result.current.storeMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          role: 'user',
          content: 'Test message',
          metadata: {
            messageType: 'text',
            importance: 0.5,
            accessCount: 0,
            lastAccessed: new Date(),
          },
        });
      });

      expect(result.current.memories.length).toBe(1);
      expect(result.current.memories[0].content).toBe('Test message');
    });

    test('limits memories to contextWindow size', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValue({
          ok: true,
          json: async () => ({
            status: 'success',
            memory_id: `mem-${Math.random()}`,
          }),
        })
        // Mock stats response
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            status: 'success',
          }),
        });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
          contextWindow: 3, // Small window to test limit
        })
      );

      // Add 5 memories
      for (let i = 0; i < 5; i++) {
        await act(async () => {
          await result.current.storeMemory({
            userId: 'user-1',
            sessionId: 'session-1',
            role: 'user',
            content: `Message ${i}`,
            metadata: {
              messageType: 'text',
              importance: 0.5,
              accessCount: 0,
              lastAccessed: new Date(),
            },
          });
        });
      }

      // Should only have 3 memories (contextWindow size)
      expect(result.current.memories.length).toBe(3);
    });

    // Note: Testing isLoading during async operation is flaky due to React's batching
    // The hook correctly sets isLoading=true at the start and false at the end
    // but testing the intermediate state is unreliable

    test('sets error on store failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error('Network error')
      );

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.storeMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          role: 'user',
          content: 'Test',
          metadata: {
            messageType: 'text',
            importance: 0.5,
            accessCount: 0,
            lastAccessed: new Date(),
          },
        });
      });

      expect(result.current.error).toBe('Network error');
    });

    test('does not store when enableMemory is false', async () => {
      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: false,
        })
      );

      await act(async () => {
        await result.current.storeMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          role: 'user',
          content: 'Test',
          metadata: {
            messageType: 'text',
            importance: 0.5,
            accessCount: 0,
            lastAccessed: new Date(),
          },
        });
      });

      expect(global.fetch).not.toHaveBeenCalled();
    });

    test('refreshes stats after successful store', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            status: 'success',
            memory_id: 'mem-1',
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            status: 'success',
            shortTermMemoryCount: 1,
          }),
        });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.storeMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          role: 'user',
          content: 'Test',
          metadata: {
            messageType: 'text',
            importance: 0.5,
            accessCount: 0,
            lastAccessed: new Date(),
          },
        });
      });

      expect(global.fetch).toHaveBeenCalledTimes(2); // store + stats
    });

    test('handles network errors gracefully', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error('Connection failed')
      );

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.storeMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          role: 'user',
          content: 'Test',
          metadata: {
            messageType: 'text',
            importance: 0.5,
            accessCount: 0,
            lastAccessed: new Date(),
          },
        });
      });

      expect(result.current.error).toBe('Connection failed');
    });
  });

  describe('3. Memory Context Tests', () => {
    test('retrieves memory context via API', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          context: {
            shortTermMemories: [
              {
                id: 'mem-1',
                content: 'Previous message',
                role: 'user',
              },
            ],
            longTermMemories: [],
            userPatterns: [],
            conversationSummary: 'Test summary',
            relevanceScore: 0.8,
          },
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      const context = await act(async () => {
        return await result.current.getMemoryContext('Current message');
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/chat/memory/context',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('Current message'),
        })
      );
    });

    test('returns context with shortTermMemories', async () => {
      const mockMemories = [
        { id: 'mem-1', content: 'Message 1', role: 'user' },
        { id: 'mem-2', content: 'Message 2', role: 'assistant' },
      ];

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          context: {
            shortTermMemories: mockMemories,
            longTermMemories: [],
            userPatterns: [],
            conversationSummary: 'Summary',
            relevanceScore: 0.7,
          },
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.getMemoryContext('Test');
      });

      expect(result.current.memoryContext?.shortTermMemories).toEqual(
        mockMemories
      );
    });

    test('returns context with longTermMemories', async () => {
      const mockLongTerm = [
        { id: 'lt-1', content: 'Old conversation', role: 'user' },
      ];

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          context: {
            shortTermMemories: [],
            longTermMemories: mockLongTerm,
            userPatterns: [],
            conversationSummary: 'Summary',
            relevanceScore: 0.6,
          },
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      const context = await act(async () => {
        return await result.current.getMemoryContext('Test');
      });

      expect(context.longTermMemories).toEqual(mockLongTerm);
    });

    test('returns context with relevanceScore', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          context: {
            shortTermMemories: [],
            longTermMemories: [],
            userPatterns: [],
            conversationSummary: 'Summary',
            relevanceScore: 0.85,
          },
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      const context = await act(async () => {
        return await result.current.getMemoryContext('Test');
      });

      expect(context.relevanceScore).toBe(0.85);
    });

    test('returns disabled context when enableMemory is false', async () => {
      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: false,
        })
      );

      const context = await act(async () => {
        return await result.current.getMemoryContext('Test');
      });

      expect(context.shortTermMemories).toEqual([]);
      expect(context.longTermMemories).toEqual([]);
      expect(context.conversationSummary).toBe('Memory system disabled');
      expect(context.relevanceScore).toBe(0);
    });

    test('returns empty context on error (not null)', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error('API error')
      );

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      const context = await act(async () => {
        return await result.current.getMemoryContext('Test');
      });

      expect(context).not.toBeNull();
      expect(context.shortTermMemories).toEqual([]);
      expect(context.conversationSummary).toBe('Memory context unavailable');
    });
  });

  describe('4. Session Management Tests', () => {
    test('clears session memory via API call', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.clearSessionMemory();
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/chat/memory/session/session-1',
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });

    test('clears local memories array on clear', async () => {
      // First store a memory
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            status: 'success',
            memory_id: 'mem-1',
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            status: 'success',
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            status: 'success',
          }),
        });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.storeMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          role: 'user',
          content: 'Test',
          metadata: {
            messageType: 'text',
            importance: 0.5,
            accessCount: 0,
            lastAccessed: new Date(),
          },
        });
      });

      expect(result.current.memories.length).toBe(1);

      await act(async () => {
        await result.current.clearSessionMemory();
      });

      expect(result.current.memories).toEqual([]);
    });

    test('clears memoryContext on clear', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({
          status: 'success',
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      // First set some context
      await act(async () => {
        await result.current.getMemoryContext('Test');
      });

      expect(result.current.memoryContext).not.toBeNull();

      // Then clear
      await act(async () => {
        await result.current.clearSessionMemory();
      });

      expect(result.current.memoryContext).toBeNull();
    });

    test('refreshes stats after clear', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            status: 'success',
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            status: 'success',
            shortTermMemoryCount: 0,
          }),
        });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.clearSessionMemory();
      });

      expect(global.fetch).toHaveBeenCalledTimes(2); // clear + stats
    });

    test('does nothing when enableMemory is false', async () => {
      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: false,
        })
      );

      await act(async () => {
        await result.current.clearSessionMemory();
      });

      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('5. Memory Stats Tests', () => {
    test('retrieves stats via API', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          shortTermMemoryCount: 10,
          userPatternCount: 5,
          activeSessions: 2,
          totalMemoryAccesses: 100,
          lancedbAvailable: true,
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.refreshMemoryStats();
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/chat/memory/stats?user_id=user-1'
      );

      expect(result.current.memoryStats).toEqual({
        shortTermMemoryCount: 10,
        userPatternCount: 5,
        activeSessions: 2,
        totalMemoryAccesses: 100,
        lancedbAvailable: true,
      });
    });

    test('updates memoryStats state on success', async () => {
      const mockStats = {
        shortTermMemoryCount: 15,
        userPatternCount: 7,
        activeSessions: 3,
        totalMemoryAccesses: 150,
        lancedbAvailable: true,
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          ...mockStats,
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.refreshMemoryStats();
      });

      expect(result.current.memoryStats).toEqual(mockStats);
    });

    test('does not set error on stats failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error('Stats error')
      );

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      const errorBefore = result.current.error;

      await act(async () => {
        await result.current.refreshMemoryStats();
      });

      // Error should not be set for stats refresh
      expect(result.current.error).toBe(errorBefore);
    });

    test('returns null when enableMemory is false', async () => {
      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: false,
        })
      );

      await act(async () => {
        await result.current.refreshMemoryStats();
      });

      expect(result.current.memoryStats).toBeNull();
      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('6. Derived State Tests', () => {
    test('hasRelevantContext is true when relevanceScore > 0.3 and has memories', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          context: {
            shortTermMemories: [{ id: 'mem-1', content: 'Test', role: 'user' }],
            longTermMemories: [],
            userPatterns: [],
            conversationSummary: 'Summary',
            relevanceScore: 0.8,
          },
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.getMemoryContext('Test');
      });

      expect(result.current.hasRelevantContext).toBe(true);
    });

    test('hasRelevantContext is false when relevanceScore <= 0.3', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          context: {
            shortTermMemories: [{ id: 'mem-1', content: 'Test', role: 'user' }],
            longTermMemories: [],
            userPatterns: [],
            conversationSummary: 'Summary',
            relevanceScore: 0.2,
          },
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      await act(async () => {
        await result.current.getMemoryContext('Test');
      });

      expect(result.current.hasRelevantContext).toBe(false);
    });

    test('contextRelevanceScore defaults to 0 when memoryContext is null', () => {
      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
        })
      );

      expect(result.current.contextRelevanceScore).toBe(0);
    });
  });

  describe('7. Auto-Store Tests', () => {
    test('auto-stores messages when autoStoreMessages is true', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          memory_id: 'mem-1',
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
          autoStoreMessages: true,
        })
      );

      // Access the internal autoStoreMessage function
      const hookWithAutoStore = result.current as any;

      await act(async () => {
        await hookWithAutoStore.autoStoreMessage('user', 'Auto-stored message');
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/chat/memory/store',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('Auto-stored message'),
        })
      );
    });

    test('does not auto-store when enableMemory is false', async () => {
      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: false,
          autoStoreMessages: true,
        })
      );

      const hookWithAutoStore = result.current as any;

      await act(async () => {
        await hookWithAutoStore.autoStoreMessage('user', 'Test');
      });

      expect(global.fetch).not.toHaveBeenCalled();
    });

    test('calls storeMemory with correct metadata', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          memory_id: 'mem-1',
        }),
      });

      const { result } = renderHook(() =>
        useChatMemory({
          userId: 'user-1',
          sessionId: 'session-1',
          enableMemory: true,
          autoStoreMessages: true,
        })
      );

      const hookWithAutoStore = result.current as any;

      await act(async () => {
        await hookWithAutoStore.autoStoreMessage('assistant', 'Response', {
          intent: 'answer_question',
        });
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/chat/memory/store',
        expect.objectContaining({
          method: 'POST',
        })
      );

      const callArgs = JSON.parse(
        (global.fetch as jest.Mock).mock.calls[0][1].body
      );

      expect(callArgs.metadata.intent).toBe('answer_question');
      expect(callArgs.metadata.messageType).toBe('text');
    });
  });
});
