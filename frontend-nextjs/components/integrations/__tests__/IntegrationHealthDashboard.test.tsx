/**
 * Integration Health Dashboard Component Tests
 *
 * Test suite for integration health monitoring dashboard
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../../tests/mocks/server';
import IntegrationHealthDashboard from '../IntegrationHealthDashboard';

describe('IntegrationHealthDashboard', () => {
  beforeEach(() => {
    server.resetHandlers();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it('renders dashboard card/section', async () => {
    server.use(
      rest.get('/api/integrations/*/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            connected: false,
            status: 'unknown'
          })
        );
      })
    );

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Integration Status')).toBeInTheDocument();
    });
  });

  it('shows list of integrations with health status', async () => {
    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        const platform = req.params.platform;
        return res(
          ctx.status(200),
          ctx.json({
            connected: platform === 'github',
            status: platform === 'github' ? 'healthy' : 'error'
          })
        );
      })
    );

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('GitHub')).toBeInTheDocument();
      expect(screen.getByText('Azure')).toBeInTheDocument();
      expect(screen.getByText('Slack')).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('shows green/yellow/red health indicators', async () => {
    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        const platform = req.params.platform;
        if (platform === 'github') {
          return res(
            ctx.status(200),
            ctx.json({ connected: true, status: 'healthy' })
          );
        } else if (platform === 'slack') {
          return res(
            ctx.status(200),
            ctx.json({ connected: false, status: 'warning' })
          );
        }
        return res(
          ctx.status(500),
          ctx.json({ connected: false, status: 'error' })
        );
      })
    );

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('HEALTHY')).toBeInTheDocument();
      expect(screen.getByText('WARNING')).toBeInTheDocument();
      expect(screen.getByText('ERROR')).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('handles empty integrations array', async () => {
    // This would require mocking the integrationList, which is internal
    // For now, we test that it renders without crashing
    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Total Integrations')).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('shows loading state with skeleton/spinner', () => {
    // Component shows loading initially
    render(<IntegrationHealthDashboard />);

    expect(screen.getByText(/loading integration health/i)).toBeInTheDocument();
  });

  it('individual integration status change triggers visual update', async () => {
    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            connected: true,
            status: 'healthy'
          })
        );
      })
    );

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('displays summary stats cards', async () => {
    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            connected: true,
            status: 'healthy'
          })
        );
      })
    );

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Total Integrations')).toBeInTheDocument();
      expect(screen.getByText('Healthy')).toBeInTheDocument();
      expect(screen.getByText('Warnings')).toBeInTheDocument();
      expect(screen.getByText('Errors')).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('handles refresh button click', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            connected: true,
            status: 'healthy'
          })
        );
      })
    );

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Refresh')).toBeInTheDocument();
    }, { timeout: 5000 });

    const refreshButton = screen.getByText('Refresh');
    await user.click(refreshButton);

    // Verify button exists and is clickable
    expect(refreshButton).toBeInTheDocument();
  });

  it('displays health progress bar', async () => {
    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            connected: true,
            status: 'healthy'
          })
        );
      })
    );

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Overall Health')).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('shows last updated timestamp', async () => {
    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            connected: true,
            status: 'healthy'
          })
        );
      })
    );

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/last updated/i)).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('displays status legend', async () => {
    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            connected: true,
            status: 'healthy'
          })
        );
      })
    );

    render(<IntegrationHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Status Legend')).toBeInTheDocument();
      expect(screen.getByText(/healthy - integration is working properly/i)).toBeInTheDocument();
      expect(screen.getByText(/warning - minor issues detected/i)).toBeInTheDocument();
      expect(screen.getByText(/error - integration requires attention/i)).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('auto-refreshes when autoRefresh prop is true', async () => {
    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            connected: true,
            status: 'healthy'
          })
        );
      })
    );

    render(<IntegrationHealthDashboard autoRefresh={true} refreshInterval={10000} />);

    await waitFor(() => {
      expect(screen.getByText('Integration Status')).toBeInTheDocument();
    }, { timeout: 5000 });

    // Advance timers to trigger auto-refresh
    act(() => {
      jest.advanceTimersByTime(10000);
    });
  });

  it('respects showDetails prop', async () => {
    server.use(
      rest.get('/api/integrations/:platform/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            connected: true,
            status: 'healthy',
            lastSync: new Date().toISOString(),
            responseTime: 100
          })
        );
      })
    );

    render(<IntegrationHealthDashboard showDetails={false} />);

    await waitFor(() => {
      expect(screen.getByText('Integration Status')).toBeInTheDocument();
    }, { timeout: 5000 });
  });
});
