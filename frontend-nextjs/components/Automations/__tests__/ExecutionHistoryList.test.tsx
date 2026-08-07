/**
 * ExecutionHistoryList Component Tests
 *
 * Tests verify the real ExecutionHistoryList component
 * (components/Automations/ExecutionHistoryList.tsx, a DEFAULT export):
 * - Loading spinner on mount
 * - Fetches GET /api/v1/workflows/:id/executions and renders rows
 * - Status badges + icons, formatted dates/durations, node counts
 * - Row click and eye-button click invoke onSelectExecution
 * - Empty state and error state
 * - Refetch when refreshTrigger prop changes
 *
 * Uses the shared MSW server (tests/mocks/server.ts).
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import ExecutionHistoryList from '../ExecutionHistoryList';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const executions = [
  {
    execution_id: 'e1',
    workflow_id: 'wf-1',
    status: 'success',
    start_time: '2024-01-15T10:00:00Z',
    end_time: '2024-01-15T10:00:05Z',
    duration_ms: 5234,
    actions_executed: ['fetch-lead', 'enrich-lead', 'notify'],
    errors: [],
  },
  {
    execution_id: 'e2',
    workflow_id: 'wf-1',
    status: 'failed',
    start_time: '2024-01-14T09:00:00Z',
    end_time: '2024-01-14T09:00:00Z',
    duration_ms: 250,
    actions_executed: [],
    errors: ['boom'],
  },
  {
    execution_id: 'e3',
    workflow_id: 'wf-1',
    status: 'running',
    start_time: '2024-01-16T08:00:00Z',
    duration_ms: undefined,
    actions_executed: [],
    errors: [],
  },
];

const historyUrl = '/api/v1/workflows/wf-1/executions';

describe('ExecutionHistoryList', () => {
  const mockOnSelectExecution = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    server.use(
      rest.get(historyUrl, (req, res, ctx) => res(ctx.json(executions)))
    );
  });

  it('shows a spinner while loading on first render', () => {
    render(
      <ExecutionHistoryList workflowId="wf-1" onSelectExecution={mockOnSelectExecution} />
    );
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('renders execution rows with status, date, duration and action counts', async () => {
    render(
      <ExecutionHistoryList workflowId="wf-1" onSelectExecution={mockOnSelectExecution} />
    );

    await waitFor(() => {
      expect(screen.getByText('success')).toBeInTheDocument();
      expect(screen.getByText('failed')).toBeInTheDocument();
      expect(screen.getByText('running')).toBeInTheDocument();
    });

    // Durations: seconds with 2 decimals, milliseconds, dash when absent
    expect(screen.getByText('5.23s')).toBeInTheDocument();
    expect(screen.getByText('250ms')).toBeInTheDocument();
    expect(screen.getByText('-')).toBeInTheDocument();

    // Action counts
    expect(screen.getByText('3 nodes')).toBeInTheDocument();
    expect(screen.getAllByText('0 nodes')).toHaveLength(2);

    // Dates are locale-formatted
    expect(screen.getByText(new Date('2024-01-15T10:00:00Z').toLocaleString())).toBeInTheDocument();
    expect(screen.getByText(new Date('2024-01-16T08:00:00Z').toLocaleString())).toBeInTheDocument();
  });

  it('renders table headers', async () => {
    render(
      <ExecutionHistoryList workflowId="wf-1" onSelectExecution={mockOnSelectExecution} />
    );

    await waitFor(() => {
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Date')).toBeInTheDocument();
      expect(screen.getByText('Duration')).toBeInTheDocument();
      expect(screen.getByText('Actions')).toBeInTheDocument();
      expect(screen.getByText('Details')).toBeInTheDocument();
    });
  });

  it('calls onSelectExecution when a row is clicked', async () => {
    const user = userEvent.setup();
    render(
      <ExecutionHistoryList workflowId="wf-1" onSelectExecution={mockOnSelectExecution} />
    );

    // Duration of e1's row is unique on the page
    const duration = await screen.findByText('5.23s');
    await user.click(duration);

    expect(mockOnSelectExecution).toHaveBeenCalledTimes(1);
    expect(mockOnSelectExecution).toHaveBeenCalledWith('e1');
  });

  it('calls onSelectExecution exactly once when the eye button is clicked', async () => {
    const user = userEvent.setup();
    render(
      <ExecutionHistoryList workflowId="wf-1" onSelectExecution={mockOnSelectExecution} />
    );

    const buttons = await screen.findAllByRole('button');
    // stopPropagation must prevent the row handler from double-firing
    await user.click(buttons[0]);

    expect(mockOnSelectExecution).toHaveBeenCalledTimes(1);
    expect(mockOnSelectExecution).toHaveBeenCalledWith('e1');
  });

  it('renders the empty state when there are no executions', async () => {
    server.use(
      rest.get(historyUrl, (req, res, ctx) => res(ctx.json([])))
    );
    render(
      <ExecutionHistoryList workflowId="wf-1" onSelectExecution={mockOnSelectExecution} />
    );

    await waitFor(() => {
      expect(screen.getByText('No execution history found for this workflow.')).toBeInTheDocument();
    });
    expect(screen.getByText('Run the workflow to see results here.')).toBeInTheDocument();
  });

  it('renders the error state when the fetch fails', async () => {
    server.use(
      rest.get(historyUrl, (req, res, ctx) => res(ctx.status(500), ctx.json({})))
    );
    render(
      <ExecutionHistoryList workflowId="wf-1" onSelectExecution={mockOnSelectExecution} />
    );

    await waitFor(() => {
      expect(screen.getByText(/Error loading history: Failed to fetch execution history/i)).toBeInTheDocument();
    });
  });

  it('refetches history when the refreshTrigger prop changes', async () => {
    let requestCount = 0;
    server.use(
      rest.get(historyUrl, (req, res, ctx) => {
        requestCount += 1;
        return res(ctx.json(executions));
      })
    );

    const { rerender } = render(
      <ExecutionHistoryList workflowId="wf-1" onSelectExecution={mockOnSelectExecution} refreshTrigger={0} />
    );

    await waitFor(() => expect(requestCount).toBe(1));

    rerender(
      <ExecutionHistoryList workflowId="wf-1" onSelectExecution={mockOnSelectExecution} refreshTrigger={1} />
    );

    await waitFor(() => expect(requestCount).toBe(2));
  });

  it('does not fetch when workflowId is empty', () => {
    let requestCount = 0;
    server.use(
      rest.get('/api/v1/workflows//executions', (req, res, ctx) => {
        requestCount += 1;
        return res(ctx.json([]));
      })
    );

    render(
      <ExecutionHistoryList workflowId="" onSelectExecution={mockOnSelectExecution} />
    );

    expect(requestCount).toBe(0);
  });
});
