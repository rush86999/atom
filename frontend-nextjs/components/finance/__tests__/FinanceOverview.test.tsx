/**
 * FinanceOverview component tests.
 *
 * Uses the shared MSW server (tests/mocks/server) per repo convention.
 * Covers the loading state, successful summary rendering with currency
 * formatting, the auth-token header, and fallback defaults on failure.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
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

  it('shows a loading spinner before the summary resolves', () => {
    server.use(
      rest.get(summaryUrl, () => new Promise<never>(() => {})) as never
    );
    render(<FinanceOverview />);

    expect(document.querySelector('svg.lucide-loader-circle')).toBeInTheDocument();
  });

  it('renders revenue metrics with currency formatting and the gross profit estimate', async () => {
    render(<FinanceOverview />);

    expect(await screen.findByText('Total Revenue')).toBeInTheDocument();
    expect(screen.getByText('$10,000.00')).toBeInTheDocument();
    expect(screen.getByText('Pending Revenue')).toBeInTheDocument();
    expect(screen.getByText('$2,500.00')).toBeInTheDocument();
    expect(screen.getByText('Runway')).toBeInTheDocument();
    expect(screen.getByText('14 Months')).toBeInTheDocument();
    expect(screen.getByText('Gross Profit')).toBeInTheDocument();
    expect(screen.getByText('$5,800.00')).toBeInTheDocument();
  });

  it('renders recent activity entries', async () => {
    render(<FinanceOverview />);

    await screen.findByText('Total Revenue');
    expect(screen.getByText('Stripe Payout')).toBeInTheDocument();
    expect(screen.getByText('+$2,400.00')).toBeInTheDocument();
    expect(screen.getByText('AWS Bill')).toBeInTheDocument();
    expect(screen.getByText('-$142.00')).toBeInTheDocument();
    expect(screen.getByText('Client Payment')).toBeInTheDocument();
    expect(screen.getByText('Upwork Earnings')).toBeInTheDocument();
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

  it('falls back to zeroed metrics when the response is not ok', async () => {
    server.use(rest.get(summaryUrl, (req, res, ctx) => res(ctx.status(500))));
    render(<FinanceOverview />);

    expect((await screen.findAllByText('$0.00')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('0 Months')).toBeInTheDocument();
  });

  it('falls back to zeroed metrics and logs when the request rejects', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    server.use(rest.get(summaryUrl, (req, res, ctx) => res.networkError('boom')));
    render(<FinanceOverview />);

    expect((await screen.findAllByText('$0.00')).length).toBeGreaterThanOrEqual(1);
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
