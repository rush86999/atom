import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatMemory } from '../useChatMemory';

// Mock API calls
const mockSaveMemory = jest.fn();
const mockLoadMemory = jest.fn();
const mockClearMemory = jest.fn();

// Mock local storage
const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
});

describe('useChatMemory Hook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockLocalStorage.getItem.mockReturnValue(null);
  });

  describe('Memory Initialization', () => {
    it('initializes with empty memory', () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      expect(result.current.messages).toEqual([]);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('initializes with existing memory from storage', () => {
      const existingMemory = {
        messages: [
          { id: '1', role: 'user', content: 'Hello' },
          { id: '2', role: 'assistant', content: 'Hi there!' },
        ],
        metadata: { createdAt: Date.now() },
      };

      mockLocalStorage.getItem.mockReturnValue(JSON.stringify(existingMemory));

      const { result } = renderHook(() => useChatMemory('test-chat'));

      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0].content).toBe('Hello');
    });

    it('handles corrupted storage data gracefully', () => {
      mockLocalStorage.getItem.mockReturnValue('invalid-json');

      const { result } = renderHook(() => useChatMemory('test-chat'));

      // Should initialize with empty state instead of crashing
      expect(result.current.messages).toEqual([]);
      expect(result.current.error).toBeNull();
    });

    it('handles different chat sessions independently', () => {
      const { result: result1 } = renderHook(() => useChatMemory('chat-1'));
      const { result: result2 } = renderHook(() => useChatMemory('chat-2'));

      expect(result1.current.messages).not.toBe(result2.current.messages);
    });
  });

  describe('Message Management', () => {
    it('adds user message to memory', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({
          role: 'user',
          content: 'Hello',
        });
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0].role).toBe('user');
      expect(result.current.messages[0].content).toBe('Hello');
    });

    it('adds assistant message to memory', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({
          role: 'assistant',
          content: 'Hi there!',
        });
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0].role).toBe('assistant');
    });

    it('adds system message to memory', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({
          role: 'system',
          content: 'System message',
        });
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0].role).toBe('system');
    });

    it('assigns unique IDs to messages', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({ role: 'user', content: 'First' });
        await result.current.addMessage({ role: 'assistant', content: 'Second' });
      });

      expect(result.current.messages[0].id).toBeDefined();
      expect(result.current.messages[1].id).toBeDefined();
      expect(result.current.messages[0].id).not.toBe(result.current.messages[1].id);
    });

    it('adds timestamps to messages', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      const beforeTime = Date.now();

      await act(async () => {
        await result.current.addMessage({ role: 'user', content: 'Test' });
      });

      const afterTime = Date.now();

      expect(result.current.messages[0].timestamp).toBeDefined();
      expect(result.current.messages[0].timestamp).toBeGreaterThanOrEqual(beforeTime);
      expect(result.current.messages[0].timestamp).toBeLessThanOrEqual(afterTime);
    });

    it('maintains message order', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({ role: 'user', content: 'First' });
        await result.current.addMessage({ role: 'assistant', content: 'Second' });
        await result.current.addMessage({ role: 'user', content: 'Third' });
      });

      expect(result.current.messages[0].content).toBe('First');
      expect(result.current.messages[1].content).toBe('Second');
      expect(result.current.messages[2].content).toBe('Third');
    });
  });

  describe('Memory Persistence', () => {
    it('saves messages to local storage', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({ role: 'user', content: 'Test' });
      });

      expect(mockLocalStorage.setItem).toHaveBeenCalled();
    });

    it('loads messages from local storage on mount', () => {
      const savedMessages = [
        { id: '1', role: 'user', content: 'Saved message', timestamp: Date.now() },
      ];

      mockLocalStorage.getItem.mockReturnValue(JSON.stringify(savedMessages));

      const { result } = renderHook(() => useChatMemory('test-chat'));

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0].content).toBe('Saved message');
    });

    it('clears memory from storage', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({ role: 'user', content: 'Test' });
        await result.current.clearMemory();
      });

      expect(result.current.messages).toEqual([]);
      expect(mockLocalStorage.removeItem).toHaveBeenCalled();
    });

    it('handles storage errors gracefully', async () => {
      mockLocalStorage.setItem.mockImplementation(() => {
        throw new Error('Storage error');
      });

      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({ role: 'user', content: 'Test' });
      });

      // Should not throw, but handle error
      expect(result.current.error).toBeDefined();
    });
  });

  describe('Message History Management', () => {
    it('limits message history to max size', async () => {
      const MAX_MESSAGES = 50;

      const { result } = renderHook(() =>
        useChatMemory('test-chat', { maxMessages: MAX_MESSAGES })
      );

      // Add more messages than max
      for (let i = 0; i < MAX_MESSAGES + 10; i++) {
        await act(async () => {
          await result.current.addMessage({
            role: 'user',
            content: `Message ${i}`,
          });
        });
      }

      // Should not exceed max
      expect(result.current.messages.length).toBeLessThanOrEqual(MAX_MESSAGES);
    });

    it('removes oldest messages when limit is reached', async () => {
      const MAX_MESSAGES = 5;

      const { result } = renderHook(() =>
        useChatMemory('test-chat', { maxMessages: MAX_MESSAGES })
      );

      // Add messages beyond limit
      for (let i = 0; i < MAX_MESSAGES + 2; i++) {
        await act(async () => {
          await result.current.addMessage({
            role: 'user',
            content: `Message ${i}`,
          });
        });
      }

      // First message should be removed
      expect(result.current.messages[0].content).toBe('Message 2');
      expect(result.current.messages.length).toBe(MAX_MESSAGES);
    });

    it('clears old messages based on time', async () => {
      const MAX_AGE_MS = 1000 * 60 * 60; // 1 hour

      const { result } = renderHook(() =>
        useChatMemory('test-chat', { maxAge: MAX_AGE_MS })
      );

      // Add old message
      await act(async () => {
        await result.current.addMessage({
          role: 'user',
          content: 'Old message',
          timestamp: Date.now() - MAX_AGE_MS - 1000,
        });
      });

      // Add recent message
      await act(async () => {
        await result.current.addMessage({
          role: 'user',
          content: 'Recent message',
          timestamp: Date.now(),
        });
      });

      // Should only have recent message
      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0].content).toBe('Recent message');
    });
  });

  describe('API Integration', () => {
    it('syncs memory with backend API', async () => {
      mockSaveMemory.mockResolvedValue({ success: true });

      const { result } = renderHook(() =>
        useChatMemory('test-chat', { syncWithBackend: true })
      );

      await act(async () => {
        await result.current.addMessage({ role: 'user', content: 'Test' });
      });

      await waitFor(() => {
        expect(mockSaveMemory).toHaveBeenCalled();
      });
    });

    it('loads memory from backend API on mount', async () => {
      const backendMemory = {
        messages: [
          { id: '1', role: 'user', content: 'From backend' },
        ],
      };

      mockLoadMemory.mockResolvedValue(backendMemory);

      const { result } = renderHook(() =>
        useChatMemory('test-chat', { syncWithBackend: true })
      );

      await waitFor(() => {
        expect(result.current.messages).toHaveLength(1);
        expect(result.current.messages[0].content).toBe('From backend');
      });
    });

    it('handles API sync errors gracefully', async () => {
      mockSaveMemory.mockRejectedValue(new Error('API Error'));

      const { result } = renderHook(() =>
        useChatMemory('test-chat', { syncWithBackend: true })
      );

      await act(async () => {
        await result.current.addMessage({ role: 'user', content: 'Test' });
      });

      // Should not throw, but handle error
      expect(result.current.error).toBeDefined();
    });
  });

  describe('Message Search and Filtering', () => {
    it('searches messages by content', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({ role: 'user', content: 'Hello world' });
        await result.current.addMessage({ role: 'assistant', content: 'Hi there' });
        await result.current.addMessage({ role: 'user', content: 'Hello again' });
      });

      const searchResults = result.current.searchMessages('Hello');

      expect(searchResults).toHaveLength(2);
      expect(searchResults[0].content).toBe('Hello world');
      expect(searchResults[1].content).toBe('Hello again');
    });

    it('filters messages by role', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({ role: 'user', content: 'User 1' });
        await result.current.addMessage({ role: 'assistant', content: 'Assistant 1' });
        await result.current.addMessage({ role: 'user', content: 'User 2' });
      });

      const userMessages = result.current.getMessagesByRole('user');

      expect(userMessages).toHaveLength(2);
      expect(userMessages.every(m => m.role === 'user')).toBe(true);
    });

    it('gets messages within time range', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      const now = Date.now();

      await act(async () => {
        await result.current.addMessage({
          role: 'user',
          content: 'Old',
          timestamp: now - 10000,
        });
        await result.current.addMessage({
          role: 'user',
          content: 'Recent',
          timestamp: now,
        });
      });

      const recentMessages = result.current.getMessagesInTimeRange(now - 5000, now + 1000);

      expect(recentMessages).toHaveLength(1);
      expect(recentMessages[0].content).toBe('Recent');
    });
  });

  describe('Memory Export and Import', () => {
    it('exports memory as JSON', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({ role: 'user', content: 'Test message' });
      });

      const exported = result.current.exportAsJSON();

      expect(exported).toBeDefined();
      expect(JSON.parse(exported)).toEqual({
        chatId: 'test-chat',
        messages: expect.any(Array),
      });
    });

    it('imports memory from JSON', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      const importData = {
        chatId: 'test-chat',
        messages: [
          { id: '1', role: 'user', content: 'Imported message', timestamp: Date.now() },
        ],
      };

      await act(async () => {
        await result.current.importFromJSON(JSON.stringify(importData));
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0].content).toBe('Imported message');
    });

    it('handles invalid import data', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.importFromJSON('invalid-json');
      });

      // Should not crash
      expect(result.current.messages).toEqual([]);
    });
  });

  describe('Error Handling', () => {
    it('handles invalid message data', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        try {
          await result.current.addMessage({ role: 'invalid' as any, content: '' });
        } catch (error) {
          // Expected to fail validation
        }
      });

      // Should not add invalid message
      expect(result.current.messages).toEqual([]);
    });

    it('recovers from storage errors', async () => {
      mockLocalStorage.getItem.mockImplementation(() => {
        throw new Error('Storage error');
      });

      const { result } = renderHook(() => useChatMemory('test-chat'));

      // Should initialize with empty state
      expect(result.current.messages).toEqual([]);
    });
  });

  describe('Performance', () => {
    it('handles large message history efficiently', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      const startTime = Date.now();

      // Add 100 messages
      for (let i = 0; i < 100; i++) {
        await act(async () => {
          await result.current.addMessage({
            role: 'user',
            content: `Message ${i}`,
          });
        });
      }

      const duration = Date.now() - startTime;

      // Should complete in reasonable time
      expect(duration).toBeLessThan(5000);
      expect(result.current.messages).toHaveLength(100);
    });

    it('debounces storage writes', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      // Add multiple messages rapidly
      await act(async () => {
        await Promise.all([
          result.current.addMessage({ role: 'user', content: '1' }),
          result.current.addMessage({ role: 'user', content: '2' }),
          result.current.addMessage({ role: 'user', content: '3' }),
        ]);
      });

      // Should only write to storage once (debounced)
      expect(mockLocalStorage.setItem).toHaveBeenCalledTimes(1);
    });
  });

  describe('Edge Cases', () => {
    it('handles empty chat ID', () => {
      const { result } = renderHook(() => useChatMemory(''));

      expect(result.current.messages).toEqual([]);
    });

    it('handles special characters in messages', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await result.current.addMessage({
          role: 'user',
          content: 'Test with emoji 🔥 and special chars <>&"',
        });
      });

      expect(result.current.messages[0].content).toContain('🔥');
    });

    it('handles very long messages', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      const longContent = 'A'.repeat(10000);

      await act(async () => {
        await result.current.addMessage({
          role: 'user',
          content: longContent,
        });
      });

      expect(result.current.messages[0].content).toHaveLength(10000);
    });

    it('handles concurrent message additions', async () => {
      const { result } = renderHook(() => useChatMemory('test-chat'));

      await act(async () => {
        await Promise.all([
          result.current.addMessage({ role: 'user', content: '1' }),
          result.current.addMessage({ role: 'user', content: '2' }),
          result.current.addMessage({ role: 'user', content: '3' }),
        ]);
      });

      expect(result.current.messages).toHaveLength(3);
    });
  });
});
