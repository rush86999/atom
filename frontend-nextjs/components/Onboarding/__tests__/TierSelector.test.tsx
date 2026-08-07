/**
 * TierSelector component tests.
 *
 * The useCognitiveTier hook is mocked so compareTiers can be driven directly.
 * Covers the five tier cards, cost/quality badges (derived from comparison
 * ranges), selection callback + selected indicator, and the loading state.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { TierSelector } from '../TierSelector';

const mockCompareTiers = jest.fn();

jest.mock('@/hooks/useCognitiveTier', () => ({
  useCognitiveTier: () => ({
    compareTiers: mockCompareTiers,
  }),
}));

const COMPARISONS = [
  { tier: 'micro', quality_range: '70', cost_range: '0.1', example_models: [] as any[], supports_cache: true },
  { tier: 'standard', quality_range: '85', cost_range: '2', example_models: [] as any[], supports_cache: true },
  { tier: 'versatile', quality_range: '92', cost_range: '8', example_models: [] as any[], supports_cache: true },
  { tier: 'heavy', quality_range: '95', cost_range: '50', example_models: [] as any[], supports_cache: true },
  { tier: 'complex', quality_range: '99', cost_range: '500', example_models: [] as any[], supports_cache: true },
];

describe('TierSelector', () => {
  const mockOnTierSelect = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockCompareTiers.mockResolvedValue(COMPARISONS);
  });

  it('renders all five tier cards with name, description and use cases', async () => {
    render(<TierSelector selectedTier="" onTierSelect={mockOnTierSelect} />);

    expect(screen.getByRole('heading', { name: 'Micro' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Standard' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Versatile' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Heavy' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Complex' })).toBeInTheDocument();

    expect(screen.getByText('Fast, efficient responses for simple queries')).toBeInTheDocument();
    expect(screen.getByText(/Quick questions/)).toBeInTheDocument();
    expect(screen.getByText(/Math proofs/)).toBeInTheDocument();
  });

  it('shows loading badges until comparisons resolve', async () => {
    mockCompareTiers.mockReturnValue(new Promise(() => {}));
    render(<TierSelector selectedTier="" onTierSelect={mockOnTierSelect} />);

    expect(screen.getAllByText('Loading...')).toHaveLength(10); // 5 cost + 5 quality
  });

  it('renders cost badges from the comparison cost range', async () => {
    render(<TierSelector selectedTier="" onTierSelect={mockOnTierSelect} />);

    await waitFor(() => expect(mockCompareTiers).toHaveBeenCalled());
    // micro: 0.1 → $, standard: 2 → $$, versatile/heavy/complex → $$$
    expect(screen.getByText('$')).toBeInTheDocument();
    expect(screen.getByText('$$')).toBeInTheDocument();
    expect(screen.getAllByText('$$$')).toHaveLength(3);
  });

  it('renders quality badges from the comparison quality range', async () => {
    render(<TierSelector selectedTier="" onTierSelect={mockOnTierSelect} />);

    await waitFor(() => expect(mockCompareTiers).toHaveBeenCalled());
    // micro: 70 → Basic, standard: 85 → Good, versatile/heavy/complex → Excellent
    expect(screen.getByText('Basic')).toBeInTheDocument();
    expect(screen.getByText('Good')).toBeInTheDocument();
    expect(screen.getAllByText('Excellent')).toHaveLength(3);
  });

  it('calls onTierSelect with the tier key when a card is clicked', async () => {
    render(<TierSelector selectedTier="" onTierSelect={mockOnTierSelect} />);

    fireEvent.click(screen.getByRole('heading', { name: 'Heavy' }));
    expect(mockOnTierSelect).toHaveBeenCalledWith('heavy');
  });

  it('marks the selected tier with a check icon and only one at a time', async () => {
    const { container } = render(
      <TierSelector selectedTier="standard" onTierSelect={mockOnTierSelect} />
    );

    expect(container.querySelectorAll('svg.lucide-check')).toHaveLength(1);
  });
});
