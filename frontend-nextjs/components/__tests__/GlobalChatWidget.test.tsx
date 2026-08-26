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
 *       GET /api/agents/approvals/pending (same-origin fetch via proxy),
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

const mockApiPost = jest.fn();
jest.mock('../../lib/api-client', () => ({
  apiClient: { post: mockApiPost },
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
      }),
      rest.get('/api/agents/approvals/pending', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json([]));
      })
    );

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
    server.use(
      rest.get('/api/agents/approvals/pending', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([{ id: 'p-1', action_type: 'send_email', reason: 'Customer email' }])
        );
      })
    );

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
    server.use(
      rest.get('/api/agents/approvals/pending', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([{ id: 'p-2', action_type: 'send_email', reason: 'Spam' }])
        );
      })
    );

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

  it('drops a 403 stale session id and switches to a fresh session', async () => {
    // History for the persisted id is rejected (owned by another account).
    server.use(
      rest.get('/api/chat/history/:sid', (req, res, ctx) =>
        res(ctx.status(403), ctx.json({ detail: 'Access denied' }))
      )
    );
    localStorage.setItem('atom_chat_session_id', 'stale-sess-403');

    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText(/Hi! I am your Universal ATOM Assistant/);

    // The stale id must be gone from storage AND from component state: the
    // next send must carry a fresh session id, not the rejected one.
    await waitFor(() => {
      const stored = localStorage.getItem('atom_chat_session_id');
      expect(stored).toBeTruthy();
      expect(stored).toMatch(/^session_/);
      expect(stored).not.toBe('stale-sess-403');
    });

    fireEvent.change(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      target: { value: 'Hi again' },
    });
    fireEvent.keyDown(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      key: 'Enter',
    });

    await waitFor(() => {
      expect(postedMessages).toHaveLength(1);
    });
    const body = postedMessages[0] as any;
    expect(body.session_id).toMatch(/^session_/);
    expect(body.session_id).not.toBe('stale-sess-403');
    expect(body.session_id).toBe(localStorage.getItem('atom_chat_session_id'));
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

