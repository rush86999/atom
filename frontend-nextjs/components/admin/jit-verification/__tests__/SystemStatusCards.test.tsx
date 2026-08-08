/**
 * SystemStatusCards component tests.
 *
 * Covers the REAL SystemStatusCards (components/admin/jit-verification/SystemStatusCards.tsx),
 * a pure display component rendering Worker/Cache/Citations/Health cards:
 * - Worker running/stopped badge states with verified/failed counts
 * - Cache hit-rate formatting + evictions row
 * - Citations total k-formatting + stale warning row
 * - Health healthy/degraded/unhealthy statuses, worker + cache sub-info, issue counts
 * - Null props render defaults without crashing
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SystemStatusCards } from '../SystemStatusCards';
import type {
  WorkerMetricsResponse,
  CacheStatsResponse,
  HealthCheckResponse,
} from '@/types/jit-verification';

const workerMetrics: WorkerMetricsResponse = {
  running: true,
  total_citations: 1500,
  verified_count: 1200,
  failed_count: 50,
  stale_facts: 3,
  outdated_facts: 1,
  last_run_time: '2026-08-07T09:00:00Z',
  last_run_duration: 60,
  average_verification_time: 0.2,
  top_citations: [],
};

const cacheStats: CacheStatsResponse = {
  l1_verification_cache_size: 8200,
  l1_query_cache_size: 1500,
  l1_verification_hits: 9000,
  l1_verification_misses: 1000,
  l1_verification_hit_rate: 0.9,
  l1_query_hits: 7000,
  l1_query_misses: 3000,
  l1_query_hit_rate: 0.7,
  l1_evictions: 4,
  l2_enabled: true,
};

const healthyStatus: HealthCheckResponse = {
  status: 'healthy',
  issues: [],
  cache: {
    l1_enabled: true,
    l2_enabled: true,
    verification_hit_rate: '87%',
    query_hit_rate: '80%',
    total_cached_verifications: 8200,
  },
  worker: {
    running: true,
    verified_count: 1200,
    failed_count: 50,
    avg_verification_time: '0.200s',
  },
  checked_at: '2026-08-07T10:00:00Z',
};

describe('SystemStatusCards', () => {
  it('renders all four status cards', () => {
    render(<SystemStatusCards workerMetrics={workerMetrics} cacheStats={cacheStats} healthStatus={healthyStatus} />);

    expect(screen.getByText('Worker Status')).toBeInTheDocument();
    expect(screen.getByText('Cache Health')).toBeInTheDocument();
    expect(screen.getByText('Citations')).toBeInTheDocument();
    expect(screen.getByText('System Health')).toBeInTheDocument();
  });

  it('shows the worker as Running/Active with verified and failed counts', () => {
    render(<SystemStatusCards workerMetrics={workerMetrics} cacheStats={cacheStats} healthStatus={healthyStatus} />);

    // "Running" appears in both the Worker Status badge and the System Health badge
    expect(screen.getAllByText('Running').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('1200')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
    expect(screen.getByText(/Last run:/)).toBeInTheDocument();
  });

  it('shows the worker as Stopped/Inactive when not running', () => {
    render(<SystemStatusCards workerMetrics={{ ...workerMetrics, running: false }} cacheStats={cacheStats} healthStatus={healthyStatus} />);

    expect(screen.getByText('Stopped')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  it('formats the cache hit rate and shows evictions', () => {
    render(<SystemStatusCards workerMetrics={workerMetrics} cacheStats={cacheStats} healthStatus={healthyStatus} />);

    expect(screen.getAllByText('90%')).toHaveLength(2); // l1_verification_hit_rate 0.9 -> 90% (big number + Hit Rate label)
    expect(screen.getByText('8.2k')).toBeInTheDocument(); // 8200 -> 8.2k
    expect(screen.getByText('Evictions')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('formats the citations total and shows the stale warning', () => {
    render(<SystemStatusCards workerMetrics={workerMetrics} cacheStats={cacheStats} healthStatus={healthyStatus} />);

    expect(screen.getByText('1.5k')).toBeInTheDocument(); // 1500 -> 1.5k
    expect(screen.getByText('Stale')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('renders a healthy system health card with worker and cache sub-info', () => {
    render(<SystemStatusCards workerMetrics={workerMetrics} cacheStats={cacheStats} healthStatus={healthyStatus} />);

    expect(screen.getByText('healthy')).toBeInTheDocument();
    expect(screen.getByText('87%')).toBeInTheDocument(); // cache hit from health payload
  });

  it('renders degraded status with the issue count', () => {
    render(
      <SystemStatusCards
        workerMetrics={workerMetrics}
        cacheStats={cacheStats}
        healthStatus={{ ...healthyStatus, status: 'degraded', issues: ['L2 cache degraded'] }}
      />
    );

    expect(screen.getByText('degraded')).toBeInTheDocument();
    expect(screen.getByText('1 issue')).toBeInTheDocument();
  });

  it('renders unhealthy status with plural issues', () => {
    render(
      <SystemStatusCards
        workerMetrics={workerMetrics}
        cacheStats={cacheStats}
        healthStatus={{ ...healthyStatus, status: 'unhealthy', issues: ['Worker down', 'Cache full'] }}
      />
    );

    expect(screen.getByText('unhealthy')).toBeInTheDocument();
    expect(screen.getByText('2 issues')).toBeInTheDocument();
  });

  it('renders default values when all props are null', () => {
    render(<SystemStatusCards workerMetrics={null} cacheStats={null} healthStatus={null} />);

    expect(screen.getByText('Stopped')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
    expect(screen.getAllByText('0%').length).toBeGreaterThanOrEqual(1); // cache hit rate default
    expect(screen.getByText('unhealthy')).toBeInTheDocument(); // health status default
  });
});
