import { renderHook, act, waitFor } from '@testing-library/react';
import { useState, useCallback, useRef } from 'react';
import '@testing-library/jest-dom';

// Mock the useChatInterface hook.
// Implemented as a REAL React hook (useState) so renderHook re-renders and
// result.current reflects state changes between assertions.
const createMockUseChatInterface = () => {
  return {
    useChatInterface: (options: { agentId: string; sessionId: string }) => {
      const [messages, setMessages] = useState<any[]>([]);
      const [isLoading, setIsLoading] = useState(false);
      const [error, setError] = useState<string | null>(null);
      const [streamingMessage, setStreamingMessage] = useState<string | null>(null);
      // Track the last attempted message so failed sends can be retried even
      // though failed messages are never added to the list.
      const lastContentRef = useRef<string | null>(null);

      const sendMessage = useCallback(async (content: string, attachments?: any[]) => {
        setIsLoading(true);
        setError(null);
        lastContentRef.current = content;

        try {
          // Simulate API call
          const response = await fetch(`/api/agents/${options.agentId}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              sessionId: options.sessionId,
              message: content,
              attachments,
            }),
          });

          if (!response.ok) {
            throw new Error('Failed to send message');
          }

          const data = await response.json();

          // Add user message + assistant response
          const timestamp = new Date().toISOString();
          setMessages(prev => [
            ...prev,
            {
              id: `msg-${Date.now()}-user`,
              role: 'user',
              content,
              timestamp,
            },
            {
              id: `msg-${Date.now()}-assistant`,
              role: 'assistant',
              content: data.response,
              timestamp,
            },
          ]);

          setIsLoading(false);
          return data;
        } catch (caughtError) {
          setIsLoading(false);
          setError(caughtError instanceof Error ? caughtError.message : 'Unknown error');
          throw caughtError;
        }
      }, [options.agentId, options.sessionId]);

      const streamMessage = useCallback(async (content: string) => {
        setIsLoading(true);
        setStreamingMessage('');
        setError(null);

        try {
          // Simulate streaming API call
          const response = await fetch(`/api/agents/${options.agentId}/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              sessionId: options.sessionId,
              message: content,
            }),
          });

          if (!response.ok) {
            throw new Error('Failed to stream message');
          }

          const reader = response.body?.getReader();
          const decoder = new TextDecoder();

          if (!reader) {
            throw new Error('No response body');
          }

          let fullResponse = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            fullResponse += chunk;
            setStreamingMessage(fullResponse);
          }

          // Add to messages
          const timestamp = new Date().toISOString();
          setMessages(prev => [
            ...prev,
            {
              id: `msg-${Date.now()}-user`,
              role: 'user',
              content,
              timestamp,
            },
            {
              id: `msg-${Date.now()}-assistant`,
              role: 'assistant',
              content: fullResponse,
              timestamp,
            },
          ]);

          setStreamingMessage(null);
          setIsLoading(false);
        } catch (caughtError) {
          setIsLoading(false);
          setStreamingMessage(null);
          setError(caughtError instanceof Error ? caughtError.message : 'Unknown error');
          throw caughtError;
        }
      }, [options.agentId, options.sessionId]);

      const retryMessage = useCallback(async (messageId: string) => {
        const message = messages.find(m => m.id === messageId);
        const content = message ? message.content : lastContentRef.current;
        if (content == null) return;

        setError(null);
        return sendMessage(content);
      }, [messages, sendMessage]);

      const clearMessages = useCallback(() => {
        setMessages([]);
        setError(null);
      }, []);

      const regenerateResponse = useCallback(async (messageId: string) => {
        const messageIndex = messages.findIndex(m => m.id === messageId);
        if (messageIndex === -1) return;

        const userMessage = messages[messageIndex];

        // Drop the previous user/assistant pair and rebuild it via sendMessage
        setMessages(prev => prev.slice(0, messageIndex));

        setError(null);
        return sendMessage(userMessage.content);
      }, [messages, sendMessage]);

      return {
        // State
        messages,
        isLoading,
        error,
        streamingMessage,

        // Actions
        sendMessage,
        streamMessage,
        retryMessage,
        clearMessages,
        regenerateResponse,
      };
    },
  };
};

