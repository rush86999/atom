/**
 * SubscriptionTracker component tests.
 *
 * useToast is mocked (repo convention — tests/setup.ts mocks the module
 * globally, and the real ToastProvider never renders toast UI under test).
 * Covers summary stats, the subscription list, the manage dialog, and the
 * cancel flow (status update, toast call, dialog close, and absence of
 * cancel for already-cancelled subs).
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import SubscriptionTracker from '../SubscriptionTracker';

const mockToast = jest.fn();

jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
}));

describe('SubscriptionTracker', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders summary stats for total, active, and recurring cost', () => {
    render(<SubscriptionTracker />);

    expect(screen.getByText('Monthly Recurring')).toBeInTheDocument();
    expect(screen.getByText('$277.49')).toBeInTheDocument();
    expect(screen.getByText('Active Subscriptions')).toBeInTheDocument();
    expect(screen.getByText('Total Tracked')).toBeInTheDocument();
    expect(screen.getAllByText('6')).toHaveLength(2);
  });

  it('renders every subscription with plan, cycle, cost and next bill date', () => {
    render(<SubscriptionTracker />);

    expect(screen.getByText('AWS')).toBeInTheDocument();
    expect(screen.getByText('Adobe Creative Cloud')).toBeInTheDocument();
    expect(screen.getByText('Slack')).toBeInTheDocument();
    expect(screen.getByText('GitHub')).toBeInTheDocument();
    expect(screen.getByText('Vercel')).toBeInTheDocument();
    expect(screen.getByText('Notion')).toBeInTheDocument();
    expect(screen.getAllByText('Pro • Monthly')).toHaveLength(2);
    expect(screen.getAllByText('2025-12-01')).toHaveLength(2);
    expect(screen.getAllByText('Active')).toHaveLength(6);
  });

  it('opens the manage dialog with subscription details', () => {
    render(<SubscriptionTracker />);

    fireEvent.click(screen.getAllByRole('button', { name: 'Manage' })[0]);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Manage Subscription')).toBeInTheDocument();
    expect(screen.getByText('Review or cancel your AWS subscription.')).toBeInTheDocument();
    expect(screen.getByText('Renews 2025-12-01')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel Subscription' })).toBeInTheDocument();
  });

  it('cancels an active subscription, updates the list, toasts, and closes the dialog', () => {
    render(<SubscriptionTracker />);

    fireEvent.click(screen.getAllByRole('button', { name: 'Manage' })[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel Subscription' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith({
      title: 'Subscription Cancelled',
      description: 'AWS has been cancelled successfully.',
    });
    expect(screen.getAllByText('Cancelled')).toHaveLength(1);
    expect(screen.getByText('$135.49')).toBeInTheDocument();
    expect(screen.getAllByText('5')).toHaveLength(1);
    expect(screen.getAllByText('6')).toHaveLength(1);
  });

  it('hides the billing cycle and cancel button for an already-cancelled subscription', () => {
    render(<SubscriptionTracker />);

    fireEvent.click(screen.getAllByRole('button', { name: 'Manage' })[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel Subscription' }));

    fireEvent.click(screen.getAllByRole('button', { name: 'Manage' })[0]);
    expect(screen.getAllByText('Cancelled')).toHaveLength(2);
    expect(screen.queryByText(/Renews/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel Subscription' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
