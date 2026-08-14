/**
 * LogsSidebar component tests.
 *
 * Uses the shared MSW server (tests/mocks/server) per repo convention.
 * Covers the empty state, log entry rendering, status icons, selection
 * expansion (inputs/outputs), refresh, close, fetch failure, and interval
 * cleanup on unmount.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { LogsSidebar } from '../LogsSidebar';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const LOGS = [
  {
    id: 'log-1',
    step_id: 'step-webhook',
    status: 'COMPLETED',
    duration_ms: 1250,
    created_at: '2026-08-14T10:00:00Z',
    trigger_data: { event: 'contact.created' },
    results: { ok: true },
  },
  {
    id: 'log-2',
    step_id: 'step-slack',
    status: 'FAILED',
    duration_ms: 42,
    created_at: '2026-08-14T09:00:00Z',
    trigger_data: null,
    results: null,
  },
];

const logsUrl = '/api/analytics/workflows/wf-1/logs';

describe('LogsSidebar', () => {
  const onClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    server.use(
      rest.get(logsUrl, (req, res, ctx) => res(ctx.json(LOGS)))
    );
  });

  it('shows the empty state when no logs are returned', async () => {
    server.use(rest.get(logsUrl, (req, res, ctx) => res(ctx.json([]))));
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    expect(screen.getByText('Execution History')).toBeInTheDocument();
    expect(await screen.findByText('No logs found yet.')).toBeInTheDocument();
  });

  it('renders log entries with step, status, duration and formatted time', async () => {
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    expect(await screen.findByText('step-webhook')).toBeInTheDocument();
    expect(screen.getByText('step-slack')).toBeInTheDocument();
    expect(screen.getByText('Duration: 1250ms')).toBeInTheDocument();
    expect(screen.getByText('Duration: 42ms')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('failed')).toBeInTheDocument();
  });

  it('renders a green check icon for completed and red x for failed logs', async () => {
    const { container } = render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    await screen.findByText('step-webhook');
    expect(container.querySelectorAll('svg.lucide-circle-check')).toHaveLength(1);
    expect(container.querySelectorAll('svg.lucide-circle-x')).toHaveLength(1);
  });

  it('expands a selected log to show inputs and outputs, and collapses on re-click', async () => {
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    fireEvent.click(await screen.findByText('step-webhook'));
    expect(screen.getByText('Inputs:')).toBeInTheDocument();
    expect(screen.getByText('Outputs:')).toBeInTheDocument();
    const expandedPre = document.querySelectorAll('pre')[0];
    expect(expandedPre).toHaveTextContent('"event": "contact.created"');

    fireEvent.click(screen.getByText('step-webhook'));
    expect(screen.queryByText('Inputs:')).not.toBeInTheDocument();
  });

  it('does not render input/output sections for logs without them', async () => {
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    fireEvent.click(await screen.findByText('step-slack'));
    expect(screen.queryByText('Inputs:')).not.toBeInTheDocument();
    expect(screen.queryByText('Outputs:')).not.toBeInTheDocument();
  });

  it('re-fetches logs when the refresh button is clicked', async () => {
    let requests = 0;
    server.use(
      rest.get(logsUrl, (req, res, ctx) => {
        requests += 1;
        return res(ctx.json(LOGS));
      })
    );
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    await screen.findByText('step-webhook');
    expect(requests).toBe(1);
    fireEvent.click(screen.getAllByRole('button')[0]);
    await waitFor(() => expect(requests).toBeGreaterThanOrEqual(2));
  });

  it('calls onClose when the close button is clicked', async () => {
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);
    await screen.findByText('step-webhook');

    fireEvent.click(screen.getByRole('button', { name: '×' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('keeps the empty state when the response is not ok', async () => {
    server.use(rest.get(logsUrl, (req, res, ctx) => res(ctx.status(500))));
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    expect(await screen.findByText('No logs found yet.')).toBeInTheDocument();
  });

  it('logs an error and stops loading when the fetch rejects', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    server.use(rest.get(logsUrl, (req, res, ctx) => res.networkError('network down')));
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    expect(screen.getByText('No logs found yet.')).toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  it('clears the polling interval on unmount', async () => {
    const clearIntervalSpy = jest.spyOn(global, 'clearInterval');
    const { unmount } = render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);
    await screen.findByText('step-webhook');

    unmount();
    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });
});