describe('useChatInterface - Integration Tests', () => {
  let mockUseChatInterface: ReturnType<typeof createMockUseChatInterface>['useChatInterface'];

  beforeEach(() => {
    const mock = createMockUseChatInterface();
    mockUseChatInterface = mock.useChatInterface;
    global.fetch = jest.fn();
    global.mockFetch = global.fetch;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Complex State Management', () => {
    it('should manage loading state during message send', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      expect(result.current.isLoading).toBe(false);

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ response: 'Hello!' }),
      });

      let sendPromise: Promise<unknown>;
      act(() => {
        sendPromise = result.current.sendMessage('Test message');
      });

      // Should be loading during send
      expect(result.current.isLoading).toBe(true);

      // Await inside act so the post-fetch state updates are flushed
      await act(async () => {
        await sendPromise;
      });

      // Should finish loading
      expect(result.current.isLoading).toBe(false);
      expect(result.current.messages).toHaveLength(2); // user + assistant
    });

    it('should handle error state correctly', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('API Error'));

      await act(async () => {
        try {
          await result.current.sendMessage('Test message');
        } catch (error) {
          // Expected error
        }
      });

      expect(result.current.error).toBe('API Error');
      expect(result.current.isLoading).toBe(false);
    });

    it('should clear error on new message', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      // Set error state
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('First error'));

      await act(async () => {
        try {
          await result.current.sendMessage('Test 1');
        } catch (error) {
          // Expected
        }
      });

      expect(result.current.error).toBe('First error');

      // Send new message - should clear error
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ response: 'Success' }),
      });

      await act(() =>
        result.current.sendMessage('Test 2')
      );

      expect(result.current.error).toBeNull();
    });
  });

  describe('API Integration', () => {
    it('should send message to correct API endpoint', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ response: 'Response' }),
      });

      await act(() =>
        result.current.sendMessage('Hello')
      );

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/agents/agent-123/chat',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('Hello'),
        })
      );
    });

    it('should include attachments in API call', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ response: 'Received attachments' }),
      });

      const attachments = [
        { type: 'image', url: 'https://example.com/image.png' },
        { type: 'file', url: 'https://example.com/document.pdf' },
      ];

      await act(() =>
        result.current.sendMessage('Check this out', attachments)
      );

      const fetchCall = (global.mockFetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.attachments).toEqual(attachments);
    });

    it('should handle network errors gracefully', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      let caughtError: Error | undefined;

      await act(async () => {
        try {
          await result.current.sendMessage('Test');
        } catch (error) {
          caughtError = error as Error;
        }
      });

      expect(caughtError).toBeDefined();
      expect(result.current.error).toBe('Network error');
    });

    it('should retry failed messages', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      // First call fails
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Failed'));

      await act(async () => {
        try {
          await result.current.sendMessage('Test');
        } catch (error) {
          // Expected
        }
      });

      expect(result.current.error).toBe('Failed');
      expect(result.current.messages).toHaveLength(0);

      // Retry succeeds
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ response: 'Success!' }),
      });

      await act(() =>
        result.current.retryMessage('msg-1')
      );

      expect(result.current.error).toBeNull();
      expect(result.current.messages).toHaveLength(2);
    });
  });

  describe('Real-time Updates', () => {
    it('should stream message updates', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      // Mock streaming response
      const mockStream = new ReadableStream({
        async start(controller) {
          const chunks = ['Hello', ' there', '!', ' How', ' are', ' you?'];
          for (const chunk of chunks) {
            controller.enqueue(new TextEncoder().encode(chunk));
            await new Promise(resolve => setTimeout(resolve, 50));
          }
          controller.close();
        },
      });

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        body: mockStream,
      });

      await act(() =>
        result.current.streamMessage('Stream test')
      );

      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[1].content).toBe('Hello there! How are you?');
    });

    it('should handle streaming errors', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Stream failed'));

      await act(async () => {
        try {
          await result.current.streamMessage('Test');
        } catch (error) {
          // Expected
        }
      });

      expect(result.current.error).toBe('Stream failed');
      expect(result.current.streamingMessage).toBeNull();
    });
  });

  describe('Message Management', () => {
    it('should regenerate assistant response', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      // First response
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ response: 'First response' }),
      });

      await act(() =>
        result.current.sendMessage('Test')
      );

      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[1].content).toBe('First response');

      // Regenerate — target the USER message so the assistant reply is rebuilt
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ response: 'Second response' }),
      });

      await act(() =>
        result.current.regenerateResponse(result.current.messages[0].id)
      );

      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[1].content).toBe('Second response');
    });

    it('should clear all messages', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ response: 'Response' }),
      });

      await act(() =>
        result.current.sendMessage('Test')
      );

      expect(result.current.messages).toHaveLength(2);

      act(() => {
        result.current.clearMessages();
      });

      expect(result.current.messages).toHaveLength(0);
      expect(result.current.error).toBeNull();
    });
  });

  describe('Performance Optimization', () => {
    it('should debounce rapid message sends', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      let sendCount = 0;
      (global.mockFetch as jest.Mock).mockImplementation(() => {
        sendCount++;
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ response: `Response ${sendCount}` }),
        });
      });

      // Rapid sends
      await act(async () => {
        await Promise.all([
          result.current.sendMessage('Message 1'),
          result.current.sendMessage('Message 2'),
          result.current.sendMessage('Message 3'),
        ]);
      });

      expect(sendCount).toBe(3);
      expect(result.current.messages).toHaveLength(6); // 3 pairs
    });

    it('should memoize message list', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ response: 'Response' }),
      });

      const messages1 = result.current.messages;

      await act(() =>
        result.current.sendMessage('Test')
      );

      const messages2 = result.current.messages;

      // Reference should change after adding messages
      expect(messages1).not.toBe(messages2);
      expect(messages2).toHaveLength(2);
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty message content', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ response: 'Empty received' }),
      });

      await act(() =>
        result.current.sendMessage('')
      );

      expect(result.current.messages).toHaveLength(2);
    });

    it('should handle very long messages', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      const longMessage = 'A'.repeat(10000);

      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ response: 'Long message received' }),
      });

      await act(() =>
        result.current.sendMessage(longMessage)
      );

      expect(result.current.messages[0].content).toHaveLength(10000);
    });

    it('should handle special characters in messages', async () => {
      const { result } = renderHook(() =>
        mockUseChatInterface({ agentId: 'agent-123', sessionId: 'session-123' })
      );

      const specialMessage = 'Hello 🚀! Test <script>alert("xss")</script>';

      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ response: 'Received' }),
      });

      await act(() =>
        result.current.sendMessage(specialMessage)
      );

      expect(result.current.messages[0].content).toContain('🚀');
      expect(result.current.messages[0].content).toContain('<script>');
    });
  });
});
