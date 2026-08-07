/**
 * CognitiveTierSettings component tests.
 *
 * Covers: loading gate, default tier + feature switches rendering, saving a
 * tier preference (success + failure toasts), cost estimation display, and
 * budget input values.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { toast } from 'sonner';
import { useCognitiveTier } from '@/hooks/useCognitiveTier';
import { CognitiveTierSettings } from '../CognitiveTierSettings';

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('@/hooks/useCognitiveTier', () => ({
  useCognitiveTier: jest.fn(),
}));

const mockUseCognitiveTier = useCognitiveTier as jest.Mock;

const basePrefs = {
  id: 'pref-1',
  workspace_id: 'default',
  default_tier: 'standard',
  min_tier: null,
  max_tier: null,
  monthly_budget_cents: 5000,
  max_cost_per_request_cents: 200,
  enable_cache_aware_routing: true,
  enable_auto_escalation: true,
  enable_minimax_fallback: false,
  preferred_providers: [],
};

const costEstimates = [
  { tier: 'standard', estimated_cost_usd: 0.5, models_in_tier: ['gpt-4o-mini'] },
  { tier: 'heavy', estimated_cost_usd: 5.0, models_in_tier: ['gpt-4o'] },
];

describe('CognitiveTierSettings', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseCognitiveTier.mockReturnValue({
      preferences: basePrefs,
      loading: false,
      saving: false,
      savePreferences: jest.fn().mockResolvedValue(true),
      estimateCost: jest.fn().mockResolvedValue(costEstimates),
    });
  });

  it('shows the loader while preferences are loading', () => {
    mockUseCognitiveTier.mockReturnValue({
      preferences: null,
      loading: true,
      saving: false,
      savePreferences: jest.fn(),
      estimateCost: jest.fn(),
    });
    const { container } = render(<CognitiveTierSettings />);
    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
    expect(screen.queryByText('Default Cognitive Tier')).not.toBeInTheDocument();
  });

  it('renders the tier selector, feature switches, and budget inputs', () => {
    render(<CognitiveTierSettings />);
    expect(screen.getByText('Default Cognitive Tier')).toBeInTheDocument();
    expect(screen.getByText('Smart Routing Features')).toBeInTheDocument();
    expect(screen.getByText('Cost Controls')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
    expect(screen.getAllByRole('switch')).toHaveLength(3);
    const budgetInputs = screen.getAllByPlaceholderText('No limit');
    expect((budgetInputs[0] as HTMLInputElement).value).toBe('50');
    expect((budgetInputs[1] as HTMLInputElement).value).toBe('2');
  });

  it('saves a default-tier change and toasts success', async () => {
    const savePreferences = jest.fn().mockResolvedValue(true);
    mockUseCognitiveTier.mockReturnValue({
      preferences: basePrefs,
      loading: false,
      saving: false,
      savePreferences,
      estimateCost: jest.fn().mockResolvedValue([]),
    });
    render(<CognitiveTierSettings />);
    fireEvent.click(screen.getByRole('combobox'));
    const option = await screen.findByRole('option', { name: /Heavy/ });
    fireEvent.click(option);
    await waitFor(() => {
      expect(savePreferences).toHaveBeenCalledWith(expect.objectContaining({ default_tier: 'heavy' }));
    });
    expect(toast.success).toHaveBeenCalledWith('Tier preference saved');
  });

  it('toasts an error when saving a preference fails', async () => {
    const savePreferences = jest.fn().mockResolvedValue(false);
    mockUseCognitiveTier.mockReturnValue({
      preferences: basePrefs,
      loading: false,
      saving: false,
      savePreferences,
      estimateCost: jest.fn().mockResolvedValue([]),
    });
    render(<CognitiveTierSettings />);
    fireEvent.click(screen.getAllByRole('switch')[1]);
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to save preference');
    });
  });

  it('estimates per-1M-token cost for the selected tier', async () => {
    render(<CognitiveTierSettings />);
    fireEvent.click(screen.getByRole('button', { name: /Estimate Cost/ }));
    await waitFor(() => {
      // 0.5 USD per token * 1e6 -> $500000.00
      expect(screen.getByText(/Estimated: \$500000\.00 per 1M tokens/)).toBeInTheDocument();
    });
  });

  it('saves budget input as cents and clears when emptied', async () => {
    const savePreferences = jest.fn().mockResolvedValue(true);
    mockUseCognitiveTier.mockReturnValue({
      preferences: basePrefs,
      loading: false,
      saving: false,
      savePreferences,
      estimateCost: jest.fn().mockResolvedValue([]),
    });
    render(<CognitiveTierSettings />);
    const budget = screen.getAllByPlaceholderText('No limit')[0] as HTMLInputElement;
    fireEvent.change(budget, { target: { value: '75' } });
    await waitFor(() => {
      expect(savePreferences).toHaveBeenCalledWith(expect.objectContaining({ monthly_budget_cents: 7500 }));
    });
  });
});
