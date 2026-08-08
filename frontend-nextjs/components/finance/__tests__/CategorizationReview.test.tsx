/**
 * CategorizationReview Component Tests
 *
 * Covers the REAL CategorizationReview (components/finance/CategorizationReview.tsx):
 * - Loading spinner while fetching /api/accounting/transactions
 * - Renders pending proposals: description, date, category badge, confidence
 *   bar + %, and reasoning
 * - Approve POSTs /api/accounting/action?action=post&id=... and removes the
 *   row on success with a toast
 * - Reject removes the row locally with a toast (no API call)
 * - Server rejection toasts the API error and keeps the row
 * - Network failure toasts "Update Failed"
 * - Empty queue renders the "AI is learning well!" state
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import CategorizationReview from '../CategorizationReview';

jest.mock('@/components/ui/use-toast', () => {
  const mockToastFn = jest.fn();
  return {
    __toast: mockToastFn,
    useToast: () => ({ toast: mockToastFn, dismiss: jest.fn(), toasts: [] }),
    ToastProvider: ({ children }: { children: any }) => children,
  };
});

const mockToast = require('@/components/ui/use-toast').__toast as jest.Mock;

const proposals = [
  {
    id: 'tx-1',
    date: '2026-08-01',
    amount: 120.5,
    description: 'AWS cloud bill',
    merchant: 'Amazon Web Services',
    suggested_category: 'Software',
    confidence: 74,
    reasoning: 'Similar to past software purchases',
  },
  {
    id: 'tx-2',
    date: '2026-08-02',
    amount: 40,
    description: 'Team lunch',
    suggested_category: 'Meals & Entertainment',
    confidence: 96,
    reasoning: 'Restaurant merchant matched',
  },
];

const queueResponse = { data: { transactions: proposals } };

describe('CategorizationReview', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => queueResponse,
    });
  });

  test('shows a spinner while loading', () => {
    global.fetch = jest.fn().mockReturnValue(new Promise(() => {}));

    const { container } = render(<CategorizationReview />);
    expect(container.querySelector('.lucide-loader-circle')).toBeInTheDocument();
  });

  test('fetches and renders the pending proposals with confidence and reasoning', async () => {
    render(<CategorizationReview />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/accounting/transactions', expect.anything());
    });

    expect(await screen.findByText('AWS cloud bill')).toBeInTheDocument();
    expect(screen.getByText('Team lunch')).toBeInTheDocument();
    expect(screen.getAllByText('Software').length).toBe(1);
    expect(screen.getByText('Meals & Entertainment')).toBeInTheDocument();
    // confidence values render as percentages
    expect(screen.getByText('74%')).toBeInTheDocument();
    expect(screen.getByText('96%')).toBeInTheDocument();
    // reasoning is quoted in the UI
    expect(screen.getByText(/Similar to past software purchases/)).toBeInTheDocument();
    expect(screen.getByText(/Restaurant merchant matched/)).toBeInTheDocument();
    expect(screen.getByText('Pending AI Categorizations')).toBeInTheDocument();
  });

  test('approving a proposal posts it and removes the row', async () => {
    let posted = false;
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        posted = true;
        return Promise.resolve({ ok: true, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => queueResponse });
    });

    render(<CategorizationReview />);
    await screen.findByText('AWS cloud bill');

    const approveButtons = screen.getAllByRole('button', { name: /Approve/i });
    fireEvent.click(approveButtons[0]);

    await waitFor(() => {
      expect(screen.queryByText('AWS cloud bill')).not.toBeInTheDocument();
    });
    expect(posted).toBe(true);
    expect((global.fetch as jest.Mock).mock.calls.some((c) => String(c[0]).includes('action=post&id=tx-1'))).toBe(true);
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Categorization Applied' })
    );
  });

  test('rejecting a proposal removes it locally without an API call', async () => {
    render(<CategorizationReview />);
    await screen.findByText('AWS cloud bill');
    const fetchCalls = (global.fetch as jest.Mock).mock.calls.length;

    const rejectButtons = screen.getAllByRole('button');
    // Reject = the icon-only ghost button with the X icon
    const reject = rejectButtons.find((b) => b.querySelector('.lucide-x'));
    fireEvent.click(reject!);

    await waitFor(() => {
      expect(screen.queryByText('AWS cloud bill')).not.toBeInTheDocument();
    });
    expect((global.fetch as jest.Mock).mock.calls.length).toBe(fetchCalls);
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Proposal Rejected' })
    );
  });

  test('server rejection toasts the API error and keeps the row', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: false, json: async () => ({ error: 'Category locked' }) });
      }
      return Promise.resolve({ ok: true, json: async () => queueResponse });
    });

    render(<CategorizationReview />);
    await screen.findByText('AWS cloud bill');

    fireEvent.click(screen.getAllByRole('button', { name: /Approve/i })[0]);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Approval Failed', description: 'Category locked', variant: 'error' })
      );
    });
    expect(screen.getByText('AWS cloud bill')).toBeInTheDocument();
  });

  test('network failure toasts Update Failed', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') return Promise.reject(new Error('offline'));
      return Promise.resolve({ ok: true, json: async () => queueResponse });
    });

    render(<CategorizationReview />);
    await screen.findByText('AWS cloud bill');

    fireEvent.click(screen.getAllByRole('button', { name: /Approve/i })[0]);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Update Failed', variant: 'error' }));
    });
  });

  test('renders the all-categorized state when the queue is empty', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: { transactions: [] } }),
    });

    render(<CategorizationReview />);

    expect(
      await screen.findByText(/All transactions are categorized. AI is learning well!/)
    ).toBeInTheDocument();
  });
});
