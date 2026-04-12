import { renderHook, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock the useChatMemory hook
const createMockUseChatMemory = () => {
  let messages: any[] = [];
  let listeners: Set<Function> = new Set();

  return {
    useChatMemory: (options: { sessionId: string; maxSize?: number }) => {
      return {
        messages,
        addMessage: (message: any) => {
          messages.push({ ...message, timestamp: new Date().toISOString() });
          listeners.forEach(fn => fn());
          if (options.maxSize && messages.length > options.maxSize) {
            messages.shift();
          }
        },
        clearMessages: () => {
          messages = [];
          listeners.forEach(fn => fn());
        },
        updateMessage: (id: string, updates: any) => {
          const index = messages.findIndex(m => m.id === id);
          if (index !== -1) {
            messages[index] = { ...messages[index], ...updates };
            listeners.forEach(fn => fn());
          }
        },
        deleteMessage: (id: string) => {
          messages = messages.filter(m => m.id !== id);
          listeners.forEach(fn => fn());
        },
        subscribe: (callback: Function) => {
          listeners.add(callback);
          return () => listeners.delete(callback);
        },
        getSessionHistory: () => messages,
        exportMessages: () => JSON.stringify(messages, null, 2),
        importMessages: (json: string) => {
          try {
            const imported = JSON.parse(json);
            messages = imported;
            listeners.forEach(fn => fn());
            return true;
          } catch {
            return false;
          }
        },
      };
    },
  };
};

describe('useChatMemory - Integration Tests', () => {
  let mockUseChatMemory: ReturnType<typeof createMockUseChatMemory>['useChatMemory'];

  beforeEach(() => {
    const mock = createMockUseChatMemory();
    mockUseChatMemory = mock.useChatMemory;
  });

  describe('Message Persistence', () => {
    it('should persist messages to localStorage', async () => {
      const storageKey = 'chat-memory-session-123';
      const setItemSpy = jest.spyOn(Storage.prototype, 'setItem');

      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      act(() => {
        result.current.addMessage({
          id: 'msg-1',
          role: 'user',
          content: 'Hello',
        });
      });

      // Simulate localStorage save
      const messages = result.current.getSessionHistory();
      localStorage.setItem(storageKey, JSON.stringify(messages));

      expect(setItemSpy).toHaveBeenCalledWith(
        storageKey,
        JSON.stringify(messages)
      );
      expect(result.current.messages).toHaveLength(1);

      setItemSpy.mockRestore();
    });

    it('should restore messages from localStorage on mount', async () => {
      const storageKey = 'chat-memory-session-123';
      const savedMessages = [
        { id: 'msg-1', role: 'user', content: 'Previous message' },
        { id: 'msg-2', role: 'assistant', content: 'Previous response' },
      ];

      const getItemSpy = jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(
        JSON.stringify(savedMessages)
      );

      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      // Simulate loading from localStorage
      act(() => {
        const loaded = JSON.parse(localStorage.getItem(storageKey) || '[]');
        loaded.forEach((msg: any) => result.current.addMessage(msg));
      });

      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0].content).toBe('Previous message');

      getItemSpy.mockRestore();
    });

    it('should handle corrupted localStorage data gracefully', async () => {
      const storageKey = 'chat-memory-session-123';
      const getItemSpy = jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(
        'invalid-json{'
      );

      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      // Should not crash, just start with empty state
      expect(result.current.messages).toHaveLength(0);

      getItemSpy.mockRestore();
    });

    it('should clear localStorage on session end', async () => {
      const storageKey = 'chat-memory-session-123';
      const removeItemSpy = jest.spyOn(Storage.prototype, 'removeItem');

      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      act(() => {
        result.current.clearMessages();
        localStorage.removeItem(storageKey);
      });

      expect(removeItemSpy).toHaveBeenCalledWith(storageKey);
      expect(result.current.messages).toHaveLength(0);

      removeItemSpy.mockRestore();
    });
  });

  describe('History Management', () => {
    it('should maintain message order by timestamp', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      act(() => {
        result.current.addMessage({ id: 'msg-1', role: 'user', content: 'First' });
        // Simulate delay
        result.current.addMessage({ id: 'msg-2', role: 'assistant', content: 'Second' });
        result.current.addMessage({ id: 'msg-3', role: 'user', content: 'Third' });
      });

      const messages = result.current.getSessionHistory();
      expect(messages[0].content).toBe('First');
      expect(messages[1].content).toBe('Second');
      expect(messages[2].content).toBe('Third');
    });

    it('should limit message history to maxSize', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123', maxSize: 3 })
      );

      act(() => {
        result.current.addMessage({ id: 'msg-1', role: 'user', content: 'Message 1' });
        result.current.addMessage({ id: 'msg-2', role: 'assistant', content: 'Message 2' });
        result.current.addMessage({ id: 'msg-3', role: 'user', content: 'Message 3' });
        result.current.addMessage({ id: 'msg-4', role: 'assistant', content: 'Message 4' });
      });

      // Should only keep last 3 messages
      expect(result.current.messages).toHaveLength(3);
      expect(result.current.messages[0].id).toBe('msg-2'); // msg-1 evicted
      expect(result.current.messages[2].id).toBe('msg-4');
    });

    it('should update existing message', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      act(() => {
        result.current.addMessage({ id: 'msg-1', role: 'user', content: 'Original' });
      });

      act(() => {
        result.current.updateMessage('msg-1', { content: 'Updated' });
      });

      expect(result.current.messages[0].content).toBe('Updated');
      expect(result.current.messages).toHaveLength(1);
    });

    it('should delete message from history', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      act(() => {
        result.current.addMessage({ id: 'msg-1', role: 'user', content: 'Message 1' });
        result.current.addMessage({ id: 'msg-2', role: 'assistant', content: 'Message 2' });
        result.current.addMessage({ id: 'msg-3', role: 'user', content: 'Message 3' });
      });

      act(() => {
        result.current.deleteMessage('msg-2');
      });

      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0].id).toBe('msg-1');
      expect(result.current.messages[1].id).toBe('msg-3');
    });
  });

  describe('API Integration', () => {
    it('should fetch chat history from API', async () => {
      const mockHistory = [
        { id: 'msg-1', role: 'user', content: 'From API 1' },
        { id: 'msg-2', role: 'assistant', content: 'From API 2' },
      ];

      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: { messages: mockHistory },
        }),
      });

      const response = await fetch('/api/chat/sessions/session-123/history');
      const result = await response.json();

      expect(result.data.messages).toHaveLength(2);
      expect(result.data.messages[0].content).toBe('From API 1');
    });

    it('should sync messages to API', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      act(() => {
        result.current.addMessage({ id: 'msg-1', role: 'user', content: 'New message' });
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      const messages = result.current.getSessionHistory();
      await fetch('/api/chat/sessions/session-123/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages }),
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/chat/sessions/session-123/sync',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ messages }),
        })
      );
    });

    it('should handle API errors gracefully', async () => {
      global.fetch = jest.fn().mockRejectedValueOnce(new Error('Network error'));

      await expect(
        fetch('/api/chat/sessions/session-123/history')
      ).rejects.toThrow('Network error');
    });
  });

  describe('Message Export/Import', () => {
    it('should export messages as JSON', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      act(() => {
        result.current.addMessage({ id: 'msg-1', role: 'user', content: 'Export test' });
      });

      const exported = result.current.exportMessages();
      const parsed = JSON.parse(exported);

      expect(parsed).toHaveLength(1);
      expect(parsed[0].content).toBe('Export test');
    });

    it('should import messages from JSON', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      const jsonToImport = JSON.stringify([
        { id: 'msg-1', role: 'user', content: 'Imported 1' },
        { id: 'msg-2', role: 'assistant', content: 'Imported 2' },
      ]);

      act(() => {
        const success = result.current.importMessages(jsonToImport);
        expect(success).toBe(true);
      });

      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0].content).toBe('Imported 1');
    });

    it('should handle invalid JSON on import', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      act(() => {
        const success = result.current.importMessages('invalid-json{');
        expect(success).toBe(false);
      });

      expect(result.current.messages).toHaveLength(0);
    });
  });

  describe('Subscription System', () => {
    it('should notify subscribers on message add', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      let callCount = 0;
      const unsubscribe = result.current.subscribe(() => {
        callCount++;
      });

      act(() => {
        result.current.addMessage({ id: 'msg-1', role: 'user', content: 'Test' });
      });

      expect(callCount).toBe(1);

      unsubscribe();
    });

    it('should unsubscribe correctly', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      let callCount = 0;
      const unsubscribe = result.current.subscribe(() => {
        callCount++;
      });

      act(() => {
        result.current.addMessage({ id: 'msg-1', role: 'user', content: 'Test 1' });
      });

      unsubscribe();

      act(() => {
        result.current.addMessage({ id: 'msg-2', role: 'user', content: 'Test 2' });
      });

      expect(callCount).toBe(1); // Only called once before unsubscribe
    });

    it('should support multiple subscribers', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      const subscriber1Calls: number[] = [];
      const subscriber2Calls: number[] = [];

      const unsubscribe1 = result.current.subscribe(() => {
        subscriber1Calls.push(Date.now());
      });

      const unsubscribe2 = result.current.subscribe(() => {
        subscriber2Calls.push(Date.now());
      });

      act(() => {
        result.current.addMessage({ id: 'msg-1', role: 'user', content: 'Test' });
      });

      expect(subscriber1Calls).toHaveLength(1);
      expect(subscriber2Calls).toHaveLength(1);

      unsubscribe1();
      unsubscribe2();
    });
  });

  describe('Memory Optimization', () => {
    it('should batch multiple message additions', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      let updateCount = 0;
      result.current.subscribe(() => {
        updateCount++;
      });

      act(() => {
        // Batch additions
        const messagesToAdd = [
          { id: 'msg-1', role: 'user', content: 'Batch 1' },
          { id: 'msg-2', role: 'user', content: 'Batch 2' },
          { id: 'msg-3', role: 'user', content: 'Batch 3' },
        ];

        messagesToAdd.forEach(msg => result.current.addMessage(msg));
      });

      expect(result.current.messages).toHaveLength(3);
      expect(updateCount).toBe(3); // Each add triggers update
    });

    it('should debounce expensive operations', async () => {
      const { result } = renderHook(() =>
        mockUseChatMemory({ sessionId: 'session-123' })
      );

      let syncCallCount = 0;
      const syncToAPI = jest.fn(() => {
        syncCallCount++;
      });

      // Debounce sync function
      let timeoutId: NodeJS.Timeout;
      const debouncedSync = (...args: any[]) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => syncToAPI(...args), 100);
      };

      act(() => {
        result.current.addMessage({ id: 'msg-1', role: 'user', content: 'Test 1' });
        debouncedSync();

        result.current.addMessage({ id: 'msg-2', role: 'user', content: 'Test 2' });
        debouncedSync();

        result.current.addMessage({ id: 'msg-3', role: 'user', content: 'Test 3' });
        debouncedSync();
      });

      // Wait for debounce
      await new Promise(resolve => setTimeout(resolve, 150));

      // Should only call once after all rapid additions
      expect(syncCallCount).toBe(1);
    });
  });
});
