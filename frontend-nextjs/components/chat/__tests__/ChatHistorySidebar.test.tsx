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
import { renderWithProviders, screen, waitFor } from '../../../tests/test-utils';
import ChatHistorySidebar from '../ChatHistorySidebar';
import { server } from '@/tests/mocks/server';
import { rest } from 'msw';

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
});