// ---------------------------------------------------------------------------
// Extended coverage: feedback, regenerate, close, network failures
// ---------------------------------------------------------------------------
describe('GlobalChatWidget (extended coverage)', () => {
  let errorSpy: jest.SpyInstance;
  let postedMessages: any[];

  const sendChatMessage = async (text: string) => {
    fireEvent.change(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      target: { value: text },
    });
    fireEvent.keyDown(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      key: 'Enter',
    });
    await screen.findByText('I created the task for you.');
  };

  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
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
            suggested_actions: [],
          })
        );
      }
      ),
      rest.get('/api/chat/history/:sid', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ messages: [] }));
      }),
      rest.get('/api/agents/approvals/pending', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json([]));
      })
    );

    mockApiPost.mockResolvedValue({ data: { success: true } });
  });

  afterEach(() => {
    errorSpy.mockRestore();
  });

  it('submits thumbs up feedback with model identity', async () => {
    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    await sendChatMessage('Rate this');

    // The welcome message also renders feedback controls; target the reply (last).
    fireEvent.click(screen.getAllByRole('button', { name: 'Thumbs up' }).pop()!);

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        '/api/chat/feedback',
        expect.objectContaining({
          feedback: 'thumbs_up',
          model: 'deepseek-v4',
          provider: 'opencode-go',
        })
      );
    });
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Helpful' })
      );
    });
  });

  it('submits thumbs down feedback and a correction comment', async () => {
    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    await sendChatMessage('Rate badly');

    fireEvent.click(screen.getAllByRole('button', { name: 'Thumbs down' }).pop()!);
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Flagged' })
      );
    });

    // open the comment box and submit a correction
    fireEvent.click(screen.getAllByRole('button', { name: 'Add comment' }).pop()!);
    const commentBox = await screen.findByPlaceholderText(
      /What was wrong or how can I improve/i
    );
    fireEvent.change(commentBox, { target: { value: 'Wrong answer' } });
    fireEvent.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        '/api/chat/feedback',
        expect.objectContaining({ feedback: 'thumbs_down', comment: 'Wrong answer' })
      );
    });
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Correction Received' })
      );
    });
  });

  it('logs feedback failures without a toast', async () => {
    mockApiPost.mockRejectedValueOnce(new Error('feedback down'));

    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');
    await sendChatMessage('Feedback will fail');

    fireEvent.click(screen.getAllByRole('button', { name: 'Thumbs up' }).pop()!);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Feedback failed', expect.anything());
    });
    expect(
      mockToast.mock.calls.some((c: any[]) => c[0]?.title === 'Helpful')
    ).toBe(false);
  });

  it('regenerates the previous exchange and records a negative signal', async () => {
    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    await sendChatMessage('Regenerate me');

    fireEvent.click(
      screen.getAllByRole('button', { name: 'Regenerate response' }).pop()!
    );

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        '/api/chat/feedback',
        expect.objectContaining({ feedback: 'thumbs_down', comment: 'regenerated' })
      );
    });
    // the original prompt is re-sent
    await waitFor(() => {
      expect(postedMessages.length).toBe(2);
    });
    expect((postedMessages[1] as any).message).toBe('Regenerate me');
  });

  it('closes the popover via the header X button', async () => {
    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    const closeButton = document
      .querySelector('.lucide-x')
      ?.closest('button') as HTMLElement;
    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByText('ATOM Assistant')).not.toBeInTheDocument();
    });
  });

  it('shows an error toast when the approval decision API fails', async () => {
    server.use(
      rest.get('/api/agents/approvals/pending', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([{ id: 'p-9', action_type: 'delete_file', reason: 'Dangerous' }])
        );
      })
    );
    mockApiPost.mockResolvedValue({ data: { success: false, error: 'nope' } });

    render(<GlobalChatWidget />);
    openChat();

    fireEvent.click(await screen.findByRole('button', { name: /approve/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Error: nope' })
      );
    });
  });

  it('shows an error toast when the approval decision POST rejects', async () => {
    server.use(
      rest.get('/api/agents/approvals/pending', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([{ id: 'p-8', action_type: 'delete_file', reason: 'Dangerous' }])
        );
      })
    );
    mockApiPost.mockRejectedValue(new Error('network down'));

    render(<GlobalChatWidget />);
    openChat();

    fireEvent.click(await screen.findByRole('button', { name: /reject/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Error: network down' })
      );
    });
  });

  it('stays silent when the pending approvals fetch fails', async () => {
    // A background poll must never surface a runtime error: the banner simply
    // stays hidden and nothing reaches console.error (the Next dev overlay
    // shows console.error calls from components).
    server.use(
      rest.get('/api/agents/approvals/pending', (req, res) => res.networkError('approvals down'))
    );

    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    await new Promise((r) => setTimeout(r, 100));
    expect(screen.queryByText('Approval Required')).not.toBeInTheDocument();
    expect(errorSpy).not.toHaveBeenCalledWith(
      'Failed to fetch pending approvals:',
      expect.anything()
    );
  });

  it('treats a failed message POST as an error bubble', async () => {
    server.use(
      rest.post('/api/chat/message', (req, res) => res.networkError('boom'))
    );

    render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    fireEvent.change(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      target: { value: 'Will fail' },
    });
    fireEvent.keyDown(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      key: 'Enter',
    });

    expect(
      await screen.findByText('Sorry, I encountered an error. Please try again.')
    ).toBeInTheDocument();
  });

  it('falls back to the welcome message when history fetch fails at the network level', async () => {
    localStorage.setItem('atom_chat_session_id', 'sess-netfail');
    server.use(
      rest.get('/api/chat/history/:sid', (req, res) => res.networkError('boom'))
    );

    render(<GlobalChatWidget />);
    openChat();

    expect(
      await screen.findByText(/Hi! I am your Universal ATOM Assistant/)
    ).toBeInTheDocument();
  });

  it('keeps messages unchanged when an agent step arrives while a user message is last', async () => {
    // Make the chat POST hang so the last message stays the user's message.
    let resolvePost: () => void = () => {};
    server.use(
      rest.post('/api/chat/message', (req, res, ctx) => {
        return res(ctx.delay(5000), ctx.json({ success: true, message: 'late' }));
      })
    );

    const { rerender } = render(<GlobalChatWidget />);
    openChat();
    await screen.findByText('ATOM Assistant');

    fireEvent.change(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      target: { value: 'Pending message' },
    });
    fireEvent.keyDown(screen.getByPlaceholderText(/Ask ATOM to schedule meetings/), {
      key: 'Enter',
    });

    expect(await screen.findByText('Pending message')).toBeInTheDocument();

    wsState.lastMessage = {
      type: 'agent_step_update',
      step: { step: 1, thought: 'Ignored thought' },
    };
    rerender(<GlobalChatWidget />);

    await new Promise((r) => setTimeout(r, 100));
    // The step could not attach to a user message, so no reasoning toggle appears.
    expect(
      screen.queryByRole('button', { name: /reasoning process/i })
    ).not.toBeInTheDocument();
    expect(screen.getByText('Pending message')).toBeInTheDocument();

    resolvePost();
  });

  it('clears a pending approval when the API reports an empty queue', async () => {
    // First load shows a pending approval, then re-opening clears it.
    // (The fetch fires when the popover opens, not on mount.)
    let approvals: any[] = [{ id: 'p-5', action_type: 'send_email', reason: 'Needs approval' }];
    server.use(
      rest.get('/api/agents/approvals/pending', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json(approvals));
      })
    );

    render(<GlobalChatWidget />);
    openChat();
    expect(await screen.findByText('Approval Required')).toBeInTheDocument();

    approvals = [];

    const closeButton = document
      .querySelector('.lucide-x')
      ?.closest('button') as HTMLElement;
    fireEvent.click(closeButton);
    openChat();

    await waitFor(() => {
      expect(screen.queryByText('Approval Required')).not.toBeInTheDocument();
    });
  });
});
