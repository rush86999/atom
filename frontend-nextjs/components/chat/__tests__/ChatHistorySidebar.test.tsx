/**
 * ChatHistorySidebar Component Tests
 *
 * Tests verify ChatHistorySidebar renders session list, handles empty
 * states, and shows loading state.
 *
 * Source: components/chat/ChatHistorySidebar.tsx
 *
 * Real behavior (verified against source):
 * - Fetches `/api/chat/sessions?user_id=default_user` on mount via
 *   apiClient (axios), NOT raw fetch — so the old `global.fetch = jest.fn()`
 *   mock never reached the component.
 * - Expects the endpoint to return `{ sessions: [...] }`.
 * - UI: "New Chat" button, "Search chats..." input, "Loading history...",
 *   "No chat history." empty state.
 *
 * The request must be stubbed via MSW so axios/XHR is intercepted. Setting
 * `global.fetch = jest.fn()` here breaks MSW interception.
 */

import React from 'react';
import { renderWithProviders, screen, fireEvent, waitFor } from '../../../tests/test-utils';
import ChatHistorySidebar from '../ChatHistorySidebar';
import { server } from '@/tests/mocks/server';
import { rest } from 'msw';

const dateStr = '2026-08-01T10:00:00.000Z';

// axios requests go to the backend baseURL (http://127.0.0.1:8000), so match
// the path against any origin rather than the relative localhost URL.
const mockSessions = (sessions: unknown[]) => {
  server.use(
    rest.get('*/api/chat/sessions', (req, res, ctx) => res(ctx.json({ sessions })))
  );
};

