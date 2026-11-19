/**
 * TeamChatPanel and Team Chat page tests.
 *
 * Push used to be driven through the shared MockWebSocket from tests/setup.ts.
 * Team Chat now uses authorized, team-scoped HTTP history refresh instead, so
 * these tests mock fetch and cover the user-visible send/read paths plus safe
 * state when a team changes or a request fails.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import TeamChatPanel from '../TeamChatPanel';
import TeamChatPage from '../../../pages/team-chat';

const MESSAGE_HISTORY = [
  { id: 'm1', team_id: 'team-1', user_id: 'u1', sender_name: 'Jane Doe', content: 'Hello team', created_at: '2026-08-01T10:00:00Z' },
  { id: 'm2', team_id: 'team-1', user_id: 'u2', sender_name: 'Bob Smith', content: 'Hi Jane', created_at: '2026-08-01T10:01:00Z' },
];

type MockRoute = {
  match: string;
  method?: string;
  res: () => { ok: boolean; status?: number; json?: any };
};

const response = (r: { ok: boolean; status?: number; json?: any }) => ({
  ok: r.ok,
  status: r.status ?? 200,
  json: async () => r.json ?? {},
});

const mockFetch = (routes: MockRoute[]) => {
  (global.fetch as jest.Mock) = jest.fn((url: string, init?: RequestInit) => {
    const route = routes.find(
      (r) =>
        String(url).includes(r.match) &&
        (!r.method || (init?.method || 'GET') === r.method)
    );
    return Promise.resolve(response(route ? route.res() : { ok: false, status: 404 }));
  });
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

describe('TeamChatPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Storage.prototype, 'getItem').mockReturnValue('token123');
    mockFetch([
      {
        match: '/api/teams/team-1/messages',
        method: 'GET',
        res: () => ({ ok: true, json: [...MESSAGE_HISTORY] }),
      },
    ]);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders the header and context line and reads authorized history', async () => {
    render(<TeamChatPanel teamId="team-1" contextType="workflow" contextId="wf-42" />);
    expect(screen.getByRole('heading', { name: /Team Chat/i })).toBeInTheDocument();
    expect(screen.getByText('Discussing: workflow #wf-42')).toBeInTheDocument();
    expect(await screen.findByText('Hello team')).toBeInTheDocument();

    const getCall = (global.fetch as jest.Mock).mock.calls.find(
      ([, init]: [string, RequestInit?]) => (init?.method || 'GET') === 'GET'
    );
    expect(getCall[0]).toContain('/api/teams/team-1/messages');
    expect(getCall[0]).toContain('context_type=workflow');
    expect(getCall[0]).toContain('context_id=wf-42');
    expect(getCall[1].headers).toEqual(
      expect.objectContaining({ Authorization: 'Bearer token123' })
    );
  });

  it('shows a spinner while loading then the oldest-first message list with initials', async () => {
    const { container } = render(<TeamChatPanel teamId="team-1" />);
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();

    expect(await screen.findByText('Hello team')).toBeInTheDocument();
    expect(screen.getByText('Hi Jane')).toBeInTheDocument();
    expect(screen.getByText('JD')).toBeInTheDocument();
    expect(screen.getByText('BS')).toBeInTheDocument();

    const messageBlocks = container.querySelectorAll('.flex.items-start.space-x-3');
    expect(messageBlocks[0]).toHaveTextContent('Hello team');
    expect(messageBlocks[1]).toHaveTextContent('Hi Jane');
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

  it('shows an actionable retry state when history fails, then recovers', async () => {
    let fail = true;
    (global.fetch as jest.Mock) = jest.fn((url: string, init?: RequestInit) => {
      if (String(url).includes('/api/teams/team-1/messages') && (init?.method || 'GET') === 'GET') {
        return Promise.resolve(
          response(
            fail
              ? { ok: false, status: 500 }
              : { ok: true, json: [...MESSAGE_HISTORY] }
          )
        );
      }
      return Promise.resolve(response({ ok: false, status: 404 }));
    });

    render(<TeamChatPanel teamId="team-1" />);
    expect(await screen.findByText('Could not load messages.')).toBeInTheDocument();

    fail = false;
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(await screen.findByText('Hello team')).toBeInTheDocument();
  });

  it('sends via the send button and shows the persisted POST message exactly once', async () => {
    mockFetch([
      {
        match: '/api/teams/team-1/messages',
        method: 'GET',
        res: () => ({ ok: true, json: [...MESSAGE_HISTORY] }),
      },
      {
        match: '/api/teams/team-1/messages',
        method: 'POST',
        res: () => ({
          ok: true,
          json: {
            id: 'm3',
            team_id: 'team-1',
            user_id: 'u1',
            sender_name: 'Jane Doe',
            content: 'New message',
            context_type: 'workflow',
            context_id: 'wf-42',
            created_at: '2026-08-01T10:02:00Z',
          },
        }),
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

    await waitFor(() => {
      expect(screen.getAllByText('New message')).toHaveLength(1);
    });
    expect(
      (screen.getByPlaceholderText('Type a message...') as HTMLTextAreaElement).value
    ).toBe('');
  });

  it('sends with Enter but not Shift+Enter', async () => {
    mockFetch([
      {
        match: '/api/teams/team-1/messages',
        method: 'GET',
        res: () => ({ ok: true, json: [...MESSAGE_HISTORY] }),
      },
      {
        match: '/api/teams/team-1/messages',
        method: 'POST',
        res: () => ({
          ok: true,
          json: {
            id: 'm3',
            team_id: 'team-1',
            user_id: 'u1',
            sender_name: 'Jane Doe',
            content: 'Enter send',
            created_at: '2026-08-01T10:02:00Z',
          },
        }),
      },
    ]);
    render(<TeamChatPanel teamId="team-1" />);
    await screen.findByText('Hello team');

    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.change(textarea, { target: { value: 'Enter send' } });
    fireEvent.keyPress(textarea, { key: 'Enter', code: 'Enter', charCode: 13 });
    await waitFor(() => {
      const posts = (global.fetch as jest.Mock).mock.calls.filter(
        ([url, init]: [string, RequestInit?]) =>
          String(url).includes('/messages') && init?.method === 'POST'
      );
      expect(posts).toHaveLength(1);
    });

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
    expect(screen.getByRole('button', { name: /send message/i })).toBeDisabled();
  });

  it('does not issue a duplicate POST while a send is pending', async () => {
    const pendingPost = deferred<any>();
    let postCount = 0;
    (global.fetch as jest.Mock) = jest.fn((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        postCount += 1;
        return pendingPost.promise;
      }
      return Promise.resolve(response({ ok: true, json: [...MESSAGE_HISTORY] }));
    });

    render(<TeamChatPanel teamId="team-1" />);
    await screen.findByText('Hello team');

    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.change(textarea, { target: { value: 'Only once' } });
    fireEvent.keyPress(textarea, { key: 'Enter', code: 'Enter', charCode: 13 });
    fireEvent.keyPress(textarea, { key: 'Enter', code: 'Enter', charCode: 13 });

    expect(postCount).toBe(1);

    await act(async () => {
      pendingPost.resolve(
        response({
          ok: true,
          json: {
            id: 'm4',
            team_id: 'team-1',
            user_id: 'u1',
            sender_name: 'Jane Doe',
            content: 'Only once',
            created_at: '2026-08-01T10:03:00Z',
          },
        })
      );
      await pendingPost.promise;
    });
    await waitFor(() => {
      expect(screen.getAllByText('Only once')).toHaveLength(1);
    });
  });

  it('retains the draft and shows an error when a send fails', async () => {
    mockFetch([
      {
        match: '/api/teams/team-1/messages',
        method: 'GET',
        res: () => ({ ok: true, json: [...MESSAGE_HISTORY] }),
      },
      {
        match: '/api/teams/team-1/messages',
        method: 'POST',
        res: () => ({ ok: false, status: 500 }),
      },
    ]);
    render(<TeamChatPanel teamId="team-1" />);
    await screen.findByText('Hello team');

    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.change(textarea, { target: { value: 'Keep this draft' } });
    fireEvent.keyPress(textarea, { key: 'Enter', code: 'Enter', charCode: 13 });

    expect(
      await screen.findByText('Message could not be sent. Please try again.')
    ).toBeInTheDocument();
    expect((textarea as HTMLTextAreaElement).value).toBe('Keep this draft');
    expect(
      screen.queryByText('Keep this draft', { selector: 'div' })
    ).not.toBeInTheDocument();
  });

  it('rejects a malformed successful POST without inventing a message or clearing the draft', async () => {
    mockFetch([
      {
        match: '/api/teams/team-1/messages',
        method: 'GET',
        res: () => ({ ok: true, json: [...MESSAGE_HISTORY] }),
      },
      {
        match: '/api/teams/team-1/messages',
        method: 'POST',
        res: () => ({
          ok: true,
          json: {
            id: '',
            team_id: 'team-2',
            user_id: 'u1',
            content: '',
            created_at: 'not-a-timestamp',
          },
        }),
      },
    ]);
    render(<TeamChatPanel teamId="team-1" />);
    await screen.findByText('Hello team');

    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.change(textarea, { target: { value: 'Unconfirmed send' } });
    fireEvent.keyPress(textarea, { key: 'Enter', code: 'Enter', charCode: 13 });

    expect(
      await screen.findByText(/could not be confirmed/i)
    ).toBeInTheDocument();
    expect((textarea as HTMLTextAreaElement).value).toBe('Unconfirmed send');
    expect(
      screen.queryByText('Unconfirmed send', { selector: 'div' })
    ).not.toBeInTheDocument();
    expect(screen.getByText('Hello team')).toBeInTheDocument();
  });

  it('clears messages on revoked history and ignores a stale in-flight send', async () => {
    const pendingPost = deferred<any>();
    const refreshCallbacks: Array<() => void> = [];
    const intervalSpy = jest
      .spyOn(window, 'setInterval')
      .mockImplementation(((handler: () => void) => {
        refreshCallbacks.push(handler);
        return refreshCallbacks.length;
      }) as unknown as typeof window.setInterval);

    let historyCount = 0;
    (global.fetch as jest.Mock) = jest.fn((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') return pendingPost.promise;
      historyCount += 1;
      if (historyCount === 1) {
        return Promise.resolve(response({ ok: true, json: [...MESSAGE_HISTORY] }));
      }
      return Promise.resolve(response({ ok: false, status: 403 }));
    });

    render(<TeamChatPanel teamId="team-1" />);
    // The component has registered its interval by now; restore the real timer
    // so Testing Library's own waitFor polling is not intercepted.
    intervalSpy.mockRestore();
    expect(await screen.findByText('Hello team')).toBeInTheDocument();

    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.change(textarea, { target: { value: 'Pending send' } });
    fireEvent.keyPress(textarea, { key: 'Enter', code: 'Enter', charCode: 13 });

    await act(async () => {
      refreshCallbacks[0]();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(await screen.findByText(/no longer have access/i)).toBeInTheDocument();
    expect(screen.queryByText('Hello team')).not.toBeInTheDocument();
    expect(screen.queryByText('Hi Jane')).not.toBeInTheDocument();

    await act(async () => {
      pendingPost.resolve(
        response({
          ok: true,
          json: {
            id: 'm5',
            team_id: 'team-1',
            user_id: 'u1',
            sender_name: 'Jane Doe',
            content: 'Pending send',
            created_at: '2026-08-01T10:05:00Z',
          },
        })
      );
      await pendingPost.promise;
    });

    await waitFor(() => {
      expect(screen.getByText(/could not be confirmed/i)).toBeInTheDocument();
    });
    expect(
      screen.queryByText('Pending send', { selector: 'div' })
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Hello team')).not.toBeInTheDocument();
    expect((textarea as HTMLTextAreaElement).value).toBe('Pending send');
  });

  it('does not show a previous team response after switching teams', async () => {
    const firstHistory = deferred<any>();
    const secondHistory = deferred<any>();
    let teamTwoRequested = false;

    (global.fetch as jest.Mock) = jest.fn((url: string) => {
      if (String(url).includes('/api/teams/team-2/messages')) {
        teamTwoRequested = true;
        return secondHistory.promise;
      }
      return firstHistory.promise;
    });

    const { rerender } = render(<TeamChatPanel teamId="team-1" />);
    rerender(<TeamChatPanel teamId="team-2" />);
    expect(teamTwoRequested).toBe(true);
    expect(screen.queryByText('Team one message')).not.toBeInTheDocument();

    await act(async () => {
      secondHistory.resolve(
        response({
          ok: true,
          json: [
            { id: 't2m1', team_id: 'team-2', user_id: 'u2', sender_name: 'Bob', content: 'Team two message', created_at: '2026-08-01T11:00:00Z' },
          ],
        })
      );
      await secondHistory.promise;
    });
    expect(await screen.findByText('Team two message')).toBeInTheDocument();

    await act(async () => {
      firstHistory.resolve(
        response({
          ok: true,
          json: [
            { id: 't1m1', team_id: 'team-1', user_id: 'u1', sender_name: 'Jane', content: 'Team one message', created_at: '2026-08-01T10:00:00Z' },
          ],
        })
      );
      await firstHistory.promise;
    });
    expect(screen.queryByText('Team one message')).not.toBeInTheDocument();
    expect(screen.getByText('Team two message')).toBeInTheDocument();
  });

  it('does not show a stale sent message in another team', async () => {
    const pendingPost = deferred<any>();
    (global.fetch as jest.Mock) = jest.fn((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') return pendingPost.promise;
      if (String(url).includes('/api/teams/team-2/messages')) {
        return Promise.resolve(
          response({
            ok: true,
            json: [
              { id: 't2m1', team_id: 'team-2', user_id: 'u2', sender_name: 'Bob', content: 'Team two message', created_at: '2026-08-01T11:00:00Z' },
            ],
          })
        );
      }
      return Promise.resolve(response({ ok: true, json: [...MESSAGE_HISTORY] }));
    });

    const { rerender } = render(<TeamChatPanel teamId="team-1" />);
    await screen.findByText('Hello team');

    const textarea = screen.getByPlaceholderText('Type a message...');
    fireEvent.change(textarea, { target: { value: 'Stale send' } });
    fireEvent.keyPress(textarea, { key: 'Enter', code: 'Enter', charCode: 13 });

    rerender(<TeamChatPanel teamId="team-2" />);
    expect(await screen.findByText('Team two message')).toBeInTheDocument();

    await act(async () => {
      pendingPost.resolve(
        response({
          ok: true,
          json: {
            id: 'stale',
            team_id: 'team-1',
            user_id: 'u1',
            sender_name: 'Jane Doe',
            content: 'Stale send',
            created_at: '2026-08-01T12:00:00Z',
          },
        })
      );
      await pendingPost.promise;
    });

    expect(screen.queryByText('Stale send')).not.toBeInTheDocument();
    expect(screen.getByText('Team two message')).toBeInTheDocument();
  });

  it('skips loading and HTTP when no auth token exists', async () => {
    jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    render(<TeamChatPanel teamId="team-1" />);

    expect(
      await screen.findByText('No messages yet. Start the conversation!')
    ).toBeInTheDocument();
    const getCalls = (global.fetch as jest.Mock).mock.calls.filter(
      ([url]: [string]) => String(url).includes('/api/teams/')
    );
    expect(getCalls).toHaveLength(0);
  });
});

describe('Team Chat page', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Storage.prototype, 'getItem').mockReturnValue('token123');
  });

  it('shows a sign-in action when there is no token and makes no scoped calls', async () => {
    jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    mockFetch([]);
    render(<TeamChatPage />);

    expect(await screen.findByText('Please sign in to use Team Chat.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('loads /api/teams/mine, selects a team, and renders its panel', async () => {
    mockFetch([
      {
        match: '/api/teams/mine',
        res: () => ({ ok: true, json: [{ id: 'team-1', name: 'Alpha' }] }),
      },
      {
        match: '/api/teams/team-1/messages',
        method: 'GET',
        res: () => ({ ok: true, json: [...MESSAGE_HISTORY] }),
      },
    ]);

    render(<TeamChatPage />);

    const picker = await screen.findByRole('combobox');
    expect(picker).toHaveValue('team-1');
    expect(screen.getByRole('option', { name: 'Alpha' })).toBeInTheDocument();
    expect(await screen.findByText('Hello team')).toBeInTheDocument();

    const teamsCall = (global.fetch as jest.Mock).mock.calls.find(
      ([url]: [string]) => String(url).includes('/api/teams/mine')
    );
    expect(teamsCall[1].headers).toEqual(
      expect.objectContaining({ Authorization: 'Bearer token123' })
    );
  });

  it('loads the newly selected team without showing the old team messages', async () => {
    mockFetch([
      {
        match: '/api/teams/mine',
        res: () => ({
          ok: true,
          json: [
            { id: 'team-1', name: 'Alpha' },
            { id: 'team-2', name: 'Beta' },
          ],
        }),
      },
      {
        match: '/api/teams/team-1/messages',
        method: 'GET',
        res: () => ({ ok: true, json: [...MESSAGE_HISTORY] }),
      },
      {
        match: '/api/teams/team-2/messages',
        method: 'GET',
        res: () => ({
          ok: true,
          json: [
            { id: 'b1', team_id: 'team-2', user_id: 'u2', sender_name: 'Bob', content: 'Beta message', created_at: '2026-08-01T11:00:00Z' },
          ],
        }),
      },
    ]);

    render(<TeamChatPage />);
    await screen.findByText('Hello team');

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'team-2' } });
    expect(await screen.findByText('Beta message')).toBeInTheDocument();
    expect(screen.queryByText('Hello team')).not.toBeInTheDocument();
  });

  it('shows an actionable error and retries the team list', async () => {
    let fail = true;
    (global.fetch as jest.Mock) = jest.fn((url: string) => {
      if (String(url).includes('/api/teams/mine')) {
        return Promise.resolve(
          response(
            fail
              ? { ok: false, status: 503 }
              : { ok: true, json: [{ id: 'team-1', name: 'Alpha' }] }
          )
        );
      }
      return Promise.resolve(response({ ok: true, json: [...MESSAGE_HISTORY] }));
    });

    render(<TeamChatPage />);
    expect(await screen.findByText('Could not load your teams.')).toBeInTheDocument();

    fail = false;
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(await screen.findByRole('combobox')).toHaveValue('team-1');
  });

  it('shows an actionable empty state when the user has no teams', async () => {
    mockFetch([
      {
        match: '/api/teams/mine',
        res: () => ({ ok: true, json: [] }),
      },
    ]);
    render(<TeamChatPage />);

    expect(await screen.findByText('No teams available yet.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });
});
