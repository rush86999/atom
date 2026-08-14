/**
 * MetricsCard component tests.
 *
 * Covers the variant classes, trend icons, size classes, optional progress
 * bar, description and footer rendering, and the default/absent states.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import MetricsCard, { MetricCardProps } from '../MetricsCard';

const renderCard = (props: Partial<MetricCardProps> = {}) =>
  render(
    <MetricsCard title="Agents" value={42} description="Total agents" {...props} />
  );

describe('MetricsCard', () => {
  it('renders title, value and description', () => {
    renderCard();

    expect(screen.getByText('Agents')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('Total agents')).toBeInTheDocument();
  });

  it('applies no variant classes by default', () => {
    const { container } = renderCard();
    expect(container.querySelector('.border-green-500')).not.toBeInTheDocument();
    expect(container.querySelector('.border-yellow-500')).not.toBeInTheDocument();
    expect(container.querySelector('.border-red-500')).not.toBeInTheDocument();
  });

  it.each([
    ['success', 'border-green-500'],
    ['warning', 'border-yellow-500'],
    ['error', 'border-red-500'],
  ] as const)('applies the %s variant classes', (variant, expectedClass) => {
    const { container } = renderCard({ variant });
    expect(container.querySelector(`.${expectedClass}`)).toBeInTheDocument();
  });

  it('shows an upward trend icon with its value', () => {
    const { container } = renderCard({ trend: 'up', trendValue: '+12%' });

    expect(container.querySelector('svg.lucide-trending-up')).toBeInTheDocument();
    expect(screen.getByText('+12%')).toBeInTheDocument();
  });

  it('shows a downward trend icon with its value', () => {
    const { container } = renderCard({ trend: 'down', trendValue: '-5%' });

    expect(container.querySelector('svg.lucide-trending-down')).toBeInTheDocument();
    expect(screen.getByText('-5%')).toBeInTheDocument();
  });

  it('shows a neutral icon for a stable trend', () => {
    const { container } = renderCard({ trend: 'stable' });

    expect(container.querySelector('svg.lucide-minus')).toBeInTheDocument();
  });

  it('renders no trend icon when trend is not provided', () => {
    const { container } = renderCard();

    expect(container.querySelector('svg.lucide-minus')).not.toBeInTheDocument();
    expect(container.querySelector('svg.lucide-trending-up')).not.toBeInTheDocument();
  });

  it('renders the progress block only when a number is provided', () => {
    const { container, rerender } = renderCard({ progress: 75 });
    const progressBlock = container.querySelector('.mt-3');
    expect(progressBlock).not.toBeNull();
    expect(progressBlock!.querySelector('.bg-blue-600')).not.toBeNull();

    rerender(<MetricsCard title="Agents" value={42} />);
    expect(container.querySelector('.mt-3')).not.toBeInTheDocument();
  });

  it('renders the footer node', () => {
    renderCard({ footer: <button>View all</button> });

    expect(screen.getByRole('button', { name: 'View all' })).toBeInTheDocument();
  });

  it('renders the icon node', () => {
    renderCard({ icon: <span>📊</span> });
    expect(screen.getByText('📊')).toBeInTheDocument();
  });

  it('applies the small size class', () => {
    const { container } = renderCard({ size: 'sm' });
    expect(container.querySelector('.text-lg')).toBeInTheDocument();
  });

  it('applies the large size class', () => {
    const { container } = renderCard({ size: 'lg' });
    expect(container.querySelector('.text-4xl')).toBeInTheDocument();
  });

  it('applies the medium size class by default', () => {
    const { container } = renderCard();
    expect(container.querySelector('.text-2xl')).toBeInTheDocument();
  });
});
