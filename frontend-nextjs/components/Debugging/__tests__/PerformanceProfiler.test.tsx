/**
 * PerformanceProfiler Component Tests
 *
 * Tests verify the REAL PerformanceProfiler component
 * (components/Debugging/PerformanceProfiler.tsx, a NAMED export):
 * - Start Profiling is disabled without a session; empty state shown
 * - Starting profiling POSTs .../profiling/start and shows the Recording badge
 * - The 2s auto-refresh interval fetches .../profiling/report and renders
 *   summary metrics, slowest steps (progress bars), slowest nodes, metadata
 *
 * fetch is mocked directly (see components/Settings/__tests__/TwoFactorSettings.test.tsx).
 * The toast hook is globally stubbed in tests/setup.ts.
 */

import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import PerformanceProfiler from '../PerformanceProfiler';

const report = {
  session_id: 'ses-1',
  total_duration_ms: 125000,
  total_steps: 12,
  average_step_duration_ms: 10416,
  slowest_steps: [
    { node_id: 'fetch-users', node_type: 'action', duration_ms: 30000, timestamp: 't' },
    { node_id: 'loop-users', node_type: 'loop', duration_ms: 15000, timestamp: 't' },
  ],
  slowest_nodes: [
    { node_id: 'fetch-users', count: 5, total_ms: 30000, avg_ms: 6000, min_ms: 1000, max_ms: 12000 },
  ],
  profiling_started_at: '2026-08-01T10:00:00Z',
  generated_at: '2026-08-01T10:05:00Z',
};

describe('PerformanceProfiler', () => {
  beforeEach(() => {
    // fixture returns a partial Response object; cast the completed mock
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: async () => report })
    ) as unknown as typeof fetch;
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  const renderProfiler = (sessionId: string | null) =>
    render(
      <PerformanceProfiler sessionId={sessionId} workflowId="wf-1" currentUserId="user-1" />
    );

  // Test 1: without a session the Start button is disabled and empty state shows
  test('start button is disabled and empty state shows without a session', () => {
    renderProfiler(null);

    expect(screen.getByRole('button', { name: /start profiling/i })).toBeDisabled();
    expect(screen.getByText('Start profiling to see performance metrics')).toBeInTheDocument();
    expect(screen.getByText('Not started')).toBeInTheDocument();
  });

  // Test 2: starting profiling POSTs the start endpoint and shows Recording
  test('starts profiling via POST and shows the recording badge', async () => {
    renderProfiler('ses-1');

    fireEvent.click(screen.getByRole('button', { name: /start profiling/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/workflows/debug/sessions/ses-1/profiling/start',
        { method: 'POST' }
      );
      expect(screen.getByText('Recording')).toBeInTheDocument();
    });
  });

  // Test 3: the auto-refresh tick loads and renders the full report
  test('auto-refresh interval fetches and renders the report', async () => {
    jest.useFakeTimers();
    renderProfiler('ses-1');

    fireEvent.click(screen.getByRole('button', { name: /start profiling/i }));
    await act(async () => {});

    // Advance past the 2s auto-refresh interval and flush the fetch
    await act(async () => {
      jest.advanceTimersByTime(2000);
    });
    await act(async () => {});

    // Summary metrics: 125000ms -> 2.08m, avg 10416 -> 10.42s
    expect(screen.getByText('Total Duration')).toBeInTheDocument();
    expect(screen.getByText('2.08m')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('10.42s')).toBeInTheDocument();

    // Slowest steps with progress bars
    expect(screen.getByText('Slowest Steps')).toBeInTheDocument();
    expect(screen.getAllByText('fetch-users').length).toBeGreaterThan(0);
    expect(screen.getByText('loop-users')).toBeInTheDocument();
    expect(screen.getByText('30.00s')).toBeInTheDocument();
    // Progress bars are plain divs with an inline translateX transform
    const bars = document.querySelectorAll<HTMLElement>('[style*="translateX"]');
    expect(bars.length).toBe(2);
    expect(Array.from(bars).some((bar) => bar.style.transform.includes('-50%'))).toBe(true);

    // Slowest nodes by average
    expect(screen.getByText('Slowest Nodes (Average)')).toBeInTheDocument();
    expect(screen.getByText('5x executed')).toBeInTheDocument();

    const reportCalls = (global.fetch as jest.Mock).mock.calls.filter(([url]) =>
      String(url).includes('/profiling/report')
    );
    expect(reportCalls.length).toBeGreaterThanOrEqual(1);
  });

  // Test 4: report metadata renders the started/generated timestamps
  test('renders metadata lines once the report is loaded', async () => {
    jest.useFakeTimers();
    renderProfiler('ses-1');

    fireEvent.click(screen.getByRole('button', { name: /start profiling/i }));
    await act(async () => {});
    await act(async () => {
      jest.advanceTimersByTime(2000);
    });
    await act(async () => {});

    expect(screen.getByText(/Started: .* ago/)).toBeInTheDocument();
    expect(screen.getByText(/Generated:/)).toBeInTheDocument();
  });
});
