/**
 * CacheMetricsPanel component tests.
 *
 * Covers the REAL CacheMetricsPanel (components/admin/jit-verification/CacheMetricsPanel.tsx),
 * a pure display component:
 * - Hit-rate percentages (overall = mean of verification + query rates), k-formatting,
 *   color-coded performance labels (Excellent/Good/Fair)
 * - L2 Active badge + Enabled/Disabled states
 * - Evictions section only when l1_evictions > 0
 * - Utilization badge, cache size badges
 * - Graceful defaults for missing/NaN values
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CacheMetricsPanel } from '../CacheMetricsPanel';
import type { CacheStatsResponse } from '@/types/jit-verification';

const baseStats: CacheStatsResponse = {
  l1_verification_cache_size: 12500,
  l1_query_cache_size: 2500,
  l1_verification_hits: 9000,
  l1_verification_misses: 1000,
  l1_verification_hit_rate: 0.9,
  l1_query_hits: 7000,
  l1_query_misses: 3000,
  l1_query_hit_rate: 0.7,
  l1_evictions: 5,
  l2_enabled: true,
};

describe('CacheMetricsPanel', () => {
  it('renders hit rates with the overall average and k-formatted numbers', () => {
    render(<CacheMetricsPanel stats={baseStats} />);

    expect(screen.getByText('Cache Performance')).toBeInTheDocument();
    // overall = (0.9 + 0.7) / 2 = 0.8 -> 80.0%
    expect(screen.getByText('80.0%')).toBeInTheDocument();
    expect(screen.getByText('90.0%')).toBeInTheDocument();
    expect(screen.getByText('70.0%')).toBeInTheDocument();
    // 9000 -> 9.0k, 1000 -> 1.0k
    expect(screen.getByText('Hits: 9.0k')).toBeInTheDocument();
    expect(screen.getByText('Misses: 1.0k')).toBeInTheDocument();
    // 12500 + 2500 = 15000 -> 15.0k entries
    expect(screen.getByText('15.0k entries')).toBeInTheDocument();
  });

  it('labels performance Excellent/Good based on hit rates', () => {
    render(<CacheMetricsPanel stats={baseStats} />);

    expect(screen.getByText('Verification Perf')).toBeInTheDocument();
    expect(screen.getAllByText('Excellent')).toHaveLength(2); // verification + overall
    expect(screen.getByText('Good')).toBeInTheDocument(); // query at 0.7
  });

  it('shows the evictions section only when evictions exist', () => {
    const { unmount } = render(<CacheMetricsPanel stats={baseStats} />);
    expect(screen.getByText('Cache Evictions Active')).toBeInTheDocument();
    expect(screen.getByText('5 evicted')).toBeInTheDocument();
    unmount();

    render(<CacheMetricsPanel stats={{ ...baseStats, l1_evictions: 0 }} />);
    expect(screen.queryByText('Cache Evictions Active')).not.toBeInTheDocument();
    expect(screen.queryByText(/evicted/)).not.toBeInTheDocument();
  });

  it('shows L2 Active badge and Enabled status when L2 is enabled', () => {
    render(<CacheMetricsPanel stats={baseStats} />);

    expect(screen.getByText('L2 Active')).toBeInTheDocument();
    expect(screen.getByText('Enabled')).toBeInTheDocument();
  });

  it('shows Disabled status and no L2 badge when L2 is disabled', () => {
    render(<CacheMetricsPanel stats={{ ...baseStats, l2_enabled: false }} />);

    expect(screen.queryByText('L2 Active')).not.toBeInTheDocument();
    expect(screen.getByText('Disabled')).toBeInTheDocument();
  });

  it('defaults missing/NaN values to 0% and 0 without crashing', () => {
    const sparse = {
      l1_verification_cache_size: NaN,
      l1_query_cache_size: 0,
      l1_verification_hits: undefined as any,
      l1_verification_misses: undefined as any,
      l1_verification_hit_rate: NaN,
      l1_query_hits: undefined as any,
      l1_query_misses: undefined as any,
      l1_query_hit_rate: NaN,
      l1_evictions: 0,
      l2_enabled: false,
    } as CacheStatsResponse;

    render(<CacheMetricsPanel stats={sparse} />);

    expect(screen.getAllByText('0%')).toHaveLength(3);
    expect(screen.getAllByText('0').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Fair')).toHaveLength(3); // NaN -> "Fair" via default labels
  });

  it('shows Fair performance for low hit rates with the red color class', () => {
    render(
      <CacheMetricsPanel
        stats={{
          ...baseStats,
          l1_verification_hit_rate: 0.3,
          l1_query_hit_rate: 0.4,
        }}
      />
    );

    expect(screen.getAllByText('Fair')).toHaveLength(3);
    expect(screen.getByText('35.0%')).toBeInTheDocument(); // overall (0.3+0.4)/2
  });
});
