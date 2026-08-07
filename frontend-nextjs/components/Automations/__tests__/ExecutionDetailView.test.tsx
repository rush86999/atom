/**
 * ExecutionDetailView Component Tests
 *
 * Tests verify the real ExecutionDetailView component
 * (components/Automations/ExecutionDetailView.tsx, a DEFAULT export):
 * - Loading state on mount
 * - Fetches GET /api/v1/workflows/executions/:id and renders details
 * - Status badge, duration formatting, ID, errors alert
 * - Trigger data + node results rendering (accordion output/error)
 * - Empty results fallback message
 * - Error state (fetch failure) with back button
 * - onBack callback on "Back to History"
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file server.use() overrides are reset automatically.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import ExecutionDetailView from '../ExecutionDetailView';
import { rest as mswRest } from 'msw';
import { server } from '@/tests/mocks/server';

const rest = mswRest;

const executionDetail = {
  execution_id: 'exec-1',
  workflow_id: 'wf-1',
  status: 'success',
  start_time: '2024-01-15T10:00:00Z',
  end_time: '2024-01-15T10:00:05Z',
  duration_ms: 5234,
  results: {
    'node-1': { status: 'success', node_title: 'Fetch Lead', output: { id: 42 }, error: null },
    'node-2': { status: 'failed', node_title: 'Enrich Lead', output: {}, error: 'API timeout' },
  },
  errors: ['Node node-2 failed: API timeout'],
  trigger_data: { source: 'hubspot', contact: { email: 'a@b.com' } },
};

const executionUrl = '/api/v1/workflows/executions/exec-1';

describe('ExecutionDetailView', () => {
  const mockOnBack = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows the loading state on mount', () => {
    server.use(
      rest.get(executionUrl, (req, res, ctx) => res(ctx.json(executionDetail)))
    );
    render(<ExecutionDetailView executionId="exec-1" onBack={mockOnBack} />);

    expect(screen.getByText('Loading execution details...')).toBeInTheDocument();
  });

  it('renders execution header, status badge, duration and ID after fetch', async () => {
    server.use(
      rest.get(executionUrl, (req, res, ctx) => res(ctx.json(executionDetail)))
    );
    render(<ExecutionDetailView executionId="exec-1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Execution Details')).toBeInTheDocument();
    });

    // Status badge is uppercased
    expect(screen.getByText('SUCCESS')).toBeInTheDocument();
    // Duration rendered as seconds with 2 decimals
    expect(screen.getByText('5.23s')).toBeInTheDocument();
    // Execution ID rendered in mono block
    expect(screen.getByText('exec-1')).toBeInTheDocument();
    expect(screen.getByText('Started')).toBeInTheDocument();
  });

  it('renders execution errors alert when errors are present', async () => {
    server.use(
      rest.get(executionUrl, (req, res, ctx) => res(ctx.json(executionDetail)))
    );
    render(<ExecutionDetailView executionId="exec-1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Execution Errors:')).toBeInTheDocument();
    });
    expect(screen.getByText('Node node-2 failed: API timeout')).toBeInTheDocument();
  });

  it('renders trigger data as pretty-printed JSON', async () => {
    server.use(
      rest.get(executionUrl, (req, res, ctx) => res(ctx.json(executionDetail)))
    );
    render(<ExecutionDetailView executionId="exec-1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Trigger Data')).toBeInTheDocument();
    });

    const pre = screen.getByText((content, element) =>
      element?.tagName === 'PRE' && content.includes('"source": "hubspot"')
    );
    expect(pre).toBeInTheDocument();
    expect(pre.textContent).toContain('"email": "a@b.com"');
  });

  it('renders node results with per-node output and error blocks', async () => {
    const user = userEvent.setup();
    server.use(
      rest.get(executionUrl, (req, res, ctx) => res(ctx.json(executionDetail)))
    );
    render(<ExecutionDetailView executionId="exec-1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Execution Details')).toBeInTheDocument();
    });

    // Node titles
    expect(screen.getByText('Fetch Lead')).toBeInTheDocument();
    expect(screen.getByText('Enrich Lead')).toBeInTheDocument();
    // Per-node status badges
    expect(screen.getByText('success')).toBeInTheDocument();
    expect(screen.getByText('failed')).toBeInTheDocument();

    // First node is open by default (Accordion defaultValue=["0"]) → OUTPUT block
    expect(screen.getByText('Node Execution Results')).toBeInTheDocument();
    expect(screen.getByText('OUTPUT')).toBeInTheDocument();
    const outputPre = screen.getByText((content, element) =>
      element?.tagName === 'PRE' && content.includes('"id": 42')
    );
    expect(outputPre).toBeInTheDocument();

    // Expand the second (failed) node → its ERROR block becomes visible
    await user.click(screen.getByText('Enrich Lead'));
    await waitFor(() => {
      expect(screen.getByText('API timeout')).toBeInTheDocument();
    });
  });

  it('shows a fallback message when there are no node results', async () => {
    server.use(
      rest.get(executionUrl, (req, res, ctx) =>
        res(ctx.json({ ...executionDetail, results: {} }))
      )
    );
    render(<ExecutionDetailView executionId="exec-1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('No node results recorded.')).toBeInTheDocument();
    });
  });

  it('renders a dash for duration when duration_ms is missing', async () => {
    const baseDetail = { ...executionDetail };
    delete (baseDetail as any).duration_ms;
    server.use(
      rest.get(executionUrl, (req, res, ctx) =>
        res(ctx.json(baseDetail))
      )
    );
    render(<ExecutionDetailView executionId="exec-1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('-')).toBeInTheDocument();
    });
  });

  it('shows an error alert and back button when the fetch fails', async () => {
    server.use(
      rest.get(executionUrl, (req, res, ctx) => res(ctx.status(500), ctx.json({})))
    );
    render(<ExecutionDetailView executionId="exec-1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Failed to fetch execution details')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /back to history/i })).toBeInTheDocument();
  });

  it('calls onBack when the back button is clicked', async () => {
    server.use(
      rest.get(executionUrl, (req, res, ctx) => res(ctx.json(executionDetail)))
    );
    const user = userEvent.setup();
    render(<ExecutionDetailView executionId="exec-1" onBack={mockOnBack} />);

    const backButton = await screen.findByRole('button', { name: /back to history/i });
    await user.click(backButton);
    expect(mockOnBack).toHaveBeenCalledTimes(1);
  });

  it('fetches the execution for the provided executionId', async () => {
    let requestedUrl: string | null = null;
    server.use(
      rest.get(executionUrl, (req, res, ctx) => {
        requestedUrl = req.url.pathname;
        return res(ctx.json(executionDetail));
      })
    );
    render(<ExecutionDetailView executionId="exec-1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(requestedUrl).toBe('/api/v1/workflows/executions/exec-1');
    });
  });
});
