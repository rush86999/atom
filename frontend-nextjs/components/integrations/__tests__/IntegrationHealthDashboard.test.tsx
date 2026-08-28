/**
 * IntegrationHealthDashboard Component Tests
 *
 * Tests verify the real IntegrationHealthDashboard component
 * (components/integrations/IntegrationHealthDashboard.tsx):
 * - Fetches a fixed list of 9 integration health endpoints
 *   (/api/integrations/{id}/health) and derives healthy/warning/error status
 * - Loading state, summary stats cards, overall health progress
 * - Integration list with per-status badges and connected badges
 * - Refresh button refetch, last-updated timestamp, status legend
 * - autoRefresh interval and showDetails prop
 *
 * Uses the shared MSW server (tests/mocks/server.ts). Real timers are used
 * throughout (fake timers break MSW + RTL waitFor). The ui/spinner module is
 * mocked (its source references React without importing it, which throws
 * "React is not defined" whenever the loading state renders the real Spinner).
 * useSession is mocked because there is no SessionProvider in tests; without a
 * token the hook skips connecting, so the health fetch is unaffected.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import IntegrationHealthDashboard from '../IntegrationHealthDashboard';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null }),
}));

// The ui/spinner module references React without importing it, which throws
// "React is not defined" in the test runtime whenever the loading state
// renders the real Spinner. Mock it to a plain div so the component's own
// "Loading integration health status..." label can still be asserted.
jest.mock('@/components/ui/spinner', () => ({
  Spinner: ({ className }: { className?: string }) => (
    <div data-testid="spinner" className={className} />
  ),
}));

const healthy = (req: any, res: any, ctx: any) =>
  res(ctx.status(200), ctx.json({ connected: true, status: 'healthy' }));

const allHealthy = [
  rest.get('/api/integrations/:platform/health', healthy),
];

const allError = [
  rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
    return res(ctx.status(500), ctx.json({ connected: false, status: 'error' }));
  }),
];

const mixedStatuses = [
  rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
    const platform = req.params.platform;
    if (platform === 'github') {
      return res(ctx.status(200), ctx.json({ connected: true, status: 'healthy' }));
    }
    if (platform === 'azure') {
      return res(ctx.status(200), ctx.json({ connected: false, status: 'warning' }));
    }
    return res(ctx.status(500), ctx.json({ connected: false, status: 'error' }));
  }),
];

describe('IntegrationHealthDashboard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
  });

  // Test 1: renders the loading state while health checks are pending
  it('renders loading state while health checks are pending', () => {
    server.use(
      rest.get('/api/integrations/:platform/health', () => new Promise<undefined>(() => {})) // never resolves
    );

    render(<IntegrationHealthDashboard />);

    expect(
      screen.getByText(/loading integration health status/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
  });

  // Test 2: renders the dashboard with the full integration list
  it('shows the list of integrations with health status', async () => {
    server.use(...allHealthy);

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Integration Status')).toBeInTheDocument();
      expect(screen.getByText('GitHub')).toBeInTheDocument();
      expect(screen.getByText('Azure')).toBeInTheDocument();
      expect(screen.getByText('Microsoft 365')).toBeInTheDocument();
      expect(screen.getByText('Notion')).toBeInTheDocument();
      expect(screen.getByText('Salesforce')).toBeInTheDocument();
      expect(screen.getByText('Slack')).toBeInTheDocument();
      expect(screen.getByText('Stripe')).toBeInTheDocument();
      expect(screen.getByText('Microsoft Teams')).toBeInTheDocument();
      expect(screen.getByText('Zoom')).toBeInTheDocument();
    });
  });

  // Test 3: shows green/yellow/red health indicators
  it('shows green/yellow/red health indicators', async () => {
    server.use(...mixedStatuses);

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('HEALTHY')).toBeInTheDocument();
      expect(screen.getByText('WARNING')).toBeInTheDocument();
    });

    // github healthy, azure warning, the other 7 errored
    expect(screen.getAllByText('ERROR')).toHaveLength(7);
    expect(screen.getByText('CONNECTED')).toBeInTheDocument(); // github only
  });

  // Test 4: displays summary stats cards
  it('displays summary stats cards', async () => {
    server.use(...allHealthy);

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Total Integrations')).toBeInTheDocument();
      expect(screen.getByText('Healthy')).toBeInTheDocument();
      expect(screen.getByText('Warnings')).toBeInTheDocument();
      expect(screen.getByText('Errors')).toBeInTheDocument();
      expect(screen.getByText('All configured')).toBeInTheDocument();
      expect(screen.getByText('Running smoothly')).toBeInTheDocument();
      expect(screen.getByText('Needs attention')).toBeInTheDocument();
      expect(screen.getByText('Requires action')).toBeInTheDocument();
    });

    // All 9 healthy: Total = 9 and Healthy = 9
    expect(screen.getAllByText('9')).toHaveLength(2);
    expect(screen.getByText('9/9 healthy')).toBeInTheDocument();
  });

  // Test 5: displays the overall health progress card
  it('displays overall health progress bar', async () => {
    server.use(...allHealthy);

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Overall Health')).toBeInTheDocument();
      expect(screen.getByText('9/9 healthy')).toBeInTheDocument();
    });
  });

  // Test 6: refresh button refetches health status
  it('handles refresh button click', async () => {
    let healthCalls = 0;
    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        healthCalls += 1;
        return res(ctx.status(200), ctx.json({ connected: true, status: 'healthy' }));
      })
    );

    render(<IntegrationHealthDashboard />);

    const refreshButton = await screen.findByRole('button', {
      name: /refresh/i,
    });
    expect(healthCalls).toBe(9); // initial load

    refreshButton.click();

    await waitFor(() => {
      expect(healthCalls).toBe(18);
    });
  });

  // Test 7: shows the last updated timestamp
  it('shows last updated timestamp', async () => {
    server.use(...allHealthy);

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/last updated/i)).toBeInTheDocument();
    });
  });

  // Test 8: displays the status legend
  it('displays status legend', async () => {
    server.use(...allHealthy);

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Status Legend')).toBeInTheDocument();
      expect(
        screen.getByText('Healthy - Integration is working properly')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Warning - Minor issues detected')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Error - Integration requires attention')
      ).toBeInTheDocument();
    });
  });

  // Test 9: fetch failures surface as error status with error counts
  it('handles failed health checks as errors', async () => {
    server.use(...allError);

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getAllByText('ERROR')).toHaveLength(9);
      expect(screen.getAllByText('1 errors')).toHaveLength(9);
      expect(screen.getByText('0/9 healthy')).toBeInTheDocument();
    });
  });

  // Test 10: respects the showDetails prop (hides per-integration details)
  it('respects showDetails prop', async () => {
    server.use(...allError);

    render(<IntegrationHealthDashboard showDetails={false} />);

    await waitFor(() => {
      expect(screen.getByText('Integration Status')).toBeInTheDocument();
      expect(screen.getAllByText('ERROR')).toHaveLength(9);
    });

    // Detail rows (error counts) are hidden when showDetails is false
    expect(screen.queryByText('1 errors')).not.toBeInTheDocument();
  });

  // Test 11: auto-refreshes when autoRefresh is true
  it('auto-refreshes when autoRefresh prop is true', async () => {
    let healthCalls = 0;
    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        healthCalls += 1;
        return res(ctx.status(200), ctx.json({ connected: true, status: 'healthy' }));
      })
    );

    render(
      <IntegrationHealthDashboard autoRefresh={true} refreshInterval={100} />
    );

    await screen.findByText('Integration Status');
    expect(healthCalls).toBe(9); // initial load

    // The 100ms interval refetches all 9 integrations after loading settles
    await waitFor(() => {
      expect(healthCalls).toBeGreaterThan(18);
    });
  });
});
