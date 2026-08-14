/**
 * LatencyDisplay component tests.
 *
 * Covers latency formatting (µs/ms), color thresholds, L2 enabled/disabled
 * states, speedup figures, the comparison bars and the summary cards.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { LatencyDisplay } from '../LatencyDisplay';
import type { CacheStatsResponse } from '@/types/jit-verification';

const l2Enabled = { l2_enabled: true } as CacheStatsResponse;
const l2Disabled = { l2_enabled: false } as CacheStatsResponse;

describe('LatencyDisplay', () => {
  it('renders L1 latency in microseconds with defaults for L2 and S3', () => {
    render(<LatencyDisplay stats={l2Enabled} />);

    expect(screen.getByText('Cache Latency')).toBeInTheDocument();
    expect(screen.getAllByText('27µs')).toHaveLength(2);
    expect(screen.getAllByText('5.0ms')).toHaveLength(2);
    expect(screen.getAllByText('200.0ms')).toHaveLength(2);
  });

  it('shows the L1 speedup factor over S3', () => {
    render(<LatencyDisplay stats={l2Enabled} />);

    expect(screen.getByText('7407x')).toBeInTheDocument();
    expect(screen.getByText('L1 Speedup')).toBeInTheDocument();
  });

  it('shows the L2 speedup card when L2 is enabled', () => {
    render(<LatencyDisplay stats={l2Enabled} />);

    expect(screen.getByText('40x')).toBeInTheDocument();
    expect(screen.getByText('L2 Speedup')).toBeInTheDocument();
    expect(screen.getByText('🚀 Fast lookup (40x faster than S3)')).toBeInTheDocument();
  });

  it('marks L2 as disabled and hides the speedup card when L2 is disabled', () => {
    render(<LatencyDisplay stats={l2Disabled} />);

    expect(screen.getByText('Disabled')).toBeInTheDocument();
    expect(screen.queryByText('L2 Speedup')).not.toBeInTheDocument();
    expect(screen.queryByText('5.0ms')).not.toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('formats sub-millisecond custom latencies as microseconds', () => {
    render(<LatencyDisplay stats={l2Enabled} l2Latency={0.5} />);

    expect(screen.getAllByText('500µs')).toHaveLength(2);
  });

  it('uses the custom S3 latency for display and speedups', () => {
    render(<LatencyDisplay stats={l2Enabled} l2Latency={10} s3Latency={1000} />);

    expect(screen.getAllByText('10.0ms')).toHaveLength(2);
    expect(screen.getAllByText('1000.0ms')).toHaveLength(2);
    expect(screen.getByText('37037x')).toBeInTheDocument();
    expect(screen.getByText('100x')).toBeInTheDocument();
  });

  it('applies the red color class for slow S3 latencies', () => {
    const { container } = render(<LatencyDisplay stats={l2Enabled} />);

    expect(container.querySelector('.text-red-600')).toBeInTheDocument();
  });

  it('applies the green color class for sub-millisecond latencies', () => {
    const { container } = render(<LatencyDisplay stats={l2Enabled} l2Latency={0.2} />);

    expect(container.querySelector('.text-green-600')).toBeInTheDocument();
  });

  it('renders the latency comparison section with formatted values', () => {
    render(<LatencyDisplay stats={l2Enabled} />);

    expect(screen.getByText('Latency Comparison')).toBeInTheDocument();
    expect(screen.getByText('L1 Cache')).toBeInTheDocument();
    expect(screen.getByText('L2 Cache')).toBeInTheDocument();
    expect(screen.getByText('R2/S3')).toBeInTheDocument();
  });

  it('renders the performance tip and cache level details', () => {
    render(<LatencyDisplay stats={l2Enabled} />);

    expect(screen.getByText(/Performance Tip/)).toBeInTheDocument();
    expect(screen.getByText('In-Memory (LRU)')).toBeInTheDocument();
    expect(screen.getByText('Distributed (Redis)')).toBeInTheDocument();
    expect(screen.getByText('Cloud Storage')).toBeInTheDocument();
    expect(screen.getByText('head_object')).toBeInTheDocument();
  });
});
