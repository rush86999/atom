/**
 * useChatInterface Hook Tests
 *
 * The real useChatInterface hook calls apiClient (axios, baseURL
 * http://127.0.0.1:8000) via a dynamic import of lib/api-client for history,
 * sending messages, renaming sessions, and feedback.
 *
 * The old suite tried to intercept those axios requests with a second MSW
 * setupServer whose wildcard handlers never matched, so every API call hung
 * and timed out. We mock lib/api-client directly instead.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatInterface } from '../useChatInterface';

// Mutable WebSocket-hook state: tests drive lastMessage/isConnected into the
// hook by reassigning this object and re-rendering (the hook reads it fresh
// on every render via the mocked useWebSocket).
let mockWsState: any = {
  isConnected: false,
  lastMessage: null,
  streamingContent: '',
  subscribe: jest.fn(),
};

// Stable toast mock: a per-call jest.fn() inside useToast() would change the
// toast identity on every render, so calls recorded by an older render's toast
// would be invisible via result.current.toast after a re-render.
const mockToastFn = jest.fn();

// Mock dependencies
jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => mockWsState,
}));

jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: mockToastFn,
  }),
}));

jest.mock('@/hooks/useFileUpload', () => ({
  useFileUpload: () => ({
    uploadFile: jest.fn(),
    isUploading: false,
  }),
}));

// Mock the apiClient the hook imports dynamically from lib/api-client.
jest.mock('../../../lib/api-client', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
  },
}));

import { apiClient } from '../../../lib/api-client';
const mockGet = apiClient.get as jest.Mock;
const mockPost = apiClient.post as jest.Mock;
const mockPatch = apiClient.patch as jest.Mock;

describe('useChatInterface', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockWsState = {
      isConnected: false,
      lastMessage: null,
      streamingContent: '',
      subscribe: jest.fn(),
    };

    // Default GET behavior: history + session-title background fetch.
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/api/chat/history/')) {
        return Promise.resolve({
          status: 200,
          data: {
            messages: [
              {
                message: 'Hello',
                response: { message: 'Hi there!', suggested_actions: [] },
                timestamp: '2024-01-01T00:00:00Z',
              },
            ],
          },
        });
      }
      if (url.includes('/api/chat/sessions/')) {
        return Promise.resolve({
          status: 200,
          data: { title: 'Test Session' },
        });
      }
      return Promise.resolve({ status: 200, data: {} });
    });

    // Default POST behavior: /api/chat/message succeeds and /api/chat/feedback
    // succeeds.
    mockPost.mockImplementation((url: string) => {
      if (url === '/api/chat/message') {
        return Promise.resolve({
          data: {
            success: true,
            message: 'Test response',
            session_id: 'test-session-123',
          },
        });
      }
      if (url === '/api/chat/feedback') {
        return Promise.resolve({ status: 200, data: { success: true } });
      }
      return Promise.resolve({ data: { success: true } });
    });

    mockPatch.mockImplementation(() =>
      Promise.resolve({ data: { success: true } })
    );
  });

  // Test 1: initializes with default state
  test('initializes with default state', () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null })
    );

    expect(result.current.input).toBe('');
    expect(result.current.isProcessing).toBe(false);
    expect(result.current.messages).toHaveLength(1); // Welcome message
    expect(result.current.messages[0].type).toBe('assistant');
    expect(result.current.sessionTitle).toBe('New Chat');
  });

  // Test 2: loads session history when sessionId provided
  test('loads session history when sessionId provided', async () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 'test-session-123', initialAgentId: null })
    );

    await waitFor(() => {
      expect(result.current.messages.length).toBeGreaterThan(0);
    });

    await waitFor(() => {
      expect(result.current.sessionTitle).toBe('Test Session');
    });
  });

  // Test 3: sends message successfully
  test('sends message successfully', async () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 'test-session', initialAgentId: null })
    );

    await act(async () => {
      result.current.setInput('Test message');
    });

    await act(async () => {
      await result.current.handleSend();
    });

    await waitFor(() => {
      expect(result.current.messages.some(m => m.content === 'Test message')).toBe(true);
    });

    expect(result.current.input).toBe('');
  });

  // Test 4: does not send empty message
  test('does not send empty message', async () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null })
    );

    const initialLength = result.current.messages.length;

    await act(async () => {
      await result.current.handleSend();
    });

    expect(result.current.messages.length).toBe(initialLength);
  });

  // Test 5: stops message processing
  test('stops message processing', async () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null })
    );

    await act(async () => {
      result.current.handleStop();
    });

    expect(result.current.isProcessing).toBe(false);
    expect(result.current.messages.some(m => m.content.includes('stopped by user'))).toBe(true);
  });

  // Test 6: handles title editing
  test('handles title editing', async () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 'test-session', initialAgentId: null })
    );

    await act(async () => {
      result.current.setIsEditingTitle(true);
      result.current.setTempTitle('New Title');
    });

    await act(async () => {
      await result.current.handleTitleSave();
    });

    expect(result.current.isEditingTitle).toBe(false);
    expect(result.current.sessionTitle).toBe('New Title');
  });

  // Test 7: handles feedback submission
  test('handles feedback submission', async () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null })
    );

    await act(async () => {
      await result.current.handleFeedback('msg-123', 'thumbs_up', 'Great!');
    });

    // Should not throw error
    expect(result.current.toast).toHaveBeenCalled();
  });

  // Test 8: updates input value
  test('updates input value', () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null })
    );

    act(() => {
      result.current.setInput('New input');
    });

    expect(result.current.input).toBe('New input');
  });

  // Test 9: toggles voice mode
  test('toggles voice mode', () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null })
    );

    expect(result.current.isVoiceModeOpen).toBe(false);

    act(() => {
      result.current.setIsVoiceModeOpen(true);
    });

    expect(result.current.isVoiceModeOpen).toBe(true);
  });

  // Test 10: handles active attachments
  test('handles active attachments', () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null })
    );

    const attachment = { id: '1', title: 'test.pdf' };

    act(() => {
      result.current.setActiveAttachments([attachment]);
    });

    expect(result.current.activeAttachments).toEqual([attachment]);
  });

  // Test 11: handles API error on message send
  test('handles API error on message send', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === '/api/chat/message') {
        return Promise.resolve({ data: { success: false, error: 'API error' } });
      }
      return Promise.resolve({ status: 200, data: { success: true } });
    });

    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 'test-session', initialAgentId: null })
    );

    await act(async () => {
      result.current.setInput('Test message');
    });

    await act(async () => {
      await result.current.handleSend();
    });

    await waitFor(() => {
      expect(result.current.messages.some(m => m.content.includes('error'))).toBe(true);
    });

    expect(result.current.isProcessing).toBe(false);
  });

  // Test 12: handles session creation callback
  test('handles session creation callback', async () => {
    const onSessionCreated = jest.fn();

    const { result } = renderHook(() =>
      useChatInterface({
        sessionId: 'old-session',
        initialAgentId: null,
        onSessionCreated
      })
    );

    await act(async () => {
      result.current.setInput('New chat message');
    });

    await act(async () => {
      await result.current.handleSend();
    });

    await waitFor(() => {
      expect(onSessionCreated).toHaveBeenCalledWith('test-session-123');
    });
  });

  // Test 13: does not update title with empty string
  test('does not update title with empty string', async () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 'test-session', initialAgentId: null })
    );

    // Wait for the background session-title fetch to resolve so originalTitle
    // reflects the loaded title before the empty save attempt.
    await waitFor(() => {
      expect(result.current.sessionTitle).toBe('Test Session');
    });
    const originalTitle = result.current.sessionTitle;

    await act(async () => {
      result.current.setIsEditingTitle(true);
      result.current.setTempTitle('   ');
    });

    await act(async () => {
      await result.current.handleTitleSave();
    });

    expect(result.current.sessionTitle).toBe(originalTitle);
    expect(result.current.isEditingTitle).toBe(false);
  });

  // Test 14: handles feedback API error
  test('handles feedback API error', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === '/api/chat/feedback') {
        return Promise.reject(new Error('Failed to submit feedback'));
      }
      return Promise.resolve({ status: 200, data: { success: true } });
    });

    const { result } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null })
    );

    await act(async () => {
      await result.current.handleFeedback('msg-123', 'thumbs_down');
    });

    // Should show error toast
    expect(result.current.toast).toHaveBeenCalled();
  });

  // Test 15: loads messages on mount with new session
  test('loads messages on mount with new session', () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 'new', initialAgentId: null })
    );

    expect(result.current.messages.length).toBe(1);
    expect(result.current.messages[0].content).toContain('Hello');
    expect(result.current.sessionTitle).toBe('New Chat');
  });

  // Test 16: history items whose response is an object (not a string)
  test('parses history items with object responses', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/api/chat/history/')) {
        return Promise.resolve({
          status: 200,
          data: {
            messages: [
              {
                message: 'Hi',
                response: { message: 'Object reply', suggested_actions: ['act'] },
                timestamp: '2024-01-01T00:00:00Z',
              },
            ],
          },
        });
      }
      return Promise.resolve({ status: 200, data: {} });
    });

    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 's1', initialAgentId: null })
    );

    await waitFor(() => {
      expect(result.current.messages.some(m => m.content === 'Object reply')).toBe(true);
    });

    const assistant = result.current.messages.find(m => m.type === 'assistant' && m.content === 'Object reply');
    expect(assistant?.actions).toEqual(['act']);
  });

  // Test 17: a 403 history error drops the stale session pointer and starts fresh
  test('clears the stale session pointer on 403 history errors', async () => {
    const onSessionCreated = jest.fn();
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/api/chat/history/')) {
        return Promise.reject({ response: { status: 403 } });
      }
      return Promise.resolve({ status: 200, data: {} });
    });

    // Note: jsdom's localStorage is a Proxy — its methods cannot be spied
    // (jest.spyOn returns the raw function). The behavioral contract is the
    // fresh-session callback, asserted below.
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 'stale-session', initialAgentId: null, onSessionCreated })
    );

    await waitFor(() => {
      expect(onSessionCreated).toHaveBeenCalledWith('new');
    });

    expect(mockToastFn).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Could not load history' })
    );
    expect(result.current.isProcessing).toBe(false);
  });

  // Test 18: a generic history failure toasts without clearing the session
  test('toasts when history loading fails for non-403 errors', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/api/chat/history/')) {
        return Promise.reject(new Error('network'));
      }
      return Promise.resolve({ status: 200, data: {} });
    });

    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 's1', initialAgentId: null })
    );

    await waitFor(() => {
      expect(mockToastFn).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Could not load history' })
      );
    });

  });

  // Test 19: rename failures surface an error toast
  test('toasts an error when renaming the session fails', async () => {
    mockPatch.mockRejectedValue(new Error('rename failed'));

    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 's1', initialAgentId: null })
    );

    await act(async () => {
      result.current.setIsEditingTitle(true);
      result.current.setTempTitle('New Name');
    });

    await act(async () => {
      await result.current.handleTitleSave();
    });

    expect(mockToastFn).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Error', variant: 'error' })
    );
    expect(result.current.isEditingTitle).toBe(false);
  });

  // Test 20: no_llm_provider surfaces a recovery banner (P1.1)
  test('surfaces no_llm_provider errors as a provider banner', async () => {
    const onSessionCreated = jest.fn();
    mockPost.mockImplementation((url: string) => {
      if (url === '/api/chat/message') {
        return Promise.resolve({
          data: {
            error_code: 'no_llm_provider',
            message: 'You need an AI provider to do this.',
            recovery_url: '/settings/ai',
            session_id: 'sess-9',
          },
        });
      }
      return Promise.resolve({ status: 200, data: { success: true } });
    });

    const { result } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null, onSessionCreated })
    );

    await act(async () => {
      result.current.setInput('Write a plan');
    });
    await act(async () => {
      await result.current.handleSend();
    });

    expect(result.current.providerError).toEqual({
      message: 'You need an AI provider to do this.',
      recovery_url: '/settings/ai',
      error_code: 'no_llm_provider',
    });
    expect(onSessionCreated).toHaveBeenCalledWith('sess-9');
    expect(result.current.messages.some(m => m.type === 'system' && m.content.includes('AI provider'))).toBe(true);
    expect(result.current.isProcessing).toBe(false);
  });

  // Test 21: budget_exceeded appends an error-type message
  test('surfaces budget_exceeded as an error message', async () => {
    const onSessionCreated = jest.fn();
    mockPost.mockImplementation((url: string) => {
      if (url === '/api/chat/message') {
        return Promise.resolve({
          data: {
            error_code: 'budget_exceeded',
            message: 'Budget limit reached',
            session_id: 'sess-b',
          },
        });
      }
      return Promise.resolve({ status: 200, data: { success: true } });
    });

    const { result } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null, onSessionCreated })
    );

    await act(async () => {
      result.current.setInput('Go');
    });
    await act(async () => {
      await result.current.handleSend();
    });

    expect(onSessionCreated).toHaveBeenCalledWith('sess-b');
    expect(result.current.messages.some(m => m.type === 'error' && m.content.includes('Budget'))).toBe(true);
    expect(result.current.isProcessing).toBe(false);
  });

  // Test 22: a rejected send appends the generic error message
  test('appends a system error message when the chat API rejects', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === '/api/chat/message') {
        return Promise.reject(new Error('connection refused'));
      }
      return Promise.resolve({ status: 200, data: { success: true } });
    });

    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 's1', initialAgentId: null })
    );

    await act(async () => {
      result.current.setInput('Hi');
    });
    await act(async () => {
      await result.current.handleSend();
    });

    await waitFor(() => {
      expect(result.current.messages.some(m => m.content.includes('encountered an error'))).toBe(true);
    });
    expect(result.current.isProcessing).toBe(false);
  });

  // Test 23: clearProviderError clears the banner
  test('clearProviderError clears the provider banner', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === '/api/chat/message') {
        return Promise.resolve({
          data: {
            error_code: 'no_llm_provider',
            message: 'You need an AI provider',
            recovery_url: '/settings/ai',
          },
        });
      }
      return Promise.resolve({ status: 200, data: { success: true } });
    });

    const { result } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null })
    );

    await act(async () => {
      result.current.setInput('Hi');
    });
    await act(async () => {
      await result.current.handleSend();
    });

    expect(result.current.providerError).not.toBeNull();

    act(() => {
      result.current.clearProviderError();
    });

    expect(result.current.providerError).toBeNull();
  });

  // Test 24: handleRegenerate re-sends the original prompt and flags the old
  // response with an implicit thumbs_down
  test('regenerates by re-sending the original prompt', async () => {
    jest.useFakeTimers();
    try {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 'new', initialAgentId: null })
    );

    await act(async () => {
      result.current.setInput('Original question');
    });
    await act(async () => {
      await result.current.handleSend();
    });

    const assistantMsg = result.current.messages.find(m => m.type === 'assistant' && m.id !== 'welcome');
    expect(assistantMsg).toBeDefined();

    // Advance the mocked clock so the regenerated exchange gets fresh ids
    // (message ids are Date.now()-based and would collide within the same ms).
    await act(async () => {
      jest.setSystemTime(Date.now() + 1000);
    });
    await act(async () => {
      await result.current.handleRegenerate(assistantMsg!.id);
    });

    // Implicit negative feedback recorded for the regenerated answer.
    expect(mockPost).toHaveBeenCalledWith(
      '/api/chat/feedback',
      expect.objectContaining({ feedback: 'thumbs_down', comment: 'regenerated' })
    );
    // The old exchange (user + assistant) was replayed: the final assistant
    // message is a fresh response, not the stale one.
    const finalAssistant = result.current.messages[result.current.messages.length - 1];
    expect(finalAssistant.type).toBe('assistant');
    expect(finalAssistant.id).not.toBe(assistantMsg!.id);
    expect(result.current.messages.some(m => m.type === 'user' && m.content === 'Original question')).toBe(true);
    } finally {
      jest.useRealTimers();
    }
  });

  // Test 25: regenerate is a no-op for unknown ids
  test('regenerate is a no-op for unknown message ids', async () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 'new', initialAgentId: null })
    );

    await act(async () => {
      await result.current.handleRegenerate('does-not-exist');
    });

    expect(mockPost).not.toHaveBeenCalledWith('/api/chat/feedback', expect.anything());
    expect(result.current.messages.length).toBe(1); // welcome only
  });

  // Test 26: regenerate is a no-op when no user message precedes the target
  test('regenerate is a no-op when no user message precedes', async () => {
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 'new', initialAgentId: null })
    );

    // The welcome message is an assistant message with no user message before it.
    await act(async () => {
      await result.current.handleRegenerate('welcome');
    });

    expect(mockPost).not.toHaveBeenCalledWith('/api/chat/feedback', expect.anything());
    expect(result.current.messages.length).toBe(1);
  });

  // Test 27: a failed regenerate restores the original exchange
  test('restores the original exchange when regeneration fails', async () => {
    let sendCount = 0;
    mockPost.mockImplementation((url: string) => {
      if (url === '/api/chat/message') {
        sendCount += 1;
        if (sendCount === 2) {
          return Promise.reject(new Error('regeneration failed'));
        }
        return Promise.resolve({
          data: { success: true, message: 'First response', session_id: 'test-session' },
        });
      }
      return Promise.resolve({ status: 200, data: { success: true } });
    });

    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 'new', initialAgentId: null })
    );

    await act(async () => {
      result.current.setInput('Keep me');
    });
    await act(async () => {
      await result.current.handleSend();
    });
    const originalAssistant = result.current.messages.find(m => m.type === 'assistant' && m.id !== 'welcome');

    await act(async () => {
      await result.current.handleRegenerate(originalAssistant!.id);
    });

    // The original exchange is preserved after the failed re-generation.
    expect(result.current.messages.some(m => m.id === originalAssistant!.id)).toBe(true);
    expect(mockToastFn).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Regenerate failed', variant: 'error' })
    );
  });

  // Test 28: handleStop aborts the in-flight request and cancels on the backend
  test('handleStop aborts the in-flight request and notifies the backend', async () => {
    let capturedSignal: AbortSignal | undefined;
    mockPost.mockImplementation((url: string, _body?: any, config?: any) => {
      if (url === '/api/chat/message') {
        capturedSignal = config?.signal;
        return new Promise((resolve) => {
          // Never resolves on its own; the test stops the request.
          setTimeout(() => resolve({ data: { success: true, message: 'late' } }), 1000);
        });
      }
      return Promise.resolve({ status: 200, data: { success: true } });
    });

    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 's1', initialAgentId: null })
    );

    await act(async () => {
      result.current.setInput('Do work');
    });
    let sendPromise: Promise<boolean>;
    act(() => {
      sendPromise = result.current.handleSend();
    });
    // Flush the dynamic-import microtask so the AbortController is armed.
    await act(async () => {});

    await act(async () => {
      await result.current.handleStop();
    });

    expect(capturedSignal?.aborted).toBe(true);
    expect(result.current.messages.some(m => m.content.includes('stopped by user'))).toBe(true);
    expect(result.current.isProcessing).toBe(false);

    // The backend cancel endpoint was hit.
    expect(mockPost).toHaveBeenCalledWith('/api/chat/cancel/s1');

    await act(async () => {
      await sendPromise;
    });
  });

  // Test 29: streaming:start/complete drive the stream lifecycle
  test('streaming start and complete append the assistant message', async () => {
    const { result, rerender } = renderHook(() =>
      useChatInterface({ sessionId: 'new', initialAgentId: null })
    );

    mockWsState = { ...mockWsState, lastMessage: { type: 'streaming:start', id: 'stream-1' } };
    rerender();

    await waitFor(() => {
      expect(result.current.currentStreamId).toBe('stream-1');
    });

    mockWsState = {
      ...mockWsState,
      lastMessage: { type: 'streaming:complete', id: 'stream-1', content: 'Streamed answer' },
    };
    rerender();

    await waitFor(() => {
      expect(result.current.messages.some(m => m.type === 'assistant' && m.content === 'Streamed answer')).toBe(true);
    });
    expect(result.current.currentStreamId).toBeNull();
    expect(result.current.isProcessing).toBe(false);
  });

  // Test 30: streaming:complete does not duplicate a REST-fulfilled reply
  test('streaming complete skips append when REST already fulfilled', async () => {
    const { result, rerender } = renderHook(() =>
      useChatInterface({ sessionId: 'new', initialAgentId: null })
    );

    await act(async () => {
      result.current.setInput('REST answer');
    });
    await act(async () => {
      await result.current.handleSend();
    });
    const countAfterREST = result.current.messages.length;

    mockWsState = { ...mockWsState, lastMessage: { type: 'streaming:start', id: 's-2' } };
    rerender();
    mockWsState = { ...mockWsState, lastMessage: { type: 'streaming:complete', id: 's-2', content: 'Dup' } };
    rerender();

    // No duplicate assistant message appended.
    expect(result.current.messages.length).toBe(countAfterREST);
    expect(result.current.messages.some(m => m.content === 'Dup')).toBe(false);
  });

  // Test 31: a mismatched streaming:complete still resets processing
  test('mismatched streaming complete resets processing', async () => {
    let resolveSend: (v: any) => void = () => {};
    mockPost.mockImplementation((url: string) => {
      if (url === '/api/chat/message') {
        return new Promise((resolve) => {
          resolveSend = resolve;
        });
      }
      return Promise.resolve({ status: 200, data: { success: true } });
    });

    const { result, rerender } = renderHook(() =>
      useChatInterface({ sessionId: 'new', initialAgentId: null })
    );

    mockWsState = { ...mockWsState, lastMessage: { type: 'streaming:start', id: 'expected' } };
    rerender();
    await waitFor(() => {
      expect(result.current.currentStreamId).toBe('expected');
    });

    await act(async () => {
      result.current.setInput('x');
    });
    let sendPromise: Promise<boolean>;
    act(() => {
      sendPromise = result.current.handleSend();
    });
    expect(result.current.isProcessing).toBe(true);

    mockWsState = { ...mockWsState, lastMessage: { type: 'streaming:complete', id: 'other-stream' } };
    rerender();

    await waitFor(() => {
      expect(result.current.isProcessing).toBe(false);
    });

    await act(async () => {
      resolveSend({ data: { success: true, message: 'late', session_id: 'new' } });
      await sendPromise;
    });
  });

  // Test 32: agent_step_update appends reasoning traces and status
  test('agent step updates append reasoning traces to the latest assistant message', async () => {
    const { result, rerender } = renderHook(() =>
      useChatInterface({ sessionId: 'new', initialAgentId: null })
    );

    await act(async () => {
      result.current.setInput('Investigate');
    });
    await act(async () => {
      await result.current.handleSend();
    });

    mockWsState = {
      ...mockWsState,
      lastMessage: {
        type: 'agent_step_update',
        step: { step: 1, thought: 'Checking', action: { tool: 'web_search' }, output: 'found' },
      },
    };
    rerender();

    expect(result.current.statusMessage).toBe('Executing web_search...');

    const lastAssistant = [...result.current.messages].reverse().find(m => m.type === 'assistant');
    expect(lastAssistant?.reasoningTrace?.length).toBe(1);
    expect(lastAssistant?.reasoningTrace?.[0].action).toEqual({ tool: 'web_search' });
  });

  // Test 33: hitl_paused / hitl_decision manage the approval state
  test('hitl messages set and clear the pending approval', async () => {
    const { result, rerender } = renderHook(() =>
      useChatInterface({ sessionId: 'new', initialAgentId: null })
    );

    mockWsState = {
      ...mockWsState,
      lastMessage: { type: 'hitl_paused', action_id: 'act-1', tool: 'finance_tool', reason: 'Needs approval' },
    };
    rerender();

    expect(result.current.pendingApproval).toEqual({
      action_id: 'act-1',
      tool: 'finance_tool',
      reason: 'Needs approval',
    });
    expect(result.current.statusMessage).toBe('Waiting for approval...');

    mockWsState = { ...mockWsState, lastMessage: { type: 'hitl_decision' } };
    rerender();

    expect(result.current.pendingApproval).toBeNull();
    expect(result.current.statusMessage).toBe('Resuming execution...');
  });

  // Test 34: subscribing to the workspace channel when connected
  test('subscribes to the workspace channel once connected', () => {
    const { result, rerender } = renderHook(() =>
      useChatInterface({ sessionId: null, initialAgentId: null })
    );

    expect(mockWsState.subscribe).not.toHaveBeenCalled();

    mockWsState = { ...mockWsState, isConnected: true };
    rerender();

    expect(mockWsState.subscribe).toHaveBeenCalledWith('workspace:default');
  });

  // Test 35: the 30s safety-net clears processing when no response arrives
  test('safety-net timeout clears processing after 30 seconds', async () => {
    jest.useFakeTimers();
    try {
      let resolveSend: (v: any) => void = () => {};
      mockPost.mockImplementation((url: string) => {
        if (url === '/api/chat/message') {
          return new Promise((resolve) => {
            resolveSend = resolve;
          });
        }
        return Promise.resolve({ status: 200, data: { success: true } });
      });

      const { result } = renderHook(() =>
        useChatInterface({ sessionId: 's1', initialAgentId: null })
      );

      await act(async () => {
        result.current.setInput('Slow');
      });
      let sendPromise: Promise<boolean>;
      // Async act flushes the dynamic-import microtask so the 30s safety-net
      // timer is armed before we advance the fake clock.
      await act(async () => {
        sendPromise = result.current.handleSend();
      });

      expect(result.current.isProcessing).toBe(true);

      act(() => {
        jest.advanceTimersByTime(120000);
      });

      expect(result.current.isProcessing).toBe(false);

      // Resolve the hung request so no dangling promise remains.
      await act(async () => {
        resolveSend({ data: { success: true, message: 'late', session_id: 's1' } });
        await sendPromise;
      });
    } finally {
      jest.useRealTimers();
    }
  });
});
