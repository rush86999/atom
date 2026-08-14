/**
 * CognitiveTierWizard component tests.
 *
 * The useCognitiveTier hook, sonner toast, and the TierSelector/CostCalculator
 * children are mocked. Covers the full 5-step walkthrough, budget entry,
 * save success/failure paths, and back-navigation guards.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CognitiveTierWizard } from '../CognitiveTierWizard';

const mockSavePreferences = jest.fn();
const mockToastSuccess = jest.fn();
const mockToastError = jest.fn();

jest.mock('@/hooks/useCognitiveTier', () => ({
  useCognitiveTier: () => ({
    savePreferences: mockSavePreferences,
    saving: false,
  }),
}));

jest.mock('sonner', () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}));

jest.mock('../TierSelector', () => ({
  TierSelector: ({ selectedTier }: { selectedTier: string }) => (
    <div data-testid="mock-tier-selector">tier:{selectedTier}</div>
  ),
}));

jest.mock('../CostCalculator', () => ({
  CostCalculator: ({ selectedTier }: { selectedTier: string }) => (
    <div data-testid="mock-cost-calculator">calc:{selectedTier}</div>
  ),
}));

describe('CognitiveTierWizard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSavePreferences.mockResolvedValue(true);
  });

  it('renders the welcome step with back disabled and starts the wizard', () => {
    render(<CognitiveTierWizard />);

    expect(screen.getByText('Welcome to Cognitive Tier Configuration')).toBeInTheDocument();
    expect(screen.getByText(/Micro:/)).toBeInTheDocument();
    expect(screen.getByText(/Complex:/)).toBeInTheDocument();

    const backButton = screen.getByRole('button', { name: /back/i });
    expect(backButton).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /get started/i }));
    expect(screen.getByText('Select Your Default Tier')).toBeInTheDocument();
    expect(screen.getByTestId('mock-tier-selector')).toBeInTheDocument();
  });

  it('walks through select → budget → review with tier and budget retained', () => {
    render(<CognitiveTierWizard />);
    fireEvent.click(screen.getByRole('button', { name: /get started/i }));

    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    expect(screen.getByText('Set Budget Limits (Optional)')).toBeInTheDocument();
    expect(screen.getByTestId('mock-cost-calculator')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('No limit'), { target: { value: '50' } });
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    expect(screen.getByText('Review Your Selection')).toBeInTheDocument();
    expect(screen.getByText('standard')).toBeInTheDocument();
    expect(screen.getByText('$50')).toBeInTheDocument();
    expect(screen.getAllByText('Enabled')).toHaveLength(2);
  });

  it('saves preferences with cents and shows the completion step on success', async () => {
    render(<CognitiveTierWizard />);
    fireEvent.click(screen.getByRole('button', { name: /get started/i }));
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    fireEvent.change(screen.getByPlaceholderText('No limit'), { target: { value: '50' } });
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    fireEvent.click(screen.getByRole('button', { name: /complete setup/i }));

    await waitFor(() =>
      expect(mockSavePreferences).toHaveBeenCalledWith({
        default_tier: 'standard',
        monthly_budget_cents: 5000,
        enable_cache_aware_routing: true,
        enable_auto_escalation: true,
      })
    );
    expect(screen.getByText('Configuration Complete!')).toBeInTheDocument();
    expect(mockToastSuccess).toHaveBeenCalledWith('Cognitive tier preferences saved!');
    expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument();
  });

  it('saves with a null budget when no budget is entered', async () => {
    render(<CognitiveTierWizard />);
    fireEvent.click(screen.getByRole('button', { name: /get started/i }));
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    fireEvent.click(screen.getByRole('button', { name: /complete setup/i }));

    await waitFor(() => expect(mockSavePreferences).toHaveBeenCalled());
    expect(mockSavePreferences.mock.calls[0][0].monthly_budget_cents).toBeNull();
  });

  it('shows an error toast and stays on review when saving fails', async () => {
    mockSavePreferences.mockResolvedValue(false);
    render(<CognitiveTierWizard />);
    fireEvent.click(screen.getByRole('button', { name: /get started/i }));
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    fireEvent.click(screen.getByRole('button', { name: /complete setup/i }));

    await waitFor(() => expect(mockToastError).toHaveBeenCalledWith('Failed to save preferences'));
    expect(screen.getByText('Review Your Selection')).toBeInTheDocument();
    expect(screen.queryByText('Configuration Complete!')).not.toBeInTheDocument();
  });

  it('goes back through steps and re-renders the previous step content', () => {
    render(<CognitiveTierWizard />);
    fireEvent.click(screen.getByRole('button', { name: /get started/i }));
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    fireEvent.click(screen.getByRole('button', { name: /back/i }));
    expect(screen.getByText('Set Budget Limits (Optional)')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /back/i }));
    expect(screen.getByText('Select Your Default Tier')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /back/i }));
    expect(screen.getByText('Welcome to Cognitive Tier Configuration')).toBeInTheDocument();
  });
});
