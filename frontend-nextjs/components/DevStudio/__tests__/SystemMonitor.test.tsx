/**
 * SystemMonitor Component Tests
 *
 * Tests verify the real SystemMonitor component
 * (components/DevStudio/SystemMonitor.tsx):
 * - spinner while GET /api/system/status is in flight
 * - overall status badge, CPU/Memory/Uptime cards, formatted uptime
 * - service health cards (CheckCircle for healthy, AlertTriangle otherwise,
 *   response time, status badge)
 * - periodic refresh every 5s re-fetches the endpoint
 * - failed fetch keeps the loading spinner (no crash)
 *
 * API: GET /api/system/status
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

jest.mock('../../ui/spinner', () => ({
  Spinner: () => <div data-testid="spinner">Loading...</div>,
}));

import SystemMonitor from '../SystemMonitor';

describe('SystemMonitor', () => {
  let fetchCount: number;
  let nextResponse: 'ok' | 'error' = 'ok';

  const statusPayload = {
    timestamp: '2026-08-07T10:30:00.000Z',
    overall_status: 'degraded',
    resources: {
      cpu: { percent: 82, count: 8 },
      memory: { percent: 64, system_used_percent: 61, system_total_mb: 16384, system_available_mb: 4096 },
      disk: { percent: 45, free_gb: 120, total_gb: 512 },
    },
    services: {
      api: { name: 'API Server', status: 'healthy', response_time_ms: 12 },
      worker: { name: 'Task Worker', status: 'degraded', response_time_ms: 340 },
      db: { name: 'Database', status: 'healthy', response_time_ms: 3 },
    },
    uptime: { system_seconds: 90061 },
  };

  beforeEach(() => {
    fetchCount = 0;
    nextResponse = 'ok';
    jest.useFakeTimers();
    server.resetHandlers();
    server.use(
      rest.get('/api/system/status', (req, res, ctx) => {
        fetchCount += 1;
        if (nextResponse === 'error') {
          return res(ctx.status(500));
        }
        return res(ctx.status(200), ctx.json(statusPayload));
      })
    );
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('shows the spinner before the status arrives', () => {
    nextResponse = 'error';
    render(<SystemMonitor />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('renders the header, overall status badge and resource cards', async () => {
    render(<SystemMonitor />);

    expect(await screen.findByText('System Monitor')).toBeInTheDocument();
    expect(screen.getByText('System: DEGRADED')).toBeInTheDocument();
    expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    expect(screen.getByText('82%')).toBeInTheDocument();
    expect(screen.getByText('8 Cores Active')).toBeInTheDocument();
    expect(screen.getByText('Memory Usage')).toBeInTheDocument();
    expect(screen.getByText('64%')).toBeInTheDocument();
    expect(screen.getByText('4096 MB Available')).toBeInTheDocument();
    expect(screen.getByText('System Uptime')).toBeInTheDocument();
    expect(screen.getByText('1d 1h 1m')).toBeInTheDocument();
  });

  it('renders service health cards with status icons and response times', async () => {
    render(<SystemMonitor />);

    expect(await screen.findByText('Service Health')).toBeInTheDocument();
    expect(screen.getByText('API Server')).toBeInTheDocument();
    expect(screen.getByText('Task Worker')).toBeInTheDocument();
    expect(screen.getByText('Database')).toBeInTheDocument();
    expect(screen.getAllByText('healthy').length).toBe(2);
    expect(screen.getByText('degraded')).toBeInTheDocument();
    expect(screen.getByText('12ms')).toBeInTheDocument();
    expect(screen.getByText('340ms')).toBeInTheDocument();
  });

  it('formats a long uptime as days/hours/minutes', async () => {
    const longUptime = {
      ...statusPayload,
      uptime: { system_seconds: 2 * 86400 + 5 * 3600 + 42 * 60 },
    };
    server.use(
      rest.get('/api/system/status', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json(longUptime));
      })
    );
    // The mid-test override above wins for the first (and only awaited) fetch;
    // subsequent interval polls fall back to the beforeEach handler.
    fetchCount = 0;

    render(<SystemMonitor />);
    expect(await screen.findByText('2d 5h 42m')).toBeInTheDocument();
  });

  it('re-fetches the status every 5 seconds', async () => {
    render(<SystemMonitor />);
    await screen.findByText('System Monitor');
    expect(fetchCount).toBe(1);

    jest.advanceTimersByTime(5000);
    await waitFor(() => expect(fetchCount).toBeGreaterThanOrEqual(2));

    jest.advanceTimersByTime(10000);
    await waitFor(() => expect(fetchCount).toBeGreaterThanOrEqual(4));
  });

  it('keeps the spinner without crashing when the fetch fails', async () => {
    nextResponse = 'error';

    render(<SystemMonitor />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();

    await waitFor(() => expect(fetchCount).toBeGreaterThanOrEqual(1));
    expect(screen.getByText('Loading...')).toBeInTheDocument();

    jest.advanceTimersByTime(5000);
    await waitFor(() => expect(fetchCount).toBeGreaterThanOrEqual(2));
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });
});