describe('ChatHistorySidebar', () => {
  const mockOnSelectSession = jest.fn();

  // Test 1: renders sidebar with new chat button
  test('renders sidebar with new chat button', () => {
    mockSessions([]);

    const { container } = renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    expect(container.textContent).toContain('New Chat');
  });

  // Test 2: shows search input
  test('shows search input', () => {
    mockSessions([]);

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    expect(screen.getByPlaceholderText('Search chats...')).toBeInTheDocument();
  });

  // Test 3: empty state shows placeholder
  test('empty state shows placeholder', async () => {
    mockSessions([]);

    const { container } = renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    await waitFor(() => {
      expect(container.textContent).toContain('No chat history.');
    });
  });

  // Test 4: loading state shows loading indicator
  test('loading state shows loading indicator', () => {
    // Delay the response so loading remains visible at assertion time.
    server.use(
      rest.get('*/api/chat/sessions', (req, res, ctx) =>
        res(ctx.delay(5000), ctx.json({ sessions: [] }))
      )
    );

    const { container } = renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    expect(container.textContent).toContain('Loading history...');
  });

  // Test 5: renders without errors
  test('renders without errors', () => {
    mockSessions([]);

    expect(() =>
      renderWithProviders(
        <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
      )
    ).not.toThrow();
  });

  // Test 6: renders sessions from an array response with title/preview/date
  test('renders sessions with title, preview and date', async () => {
    mockSessions([
      {
        session_id: 's-1',
        title: 'Launch planning',
        history: [{ message: 'We ship the announcement on Monday morning.' }],
        last_updated: dateStr,
      },
      {
        session_id: 's-2',
        title: 'Bug triage',
        history: [{ message: 'Fixed the login flow' }],
        created_at: '2026-07-20T10:00:00.000Z',
      },
      { session_id: 's-3', message_count: 12 },
    ]);

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    expect(await screen.findByText('Launch planning')).toBeInTheDocument();
    expect(screen.getByText('Bug triage')).toBeInTheDocument();
    expect(screen.getByText(new Date(dateStr).toLocaleDateString())).toBeInTheDocument();
    expect(screen.getByText('We ship the announcement on Monday morning.')).toBeInTheDocument();
    // No title/history/date → fallbacks: Untitled Chat, "N messages", Unknown
    expect(screen.getByText('Untitled Chat')).toBeInTheDocument();
    expect(screen.getByText('12 messages')).toBeInTheDocument();
    expect(screen.getByText('Unknown')).toBeInTheDocument();
  });

  // Test 7: supports dict-shaped sessions {session_id: {...}}
  test('renders sessions returned as a dict keyed by session id', async () => {
    mockSessions({
      's-1': { title: 'Dict session', history: [{ message: 'hello' }], last_active: dateStr },
      's-2': { title: 'Another one', history: [{ message: 'world' }], last_updated: dateStr },
    });

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    expect(await screen.findByText('Dict session')).toBeInTheDocument();
    expect(screen.getByText('Another one')).toBeInTheDocument();
  });

  // Test 8: filters out sessions with id "new" (reserved sentinel)
  test('filters out the "new" sentinel session', async () => {
    mockSessions([
      { session_id: 'new', title: 'Fake new chat' },
      { session_id: 'real-1', title: 'Real session', history: [{ message: 'hi' }], last_updated: dateStr },
    ]);

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    await screen.findByText('Real session');
    expect(screen.queryByText('Fake new chat')).not.toBeInTheDocument();
  });

  // Test 9: derives title and preview from the last history message
  test('derives title and preview from the last history message', async () => {
    mockSessions([
      {
        session_id: 's-1',
        history: [{ message: 'Let me check the numbers and get back to you' }],
        last_updated: dateStr,
      },
    ]);

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    expect(await screen.findByText('Let me check the numbers and get back to...')).toBeInTheDocument();
    expect(screen.getByText('Let me check the numbers and get back to you')).toBeInTheDocument();
  });

  // Test 10: clicking a session selects it
  test('selects a session on click', async () => {
    mockSessions([
      { session_id: 's-1', title: 'Click me', history: [{ message: 'hi' }], last_updated: dateStr },
    ]);

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    fireEvent.click(await screen.findByText('Click me'));
    expect(mockOnSelectSession).toHaveBeenCalledWith('s-1');
  });

  // Test 11: highlights the selected session
  test('highlights the selected session', async () => {
    mockSessions([
      { session_id: 's-1', title: 'Selected one', history: [{ message: 'hi' }], last_updated: dateStr },
    ]);

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId="s-1" onSelectSession={mockOnSelectSession} />
    );

    const row = (await screen.findByText('Selected one')).closest('.cursor-pointer') as HTMLElement;
    expect(row).toHaveClass('border-indigo-500/30');
    expect(row).toHaveClass('bg-slate-800');
  });

  // Test 12: search filters by title
  test('filters sessions by search query', async () => {
    mockSessions([
      { session_id: 's-1', title: 'Launch planning', history: [{ message: 'a' }], last_updated: dateStr },
      { session_id: 's-2', title: 'Bug triage', history: [{ message: 'b' }], last_updated: dateStr },
    ]);

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );
    await screen.findByText('Launch planning');

    fireEvent.change(screen.getByPlaceholderText('Search chats...'), {
      target: { value: 'launch' },
    });
    expect(screen.getByText('Launch planning')).toBeInTheDocument();
    expect(screen.queryByText('Bug triage')).not.toBeInTheDocument();
  });

  // Test 13: search matches previews and shows "No matches found." otherwise
  test('matches preview text and shows the no-matches empty state', async () => {
    mockSessions([
      { session_id: 's-1', title: 'Unrelated', history: [{ message: 'remember to review the Q3 numbers' }], last_updated: dateStr },
    ]);

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );
    await screen.findByText('Unrelated');

    fireEvent.change(screen.getByPlaceholderText('Search chats...'), {
      target: { value: 'Q3 numbers' },
    });
    expect(screen.getByText('Unrelated')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Search chats...'), {
      target: { value: 'zzz-no-match' },
    });
    expect(screen.getByText('No matches found.')).toBeInTheDocument();
  });

  // Test 14: empty history array renders the empty state
  test('shows "No chat history." for an empty sessions array', async () => {
    mockSessions([]);

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    await waitFor(() => {
      expect(screen.getByText('No chat history.')).toBeInTheDocument();
    });
  });

  // Test 15: non-200 status falls back to the empty state
  test('handles non-200 responses as a failure', async () => {
    server.use(
      rest.get('*/api/chat/sessions', (req, res, ctx) => res(ctx.status(201), ctx.json({ sessions: [] })))
    );
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    await waitFor(() => {
      expect(screen.getByText('No chat history.')).toBeInTheDocument();
    });
    expect(consoleSpy).toHaveBeenCalledWith('Error fetching chat history:', expect.anything());

    consoleSpy.mockRestore();
  });

  // Test 16: request failure (5xx) falls back to the empty state
  // NOTE: 5xx errors pass through the apiClient retry interceptor (1s/2s
  // exponential backoff), so the empty state takes ~3s to settle.
  test('handles request failures gracefully', async () => {
    server.use(
      rest.get('*/api/chat/sessions', (req, res, ctx) => res(ctx.status(500)))
    );
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    await waitFor(
      () => {
        expect(screen.getByText('No chat history.')).toBeInTheDocument();
      },
      { timeout: 10000 }
    );
    expect(consoleSpy).toHaveBeenCalledWith('Error fetching chat history:', expect.anything());

    consoleSpy.mockRestore();
  });

  // Test 17: "New Chat" button selects the new-chat sentinel
  test('new chat button selects the "new" sentinel', async () => {
    mockSessions([]);

    renderWithProviders(
      <ChatHistorySidebar selectedSessionId={null} onSelectSession={mockOnSelectSession} />
    );

    fireEvent.click(screen.getByRole('button', { name: /new chat/i }));
    expect(mockOnSelectSession).toHaveBeenCalledWith('new');
  });
});
