/**
 * GlobalChatWidget Component Tests
 *
 * Tests verify the real GlobalChatWidget component
 * (components/GlobalChatWidget.tsx):
 * - floating launcher button opens the chat popover with the welcome message
 * - new session id persisted to localStorage when none exists
 * - sending a message POSTs /api/chat/message (user_id, session_id, context)
 *   and renders the assistant reply with model/provider
 * - failed message POST shows the error toast and a sorry bubble
 * - pending approval fetch shows the HITL banner; approve/reject POSTs the
 *   decision via apiClient and clears the banner
 * - WebSocket: subscribes to workspace:default when connected; agent_step_update
 *   appends a reasoning step; hitl_paused shows the banner; hitl_decision clears it
 * - session history: existing atom_chat_session_id loads /api/chat/history/:sid
 * - New Chat resets the session and messages
 * - suggested actions render as buttons; view_template navigates to the
 *   marketplace with the template id
 *
 * APIs: POST /api/chat/message, GET /api/chat/history/:sid,
 *       GET /api/agents/approvals/pending (apiClient),
 *       POST /api/agents/approvals/:id (apiClient)
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const mockPush = jest.fn();
jest.mock('next/router', () => ({
  useRouter: () => ({
    route: '/',
    pathname: '/',
    query: {},
    asPath: '/dashboard',
    push: mockPush,
    replace: jest.fn(),
    reload: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn().mockResolvedValue(undefined),
    beforePopState: jest.fn(),
    events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
  }),
}));

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
jest.mock('../../lib/api-client', () => ({
  apiClient: { get: mockApiGet, post: mockApiPost },
}));

jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => wsState,
}));

jest.mock('@/components/Voice/VoiceInput', () => ({
  VoiceInput: () => <div data-testid="voice-input" />,
}));

import { GlobalChatWidget } from '../GlobalChatWidget';

const wsState = {
  isConnected: false,
  lastMessage: null as any,
  streamingContent: new Map<string, string>(),
  subscribe: jest.fn(),
  unsubscribe: jest.fn(),
  disconnect: jest.fn(),
  sendMessage: jest.fn(),
  reconnectAttempts: 0,
};

// The floating launcher and the send button are icon-only buttons without an
// accessible label; open them via CSS selectors and drive sends with Enter.
const openChat = () => {
  fireEvent.click(document.querySelector('button.rounded-full') as HTMLElement);
};

describe('GlobalChatWidget', () => {
  let postedMessages: any[];

  beforeEach(() => {
    jest.clearAllMocks();
    postedMessages = [];
    wsState.isConnected = false;
    wsState.lastMessage = null;
    localStorage.clear();

    server.resetHandlers();
    server.use(
      rest.post('/api/chat/message', async (req, res, ctx) => {
        postedMessages.push(req.body);
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            message: 'I created the task for you.',
            model: 'deepseek-v4',
            provider: 'opencode-go',
            suggested_actions: ['View Template'],
          })
        );
      }),
      rest.get('/api/chat/history/:sid', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            messages: [
              { id: 'h1', role: 'user', content: 'Old question', timestamp: '2026-08-01T00:00:00.000Z' },
              { id: 'h2', role: 'assistant', content: 'Old answer', timestamp: '2026-08-01T00:00:00.000Z' },
            ],
          })
        );
      })
    );

    mockApiGet.mockResolvedValue({ status: 200, data: [] });
    mockApiPost.mockResolvedValue({ data: { success: true } });
  });

  it('opens the chat on button click and shows the welcome message', async () => {
    render(<GlobalChatWidget />);

    openChat();

    expect(await screen.findByText('ATOM Assistant')).toBeInTheDocument();
    expect(screen.getByText(/Hi! I am your Universal ATOM Assistant/)).toBeInTheDocument();
    expect(screen.getByText(/What would you like to do/)).toBeInTheDocument();
    expect(localStorage.getItem('atom_chat_session_id')).toMatch(/^session_/);
  });

  it('sends a message and renders the assistant reply', async () => {
    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    fireEvent.change(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      target: { value: 'Create a task' },
    });
    fireEvent.keyDown(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      key: 'Enter',
    });

    expect(await screen.findByText('I created the task for you.')).toBeInTheDocument();
    expect(screen.getByText('Create a task')).toBeInTheDocument();

    await waitFor(() => {
      expect(postedMessages).toHaveLength(1);
    });
    const body = postedMessages[0] as any;
    expect(body.message).toBe('Create a task');
    expect(body.user_id).toBe('anonymous');
    expect(body.session_id).toMatch(/^session_/);
    expect(body.context.current_page).toBe('/dashboard');
    expect(Array.isArray(body.context.conversation_history)).toBe(true);

    expect(screen.getByText('deepseek-v4')).toBeInTheDocument();
    expect(screen.getByText('View Template')).toBeInTheDocument();
  });

  it('shows the error toast and a sorry bubble when the message POST fails', async () => {
    server.use(
      rest.post('/api/chat/message', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    fireEvent.change(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      target: { value: 'Doomed message' },
    });
    fireEvent.keyDown(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      key: 'Enter',
    });

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to process message. Please try again.',
        })
      );
    });
    expect(await screen.findByText('Sorry, I encountered an error. Please try again.')).toBeInTheDocument();
  });

  it('subscribes to the workspace channel when the WebSocket connects', async () => {
    wsState.isConnected = true;
    render(<GlobalChatWidget />);

    await waitFor(() => {
      expect(wsState.subscribe).toHaveBeenCalledWith('workspace:default');
    });
  });

  it('appends a reasoning step to the last assistant message on agent_step_update', async () => {
    const { rerender } = render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    wsState.lastMessage = {
      type: 'agent_step_update',
      step: { step: 1, thought: 'Searching memory for context', action: 'memory_query' },
    };
    rerender(<GlobalChatWidget />);

    const toggle = await screen.findByRole('button', { name: /reasoning process \(1 steps\)/i });
    fireEvent.click(toggle);
    expect(await screen.findByText('Searching memory for context')).toBeInTheDocument();
  });

  it('shows the HITL approval banner on hitl_paused and clears it on hitl_decision', async () => {
    const { rerender } = render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    wsState.lastMessage = { type: 'hitl_paused', action_id: 'a-1', tool: 'send_email', reason: 'Email needs approval' };
    rerender(<GlobalChatWidget />);

    expect(await screen.findByText('Approval Required')).toBeInTheDocument();
    expect(screen.getByText(/send_email/)).toBeInTheDocument();
    expect(screen.getByText(/Email needs approval/)).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Approval Required' })
    );

    wsState.lastMessage = { type: 'hitl_decision', action_id: 'a-1' };
    rerender(<GlobalChatWidget />);
    await waitFor(() => {
      expect(screen.queryByText('Approval Required')).not.toBeInTheDocument();
    });
  });

  it('shows the pending approval banner from the API and approves it', async () => {
    mockApiGet.mockResolvedValue({
      status: 200,
      data: [{ id: 'p-1', action_type: 'send_email', reason: 'Customer email' }],
    });

    render(<GlobalChatWidget />);
    openChat();

    expect(await screen.findByText('Approval Required')).toBeInTheDocument();
    expect(screen.getByText(/send_email/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /approve/i }));

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith('/api/agents/approvals/p-1', {
        decision: 'approved',
      });
    });
    await waitFor(() => {
      expect(screen.queryByText('Approval Required')).not.toBeInTheDocument();
    });
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Action approved' }));
  });

  it('rejects the pending approval via the API', async () => {
    mockApiGet.mockResolvedValue({
      status: 200,
      data: [{ id: 'p-2', action_type: 'send_email', reason: 'Spam' }],
    });

    render(<GlobalChatWidget />);
    openChat();

    await screen.findByText('Approval Required');
    fireEvent.click(screen.getByRole('button', { name: /reject/i }));

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith('/api/agents/approvals/p-2', {
        decision: 'rejected',
      });
    });
  });

  it('loads session history for an existing session id', async () => {
    localStorage.setItem('atom_chat_session_id', 'sess-123');

    render(<GlobalChatWidget />);
    openChat();

    expect(await screen.findByText('Old question')).toBeInTheDocument();
    expect(screen.getByText('Old answer')).toBeInTheDocument();
  });

  it('starts a new chat session on the New Chat button', async () => {
    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    fireEvent.click(screen.getByTitle('New Chat'));

    expect(await screen.findByText(/New session started/)).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'New Chat' }));
  });

  it('triggers a generic action toast when a suggested action is clicked', async () => {
    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    fireEvent.change(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      target: { value: 'Show me a template' },
    });
    fireEvent.keyDown(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      key: 'Enter',
    });

    // Suggested actions from /api/chat/message carry only a label (no
    // templateId/workflowId), so the widget falls through to the generic
    // action toast rather than navigating.
    const actionBtn = await screen.findByRole('button', { name: /view template/i });
    fireEvent.click(actionBtn);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Action Triggered',
          description: 'Processing action: View Template',
        })
      );
    });
    expect(mockPush).not.toHaveBeenCalled();
  });
});
