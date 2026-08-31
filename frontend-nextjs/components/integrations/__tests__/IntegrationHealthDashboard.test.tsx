/**
 * IntegrationHealthDashboard Component Tests
 *
 * Tests verify the real IntegrationHealthDashboard component
 * (components/integrations/IntegrationHealthDashboard.tsx), which renders
 * GET /api/integrations/health-status — the backend's real connection state
 * (UserConnection rows, tenant connectors, env credentials) plus live
 * provider verification where a credential is exercisable:
 * - healthy       connected + live provider call succeeded
 * - unreachable   connected + live provider call failed
 * - connected     connected, credential not exercisable in one call
 * - not_connected no connection or credential exists
 *
 * Uses the shared MSW server (tests/mocks/server.ts). Real timers are used
 * throughout (fake timers break MSW + RTL waitFor). The ui/spinner module is
 * mocked (its source references React without importing it, which throws
 * "React is not defined" whenever the loading state renders the real Spinner).
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import IntegrationHealthDashboard from '../IntegrationHealthDashboard';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

// The ui/spinner module references React without importing it, which throws
// "React is not defined" in the test runtime whenever the loading state
// renders the real Spinner. Mock it to a plain div so the component's own
// "Loading integration health status..." label can still be asserted.
jest.mock('@/components/ui/spinner', () => ({
  Spinner: ({ className }: { className?: string }) => (
    <div data-testid="spinner" className={className} />
  ),
}));

const providers = (extra: Record<string, any> = {}) => ({
  checked_at: '2026-08-29T00:00:00Z',
  providers: {
    github: {
      name: 'GitHub',
      category: 'development',
      connected: true,
      source: 'env',
      status: 'healthy',
      verified: true,
      response_time_ms: 212,
      error: null,
      checked_at: '2026-08-29T00:00:00Z',
    },
    slack: {
      name: 'Slack',
      category: 'communication',
      connected: true,
      source: 'user_connection',
      status: 'unreachable',
      verified: true,
      response_time_ms: 140,
      error: 'HTTP 401',
      checked_at: '2026-08-29T00:00:00Z',
    },
    salesforce: {
      name: 'Salesforce',
      category: 'crm',
      connected: true,
      source: 'user_connection',
      status: 'connected',
      verified: false,
      response_time_ms: null,
      error: null,
      checked_at: '2026-08-29T00:00:00Z',
    },
    stripe: {
      name: 'Stripe',
      category: 'finance',
      connected: false,
      source: 'none',
      status: 'not_connected',
      verified: false,
      response_time_ms: null,
      error: null,
      checked_at: null,
    },
    ...extra,
  },
});

const healthStatus = (body: any) =>
  rest.get('/api/integrations/health-status', (req, res, ctx) =>
    res(ctx.status(200), ctx.json(body))
  );

describe('IntegrationHealthDashboard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
  });

  // Test 1: renders the loading state while the status fetch is pending
  it('renders loading state while the health-status fetch is pending', () => {
    server.use(
      rest.get('/api/integrations/health-status', () => new Promise<undefined>(() => {})) // never resolves
    );

    render(<IntegrationHealthDashboard />);

    expect(
      screen.getByText(/loading integration health status/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
  });

  // Test 2: renders every provider reported by the backend
  it('shows the providers reported by health-status', async () => {
    server.use(healthStatus(providers()));

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Integration Status')).toBeInTheDocument();
      expect(screen.getByText('GitHub')).toBeInTheDocument();
      expect(screen.getByText('Slack')).toBeInTheDocument();
      expect(screen.getByText('Salesforce')).toBeInTheDocument();
      expect(screen.getByText('Stripe')).toBeInTheDocument();
    });
  });

  // Test 3: shows the four real statuses
  it('shows healthy/unverified/unreachable/not-connected indicators', async () => {
    server.use(healthStatus(providers()));

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('HEALTHY')).toBeInTheDocument();
      expect(screen.getByText('UNREACHABLE')).toBeInTheDocument();
      expect(screen.getByText('UNVERIFIED')).toBeInTheDocument();
      expect(screen.getByText('NOT CONNECTED')).toBeInTheDocument();
    });
  });

  // Test 4: surfaces the real provider error and measured response time
  it('shows the real error and response time details', async () => {
    server.use(healthStatus(providers()));

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('HTTP 401')).toBeInTheDocument();
      expect(screen.getByText('212ms')).toBeInTheDocument();
      expect(screen.getByText('Source: environment credentials')).toBeInTheDocument();
      expect(screen.getAllByText('Source: in-app connection')).toHaveLength(2);
    });
  });

  // Test 5: displays summary stats cards
  it('displays summary stats cards', async () => {
    server.use(healthStatus(providers()));

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
      expect(screen.getByText('Verified healthy')).toBeInTheDocument();
      expect(screen.getByText('Unreachable')).toBeInTheDocument();
      expect(screen.getByText('Unverified')).toBeInTheDocument();
      expect(screen.getByText('of 4 known integrations')).toBeInTheDocument();
      expect(screen.getByText('Live provider API call succeeded')).toBeInTheDocument();
      expect(screen.getByText('Credential rejected or provider failed')).toBeInTheDocument();
      expect(screen.getByText('Connected, credential not exercisable')).toBeInTheDocument();
    });
  });

  // Test 6: displays the connections progress card
  it('displays the connections progress card', async () => {
    server.use(healthStatus(providers()));

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Connections')).toBeInTheDocument();
      expect(screen.getByText('3/4 connected')).toBeInTheDocument();
      expect(screen.getByText('1 not connected')).toBeInTheDocument();
      expect(screen.getByText('1 verified healthy')).toBeInTheDocument();
    });
  });

  // Test 7: refresh button refetches health status
  it('handles refresh button click', async () => {
    let calls = 0;
    server.use(
      rest.get('/api/integrations/health-status', (req, res, ctx) => {
        calls += 1;
        return res(ctx.status(200), ctx.json(providers()));
      })
    );

    render(<IntegrationHealthDashboard />);

    const refreshButton = await screen.findByRole('button', {
      name: /refresh/i,
    });
    expect(calls).toBe(1); // initial load

    refreshButton.click();

    await waitFor(() => {
      expect(calls).toBe(2);
    });
  });

  // Test 8: shows the last updated timestamp
  it('shows last updated timestamp', async () => {
    server.use(healthStatus(providers()));

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/last updated/i)).toBeInTheDocument();
    });
  });

  // Test 9: displays the status legend
  it('displays status legend', async () => {
    server.use(healthStatus(providers()));

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Status Legend')).toBeInTheDocument();
      expect(
        screen.getByText('Healthy — connected and a live provider API call succeeded')
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          'Unreachable — connected but the credential was rejected or the provider failed'
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          'Unverified — connected, but the credential needs an interactive flow to test'
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          'Not connected — no connection or stored credential for this integration'
        )
      ).toBeInTheDocument();
    });
  });

  // Test 10: a failing status fetch must not crash the dashboard
  it('handles a failing health-status fetch without crashing', async () => {
    server.use(
      rest.get('/api/integrations/health-status', (req, res, ctx) =>
        res(ctx.status(500))
      )
    );

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Integration Status')).toBeInTheDocument();
    });
    // No provider rows rendered
    expect(screen.queryByText('GitHub')).not.toBeInTheDocument();
  });

  // Test 11: respects the showDetails prop (hides per-integration details)
  it('respects showDetails prop', async () => {
    server.use(healthStatus(providers()));

    render(<IntegrationHealthDashboard showDetails={false} />);

    await waitFor(() => {
      expect(screen.getByText('Integration Status')).toBeInTheDocument();
      expect(screen.getByText('UNREACHABLE')).toBeInTheDocument();
    });

    // Detail rows (error, response time, source) are hidden when showDetails is false
    expect(screen.queryByText('HTTP 401')).not.toBeInTheDocument();
    expect(screen.queryByText('212ms')).not.toBeInTheDocument();
    expect(screen.queryByText(/Source:/)).not.toBeInTheDocument();
  });

  // Test 12: auto-refreshes when autoRefresh is true
  it('auto-refreshes when autoRefresh prop is true', async () => {
    let calls = 0;
    server.use(
      rest.get('/api/integrations/health-status', (req, res, ctx) => {
        calls += 1;
        return res(ctx.status(200), ctx.json(providers()));
      })
    );

    render(
      <IntegrationHealthDashboard autoRefresh={true} refreshInterval={100} />
    );

    await screen.findByText('Integration Status');
    expect(calls).toBe(1); // initial load

    await waitFor(() => {
      expect(calls).toBeGreaterThan(2);
    });
  });
});
