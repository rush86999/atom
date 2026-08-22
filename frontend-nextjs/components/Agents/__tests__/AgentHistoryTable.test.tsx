/**
 * AgentHistoryTable Component Tests
 *
 * Tests verify the real AgentHistoryTable component
 * (components/Agents/AgentHistoryTable.tsx, a NAMED export):
 * - Fetches GET {API_BASE}/api/agents/history on mount with auth token
 * - Empty state ("No history available.")
 * - Renders job rows (agent id, status badge, start time, result summary)
 * - Falls back to logs, then to "-" when no summary/logs present
 * - Handles fetch failures without crashing
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AgentHistoryTable } from '../AgentHistoryTable';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

// The component fetches with native fetch against NEXT_PUBLIC_API_URL
// (http://localhost:8000 in the jest env) — MSW must intercept that origin.
const historyUrl = '*/api/agents/history';

const jobs = [
  {
    id: 'job-1',
    agent_id: 'agent-1',
    status: 'success',
    start_time: '2024-01-15T10:00:00Z',
    end_time: '2024-01-15T10:00:30Z',
    logs: 'did stuff',
    result_summary: 'Completed 3 tasks',
  },
  {
    id: 'job-2',
    agent_id: 'agent-2',
    status: 'failed',
    start_time: '2024-01-14T09:00:00Z',
    end_time: '2024-01-14T09:00:05Z',
    logs: 'exhausted retries',
    result_summary: '',
  },
  {
    id: 'job-3',
    agent_id: 'agent-3',
    status: 'running',
    start_time: '2024-01-16T08:00:00Z',
    end_time: '',
    logs: '',
    result_summary: '',
  },
];

describe('AgentHistoryTable', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the card title and empty state when there is no history', async () => {
    server.use(
      rest.get(historyUrl, (req, res, ctx) => res(ctx.status(200), ctx.json([])))
    );
    render(<AgentHistoryTable />);

    expect(screen.getByText('Execution History')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('No history available.')).toBeInTheDocument();
    });
  });

  it('renders job rows with agent id, status, date and summary', async () => {
    server.use(
      rest.get(historyUrl, (req, res, ctx) => res(ctx.status(200), ctx.json(jobs)))
    );
    render(<AgentHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('agent-1')).toBeInTheDocument();
    });

    // Statuses rendered (lowercase — matches the backend AgentExecution values)
    expect(screen.getByText('success')).toBeInTheDocument();
    expect(screen.getByText('failed')).toBeInTheDocument();
    expect(screen.getByText('running')).toBeInTheDocument();

    // Formatted start times (ISO-8601 style "YYYY-MM-DD HH:MM" in UTC)
    expect(screen.getByText('2024-01-15 10:00')).toBeInTheDocument();
    expect(screen.getByText('2024-01-16 08:00')).toBeInTheDocument();

    // Result summary preferred over logs
    expect(screen.getByText('Completed 3 tasks')).toBeInTheDocument();
  });

  it('falls back to logs when result_summary is missing', async () => {
    server.use(
      rest.get(historyUrl, (req, res, ctx) => res(ctx.status(200), ctx.json(jobs)))
    );
    render(<AgentHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('exhausted retries')).toBeInTheDocument();
    });
  });

  it('renders a dash when neither summary nor logs exist', async () => {
    server.use(
      rest.get(historyUrl, (req, res, ctx) => res(ctx.status(200), ctx.json(jobs)))
    );
    render(<AgentHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('-')).toBeInTheDocument();
    });
  });

  it('sends the stored auth token as a Bearer header', async () => {
    let authHeader: string | null = null;
    server.use(
      rest.get(historyUrl, (req, res, ctx) => {
        authHeader = req.headers.get('Authorization');
        return res(ctx.status(200), ctx.json([]));
      })
    );
    // localStorage is a real jsdom Storage instance (setup.ts's mock assignment
    // does not survive the getter-only global) → spy on Storage.prototype.
    window.localStorage.setItem('auth_token', 'test-token-123');
    render(<AgentHistoryTable />);

    await waitFor(() => {
      expect(authHeader).toBe('Bearer test-token-123');
    });
    window.localStorage.removeItem('auth_token');
  });

  it('renders the empty state when the fetch returns a server error', async () => {
    server.use(
      rest.get(historyUrl, (req, res, ctx) => res(ctx.status(500), ctx.json({})))
    );
    render(<AgentHistoryTable />);

    // A server error surfaces the error message (distinct from the empty state)
    await waitFor(() => {
      expect(screen.getByTestId('execution-error-message')).toBeInTheDocument();
    });
  });

  it('logs the error when the request fails at the network level', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    server.use(
      rest.get(historyUrl, (req, res, ctx) => res.networkError('boom'))
    );
    render(<AgentHistoryTable />);

    await waitFor(() => {
      expect(screen.getByTestId('execution-error-message')).toBeInTheDocument();
    });
    expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to fetch history', expect.anything());
    consoleErrorSpy.mockRestore();
  });
});
