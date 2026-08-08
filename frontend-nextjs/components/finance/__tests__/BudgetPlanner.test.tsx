/**
 * BudgetPlanner Component Tests
 *
 * Covers the REAL BudgetPlanner (components/finance/BudgetPlanner.tsx):
 * - Renders the seeded budgets with spent/limit values and % used labels
 * - Over-budget categories render the spent amount in red and cap at 100%
 * - Add Budget dialog creates a new budget row and toasts success
 * - Invalid limits (NaN / <= 0) toast an error and add nothing
 * - Empty category/limit cannot submit (native required validation)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import BudgetPlanner from '../BudgetPlanner';

jest.mock('@/components/ui/use-toast', () => {
  const mockToastFn = jest.fn();
  return {
    __toast: mockToastFn,
    useToast: () => ({ toast: mockToastFn, dismiss: jest.fn(), toasts: [] }),
    ToastProvider: ({ children }: { children: any }) => children,
  };
});

const mockToast = require('@/components/ui/use-toast').__toast as jest.Mock;

describe('BudgetPlanner', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders all seeded budgets with spent/limit and usage percentages', () => {
    render(<BudgetPlanner />);

    expect(screen.getByText('Infrastructure')).toBeInTheDocument();
    expect(screen.getByText('Software Subscriptions')).toBeInTheDocument();
    expect(screen.getByText('Marketing')).toBeInTheDocument();
    expect(screen.getByText('Office & Rent')).toBeInTheDocument();
    expect(screen.getByText('Travel')).toBeInTheDocument();

    // Infrastructure: 142/200 → 71%
    expect(screen.getByText('71% used')).toBeInTheDocument();
    // Software: 345/500 → 69%
    expect(screen.getByText('69% used')).toBeInTheDocument();
    // Marketing: 850/1000 → 85%
    expect(screen.getByText('85% used')).toBeInTheDocument();
    // Office & Rent hits exactly 100%; Travel is capped at 100%
    expect(screen.getAllByText('100% used').length).toBe(2);

    // amounts render raw (no toLocaleString): $1200, $345, ...
    expect(screen.getByText('$142')).toBeInTheDocument();
    expect(screen.getByText('$1200')).toBeInTheDocument();
  });

  test('marks the over-budget spent amount in red', () => {
    render(<BudgetPlanner />);

    const spentAmount = screen.getByText('$1200');
    expect(spentAmount.className).toContain('text-red-500');
    // A within-budget amount is NOT red
    expect(screen.getByText('$345').className).not.toContain('text-red-500');
  });

  test('adds a new budget via the dialog and toasts success', async () => {
    render(<BudgetPlanner />);

    fireEvent.click(screen.getByRole('button', { name: /Add Budget/i }));

    fireEvent.change(screen.getByLabelText('Category Name'), { target: { value: 'Legal Fees' } });
    fireEvent.change(screen.getByLabelText('Monthly Limit ($)'), { target: { value: '750' } });
    fireEvent.click(screen.getByRole('button', { name: /Create Budget/i }));

    await waitFor(() => {
      expect(screen.getByText('Legal Fees')).toBeInTheDocument();
    });
    // New budget starts at $0 / $750 (spent is wrapped in a span, so compare
    // the row div's full textContent)
    expect(
      screen.getByText((_, el) => el?.tagName === 'DIV' && el.textContent === '$0 / $750')
    ).toBeInTheDocument();
    expect(screen.getByText('0% used')).toBeInTheDocument();

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Budget Added', description: 'Created new budget for Legal Fees' })
    );
  });

  test('rejects invalid (zero/negative) limits with an error toast', async () => {
    render(<BudgetPlanner />);

    fireEvent.click(screen.getByRole('button', { name: /Add Budget/i }));
    fireEvent.change(screen.getByLabelText('Category Name'), { target: { value: 'Bad Budget' } });
    fireEvent.change(screen.getByLabelText('Monthly Limit ($)'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: /Create Budget/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Invalid Limit',
          description: 'Please enter a valid number for the budget limit.',
          variant: 'error',
        })
      );
    });
    expect(screen.queryByText('Bad Budget')).not.toBeInTheDocument();

    // Same for a negative limit
    fireEvent.change(screen.getByLabelText('Monthly Limit ($)'), { target: { value: '-5' } });
    fireEvent.click(screen.getByRole('button', { name: /Create Budget/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledTimes(2);
    });
    expect(screen.queryByText('Bad Budget')).not.toBeInTheDocument();
  });

  test('cannot submit with an empty category (native required validation)', () => {
    render(<BudgetPlanner />);

    fireEvent.click(screen.getByRole('button', { name: /Add Budget/i }));
    fireEvent.change(screen.getByLabelText('Monthly Limit ($)'), { target: { value: '500' } });
    fireEvent.click(screen.getByRole('button', { name: /Create Budget/i }));

    // jsdom constraint validation blocks the submit handler
    expect(mockToast).not.toHaveBeenCalled();
  });
});
