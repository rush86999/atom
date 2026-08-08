/**
 * WorkerStatusMonitor component tests.
 *
 * Covers the REAL WorkerStatusMonitor (components/admin/jit-verification/WorkerStatusMonitor.tsx):
 * - Running/stopped states with the correct control button and badges
 * - Run information (Last Run / Duration / Next Run) when running
 * - Verification metrics: totals, success rate %, avg time (ms vs s)
 * - Top citations list with access badges + "Most Accessed" marker
 * - Warning indicators for stale facts / failures
 * - Start/Stop worker API calls with toast + onUpdate on success and error paths
 *
 * jitVerificationAPI is mocked at module level.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { WorkerStatusMonitor } from '../WorkerStatusMonitor';
import { jitVerificationAPI } from '@/lib/api-admin';
import type { WorkerMetricsResponse } from '@/types/jit-verification';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

jest.mock('@/lib/api-admin', () => ({
  jitVerificationAPI: {
    startWorker: jest.fn(),
    stopWorker: jest.fn(),
  },
}));

const startWorkerMock = jitVerificationAPI.startWorker as jest.Mock;
const stopWorkerMock = jitVerificationAPI.stopWorker as jest.Mock;

const runningMetrics: WorkerMetricsResponse = {
  running: true,
  total_citations: 3,
  verified_count: 2,
  failed_count: 1,
  stale_facts: 2,
  outdated_facts: 1,
  last_run_time: new Date().toISOString(),
  last_run_duration: 125,
  average_verification_time: 0.4,
  top_citations: [
    { citation: 'https://bucket.s3.amazonaws.com/policy.pdf', access_count: 42 },
    { citation: 'https://bucket.s3.amazonaws.com/handbook.pdf', access_count: 30 },
  ],
};

const stoppedMetrics: WorkerMetricsResponse = {
  running: false,
  total_citations: 0,
  verified_count: 0,
  failed_count: 0,
  stale_facts: 0,
  outdated_facts: 0,
  last_run_duration: 0,
  average_verification_time: 0,
  top_citations: [],
};

describe('WorkerStatusMonitor', () => {
  const onUpdate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    startWorkerMock.mockResolvedValue({ data: { status: 'ok' } });
    stopWorkerMock.mockResolvedValue({ data: { status: 'ok' } });
  });

  it('renders the running state with metrics, run info, and a Stop button', () => {
    render(<WorkerStatusMonitor metrics={runningMetrics} onUpdate={onUpdate} />);

    expect(screen.getByText('Verification Worker')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Worker Active')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Stop Worker/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Start Worker/ })).not.toBeInTheDocument();

    // Run info
    expect(screen.getByText('Last Run')).toBeInTheDocument();
    expect(screen.getByText('Just now')).toBeInTheDocument();
    expect(screen.getByText('Duration')).toBeInTheDocument();
    expect(screen.getByText('2m 5s')).toBeInTheDocument(); // 125s
    expect(screen.getByText('Next Run')).toBeInTheDocument();
    expect(screen.getByText(/^(In \d+m|In \d+h \d+m|Due now)$/)).toBeInTheDocument();

    // Metrics
    expect(screen.getByText('66.7%')).toBeInTheDocument(); // 2/3 success rate
    expect(screen.getByText('400ms')).toBeInTheDocument(); // avg 0.4s < 1s -> ms

    // Top citations
    expect(screen.getByText('Top Citations (by access)')).toBeInTheDocument();
    expect(screen.getByText('https://bucket.s3.amazonaws.com/policy.pdf')).toBeInTheDocument();
    expect(screen.getByText('42x')).toBeInTheDocument();
    expect(screen.getByText('Most Accessed')).toBeInTheDocument();

    // Warnings
    expect(screen.getByText('Attention Required')).toBeInTheDocument();
    expect(screen.getByText('• 2 business facts have outdated citations')).toBeInTheDocument();
    expect(screen.getByText('• 1 verification failures detected')).toBeInTheDocument();
  });

  it('renders the stopped state with a Start button and no run info', () => {
    render(<WorkerStatusMonitor metrics={stoppedMetrics} onUpdate={onUpdate} />);

    expect(screen.getByText('Stopped')).toBeInTheDocument();
    expect(screen.getByText('Worker Stopped')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Start Worker/ })).toBeInTheDocument();

    // No run info when not running
    expect(screen.queryByText('Last Run')).not.toBeInTheDocument();
    expect(screen.queryByText('Next Run')).not.toBeInTheDocument();
    // Success rate 0.0 when no citations (rendered as "0.0" + "%" text nodes)
    expect(screen.getByText(/0\.0%/)).toBeInTheDocument();
    // No warnings when clean
    expect(screen.queryByText('Attention Required')).not.toBeInTheDocument();
  });

  it('shows "Not scheduled" and a dash for duration when there is no last run', () => {
    render(
      <WorkerStatusMonitor
        metrics={{ ...runningMetrics, last_run_time: undefined, last_run_duration: 0 }}
        onUpdate={onUpdate}
      />
    );

    expect(screen.getByText('Not scheduled')).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.getByText('Never')).toBeInTheDocument();
  });

  it('starts the worker, toasts, and calls onUpdate', async () => {
    render(<WorkerStatusMonitor metrics={stoppedMetrics} onUpdate={onUpdate} />);

    fireEvent.click(screen.getByRole('button', { name: /Start Worker/ }));

    await waitFor(() => {
      expect(startWorkerMock).toHaveBeenCalled();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Worker started' })
    );
    expect(onUpdate).toHaveBeenCalled();
  });

  it('toasts an error when starting the worker fails', async () => {
    startWorkerMock.mockRejectedValue({ userMessage: 'cannot start' });
    render(<WorkerStatusMonitor metrics={stoppedMetrics} onUpdate={onUpdate} />);

    fireEvent.click(screen.getByRole('button', { name: /Start Worker/ }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Failed to start worker', description: 'cannot start', variant: 'destructive' })
      );
    });
    expect(onUpdate).not.toHaveBeenCalled();
  });

  it('stops the worker, toasts, and calls onUpdate', async () => {
    render(<WorkerStatusMonitor metrics={runningMetrics} onUpdate={onUpdate} />);

    fireEvent.click(screen.getByRole('button', { name: /Stop Worker/ }));

    await waitFor(() => {
      expect(stopWorkerMock).toHaveBeenCalled();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Worker stopped' })
    );
    expect(onUpdate).toHaveBeenCalled();
  });
});
