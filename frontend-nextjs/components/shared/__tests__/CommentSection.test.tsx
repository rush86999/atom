/**
 * CommentSection Component Tests
 *
 * Verifies the real CommentSection (components/shared/CommentSection.tsx)
 * over the global MockWebSocket (tests/setup.ts):
 * - opens a WebSocket with the auth token and subscribes to the channel
 * - renders incoming comment/message frames with sender attribution
 * - ignores non-JSON frames (keepalives/proxy noise) without crashing
 * - sending optimistically renders the message and sends a comment frame
 * - feedback on agent messages toasts and POSTs to /api/reasoning/feedback
 *   with the agent_id mapped from the sender name
 * - unmounting unsubscribes and closes an open socket
 */
import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };

jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { name: 'Rushi' } }, status: 'authenticated' }),
}));

// imported after the mocks so their factories never run before the mock vars exist
import { CommentSection } from '../CommentSection';

let feedbackBody: any = null;

const getMockWS = (): any => {
  const instances = (global as any).WebSocket.getMockInstances();
  return instances[instances.length - 1];
};

describe('CommentSection', () => {
  beforeEach(() => {
    mockToast.toast.mockClear();
    mockToast.dismiss.mockClear();
    (global as any).WebSocket.mock.calls.length = 0;
    (global as any).WebSocket.mock.instances.length = 0;
    feedbackBody = null;
    server.resetHandlers();
    server.use(
      rest.post('/api/reasoning/feedback', (req, res, ctx) => {
        feedbackBody = req.body;
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );
  });

  it('opens a WebSocket with the auth token and subscribes on open', () => {
    render(<CommentSection channel="projects" />);

    const ws = getMockWS();
    expect(ws).toBeDefined();
    expect(ws._url).toContain('ws://localhost:8000/ws?token=');

    act(() => {
      ws.onopen(new Event('open'));
    });

    expect(ws.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'subscribe', channel: 'projects' })
    );
  });

  it('renders incoming comment frames with sender attribution', () => {
    render(<CommentSection channel="projects" />);
    const ws = getMockWS();

    act(() => {
      ws.onmessage({
        data: JSON.stringify({
          type: 'comment',
          sender: 'Alice',
          senderType: 'agent',
          content: 'Ping — check the numbers',
          id: 'm1',
        }),
      });
    });

    // agent-sent messages show the sender label above the bubble
    expect(screen.getByText('Ping — check the numbers')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
  });

  it('renders incoming message frames too', () => {
    render(<CommentSection channel="projects" />);
    const ws = getMockWS();

    act(() => {
      ws.onmessage({
        data: JSON.stringify({ type: 'message', sender: 'Bob', content: 'LGTM' }),
      });
    });

    expect(screen.getByText('LGTM')).toBeInTheDocument();
  });

  it('ignores non-JSON frames without crashing', () => {
    render(<CommentSection channel="projects" />);
    const ws = getMockWS();

    act(() => {
      ws.onmessage({ data: 'keepalive-ping' });
      ws.onmessage({ data: ': proxy comment' });
    });

    expect(screen.queryByText('keepalive-ping')).not.toBeInTheDocument();
    expect(screen.getByText('Team Discussion')).toBeInTheDocument();
  });

  it('sends a comment frame and optimistically renders the message', () => {
    render(<CommentSection channel="projects" />);
    const ws = getMockWS();

    fireEvent.change(screen.getByPlaceholderText('Discuss projects...'), {
      target: { value: 'I reviewed the numbers' },
    });
    fireEvent.click(screen.getByRole('button', { name: '' }));

    expect(ws.send).toHaveBeenCalledWith(
      JSON.stringify({
        type: 'comment',
        channel: 'projects',
        content: 'I reviewed the numbers',
        sender: 'Rushi',
        senderType: 'user',
      })
    );
    expect(screen.getByText('I reviewed the numbers')).toBeInTheDocument();
    expect((screen.getByPlaceholderText('Discuss projects...') as HTMLInputElement).value).toBe('');
  });

  it('does not send empty messages', () => {
    render(<CommentSection channel="projects" />);
    const ws = getMockWS();

    fireEvent.change(screen.getByPlaceholderText('Discuss projects...'), {
      target: { value: '   ' },
    });
    fireEvent.click(screen.getByRole('button', { name: '' }));

    expect(ws.send).not.toHaveBeenCalled();
  });

  it('posts thumbs-up feedback for agent messages with the mapped agent id', async () => {
    render(<CommentSection channel="projects" />);
    const ws = getMockWS();

    act(() => {
      ws.onmessage({
        data: JSON.stringify({
          type: 'comment',
          sender: 'Atom Agent',
          senderType: 'agent',
          content: 'Here is the summary',
        }),
      });
    });

    fireEvent.click(screen.getByRole('button', { name: 'Thumbs up' }));

    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Helpful' })
    );
    await waitFor(() => {
      expect(feedbackBody).toEqual(
        expect.objectContaining({
          agent_id: 'atom_meta_agent',
          feedback_type: 'thumbs_up',
          run_id: expect.stringContaining('team-chat-projects-'),
        })
      );
    });
    expect(feedbackBody.step_content.output).toBe('Here is the summary');
  });

  it('maps finance/analyst sender names to their specialist agent ids', async () => {
    render(<CommentSection channel="projects" />);
    const ws = getMockWS();

    act(() => {
      ws.onmessage({
        data: JSON.stringify({
          type: 'comment',
          id: 'msg-finance',
          sender: 'Finance Specialist',
          senderType: 'agent',
          content: 'Budget is fine',
        }),
      });
      ws.onmessage({
        data: JSON.stringify({
          type: 'comment',
          id: 'msg-analyst',
          sender: 'Data Analyst',
          senderType: 'agent',
          content: 'Numbers check out',
        }),
      });
    });

    fireEvent.click(screen.getAllByRole('button', { name: 'Thumbs up' })[0]);
    await waitFor(() => expect(feedbackBody.agent_id).toBe('finance_specialist'));

    fireEvent.click(screen.getAllByRole('button', { name: 'Thumbs up' })[1]);
    await waitFor(() => expect(feedbackBody.agent_id).toBe('data_analyst'));
  });

  it('unsubscribes and closes the socket on unmount when open', () => {
    const { unmount } = render(<CommentSection channel="projects" />);
    const ws = getMockWS();
    ws.readyState = 1; // WebSocket.OPEN

    unmount();

    expect(ws.send).toHaveBeenCalledWith(JSON.stringify({ type: 'unsubscribe', channel: 'projects' }));
    expect(ws.close).toHaveBeenCalled();
  });
});
