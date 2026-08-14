/**
 * useChatInterface Hook — supplemental branch coverage.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatInterface } from '../useChatInterface';

let mockWsState: any = {
  isConnected: false,
  lastMessage: null,
  streamingContent: '',
  subscribe: jest.fn(),
};

const mockToastFn = jest.fn();

jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => mockWsState,
}));

jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({ toast: mockToastFn }),
}));

jest.mock('@/hooks/useFileUpload', () => ({
  useFileUpload: () => ({ uploadFile: jest.fn(), isUploading: false }),
}));

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

describe('useChatInterface (supplemental branches)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockToastFn.mockClear();
    mockWsState = {
      isConnected: false,
      lastMessage: null,
      streamingContent: '',
      subscribe: jest.fn(),
    };
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/api/chat/sessions/')) {
        return Promise.resolve({ status: 200, data: { title: 'T' } });
      }
      return Promise.resolve({ status: 200, data: {} });
    });
  });

  test('history parses object responses without suggested_actions', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/api/chat/history/')) {
        return Promise.resolve({
          status: 200,
          data: {
            messages: [
              { message: 'Hi', response: { message: 'Plain object reply' }, timestamp: '2024-01-01T00:00:00Z' },
            ],
          },
        });
      }
      return Promise.resolve({ status: 200, data: { title: 'T' } });
    });
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 's1', initialAgentId: null })
    );
    await waitFor(() => {
      expect(result.current.messages.some(m => m.content === 'Plain object reply')).toBe(true);
    });
    const assistant = result.current.messages.find(m => m.type === 'assistant' && m.content === 'Plain object reply');
    expect(assistant?.actions).toEqual([]);
  });

  test('history survives an existing optimistic user message (merge, not replace)', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/api/chat/history/')) {
        return Promise.resolve({
          status: 200,
          data: {
            messages: [
              { message: 'Old', response: 'Old reply', timestamp: '2024-01-01T00:00:00Z' },
            ],
          },
        });
      }
      return Promise.resolve({ status: 200, data: { title: 'T' } });
    });
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 's1', initialAgentId: null })
    );
    // Fire a message send before history resolves so the optimistic message exists.
    mockPost.mockResolvedValue({ status: 200, data: { message: 'ok', sessionId: 's1' } });
    await act(async () => {
      result.current.setInput('live message');
    });
    await act(async () => {
      await result.current.handleSend();
    });
    await waitFor(() => {
      expect(result.current.messages.some(m => m.content === 'live message')).toBe(true);
    });
    expect(result.current.messages.some(m => m.content === 'Old reply')).toBe(true);
  });

  test('rename failure toasts an error', async () => {
    mockPatch.mockResolvedValue({ status: 200, data: { success: false } });
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
      expect.objectContaining({ title: 'Error', description: 'Failed to rename session.' })
    );
  });

  test('feedback failure toasts an error when the API reports failure', async () => {
    mockPost.mockResolvedValue({ status: 201, data: { success: false, error: 'nope' } });
    const { result } = renderHook(() =>
      useChatInterface({ sessionId: 's1', initialAgentId: null })
    );
    await act(async () => {
      await result.current.handleFeedback('msg-123', 'thumbs_up', 'Great!');
    });
    expect(mockToastFn).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Error', description: 'Failed to submit feedback. Please try again.' })
    );
  });

  test('agent step update with an action sets the executing status', async () => {
    const { result, rerender } = renderHook(() =>
      useChatInterface({ sessionId: 's1', initialAgentId: null })
    );
    mockWsState = {
      ...mockWsState,
      lastMessage: {
        type: 'agent_step_update',
        step: { step: 2, action: { tool: 'search_tool' }, thought: 'looking' },
      },
    };
    rerender();
    expect(result.current.statusMessage).toBe('Executing search_tool...');
  });

  test('agent step update with only a thought sets the thinking status', async () => {
    const { result, rerender } = renderHook(() =>
      useChatInterface({ sessionId: 's1', initialAgentId: null })
    );
    mockWsState = {
      ...mockWsState,
      lastMessage: {
        type: 'agent_step_update',
        step: { step: 1, thought: 'pondering', action: undefined },
      },
    };
    rerender();
    expect(result.current.statusMessage).toBe('Thinking...');
  });

  test('agent step update without action or thought leaves the status untouched', async () => {
    const { result, rerender } = renderHook(() =>
      useChatInterface({ sessionId: 's1', initialAgentId: null })
    );
    const before = result.current.statusMessage;
    mockWsState = {
      ...mockWsState,
      lastMessage: { type: 'agent_step_update', step: { step: 1 } },
    };
    rerender();
    expect(result.current.statusMessage).toBe(before);
  });
});
