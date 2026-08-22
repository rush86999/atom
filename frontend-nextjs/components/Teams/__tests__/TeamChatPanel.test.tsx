/**
 * TeamChatPanel component tests.
 *
 * fetch is mocked for history load + message send; the global MockWebSocket
 * (from tests/setup.ts) is used to drive subscribe/open/message events.
 * Covers rendering, empty state, send flows (button + Enter), WebSocket
 * subscribe/receive with context filtering, and the no-token guard.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import TeamChatPanel from '../TeamChatPanel';

const MESSAGE_HISTORY = [
  { id: 'm1', team_id: 'team-1', user_id: 'u1', sender_name: 'Jane Doe', content: 'Hello team', created_at: '2026-08-01T10:00:00Z' },
  { id: 'm2', team_id: 'team-1', user_id: 'u2', sender_name: 'Bob Smith', content: 'Hi Jane', created_at: '2026-08-01T10:01:00Z' },
];

const mockFetch = (routes: Array<{ match: string; method?: string; res: () => { ok: boolean; status?: number; json?: any } }>) => {
  (global.fetch as jest.Mock) = jest.fn((url: string, init?: RequestInit) => {
    const route = routes.find(
      (r) =>
        String(url).includes(r.match) &&
        (!r.method || (init?.method || 'GET') === r.method)
    );
    const r = route ? route.res() : { ok: false, status: 404, json: {} };
    return Promise.resolve({
      ok: r.ok,
      status: r.status ?? 200,
      json: async () => r.json ?? {},
    });
  });
};

const mockWebSocket = () => (global as any).WebSocket as any;

describe('TeamChatPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // The global MockWebSocket tracks calls/instances on plain arrays that are
    // not jest mocks — reset them so per-test length assertions are valid.
    mockWebSocket().mock.calls.length = 0;
    mockWebSocket().mock.instances.length = 0;
    // localStorage is a real jsdom Storage instance (setup.ts's mock assignment
    // does not survive the getter-only global) → spy on Storage.prototype.
    jest.spyOn(Storage.prototype, 'getItem').mockReturnValue('token123');
    mockFetch([
      {
        match: '/api/teams/team-1/messages',
        method: 'GET',
        res: () => ({ ok: true, json: [...MESSAGE_HISTORY] }),
      },
    ]);
    (localStorage.getItem as jest.Mock).mockReturnValue('token123');
  });

  it('renders the header and context line', async () => {
    render(<TeamChatPanel teamId="team-1" contextType="workflow" contextId="wf-42" />);
    expect(screen.getByRole('heading', { name: /Team Chat/i })).toBeInTheDocument();
    expect(screen.getByText('Discussing: workflow #wf-42')).toBeInTheDocument();
    // Message history loaded
    expect(await screen.findByText('Hello team')).toBeInTheDocument();
  });

  it('shows a spinner while loading then the message list with sender initials', async () => {
    const { container } = render(<TeamChatPanel teamId="team-1" />);
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();

    expect(await screen.findByText('Hello team')).toBeInTheDocument();
    expect(screen.getByText('Hi Jane')).toBeInTheDocument();
    // Initials: Jane Doe → JD, Bob Smith → BS
    expect(screen.getByText('JD')).toBeInTheDocument();
    expect(screen.getByText('BS')).toBeInTheDocument();
    // History is reversed (latest first) by the component: the first rendered
    // message block is m2 (Hi Jane), the second is m1 (Hello team).
    const messageBlocks = container.querySelectorAll('.flex.items-start.space-x-3');
    expect(messageBlocks[0]).toHaveTextContent('Hi Jane');
    expect(messageBlocks[1]).toHaveTextContent('Hello team');
  });

  it('shows the empty state when there are no messages', async () => {
    mockFetch([
      {
        match: '/api/teams/team-1/messages',
        method: 'GET',
        res: () => ({ ok: true, json: [] }),
      },
    ]);
    render(<TeamChatPanel teamId="team-1" />);
    expect(
      await screen.findByText('No messages yet. Start the conversation!')
    ).toBeInTheDocument();
  });

  it('sends a message via the send button and clears the input', async () => {
    mockFetch([
      {
        match: '/api/teams/team-1/messages',
        method: 'GET',
        res: () => ({ ok: true, json: [...MESSAGE_HISTORY] }),
      },
      {
        match: '/api/teams/team-1/messages',
        method: 'POST',
        res: () => ({ ok: true, json: { id: 'm3' } }),
      },
    ]);
    const { container } = render(
      <TeamChatPanel teamId="team-1" contextType="workflow" contextId="wf-42" />
    );
    await screen.findByText('Hello team');

    fireEvent.change(screen.getByPlaceholderText('Type a message...'), {
      target: { value: 'New message' },
    });
    fireEvent.click(container.querySelector('svg.lucide-send')!.closest('button')!);
    await waitFor(() => {
      const post = (global.fetch as jest.Mock).mock.calls.find(
        ([url, init]: [string, RequestInit?]) =>
          String(url).includes('/api/teams/team-1/messages') && init?.method === 'POST'
      );
      expect(post).toBeDefined();
      expect(JSON.parse(post[1].body)).toEqual({
        content: 'New message',
        context_type: 'workflow',
        context_id: 'wf-42',
      });
      expect(post[1].headers).toEqual(
        expect.objectContaining({ Authorization: 'Bearer token123' })
      );
    });
    expect(
      (screen.getByPlaceholderText('Type a message...') as HTMLTextAreaElement).value
    ).toBe('');
  });

  it('sends a message with Enter but not Shift+Enter', async () => {
    mockFetch([
      {
        match: '/api/teams/team-1/messages',
        method: 'GET',
        res: () => ({ ok: true, json: [...MESSAGE_HISTORY] }),
      },
      {
        match: '/api/teams/team-1/messages',
        method: 'POST',
        res: () => ({ ok: true, json: { id: 'm3' } }),
      },
    ]);
    render(<TeamChatPanel teamId="team-1" />);
    await screen.findByText('Hello team');

    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.change(textarea, { target: { value: 'Enter send' } });
    fireEvent.keyPress(textarea, {
      key: 'Enter',
      code: 'Enter',
      charCode: 13,
    });
    await waitFor(() => {
      const posts = (global.fetch as jest.Mock).mock.calls.filter(
        ([url, init]: [string, RequestInit?]) =>
          String(url).includes('/messages') && init?.method === 'POST'
      );
      expect(posts).toHaveLength(1);
    });

    // Shift+Enter should NOT send.
    fireEvent.change(textarea, { target: { value: 'No send' } });
    fireEvent.keyPress(textarea, {
      key: 'Enter',
      code: 'Enter',
      charCode: 13,
      shiftKey: true,
    });
    const posts = (global.fetch as jest.Mock).mock.calls.filter(
      ([url, init]: [string, RequestInit?]) =>
        String(url).includes('/messages') && init?.method === 'POST'
    );
    expect(posts).toHaveLength(1);
  });

  it('does not send empty or whitespace-only messages', async () => {
    render(<TeamChatPanel teamId="team-1" />);
    await screen.findByText('Hello team');

    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.change(textarea, { target: { value: '   ' } });
    const sendButton = screen.getAllByRole('button').find((b) => (b as HTMLButtonElement).disabled);
    expect(sendButton).toBeDisabled();
  });

  it('subscribes to the team channel over WebSocket', async () => {
    render(<TeamChatPanel teamId="team-1" />);
    await screen.findByText('Hello team');

    await waitFor(() => {
      expect(mockWebSocket().getMockCalls().length).toBe(1);
    });
    const ws = mockWebSocket().getMockInstances()[0];
    expect(ws._url).toBe('/ws?token=token123');

    act(() => {
      ws._onopen?.(new Event('open'));
    });
    expect(ws.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'subscribe', channel: 'team:team-1' })
    );
  });

  it('appends a received message matching the context filter', async () => {
    render(<TeamChatPanel teamId="team-1" contextType="workflow" contextId="wf-42" />);
    await screen.findByText('Hello team');

    const ws = mockWebSocket().getMockInstances()[0];
    act(() => {
      ws._onmessage?.({
        data: JSON.stringify({
          type: 'message.received',
          data: { id: 'm9', sender_name: 'Carol', content: 'Live update', context_type: 'workflow', context_id: 'wf-42', created_at: '2026-08-01T12:00:00Z' },
        }),
      });
    });
    expect(screen.getByText('Live update')).toBeInTheDocument();
    expect(screen.getByText('C')).toBeInTheDocument(); // Carol → C
  });

  it('ignores received messages that do not match the context filter', async () => {
    render(<TeamChatPanel teamId="team-1" contextType="workflow" contextId="wf-42" />);
    await screen.findByText('Hello team');

    const ws = mockWebSocket().getMockInstances()[0];
    act(() => {
      ws._onmessage?.({
        data: JSON.stringify({
          type: 'message.received',
          data: { id: 'm10', sender_name: 'Carol', content: 'Other context', context_type: 'workflow', context_id: 'wf-99', created_at: '2026-08-01T12:00:00Z' },
        }),
      });
      ws._onmessage?.({
        data: JSON.stringify({
          type: 'message.received',
          data: { id: 'm11', sender_name: 'Carol', content: 'No context at all', created_at: '2026-08-01T12:00:00Z' },
        }),
      });
    });
    expect(screen.queryByText('Other context')).not.toBeInTheDocument();
    expect(screen.queryByText('No context at all')).not.toBeInTheDocument();
  });

  it('skips loading and websocket when no auth token exists', () => {
    jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    render(<TeamChatPanel teamId="team-1" />);

    const getCalls = (global.fetch as jest.Mock).mock.calls.filter(
      ([url]: [string]) => String(url).includes('/api/teams/')
    );
    expect(getCalls).toHaveLength(0);
    expect(mockWebSocket().getMockCalls().length).toBe(0);
    expect(
      screen.getByText('No messages yet. Start the conversation!')
    ).toBeInTheDocument();
  });
});
