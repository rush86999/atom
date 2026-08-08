/**
 * VerificationLogs component tests.
 *
 * Covers the REAL VerificationLogs (components/admin/jit-verification/VerificationLogs.tsx):
 * - Fetches logs from /api/admin/governance/jit/logs?time_range=... on mount
 * - Renders stats (Total/Info/Warnings/Errors), log entries with level badges
 *   and citation links
 * - Empty response renders the "No logs found" empty state
 * - Time-range select triggers a refetch with the new time_range
 * - Log-level select filters the rendered entries
 * - Refresh re-fetches (guards the removed-mockLogs regression: clicking Refresh
 *   used to throw ReferenceError: mockLogs is not defined)
 * - Export CSV triggers a download + toast
 *
 * fetch is mocked directly (pattern: components/Debugging/__tests__/SessionPersistence.test.tsx).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { VerificationLogs } from '../VerificationLogs';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const sampleLogs = [
  {
    timestamp: '2026-08-07T10:00:00Z',
    event: 'Worker cycle started',
    details: 'Batch of 50 facts',
    level: 'info',
  },
  {
    timestamp: '2026-08-07T10:01:00Z',
    event: 'Cache entry evicted',
    citation: 'https://bucket.s3.amazonaws.com/handbook.pdf',
    level: 'warning',
  },
  {
    timestamp: '2026-08-07T10:02:00Z',
    event: 'Verification failed',
    details: 'Connection timeout',
    level: 'error',
  },
];

describe('VerificationLogs', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ logs: sampleLogs }),
    });
  });

  it('fetches logs on mount with the default 24h time range and renders stats', async () => {
    render(<VerificationLogs />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/admin/governance/jit/logs?time_range=24h');
    });

    // Stats cards
    expect(await screen.findByText('Verification Activity Logs')).toBeInTheDocument();
    expect(screen.getByText('Total Events')).toBeInTheDocument();
    expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Info')).toBeInTheDocument();
    expect(screen.getByText('Warnings')).toBeInTheDocument();
    expect(screen.getByText('Errors')).toBeInTheDocument();

    // Log entries with level badges and details
    expect(screen.getByText('Worker cycle started')).toBeInTheDocument();
    expect(screen.getByText('Batch of 50 facts')).toBeInTheDocument();
    expect(screen.getByText('INFO')).toBeInTheDocument();
    expect(screen.getByText('WARNING')).toBeInTheDocument();
    expect(screen.getByText('ERROR')).toBeInTheDocument();
    expect(screen.getByText('Verification failed')).toBeInTheDocument();
    expect(screen.getByText('https://bucket.s3.amazonaws.com/handbook.pdf')).toBeInTheDocument();
  });

  it('handles a failed fetch by showing the empty state', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('network down'));
    render(<VerificationLogs />);

    expect(await screen.findByText('No logs found')).toBeInTheDocument();
    expect(screen.getByText('Try changing the filter or time range')).toBeInTheDocument();
  });

  it('renders the empty state when the API returns no logs', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ logs: [] }) });
    render(<VerificationLogs />);

    expect(await screen.findByText('No logs found')).toBeInTheDocument();
    expect(screen.getByText('0 entries')).toBeInTheDocument();
  });

  it('changes the time range and refetches with the new parameter', async () => {
    render(<VerificationLogs />);
    await screen.findByText('Worker cycle started');

    const combos = screen.getAllByRole('combobox');
    fireEvent.click(combos[1]); // time range select
    const option = await screen.findByRole('option', { name: 'Last Hour' });
    fireEvent.click(option);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/admin/governance/jit/logs?time_range=1h');
    });
  });

  it('filters log entries by level', async () => {
    render(<VerificationLogs />);
    await screen.findByText('Worker cycle started');

    const combos = screen.getAllByRole('combobox');
    fireEvent.click(combos[0]); // log level select
    const option = await screen.findByRole('option', { name: 'Error' });
    fireEvent.click(option);

    expect(screen.getByText('Verification failed')).toBeInTheDocument();
    expect(screen.queryByText('Worker cycle started')).not.toBeInTheDocument();
    expect(screen.queryByText('Cache entry evicted')).not.toBeInTheDocument();
    expect(screen.getByText('1 entries')).toBeInTheDocument();
  });

  it('refreshes by re-fetching the API (no longer references removed mockLogs)', async () => {
    render(<VerificationLogs />);
    await screen.findByText('Worker cycle started');

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        logs: [{ timestamp: '2026-08-07T11:00:00Z', event: 'Fresh cycle started', level: 'info' }],
      }),
    });

    fireEvent.click(screen.getByRole('button', { name: /Refresh/ }));

    await waitFor(() => {
      expect(screen.getByText('Fresh cycle started')).toBeInTheDocument();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Logs refreshed' })
    );
    // Original setLogs replaced — old entries are gone
    expect(screen.queryByText('Worker cycle started')).not.toBeInTheDocument();
  });

  it('exports the filtered logs as CSV and toasts', async () => {
    render(<VerificationLogs />);
    await screen.findByText('Worker cycle started');

    fireEvent.click(screen.getByRole('button', { name: /Export CSV/ }));

    expect(global.URL.createObjectURL).toHaveBeenCalled();
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Logs exported', description: '3 log entries exported as CSV' })
    );
  });
});
