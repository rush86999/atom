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

// Mock dependencies
jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: (): any => ({
    isConnected: false,
    lastMessage: null,
    streamingContent: '',
    subscribe: jest.fn(),
  }),
}));

jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
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
});
