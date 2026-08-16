/**
 * HealthMetricsGrid tests (components/dashboard/HealthMetricsGrid.tsx)
 *
 * Covers all four metric cards, every trend icon branch (up/down/stable),
 * and every status color branch (healthy/warning/neutral).
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { HealthMetricsGrid } from '@/components/dashboard/HealthMetricsGrid';

const metric = (overrides: Partial<any> = {}) => ({
  value: '12',
  trend: 'up' as const,
  trend_value: '5%',
  status: 'healthy' as const,
  ...overrides,
});

describe('HealthMetricsGrid', () => {
  it('renders all four metric cards with their values and trend text', () => {
    render(
      <HealthMetricsGrid
        metrics={{
          cash_runway: metric({ value: '18 months' }),
          lead_velocity: metric({ value: '24', trend_value: '8%' }),
          active_deals: metric({ value: '51', trend_value: '3%' }),
          churn_risk: metric({ value: '2.1%', trend_value: '0.4%' }),
        }}
      />
    );

    expect(screen.getByText('Cash Runway')).toBeInTheDocument();
    expect(screen.getByText('Lead Velocity')).toBeInTheDocument();
    expect(screen.getByText('Active Deals')).toBeInTheDocument();
    expect(screen.getByText('Churn Risk')).toBeInTheDocument();
    expect(screen.getByText('18 months')).toBeInTheDocument();
    expect(screen.getByText('24')).toBeInTheDocument();
    expect(screen.getByText('51')).toBeInTheDocument();
    expect(screen.getByText('2.1%')).toBeInTheDocument();
    // up trends render a "+" prefix
    expect(screen.getAllByText(/^\+5% from last month$/)).toHaveLength(1);
    expect(screen.getByText(/^\+8% from last month$/)).toBeInTheDocument();
  });

  it('renders down and stable trends without the + prefix', () => {
    render(
      <HealthMetricsGrid
        metrics={{
          cash_runway: metric({ trend: 'down', trend_value: '2 mo' }),
          lead_velocity: metric({ trend: 'stable', trend_value: '0%' }),
          active_deals: metric({ trend: 'down', trend_value: '1' }),
          churn_risk: metric({ trend: 'stable', trend_value: '0.1%' }),
        }}
      />
    );

    expect(screen.getByText(/^2 mo from last month$/)).toBeInTheDocument();
    expect(screen.getAllByText(/^0% from last month$/)).toHaveLength(1);
    expect(screen.getByText(/^1 from last month$/)).toBeInTheDocument();
    expect(screen.getAllByText(/^0.1% from last month$/)).toHaveLength(1);
  });

  it('applies status colors for warning and neutral statuses', () => {
    render(
      <HealthMetricsGrid
        metrics={{
          cash_runway: metric({ status: 'warning' }),
          lead_velocity: metric({ status: 'neutral' }),
          active_deals: metric({ status: 'healthy' }),
          churn_risk: metric({ status: 'neutral' }),
        }}
      />
    );

    const paragraphs = screen
      .getAllByText(/from last month$/)
      .map((el) => el.className);
    expect(paragraphs.some((c) => c.includes('text-red-600'))).toBe(true);
    expect(paragraphs.some((c) => c.includes('text-muted-foreground'))).toBe(
      true
    );
    expect(paragraphs.some((c) => c.includes('text-green-600'))).toBe(true);
  });
});
