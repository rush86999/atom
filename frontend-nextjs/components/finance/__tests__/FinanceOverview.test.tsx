/**
 * FinanceOverview component tests.
 *
 * Uses the shared MSW server (tests/mocks/server) per repo convention.
 * Covers the loading state, the two API-supplied revenue totals with currency
 * formatting (including an honest zero), per-metric availability, the
 * auth-token header, and the unavailable/retry cycle: any rejected, non-OK, or
 * malformed response must show an accessible unavailable state with a working
 * in-place retry.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import FinanceOverview from '../FinanceOverview';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const SUMMARY = {
  data: {
    total_revenue: 10000,
    pending_revenue: 2500,
    runway_months: 14,
    currency: 'USD',
    metric_availability: {
      total_revenue: true,
      pending_revenue: true,
    },
  },
};

const ZERO_SUMMARY = {
  data: {
    total_revenue: 0,
    pending_revenue: 0,
    currency: 'USD',
    metric_availability: {
      total_revenue: true,
      pending_revenue: true,
    },
  },
};

const summaryUrl = '/api/accounting/summary';

describe('FinanceOverview', () => {
  let lastAuthHeader: string | undefined;

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    lastAuthHeader = undefined;
    server.use(
      rest.get(summaryUrl, (req, res, ctx) => {
        lastAuthHeader = req.headers.get('Authorization') ?? undefined;
        return res(ctx.json(SUMMARY));
      })
    );
  });

  it('shows an accessible loading state before the summary resolves', () => {
    server.use(
      rest.get(summaryUrl, () => new Promise<never>(() => {})) as never
    );
    render(<FinanceOverview />);

    expect(
      screen.getByRole('status', { name: /loading finance summary/i })
    ).toBeInTheDocument();
  });

  it('renders only the API-supplied revenue totals with currency formatting', async () => {
    render(<FinanceOverview />);

    expect(await screen.findByText('Total Revenue')).toBeInTheDocument();
    expect(screen.getByText('$10,000.00')).toBeInTheDocument();
    expect(screen.getByText('Pending Revenue')).toBeInTheDocument();
    expect(screen.getByText('$2,500.00')).toBeInTheDocument();

    expect(screen.queryByText('Runway')).not.toBeInTheDocument();
    expect(screen.queryByText('Gross Profit')).not.toBeInTheDocument();
    expect(screen.queryByText('$5,800.00')).not.toBeInTheDocument();
    expect(screen.queryByText(/20\.1%/)).not.toBeInTheDocument();
    expect(screen.queryByText('Recent Activity')).not.toBeInTheDocument();
    expect(screen.queryByText('Chart Visualization Placeholder')).not.toBeInTheDocument();
  });

  it('renders one available total and Not synced for a metric flagged unavailable', async () => {
    server.use(
      rest.get(summaryUrl, (req, res, ctx) =>
        res(ctx.json({
          data: {
            total_revenue: 10000,
            pending_revenue: 0,
            currency: 'USD',
            metric_availability: {
              total_revenue: true,
              pending_revenue: false,
            },
          },
        }))
      )
    );
    render(<FinanceOverview />);

    expect(await screen.findByText('Total Revenue')).toBeInTheDocument();
    expect(screen.getByText('$10,000.00')).toBeInTheDocument();
    expect(screen.getByText('Pending Revenue')).toBeInTheDocument();
    expect(screen.getByText('Not synced')).toBeInTheDocument();
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('renders Not synced for an available metric flagged unavailable regardless of its stale value', async () => {
    server.use(
      rest.get(summaryUrl, (req, res, ctx) =>
        res(ctx.json({
          data: {
            total_revenue: 0,
            pending_revenue: 2500,
            currency: 'USD',
            metric_availability: {
              total_revenue: false,
              pending_revenue: true,
            },
          },
        }))
      )
    );
    render(<FinanceOverview />);

    expect(await screen.findByText('Total Revenue')).toBeInTheDocument();
    expect(screen.getByText('Not synced')).toBeInTheDocument();
    expect(screen.getByText('$2,500.00')).toBeInTheDocument();
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('renders an honest zero for a valid summary reporting zero balances', async () => {
    server.use(
      rest.get(summaryUrl, (req, res, ctx) => res(ctx.json(ZERO_SUMMARY)))
    );
    render(<FinanceOverview />);

    expect(await screen.findByText('Total Revenue')).toBeInTheDocument();
    expect(screen.getAllByText('$0.00')).toHaveLength(2);
    expect(screen.queryByText('Not synced')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('includes the auth token in the Authorization header when present', async () => {
    localStorage.setItem('auth_token', 'tok-123');
    render(<FinanceOverview />);

    await waitFor(() => expect(lastAuthHeader).toBe('Bearer tok-123'));
  });

  it('omits the Authorization header when no token is stored', async () => {
    render(<FinanceOverview />);

    await waitFor(() => expect(lastAuthHeader).toBeUndefined());
  });

  it('shows an accessible unavailable state with Try again when the response is not ok', async () => {
    server.use(rest.get(summaryUrl, (req, res, ctx) => res(ctx.status(500))));
    render(<FinanceOverview />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/finance summary unavailable/i);
    expect(screen.getByRole('button', { name: /try again/i })).toBeEnabled();

    expect(screen.queryByText('Total Revenue')).not.toBeInTheDocument();
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument();
  });

  it('shows the unavailable state and logs when the request rejects', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    server.use(rest.get(summaryUrl, (req, res, ctx) => res.networkError('boom')));
    render(<FinanceOverview />);

    expect(await screen.findByRole('alert')).toHaveTextContent(/finance summary unavailable/i);
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  it.each([
    [
      'a missing availability map',
      { data: { total_revenue: 10000, pending_revenue: 2500, currency: 'USD' } },
    ],
    [
      'an availability map missing a metric flag',
      {
        data: {
          total_revenue: 10000,
          pending_revenue: 2500,
          currency: 'USD',
          metric_availability: { total_revenue: true },
        },
      },
    ],
    [
      'an availability map with a non-boolean flag',
      {
        data: {
          total_revenue: 10000,
          pending_revenue: 2500,
          currency: 'USD',
          metric_availability: { total_revenue: true, pending_revenue: 'yes' },
        },
      },
    ],
    [
      'a missing required total',
      {
        data: {
          total_revenue: undefined,
          pending_revenue: 2500,
          currency: 'USD',
          metric_availability: { total_revenue: true, pending_revenue: true },
        },
      },
    ],
    [
      'a non-numeric available total',
      {
        data: {
          total_revenue: '10000',
          pending_revenue: 2500,
          currency: 'USD',
          metric_availability: { total_revenue: true, pending_revenue: true },
        },
      },
    ],
    [
      'a non-numeric available total even when the other metric is unavailable',
      {
        data: {
          total_revenue: '10000',
          pending_revenue: 2500,
          currency: 'USD',
          metric_availability: { total_revenue: true, pending_revenue: false },
        },
      },
    ],
    [
      'a missing data envelope',
      { total_revenue: 10000, pending_revenue: 2500, currency: 'USD' },
    ],
    [
      'an unsupported currency',
      {
        data: {
          total_revenue: 10000,
          pending_revenue: 2500,
          currency: 'NOT-A-CURRENCY',
          metric_availability: { total_revenue: true, pending_revenue: true },
        },
      },
    ],
  ])('shows the unavailable state for %s', async (_label, payload) => {
    server.use(
      rest.get(summaryUrl, (req, res, ctx) => res(ctx.json(payload)))
    );
    render(<FinanceOverview />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/finance summary unavailable/i);
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    expect(screen.queryByText('$10,000.00')).not.toBeInTheDocument();
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument();
  });

  it('shows the unavailable state when the response body is not valid JSON', async () => {
    server.use(
      rest.get(summaryUrl, (req, res, ctx) =>
        res(ctx.set('Content-Type', 'application/json'), ctx.body('not-json'))
      )
    );
    render(<FinanceOverview />);

    expect(await screen.findByRole('alert')).toHaveTextContent(/finance summary unavailable/i);
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument();
  });

  it('recovers in place when Try again succeeds after a failed response', async () => {
    let requestCount = 0;
    server.use(
      rest.get(summaryUrl, (req, res, ctx) => {
        requestCount += 1;
        return requestCount === 1
          ? res(ctx.status(503))
          : res(ctx.json(SUMMARY));
      })
    );
    render(<FinanceOverview />);

    const alert = await screen.findByRole('alert');
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));

    // The unavailable state stays visible until a valid summary arrives.
    expect(alert).toBeInTheDocument();

    expect(await screen.findByText('$10,000.00')).toBeInTheDocument();
    expect(screen.getByText('$2,500.00')).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    );
    expect(requestCount).toBe(2);
  });
});
