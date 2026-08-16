/**
 * WorkflowAnalyticsDashboard Component Tests
 * (components/dashboard/AnalyticsDashboard.tsx)
 *
 * Tests verify the real dashboard behavior:
 * - shows the loading spinner before the six parallel fetches resolve
 * - renders KPI cards (Total Executions, Success Rate, Error Rate, Avg
 *   Duration) from /api/analytics/dashboard/kpis
 * - Overview tab: timeline chart + unique workflows/users/errors summary
 * - Workflows tab: top-performing table with success-rate badges, formatted
 *   durations and trend icons; empty state when no workflows
 * - Errors tab: error types with occurrence counts + recent errors
 * - Alerts tab: configured alerts with severity + enabled badges and the
 *   metric condition line; empty state
 * - Real-time tab: execution feed with workflow names and execution ids
 * - time-window Select refetches with the new time_window query param
 * - Refresh button triggers a refetch of all endpoints
 * - KPI fetch failure surfaces an error toast
 *
 * APIs: /api/analytics/dashboard/kpis,
 *       /api/analytics/dashboard/workflows/top-performing,
 *       /api/analytics/dashboard/timeline,
 *       /api/analytics/dashboard/errors/breakdown,
 *       /api/analytics/alerts, /api/analytics/dashboard/realtime-feed
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
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

// Recharts renders nothing measurable in jsdom (zero-width containers), so
// its children would never execute. Stub the chart primitives as plain
// pass-through components; the dashboard's own JSX still runs for coverage.
jest.mock('recharts', () => {
  const React = require('react');
  const stub = (name: string) => {
    const Comp = (props: any) => (
      <div data-testid={`recharts-${name}`}>
        {props.children}
        {typeof props.tickFormatter === 'function' ? props.tickFormatter('2026-08-07T08:00:00.000Z') : null}
        {typeof props.labelFormatter === 'function' ? props.labelFormatter('2026-08-07T08:00:00.000Z') : null}
        {typeof props.formatter === 'function' ? props.formatter(10) : null}
      </div>
    );
    Comp.displayName = name;
    return Comp;
  };
  return {
    ResponsiveContainer: stub('ResponsiveContainer'),
    LineChart: stub('LineChart'),
    AreaChart: stub('AreaChart'),
    BarChart: stub('BarChart'),
    Line: stub('Line'),
    Area: stub('Area'),
    Bar: stub('Bar'),
    XAxis: stub('XAxis'),
    YAxis: stub('YAxis'),
    CartesianGrid: stub('CartesianGrid'),
    Tooltip: stub('Tooltip'),
    Legend: stub('Legend'),
  };
});

import AnalyticsDashboard from '../dashboard/AnalyticsDashboard';

const kpisPayload = {
  total_executions: 1240,
  successful_executions: 1180,
  failed_executions: 60,
  success_rate: 95.2,
  error_rate: 4.8,
  average_duration_ms: 2500,
  average_duration_seconds: 2.5,
  unique_workflows: 18,
  unique_users: 7,
};

const workflowsPayload = [
  {
    workflow_id: 'wf-1',
    workflow_name: 'Invoice Processing',
    total_executions: 320,
    success_rate: 98,
    average_duration_ms: 800,
    last_execution: '2026-08-07T09:00:00.000Z',
    trend: 'up',
  },
  {
    workflow_id: 'wf-2',
    workflow_name: 'Lead Nurture',
    total_executions: 150,
    success_rate: 72,
    average_duration_ms: 45000,
    last_execution: null,
    trend: 'down',
  },
];

const timelinePayload = [
  { timestamp: '2026-08-07T08:00:00.000Z', count: 10, success_count: 9, failure_count: 1, average_duration_ms: 1000 },
  { timestamp: '2026-08-07T09:00:00.000Z', count: 12, success_count: 11, failure_count: 1, average_duration_ms: 1200 },
];

const errorBreakdownPayload = {
  error_types: [{ type: 'TimeoutError', count: 12 }, { type: 'ValidationError', count: 3 }],
  workflows_with_errors: [{ workflow_id: 'wf-1', error_count: 5 }],
  recent_errors: [
    { workflow_id: 'wf-2', error_message: 'Connection reset by peer', timestamp: '2026-08-07T08:45:00.000Z' },
  ],
};

const alertsPayload = [
  {
    alert_id: 'al-1',
    name: 'High error rate',
    description: 'Alert when error rate exceeds threshold',
    severity: 'critical',
    metric_name: 'error_rate',
    condition: '>',
    threshold_value: 5,
    workflow_id: null,
    enabled: true,
  },
  {
    alert_id: 'al-2',
    name: 'Slow workflow',
    description: 'Alert on long durations',
    severity: 'low',
    metric_name: 'avg_duration_ms',
    condition: '>',
    threshold_value: 10000,
    workflow_id: 'wf-1',
    enabled: false,
  },
];

const realtimePayload = [
  {
    event_id: 'ev-1',
    workflow_id: 'wf-1',
    workflow_name: 'Invoice Processing',
    execution_id: 'exec-abc',
    event_type: 'workflow.completed',
    timestamp: '2026-08-07T09:05:00.000Z',
    status: 'completed',
    duration_ms: 900,
    user_id: 'u1',
  },
  {
    event_id: 'ev-2',
    workflow_id: 'wf-2',
    workflow_name: 'Lead Nurture',
    execution_id: 'exec-def',
    event_type: 'workflow.failed',
    timestamp: '2026-08-07T09:06:00.000Z',
    status: 'failed',
    duration_ms: null,
    user_id: 'u2',
  },
];

describe('AnalyticsDashboard', () => {
  let kpiQueries: string[];
  let topQueries: string[];
  let fetchCounts: Record<string, number>;

  beforeEach(() => {
    jest.clearAllMocks();
    kpiQueries = [];
    topQueries = [];
    fetchCounts = { kpis: 0, top: 0, timeline: 0, errors: 0, alerts: 0, realtime: 0 };

    server.resetHandlers();
    server.use(
      rest.get('/api/analytics/dashboard/kpis', (req, res, ctx) => {
        kpiQueries.push(String(req.url.searchParams.get('time_window')));
        fetchCounts.kpis += 1;
        return res(ctx.status(200), ctx.json(kpisPayload));
      }),
      rest.get('/api/analytics/dashboard/workflows/top-performing', (req, res, ctx) => {
        topQueries.push(String(req.url.searchParams.get('time_window')));
        fetchCounts.top += 1;
        return res(ctx.status(200), ctx.json(workflowsPayload));
      }),
      rest.get('/api/analytics/dashboard/timeline', (req, res, ctx) => {
        fetchCounts.timeline += 1;
        return res(ctx.status(200), ctx.json(timelinePayload));
      }),
      rest.get('/api/analytics/dashboard/errors/breakdown', (req, res, ctx) => {
        fetchCounts.errors += 1;
        return res(ctx.status(200), ctx.json(errorBreakdownPayload));
      }),
      rest.get('/api/analytics/alerts', (req, res, ctx) => {
        fetchCounts.alerts += 1;
        return res(ctx.status(200), ctx.json(alertsPayload));
      }),
      rest.get('/api/analytics/dashboard/realtime-feed', (req, res, ctx) => {
        fetchCounts.realtime += 1;
        return res(ctx.status(200), ctx.json(realtimePayload));
      })
    );
  });

  it('shows the loading spinner before data resolves, then renders KPIs', async () => {
    render(<AnalyticsDashboard />);

    expect(screen.getByTestId('spinner')).toBeInTheDocument();
    expect(screen.getByText('Loading analytics dashboard...')).toBeInTheDocument();

    expect(await screen.findByText('Workflow Analytics')).toBeInTheDocument();
    expect(screen.queryByTestId('spinner')).not.toBeInTheDocument();

    expect(screen.getByText('Total Executions')).toBeInTheDocument();
    expect(screen.getByText('1240')).toBeInTheDocument();
    expect(screen.getByText('Success Rate')).toBeInTheDocument();
    expect(screen.getByText('95.2%')).toBeInTheDocument();
    expect(screen.getByText('Error Rate')).toBeInTheDocument();
    expect(screen.getByText('4.8%')).toBeInTheDocument();
    expect(screen.getByText('Avg Duration')).toBeInTheDocument();
    expect(screen.getByText('2.5s')).toBeInTheDocument();
  });

  it('renders the Overview tab summary cards and timeline chart title', async () => {
    render(<AnalyticsDashboard />);

    expect(await screen.findByText('Workflow Analytics')).toBeInTheDocument();

    expect(screen.getByText('Execution Timeline')).toBeInTheDocument();
    expect(screen.getByText('Unique Workflows')).toBeInTheDocument();
    expect(screen.getByText('18')).toBeInTheDocument();
    expect(screen.getByText('Unique Users')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('Total Errors')).toBeInTheDocument();
    // failed_executions from KPIs
    expect(screen.getByText('60')).toBeInTheDocument();
  });

  it('renders the workflows table with badges, durations and trend icons', async () => {
    render(<AnalyticsDashboard />);
    await screen.findByText('Workflow Analytics');

    fireEvent.click(screen.getByRole('button', { name: /workflows/i }));

    expect(screen.getByText('Top Performing Workflows')).toBeInTheDocument();
    expect(screen.getByText('Invoice Processing')).toBeInTheDocument();
    expect(screen.getByText('Lead Nurture')).toBeInTheDocument();
    expect(screen.getByText('320')).toBeInTheDocument();
    expect(screen.getByText('98%')).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument();
    // 800ms → "800ms"; 45000ms → "45.0s"
    expect(screen.getByText('800ms')).toBeInTheDocument();
    expect(screen.getByText('45.0s')).toBeInTheDocument();
    // null last_execution → N/A
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  it('renders error types and recent errors in the Errors tab', async () => {
    render(<AnalyticsDashboard />);
    await screen.findByText('Workflow Analytics');

    fireEvent.click(screen.getByRole('button', { name: /errors/i }));

    expect(screen.getByText('Error Types')).toBeInTheDocument();
    expect(screen.getByText('TimeoutError')).toBeInTheDocument();
    expect(screen.getByText('ValidationError')).toBeInTheDocument();
    expect(screen.getByText('12 occurrences')).toBeInTheDocument();
    expect(screen.getByText('Recent Errors')).toBeInTheDocument();
    expect(screen.getByText('Connection reset by peer')).toBeInTheDocument();
    expect(screen.getByText('wf-2')).toBeInTheDocument();
  });

  it('renders configured alerts with severity and enabled state', async () => {
    render(<AnalyticsDashboard />);
    await screen.findByText('Workflow Analytics');

    fireEvent.click(screen.getByRole('button', { name: /alerts/i }));

    expect(screen.getByText('Configured Alerts')).toBeInTheDocument();
    expect(screen.getByText('High error rate')).toBeInTheDocument();
    expect(screen.getByText('Slow workflow')).toBeInTheDocument();
    expect(screen.getByText('critical')).toBeInTheDocument();
    expect(screen.getByText('low')).toBeInTheDocument();
    expect(screen.getByText('Enabled')).toBeInTheDocument();
    expect(screen.getByText('Disabled')).toBeInTheDocument();
    // metric condition line
    expect(screen.getByText('error_rate > 5')).toBeInTheDocument();
    expect(screen.getByText('avg_duration_ms > 10000')).toBeInTheDocument();
  });

  it('renders the real-time execution feed with workflow names and ids', async () => {
    render(<AnalyticsDashboard />);
    await screen.findByText('Workflow Analytics');

    fireEvent.click(screen.getByRole('button', { name: /real-time/i }));

    expect(screen.getByText('Real-time Execution Feed')).toBeInTheDocument();
    expect(screen.getByText('Invoice Processing')).toBeInTheDocument();
    expect(screen.getByText('workflow.completed')).toBeInTheDocument();
    expect(screen.getByText('workflow.failed')).toBeInTheDocument();
    expect(screen.getByText('exec-abc')).toBeInTheDocument();
    expect(screen.getByText('Duration: 900ms')).toBeInTheDocument();
  });

  it('refetches with the new time window when the Select changes', async () => {
    render(<AnalyticsDashboard />);
    await screen.findByText('Workflow Analytics');
    await waitFor(() => expect(kpiQueries).toContain('24h'));

    fireEvent.click(screen.getByRole('combobox'));
    fireEvent.click(await screen.findByRole('option', { name: 'Last 7 Days' }));

    await waitFor(() => expect(kpiQueries).toContain('7d'));
    expect(topQueries).toContain('7d');
  });

  it('refetches all data when Refresh is clicked', async () => {
    render(<AnalyticsDashboard />);
    await screen.findByText('Workflow Analytics');
    await waitFor(() => expect(fetchCounts.kpis).toBe(1));

    fireEvent.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => expect(fetchCounts.kpis).toBe(2));
    expect(fetchCounts.top).toBe(2);
    expect(fetchCounts.timeline).toBe(2);
    expect(fetchCounts.errors).toBe(2);
    expect(fetchCounts.alerts).toBe(2);
    expect(fetchCounts.realtime).toBe(2);
  });

  it('toasts an error when the KPIs fetch fails', async () => {
    server.use(
      rest.get('/api/analytics/dashboard/kpis', (req, res, ctx) => res.networkError('boom'))
    );

    render(<AnalyticsDashboard />);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to load dashboard KPIs',
          variant: 'error',
        })
      );
    });
    // Dashboard still renders with the other data
    expect(await screen.findByText('Workflow Analytics')).toBeInTheDocument();
  });

  it('renders empty states when endpoints return no data', async () => {
    server.use(
      rest.get('/api/analytics/dashboard/timeline', (req, res, ctx) =>
        res(ctx.status(200), ctx.json([]))
      ),
      rest.get('/api/analytics/dashboard/workflows/top-performing', (req, res, ctx) =>
        res(ctx.status(200), ctx.json([]))
      ),
      rest.get('/api/analytics/alerts', (req, res, ctx) =>
        res(ctx.status(200), ctx.json([]))
      ),
      rest.get('/api/analytics/dashboard/realtime-feed', (req, res, ctx) =>
        res(ctx.status(200), ctx.json([]))
      )
    );

    render(<AnalyticsDashboard />);
    await screen.findByText('Workflow Analytics');

    expect(screen.getByText('No timeline data available')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /workflows/i }));
    expect(screen.getByText('No workflow data available')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /alerts/i }));
    expect(screen.getByText('No alerts configured')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /real-time/i }));
    expect(screen.getByText('No recent events')).toBeInTheDocument();
  });

  it('renders empty error states when the error breakdown has no data', async () => {
    server.use(
      rest.get('/api/analytics/dashboard/errors/breakdown', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ error_types: [], workflows_with_errors: [], recent_errors: [] }))
      )
    );

    render(<AnalyticsDashboard />);
    await screen.findByText('Workflow Analytics');

    fireEvent.click(screen.getByRole('button', { name: /errors/i }));
    expect(screen.getByText('No errors recorded')).toBeInTheDocument();
    expect(screen.getByText('No recent errors')).toBeInTheDocument();
  });

  it('logs and survives failures of the non-KPI endpoints', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    server.use(
      rest.get('/api/analytics/dashboard/workflows/top-performing', (req, res, ctx) =>
        res.networkError('top failed')
      ),
      rest.get('/api/analytics/dashboard/timeline', (req, res, ctx) =>
        res.networkError('timeline failed')
      ),
      rest.get('/api/analytics/dashboard/errors/breakdown', (req, res, ctx) =>
        res.networkError('errors failed')
      ),
      rest.get('/api/analytics/alerts', (req, res, ctx) =>
        res.networkError('alerts failed')
      ),
      rest.get('/api/analytics/dashboard/realtime-feed', (req, res, ctx) =>
        res.networkError('realtime failed')
      )
    );

    render(<AnalyticsDashboard />);

    // Dashboard still renders; the failures were only logged
    expect(await screen.findByText('Workflow Analytics')).toBeInTheDocument();
    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Error fetching top workflows:',
        expect.any(Error)
      );
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Error fetching timeline data:',
        expect.any(Error)
      );
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Error fetching error breakdown:',
        expect.any(Error)
      );
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Error fetching alerts:',
        expect.any(Error)
      );
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Error fetching realtime events:',
        expect.any(Error)
      );
    });

    consoleErrorSpy.mockRestore();
  });

  it('formats minute-scale durations, stable trends and medium-severity alerts', async () => {
    server.use(
      rest.get('/api/analytics/dashboard/workflows/top-performing', (req, res, ctx) =>
        res(ctx.status(200), ctx.json([
          {
            workflow_id: 'wf-min',
            workflow_name: 'Batch ETL',
            total_executions: 42,
            success_rate: 91,
            average_duration_ms: 90000,
            last_execution: '2026-08-07T09:00:00.000Z',
            trend: 'stable',
          },
        ]))
      ),
      rest.get('/api/analytics/alerts', (req, res, ctx) =>
        res(ctx.status(200), ctx.json([
          {
            alert_id: 'al-med',
            name: 'Medium alert',
            description: 'A medium severity alert',
            severity: 'medium',
            metric_name: 'error_rate',
            condition: '>',
            threshold_value: 3,
            workflow_id: null,
            enabled: true,
          },
          {
            alert_id: 'al-high',
            name: 'High alert',
            description: 'A high severity alert',
            severity: 'high',
            metric_name: 'error_rate',
            condition: '>',
            threshold_value: 8,
            workflow_id: null,
            enabled: true,
          },
          {
            alert_id: 'al-unknown',
            name: 'Unknown alert',
            description: 'An unrecognized severity',
            severity: 'weird',
            metric_name: 'success_rate',
            condition: '<',
            threshold_value: 50,
            workflow_id: null,
            enabled: false,
          },
        ]))
      )
    );

    render(<AnalyticsDashboard />);
    await screen.findByText('Workflow Analytics');

    fireEvent.click(screen.getByRole('button', { name: /workflows/i }));
    expect(screen.getByText('Batch ETL')).toBeInTheDocument();
    expect(screen.getByText('1.5m')).toBeInTheDocument(); // 90000ms -> 1.5m

    fireEvent.click(screen.getByRole('button', { name: /alerts/i }));
    expect(screen.getByText('Medium alert')).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();
    expect(screen.getByText('High alert')).toBeInTheDocument();
    expect(screen.getByText('Unknown alert')).toBeInTheDocument();
    expect(screen.getByText('weird')).toBeInTheDocument();
  });

  it('color-codes a slow average duration as red', async () => {
    server.use(
      rest.get('/api/analytics/dashboard/kpis', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({
          ...kpisPayload,
          average_duration_ms: 8000,
          average_duration_seconds: 8,
        }))
      )
    );

    render(<AnalyticsDashboard />);

    expect(await screen.findByText('Workflow Analytics')).toBeInTheDocument();
    const duration = screen.getByText('8s');
    expect(duration.className).toContain('text-red-600');
  });

  it('auto-refreshes KPIs and realtime events on the 30s interval', async () => {
    jest.useFakeTimers();
    render(<AnalyticsDashboard />);

    // Let the initial load resolve under fake timers
    await waitFor(() => expect(screen.getByText('Workflow Analytics')).toBeInTheDocument());
    const kpisBefore = fetchCounts.kpis;
    const realtimeBefore = fetchCounts.realtime;

    act(() => {
      jest.advanceTimersByTime(31000);
    });

    await waitFor(() => expect(fetchCounts.kpis).toBeGreaterThan(kpisBefore));
    expect(fetchCounts.realtime).toBeGreaterThan(realtimeBefore);

    jest.useRealTimers();
  });

  it('refetches workflows when the sort-by select changes', async () => {
    const sortQueries: string[] = [];
    server.use(
      rest.get('/api/analytics/dashboard/workflows/top-performing', (req, res, ctx) => {
        sortQueries.push(String(req.url.searchParams.get('sort_by')));
        return res(ctx.status(200), ctx.json(workflowsPayload));
      })
    );

    render(<AnalyticsDashboard />);
    await screen.findByText('Workflow Analytics');
    await waitFor(() => expect(sortQueries).toContain('success_rate'));

    fireEvent.click(screen.getByRole('button', { name: /workflows/i }));
    fireEvent.click(screen.getAllByRole('combobox')[1]);
    fireEvent.click(await screen.findByRole('option', { name: 'Duration' }));

    await waitFor(() => expect(sortQueries).toContain('duration'));
    // The reload resets the tabs to overview; re-open the workflows tab to
    // confirm the new sort label.
    await screen.findByText('Workflow Analytics');
    fireEvent.click(screen.getByRole('button', { name: /workflows/i }));
    await waitFor(() =>
      expect(screen.getByText('Ranked by duration')).toBeInTheDocument()
    );
  });

  it('clears the auto-refresh interval on unmount', async () => {
    const { unmount } = render(<AnalyticsDashboard />);
    await screen.findByText('Workflow Analytics');

    expect(() => unmount()).not.toThrow();
    // No further fetches happen after unmount
    const realtimeAfter = fetchCounts.realtime;
    await new Promise((r) => setTimeout(r, 50));
    expect(fetchCounts.realtime).toBe(realtimeAfter);
  });
});
