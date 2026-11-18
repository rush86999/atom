/**
 * LogsSidebar component tests.
 *
 * Uses the shared MSW server (tests/mocks/server) per repo convention.
 * Covers the canonical receipt endpoint, signed-in Bearer auth, empty vs.
 * failed/malformed responses, receipt-only expansion, refresh, close,
 * polling cleanup, and workflow-switch races with deferred responses.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { LogsSidebar } from '../LogsSidebar';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const WORKFLOW_ONE_LOGS_URL = '/api/v1/analytics/workflows/wf-1/logs';
const WORKFLOW_TWO_LOGS_URL = '/api/v1/analytics/workflows/wf-2/logs';

const LOGS = [
  {
    id: 'log-1',
    workflow_id: 'wf-1',
    execution_id: 'exec-1',
    step_id: 'step-webhook',
    status: 'COMPLETED',
    duration_ms: 1250,
    created_at: '2026-08-14T10:00:00Z',
    updated_at: '2026-08-14T10:00:01Z',
    // These are deliberately part of the mock payload to prove they are never
    // rendered: the receipt contract is metadata only.
    trigger_data: { event: 'contact.created' },
    results: { ok: true },
  },
  {
    id: 'log-2',
    workflow_id: 'wf-1',
    execution_id: 'exec-2',
    step_id: 'step-slack',
    status: 'FAILED',
    duration_ms: 42,
    created_at: '2026-08-14T09:00:00Z',
    trigger_data: null,
    results: null,
  },
];

const WORKFLOW_TWO_LOGS = [
  {
    id: 'log-new',
    workflow_id: 'wf-2',
    execution_id: 'exec-new',
    step_id: 'step-new',
    status: 'COMPLETED',
    duration_ms: 7,
    created_at: '2026-08-15T11:00:00Z',
  },
];

function deferred() {
  let resolve!: () => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<void>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe('LogsSidebar', () => {
  const onClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    server.use(
      rest.get(WORKFLOW_ONE_LOGS_URL, (req, res, ctx) => res(ctx.json(LOGS)))
    );
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('shows the empty state when no logs are returned', async () => {
    server.use(rest.get(WORKFLOW_ONE_LOGS_URL, (req, res, ctx) => res(ctx.json([]))));
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    expect(screen.getByText('Execution History')).toBeInTheDocument();
    expect(await screen.findByText('No logs found yet.')).toBeInTheDocument();
  });

  it('requests the canonical encoded logs endpoint', async () => {
    let requestedPath = '';
    server.use(
      rest.get('/api/v1/analytics/workflows/:workflowId/logs', (req, res, ctx) => {
        requestedPath = req.url.pathname;
        return res(ctx.json([]));
      })
    );

    render(<LogsSidebar workflowId="wf 1/2" onClose={onClose} />);
    await screen.findByText('No logs found yet.');

    expect(requestedPath).toBe('/api/v1/analytics/workflows/wf%201%2F2/logs');
  });

  it('sends the signed-in auth_token as a Bearer header', async () => {
    let authorization: string | null = null;
    localStorage.setItem('auth_token', 'signed-in-token');
    server.use(
      rest.get(WORKFLOW_ONE_LOGS_URL, (req, res, ctx) => {
        authorization = req.headers.get('authorization');
        return res(ctx.json(LOGS));
      })
    );

    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);
    await screen.findByText('step-webhook');

    expect(authorization).toBe('Bearer signed-in-token');
  });

  it('does not attach an Authorization header when no token is stored', async () => {
    let authorization: string | null = 'not-requested';
    server.use(
      rest.get(WORKFLOW_ONE_LOGS_URL, (req, res, ctx) => {
        authorization = req.headers.get('authorization');
        return res(ctx.json(LOGS));
      })
    );

    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);
    await screen.findByText('step-webhook');

    expect(authorization).toBeNull();
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

  it('expands a selected log to show receipt metadata only', async () => {
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    const receiptRow = await screen.findByText('step-webhook');
    fireEvent.click(receiptRow);

    expect(screen.getByText('Execution ID')).toBeInTheDocument();
    expect(screen.getByText('exec-1')).toBeInTheDocument();
    expect(screen.getByText('Workflow ID')).toBeInTheDocument();
    expect(screen.getByText('wf-1')).toBeInTheDocument();
    expect(screen.getByText('Log ID')).toBeInTheDocument();
    expect(screen.getByText('log-1')).toBeInTheDocument();

    // Raw execution payload fields must never be displayed.
    expect(screen.queryByText('Inputs:')).not.toBeInTheDocument();
    expect(screen.queryByText('Outputs:')).not.toBeInTheDocument();
    expect(screen.queryByText(/contact\.created/)).not.toBeInTheDocument();
    expect(screen.queryByText(/"ok": true/)).not.toBeInTheDocument();

    fireEvent.click(receiptRow);
    expect(screen.queryByText('Execution ID')).not.toBeInTheDocument();
  });

  it('re-fetches logs when the refresh button is clicked', async () => {
    let requests = 0;
    server.use(
      rest.get(WORKFLOW_ONE_LOGS_URL, (req, res, ctx) => {
        requests += 1;
        return res(ctx.json(LOGS));
      })
    );
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    await screen.findByText('step-webhook');
    expect(requests).toBe(1);
    fireEvent.click(screen.getByRole('button', { name: 'Refresh logs' }));
    await waitFor(() => expect(requests).toBeGreaterThanOrEqual(2));
  });

  it('calls onClose when the close button is clicked', async () => {
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);
    await screen.findByText('step-webhook');

    fireEvent.click(screen.getByRole('button', { name: '×' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows an error, not the empty state, when the response is not ok', async () => {
    server.use(rest.get(WORKFLOW_ONE_LOGS_URL, (req, res, ctx) => res(ctx.status(500))));
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Failed to load logs.');
    expect(screen.queryByText('No logs found yet.')).not.toBeInTheDocument();
  });

  it('shows an error, not the empty state, for malformed JSON', async () => {
    server.use(rest.get(WORKFLOW_ONE_LOGS_URL, (req, res, ctx) => res(ctx.text('not-json'))));
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Failed to load logs.');
    expect(screen.queryByText('No logs found yet.')).not.toBeInTheDocument();
  });

  it('shows an error, not the empty state, for an unexpected response shape', async () => {
    server.use(rest.get(WORKFLOW_ONE_LOGS_URL, (req, res, ctx) => res(ctx.json({ logs: LOGS }))));
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Failed to load logs.');
    expect(screen.queryByText('No logs found yet.')).not.toBeInTheDocument();
  });

  it('logs an error and shows the error state when the fetch rejects', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    server.use(rest.get(WORKFLOW_ONE_LOGS_URL, (req, res, ctx) => res.networkError('network down')));
    render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);

    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to load logs.');
    expect(screen.queryByText('No logs found yet.')).not.toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  it('immediately hides the previous list and selection when the workflow changes', async () => {
    const secondResponse = deferred();
    let secondRequestStarted = false;

    server.use(
      rest.get(WORKFLOW_TWO_LOGS_URL, async (req, res, ctx) => {
        secondRequestStarted = true;
        await secondResponse.promise;
        return res(ctx.json(WORKFLOW_TWO_LOGS));
      })
    );

    const { rerender } = render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);
    fireEvent.click(await screen.findByText('step-webhook'));
    expect(screen.getByText('exec-1')).toBeInTheDocument();

    rerender(<LogsSidebar workflowId="wf-2" onClose={onClose} />);

    // The old list and selected detail disappear in the same render as the
    // switch, before the new workflow's deferred response resolves.
    expect(screen.queryByText('step-webhook')).not.toBeInTheDocument();
    expect(screen.queryByText('exec-1')).not.toBeInTheDocument();
    expect(screen.getByText('Loading logs…')).toBeInTheDocument();

    await waitFor(() => expect(secondRequestStarted).toBe(true));
    await act(async () => {
      secondResponse.resolve();
      await secondResponse.promise;
    });

    expect(await screen.findByText('step-new')).toBeInTheDocument();
    expect(screen.queryByText('step-webhook')).not.toBeInTheDocument();
  });

  it('ignores a stale deferred response that resolves after switching workflows', async () => {
    const firstResponse = deferred();
    const secondResponse = deferred();
    let firstRequestStarted = false;
    let secondRequestStarted = false;

    server.use(
      rest.get(WORKFLOW_ONE_LOGS_URL, async (req, res, ctx) => {
        firstRequestStarted = true;
        await firstResponse.promise;
        return res(ctx.json(LOGS));
      }),
      rest.get(WORKFLOW_TWO_LOGS_URL, async (req, res, ctx) => {
        secondRequestStarted = true;
        await secondResponse.promise;
        return res(ctx.json(WORKFLOW_TWO_LOGS));
      })
    );

    const { rerender } = render(<LogsSidebar workflowId="wf-1" onClose={onClose} />);
    await waitFor(() => expect(firstRequestStarted).toBe(true));

    rerender(<LogsSidebar workflowId="wf-2" onClose={onClose} />);
    await waitFor(() => expect(secondRequestStarted).toBe(true));

    await act(async () => {
      secondResponse.resolve();
      await secondResponse.promise;
    });
    expect(await screen.findByText('step-new')).toBeInTheDocument();

    // The first workflow response lands late. Even though the browser may or
    // may not have cancelled it, it must not replace workflow two's data.
    await act(async () => {
      firstResponse.resolve();
      await firstResponse.promise;
    });
    await waitFor(() => expect(screen.queryByText('step-new')).toBeInTheDocument());
    expect(screen.queryByText('step-webhook')).not.toBeInTheDocument();
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
