/**
 * UnifiedServicesManager Component Tests
 * (components/UnifiedServicesManager.tsx)
 *
 * Tests verify the real component against the communication services API:
 * - loads implementation status on mount and renders both services with
 *   their current implementation + health status (per-service /health fetch)
 * - renders environment badge and the stats cards (healthy / mock / real /
 *   error counts) computed from service state
 * - expand/collapse reveals implementation availability + health details
 * - Switch to Real POSTs /implementations/switch with the service name and
 *   implementation type, refetches status, and fires onImplementationChange
 * - switch failure surfaces the error banner
 * - "All to Mock" switches every service
 * - refresh button refetches implementations + health for all services
 * - health check button fires onServiceHealthChange
 *
 * APIs: GET /implementations, GET /health,
 *       POST /implementations/switch (base http://localhost:8000)
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

import { UnifiedServicesManager } from '../UnifiedServicesManager';

// The component fetches relative URLs (process.env.NEXT_PUBLIC_API_BASE_URL
// unset in tests); MSW resolves those against the jsdom origin, so handlers
// must be host-agnostic paths rather than absolute http://localhost:8000 URLs.
const BASE = '';

const implPayload = {
  environment: 'production',
  services: {
    Slack: {
      current: 'mock',
      mock_available: true,
      real_available: true,
      health: { status: 'unknown' },
    },
    MicrosoftTeams: {
      current: 'mock',
      mock_available: true,
      real_available: false,
      health: { status: 'unknown' },
    },
  },
};

const healthPayload = {
  services: {
    slack: {
      status: 'healthy',
      api_healthy: true,
      config_healthy: true,
      token_valid: true,
      checked_at: '2026-08-07T10:00:00.000Z',
    },
    microsoftteams: {
      status: 'healthy',
      api_healthy: true,
      config_healthy: true,
      token_valid: true,
      checked_at: '2026-08-07T10:00:00.000Z',
    },
  },
};

describe('UnifiedServicesManager', () => {
  // The initial state already renders "Slack" — wait for the loaded
  // environment badge to know the mount fetch has completed.
  const waitForLoad = () => screen.findByText('Environment: production');

  let implFetches: number;
  let healthFetches: number;
  let switchBodies: any[];
  let switchOk: boolean;

  beforeEach(() => {
    jest.clearAllMocks();
    implFetches = 0;
    healthFetches = 0;
    switchBodies = [];
    switchOk = true;

    server.resetHandlers();
    server.use(
      rest.get(`${BASE}/implementations`, (req, res, ctx) => {
        implFetches += 1;
        return res(ctx.status(200), ctx.json(implPayload));
      }),
      rest.get(`${BASE}/health`, (req, res, ctx) => {
        healthFetches += 1;
        return res(ctx.status(200), ctx.json(healthPayload));
      }),
      rest.post(`${BASE}/implementations/switch`, async (req, res, ctx) => {
        switchBodies.push(req.body);
        if (!switchOk) return res(ctx.status(400), ctx.json({ error: 'Switch rejected' }));
        return res(ctx.status(200), ctx.json({ ok: true }));
      })
    );
  });

  it('renders both services with implementations and health from the API', async () => {
    render(<UnifiedServicesManager />);

    expect(await screen.findByText('Slack')).toBeInTheDocument();
    expect(screen.getByText('MicrosoftTeams')).toBeInTheDocument();

    // environment from the API (waits for the mount fetch to resolve)
    expect(await waitForLoad()).toBeInTheDocument();

    // current implementation badges + healthy status from /health
    const mocks = screen.getAllByText('mock');
    expect(mocks.length).toBeGreaterThanOrEqual(2);
    expect(await screen.findAllByText('healthy')).toHaveLength(2);

    expect(implFetches).toBe(1);
    expect(healthFetches).toBe(2);
  });

  it('computes the stats cards from service state', async () => {
    render(<UnifiedServicesManager />);

    await waitForLoad();
    expect(await screen.findAllByText('healthy')).toHaveLength(2);

    expect(screen.getByText('Healthy Services')).toBeInTheDocument();
    expect(screen.getByText('Mock Implementations')).toBeInTheDocument();
    expect(screen.getByText('Real Implementations')).toBeInTheDocument();
    expect(screen.getByText('Services with Errors')).toBeInTheDocument();
    // 2 healthy services + 2 mock implementations
    expect(screen.getAllByText('2')).toHaveLength(2);
    expect(screen.getAllByText('0')).toHaveLength(2); // real + error counts
  });

  it('expands a service to reveal implementation availability and health details', async () => {
    render(<UnifiedServicesManager />);
    await waitForLoad();

    fireEvent.click(screen.getAllByTitle('Toggle details')[0]);

    expect(screen.getByText('Implementation Status')).toBeInTheDocument();
    expect(screen.getByText('Mock Implementation')).toBeInTheDocument();
    expect(screen.getByText('Real Implementation')).toBeInTheDocument();
    expect(screen.getByText('Switch Implementation')).toBeInTheDocument();
    expect(screen.getByText('Health Details')).toBeInTheDocument();
    expect(screen.getByText('✅ Healthy')).toBeInTheDocument();
    // config_healthy + token_valid both render "✅ Valid"
    expect(screen.getAllByText('✅ Valid')).toHaveLength(2);

    // collapse again
    fireEvent.click(screen.getAllByTitle('Toggle details')[0]);
    expect(screen.queryByText('Implementation Status')).not.toBeInTheDocument();
  });

  it('switches a service to real: POSTs, refetches, and fires the callback', async () => {
    const onImplementationChange = jest.fn();

    render(
      <UnifiedServicesManager
        onImplementationChange={onImplementationChange}
        onServiceHealthChange={jest.fn()}
      />
    );
    await waitForLoad();

    fireEvent.click(screen.getAllByTitle('Toggle details')[0]);
    fireEvent.click(screen.getByText('🌐 Switch to Real'));

    await waitFor(() => expect(switchBodies).toHaveLength(1));
    expect(switchBodies[0]).toEqual({
      service_name: 'Slack',
      implementation_type: 'real',
    });

    // status refetched after switch
    await waitFor(() => expect(implFetches).toBe(2));
    expect(onImplementationChange).toHaveBeenCalledWith('Slack', 'real');
  });

  it('shows an error banner when the switch fails and does not fire the callback', async () => {
    switchOk = false;
    const onImplementationChange = jest.fn();

    render(<UnifiedServicesManager onImplementationChange={onImplementationChange} />);
    await waitForLoad();

    fireEvent.click(screen.getAllByTitle('Toggle details')[0]);
    fireEvent.click(screen.getByText('🌐 Switch to Real'));

    expect(await screen.findByText('Switch rejected')).toBeInTheDocument();
    expect(onImplementationChange).not.toHaveBeenCalled();
  });

  it('disables the switch button for implementations that are unavailable', async () => {
    render(<UnifiedServicesManager />);
    await waitForLoad();

    // expandedService is single-valued: only one service is expanded at a time.
    // Expand Slack first → its Switch to Real is enabled.
    fireEvent.click(screen.getAllByTitle('Toggle details')[0]);
    expect(screen.getAllByText('🌐 Switch to Real')[0].closest('button')).not.toBeDisabled();

    // Toggle to Teams (replaces the expanded service) → real_available: false
    // means its Switch to Real button is disabled.
    fireEvent.click(screen.getAllByTitle('Toggle details')[1]);
    expect(screen.getAllByText('🌐 Switch to Real')[0].closest('button')).toBeDisabled();
  });

  it('"All to Mock" switches every service', async () => {
    render(<UnifiedServicesManager />);
    await waitForLoad();

    fireEvent.click(screen.getByText('🎭 All to Mock'));

    await waitFor(() => expect(switchBodies).toHaveLength(2));
    expect(switchBodies.map((b) => b.service_name)).toEqual(['Slack', 'MicrosoftTeams']);
    expect(switchBodies.every((b) => b.implementation_type === 'mock')).toBe(true);
  });

  it('re-fetches status and health when Refresh is clicked', async () => {
    render(<UnifiedServicesManager />);
    await waitForLoad();
    await waitFor(() => expect(implFetches).toBe(1));

    fireEvent.click(screen.getByText('Refresh'));

    await waitFor(() => expect(implFetches).toBe(2));
    // refreshData = fetchImplementationStatus (1 impl + 2 health) + 2 health
    expect(healthFetches).toBe(6); // 2 from mount + 4 from refresh
  });

  it('renders a loading indicator while fetching', async () => {
    server.use(
      rest.get(`${BASE}/implementations`, (req, res, ctx) => {
        implFetches += 1;
        return new Promise((resolve) => setTimeout(() => {
          resolve(res(ctx.status(200), ctx.json(implPayload)));
        }, 100));
      })
    );

    render(<UnifiedServicesManager />);

    expect(screen.getByText('Loading services status...')).toBeInTheDocument();
    // wait for the delayed implementations response to land (the initial
    // state already renders "Slack", so wait on the environment badge)
    expect(await screen.findByText('Environment: production')).toBeInTheDocument();
    expect(screen.queryByText('Loading services status...')).not.toBeInTheDocument();
  });

  it('fires onServiceHealthChange when a service health check is triggered', async () => {
    const onServiceHealthChange = jest.fn();

    render(<UnifiedServicesManager onServiceHealthChange={onServiceHealthChange} />);
    await waitForLoad();

    fireEvent.click(screen.getAllByTitle('Check health')[0]);

    await waitFor(() => {
      expect(onServiceHealthChange).toHaveBeenCalledWith(
        expect.objectContaining({ service: 'Slack', status: 'healthy', api_healthy: true })
      );
    });
  });

  it('fires onServiceHealthChange after a successful switch (deferred health check)', async () => {
    const onServiceHealthChange = jest.fn();

    // The component defers the post-switch health check with a 1s setTimeout.
    // Real timers: waitFor must outlive that delay (a global setTimeout spy
    // would corrupt RTL's waitFor timer bookkeeping).
    render(
      <UnifiedServicesManager
        onImplementationChange={jest.fn()}
        onServiceHealthChange={onServiceHealthChange}
      />
    );
    await waitForLoad();

    fireEvent.click(screen.getAllByTitle('Toggle details')[0]);
    fireEvent.click(screen.getByText('🌐 Switch to Real'));

    await waitFor(
      () => {
        expect(onServiceHealthChange).toHaveBeenCalledWith(
          expect.objectContaining({ service: 'Slack', status: 'healthy' })
        );
      },
      { timeout: 3000 }
    );
  });

  it('clears the deferred post-switch health check on unmount', async () => {
    const onServiceHealthChange = jest.fn();

    const { unmount } = render(
      <UnifiedServicesManager
        onImplementationChange={jest.fn()}
        onServiceHealthChange={onServiceHealthChange}
      />
    );
    await waitForLoad();

    fireEvent.click(screen.getAllByTitle('Toggle details')[0]);
    fireEvent.click(screen.getByText('🌐 Switch to Real'));
    // switch POST + status refetch completed
    await waitFor(() => expect(implFetches).toBe(2));
    expect(healthFetches).toBe(4); // 2 mount + 2 refetch

    unmount();

    // Wait past the 1s deferred health-check window: nothing may fire
    // (fetch or callback) after the component is gone.
    await new Promise((resolve) => setTimeout(resolve, 1200));

    expect(healthFetches).toBe(4);
    expect(onServiceHealthChange).not.toHaveBeenCalled();
  });

  it('renders an error state when the implementations fetch fails', async () => {
    server.use(
      rest.get(`${BASE}/implementations`, (req, res, ctx) => res.networkError('boom'))
    );

    render(<UnifiedServicesManager />);

    // network error → fetch rejects with a plain TypeError; the component
    // surfaces err.message ("Failed to fetch")
    expect(await screen.findByText('Failed to fetch')).toBeInTheDocument();
  });
});
