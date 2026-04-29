/**
 * useChatInterface Hook Tests
 *
 * Tests verify chat interface state management, message sending,
 * session history loading, feedback handling, and WebSocket integration.
 *
 * Source: hooks/chat/useChatInterface.ts (133 lines uncovered)
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatInterface } from '../useChatInterface';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

// Mock dependencies
jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => ({
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

// Setup MSW server
// Note: MSW handlers match both relative and absolute URLs automatically
// The fetch wrapper in setup.ts converts relative URLs to absolute (localhost:8000)
// We need to handle multiple URL patterns due to fetch inconsistencies
const server = setupServer(
  rest.post('*/api/chat/message', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        message: 'Test response',
        session_id: 'test-session-123',
      })
    );
  }),

  rest.get('*/api/chat/history/:sessionId', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        messages: [
          {
            message: 'Hello',
            response: { message: 'Hi there!', suggested_actions: [] },
            timestamp: '2024-01-01T00:00:00Z',
          },
        ],
      })
    );
  }),

  rest.get('*/api/chat/sessions/:sessionId', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ title: 'Test Session' })
    );
  }),

  rest.patch('*/api/chat/sessions/:sessionId', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true })
    );
  }),

  rest.post('*/api/atom-agent/feedback', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true })
    );
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('useChatInterface', () => {
  beforeEach(() => {
    jest.clearAllMocks();
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
    server.use(
      rest.post('/api/chat/message', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

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
    server.use(
      rest.post('/api/atom-agent/feedback', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

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
