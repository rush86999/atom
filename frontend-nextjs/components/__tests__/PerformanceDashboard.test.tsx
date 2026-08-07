/**
 * PerformanceDashboard Component Tests
 *
 * Tests verify the real PerformanceDashboard component
 * (components/PerformanceDashboard.tsx):
 * - loading spinner before /api/health resolves
 * - header stats: status badge, uptime, response time, error rate, healthy
 *   integrations count, memory/cpu/redis resource cards, system details table
 * - /api/health failure shows the error Alert and stops loading
 * - auto-refresh toggle button flips Auto-refresh On/Off
 * - time-range Select refetches /api/analytics with the new timeRange
 * - User Activity tab renders analytics metrics (active users, feature usage)
 *
 * API: GET /api/health, GET /api/analytics?timeRange=...
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

jest.mock('@/components/ui/spinner', () => ({
  Spinner: () => <div data-testid="spinner">Loading...</div>,
}));

import PerformanceDashboard from '../PerformanceDashboard';

const healthPayload = {
  status: 'degraded',
  timestamp: '2026-08-07T10:00:00.000Z',
  uptime: 90061,
  version: '1.2.3',
  environment: 'test',
  checks: {
    database: { status: 'healthy', responseTime: 5 },
    redis: { status: 'healthy', responseTime: 2, connected: true },
    auth: { status: 'healthy' },
    memory: { status: 'healthy', used: 536870912, total: 8589934592, percentage: 25.5 },
    cpu: { status: 'healthy', usage: 12.5 },
    integrations: {
      total: 3,
      healthy: 2,
      unhealthy: 1,
      details: [
        { service: 'Slack', status: 'healthy' },
        { service: 'Notion', status: 'healthy' },
        { service: 'Gmail', status: 'unhealthy' },
      ],
    },
  },
  performance: {
    responseTime: 42,
    throughput: 1200,
    errorRate: 0.5,
    lastHour: { requests: 43200, errors: 216, averageResponseTime: 41 },
  },
};

const analyticsPayload = {
  data: {
    timestamp: '2026-08-07T10:00:00.000Z',
    metrics: {
      users: { total: 40, active: 12, new: 3 },
      integrations: { total: 3, connected: 2, usage: [] },
      performance: { averageResponseTime: 42, throughput: 1200, errorRate: 0.5 },
      features: { searchQueries: 88, workflowExecutions: 12, agentTasks: 5, aiInteractions: 200 },
    },
  },
};

describe('PerformanceDashboard', () => {
  let analyticsQueries: string[];

  beforeEach(() => {
    jest.clearAllMocks();
    analyticsQueries = [];

    server.resetHandlers();
    server.use(
      rest.get('/api/health', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json(healthPayload));
      }),
      rest.get('/api/analytics', (req, res, ctx) => {
        analyticsQueries.push(String(req.url.searchParams.get('timeRange')));
        return res(ctx.status(200), ctx.json(analyticsPayload));
      })
    );
  });

  it('shows the loading spinner before health data arrives', () => {
    server.use(
      rest.get('/api/health', (req, res, ctx) => {
        return res(ctx.delay(1000), ctx.json(healthPayload));
      })
    );
    render(<PerformanceDashboard />);
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
    expect(screen.getByText('Loading performance data...')).toBeInTheDocument();
  });

  it('renders the header stats and resource cards', async () => {
    render(<PerformanceDashboard />);

    expect(await screen.findByText('Performance Monitor')).toBeInTheDocument();
    expect(screen.getByText('DEGRADED')).toBeInTheDocument();
    expect(screen.getByText('1d 1h 1m')).toBeInTheDocument();
    expect(screen.getByText('Version: 1.2.3')).toBeInTheDocument();
    expect(screen.getByText('42ms')).toBeInTheDocument();
    expect(screen.getByText('Error Rate: 0.50%')).toBeInTheDocument();
    expect(screen.getByText('2/3')).toBeInTheDocument();
    expect(screen.getByText('1 unhealthy')).toBeInTheDocument();
  });

  it('renders memory, cpu and redis resource cards', async () => {
    render(<PerformanceDashboard />);

    expect(await screen.findByText('Memory')).toBeInTheDocument();
    expect(screen.getByText('512.0 MB')).toBeInTheDocument();
    expect(screen.getByText('25.5% utilized')).toBeInTheDocument();
    expect(screen.getByText('CPU')).toBeInTheDocument();
    expect(screen.getByText('12.5%')).toBeInTheDocument();
    expect(screen.getAllByText('Redis').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('Response Time: 2ms')).toBeInTheDocument();
  });

  it('renders the system details table rows', async () => {
    render(<PerformanceDashboard />);

    expect(await screen.findByText('System Details')).toBeInTheDocument();
    expect(screen.getByText('Database')).toBeInTheDocument();
    expect(screen.getByText('Auth Service')).toBeInTheDocument();
    expect(screen.getAllByText('healthy').length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText('5ms')).toBeInTheDocument();
  });

  it('shows the error alert when the health check fails', async () => {
    server.use(
      rest.get('/api/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<PerformanceDashboard />);

    expect(await screen.findByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Failed to fetch health data')).toBeInTheDocument();
    expect(screen.queryByTestId('spinner')).not.toBeInTheDocument();
  });

  it('toggles the auto-refresh button label', async () => {
    render(<PerformanceDashboard />);

    const toggle = await screen.findByRole('button', { name: /auto-refresh on/i });
    fireEvent.click(toggle);
    expect(screen.getByRole('button', { name: /auto-refresh off/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /auto-refresh off/i }));
    expect(screen.getByRole('button', { name: /auto-refresh on/i })).toBeInTheDocument();
  });

  it('refetches analytics with the selected time range', async () => {
    render(<PerformanceDashboard />);
    await screen.findByText('Performance Monitor');
    expect(analyticsQueries).toContain('24h');

    fireEvent.click(screen.getByRole('combobox'));
    fireEvent.click(await screen.findByText('1 Hour'));

    await waitFor(() => {
      expect(analyticsQueries).toContain('1h');
    });
  });

  it('renders analytics metrics on the User Activity tab', async () => {
    render(<PerformanceDashboard />);
    await screen.findByText('Performance Monitor');

    fireEvent.click(screen.getByText('User Activity'));

    expect(await screen.findByText('Active Users')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('+3 new users')).toBeInTheDocument();
    expect(screen.getByText('Feature Usage')).toBeInTheDocument();
    expect(screen.getByText('88')).toBeInTheDocument();
    expect(screen.getByText('Search queries in 24h')).toBeInTheDocument();
  });
});
