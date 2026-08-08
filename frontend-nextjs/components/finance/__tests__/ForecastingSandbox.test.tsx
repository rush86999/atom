/**
 * ForecastingSandbox Component Tests
 *
 * Covers the REAL ForecastingSandbox (components/finance/ForecastingSandbox.tsx):
 * - Fetches /api/accounting/forecast?workspace_id=default-workspace on mount
 *   and feeds the projection into the chart
 * - Chart surfaces are mocked (recharts cannot render without layout in
 *   jsdom); the data payload is asserted via the mocked LineChart
 * - Scenario sandbox: Analyze POSTs the encoded description to
 *   /api/accounting/scenario and renders impact value, risk level, and
 *   analysis with a success toast
 * - Scenario failures toast "Scenario Failed" and keep the sandbox usable
 * - Empty projection renders without crashing
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ForecastingSandbox from '../ForecastingSandbox';

jest.mock('@/components/ui/use-toast', () => {
  const mockToastFn = jest.fn();
  return {
    __toast: mockToastFn,
    useToast: () => ({ toast: mockToastFn, dismiss: jest.fn(), toasts: [] }),
    ToastProvider: ({ children }: { children: any }) => children,
  };
});

const mockToast = require('@/components/ui/use-toast').__toast as jest.Mock;

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="chart-container">{children}</div>,
  LineChart: ({ children, data }: any) => (
    <div data-testid="line-chart" data-points={data ? data.length : 0}>{children}</div>
  ),
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ReferenceLine: () => null,
}));

const projection = [
  { week_start: '2026-08-03', projected_balance: 12000 },
  { week_start: '2026-08-10', projected_balance: 9800 },
  { week_start: '2026-08-17', projected_balance: 7500 },
];

describe('ForecastingSandbox', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ projection }),
    });
  });

  test('fetches the forecast on mount and feeds the projection to the chart', async () => {
    render(<ForecastingSandbox />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/accounting/forecast?workspace_id=default-workspace',
        expect.anything()
      );
    });

    expect(await screen.findByText('13-Week Cash Flow Forecast')).toBeInTheDocument();
    expect(screen.getByTestId('line-chart').getAttribute('data-points')).toBe('3');
    expect(screen.getByTestId('chart-container')).toBeInTheDocument();
  });

  test('renders the chart with zero points when the API returns an empty projection', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ projection: [] }) });

    render(<ForecastingSandbox />);

    await waitFor(() => {
      expect(screen.getByTestId('line-chart').getAttribute('data-points')).toBe('0');
    });
    expect(screen.getByText('13-Week Cash Flow Forecast')).toBeInTheDocument();
  });

  test('degrades gracefully when the forecast fetch fails', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('forecast down'));

    render(<ForecastingSandbox />);

    expect(await screen.findByText('13-Week Cash Flow Forecast')).toBeInTheDocument();
    expect(screen.getByTestId('line-chart').getAttribute('data-points')).toBe('0');
  });

  test('runs a scenario and renders the impact analysis', async () => {
    let scenarioHit = false;
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        scenarioHit = true;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            impact_value: -1500,
            risk_level: 'medium',
            analysis: 'Cash runway shortens by two weeks.',
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({ projection }) });
    });

    render(<ForecastingSandbox />);
    await screen.findByText('13-Week Cash Flow Forecast');

    fireEvent.change(screen.getByPlaceholderText('Describe a scenario...'), {
      target: { value: 'Hire a dev for $10k/mo' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Analyze/i }));

    expect(await screen.findByText('Scenario Impact Análisis')).toBeInTheDocument();
    expect(scenarioHit).toBe(true);
    expect(
      (global.fetch as jest.Mock).mock.calls.some(
        (c) => String(c[0]).includes('scenario?') && String(c[0]).includes(encodeURIComponent('Hire a dev for $10k/mo'))
      )
    ).toBe(true);

    // Negative impact renders with a leading minus, $, and absolute value
    // (the pieces are separate text nodes inside the <p>)
    expect(
      screen.getByText((_, el) => el?.tagName === 'P' && el.textContent === '-$1,500')
    ).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();
    expect(screen.getByText(/Cash runway shortens by two weeks/)).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Scenario Modeled' })
    );
  });

  test('does nothing when Analyze is clicked without a scenario', () => {
    render(<ForecastingSandbox />);

    fireEvent.click(screen.getByRole('button', { name: /Analyze/i }));

    expect(mockToast).not.toHaveBeenCalled();
    expect(
      (global.fetch as jest.Mock).mock.calls.some((c) => String(c[0]).includes('scenario?'))
    ).toBe(false);
  });

  test('toasts Scenario Failed when the scenario request errors', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') return Promise.resolve({ ok: false });
      return Promise.resolve({ ok: true, json: async () => ({ projection }) });
    });

    render(<ForecastingSandbox />);
    await screen.findByText('13-Week Cash Flow Forecast');

    fireEvent.change(screen.getByPlaceholderText('Describe a scenario...'), {
      target: { value: 'Lose our biggest client' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Analyze/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Scenario Failed', variant: 'destructive' })
      );
    });
    expect(screen.queryByText('Scenario Impact Análisis')).not.toBeInTheDocument();
  });
});
