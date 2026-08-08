/**
 * TransactionsList Component Tests
 *
 * Covers the REAL TransactionsList (components/finance/TransactionsList.tsx):
 * - Fetches /api/accounting/all on mount; renders rows with description,
 *   merchant, category badge, confidence %, and signed amounts
 * - Listens for the global `transactionCreated` event and refetches
 * - Search filters rows by description/merchant
 * - Confidence dropdown filter (High/Medium/Low checkboxes)
 * - "Pending Review" badge counts review_required transactions
 * - Export CSV builds a data URI and toasts; empty list toasts an error
 * - Create dialog POSTs /api/accounting/transactions and prepends the row
 * - Edit dialog PUTs /api/accounting/:id and dispatches transactionCreated
 * - Delete confirms, DELETEs, and removes the row; declined confirm cancels
 * - Empty state renders "No transactions found."
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import TransactionsList from '../TransactionsList';

jest.mock('@/components/ui/use-toast', () => {
  const mockToastFn = jest.fn();
  return {
    __toast: mockToastFn,
    useToast: () => ({ toast: mockToastFn, dismiss: jest.fn(), toasts: [] }),
    ToastProvider: ({ children }: { children: any }) => children,
  };
});

const mockToast = require('@/components/ui/use-toast').__toast as jest.Mock;

const transactions = [
  {
    id: 'tx-1',
    date: '2026-08-01',
    amount: 120.5,
    description: 'AWS cloud bill',
    merchant: 'Amazon Web Services',
    suggested_category: 'Software',
    confidence: 95,
    reasoning: 'Subscription merchant',
    status: 'review_required',
  },
  {
    id: 'tx-2',
    date: '2026-08-02',
    amount: -45.0,
    description: 'Client refund',
    merchant: 'Acme Corp',
    suggested_category: 'Refunds',
    confidence: 62,
    reasoning: 'Return processed',
  },
];

const listResponse = { data: { transactions } };

const jsonOk = (body: unknown) => Promise.resolve({ ok: true, json: async () => body });

describe('TransactionsList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => listResponse });
  });

  test('fetches transactions on mount and renders rows', async () => {
    render(<TransactionsList />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/accounting/all', expect.anything());
    });

    expect(await screen.findByText('AWS cloud bill')).toBeInTheDocument();
    expect(screen.getByText('Client refund')).toBeInTheDocument();
    expect(screen.getByText('Amazon Web Services')).toBeInTheDocument();
    expect(screen.getByText('Software')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText('62%')).toBeInTheDocument();
    // positive amounts get a + sign, negatives render as-is
    expect(screen.getByText('+120.50')).toBeInTheDocument();
    expect(screen.getByText('-45.00')).toBeInTheDocument();
    expect(screen.getByText('1 Pending Review')).toBeInTheDocument();
  });

  test('refetches when the global transactionCreated event fires', async () => {
    render(<TransactionsList />);
    await screen.findByText('AWS cloud bill');
    const callsBefore = (global.fetch as jest.Mock).mock.calls.length;

    window.dispatchEvent(new Event('transactionCreated'));

    await waitFor(() => {
      expect((global.fetch as jest.Mock).mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });

  test('filters rows by search term', async () => {
    render(<TransactionsList />);
    await screen.findByText('AWS cloud bill');

    fireEvent.change(screen.getByPlaceholderText('Search transactions...'), {
      target: { value: 'refund' },
    });

    expect(screen.getByText('Client refund')).toBeInTheDocument();
    expect(screen.queryByText('AWS cloud bill')).not.toBeInTheDocument();
  });

  test('confidence filter checkboxes narrow the list', async () => {
    render(<TransactionsList />);
    await screen.findByText('AWS cloud bill');

    const user = userEvent.setup();
    const filterTrigger = screen.getAllByRole('button').find((b) => b.querySelector('.lucide-funnel'));
    await user.click(filterTrigger!);

    // Uncheck High → the 95% row disappears
    const highItem = await screen.findByText('High (≥ 90%)');
    await user.click(highItem);

    expect(screen.queryByText('AWS cloud bill')).not.toBeInTheDocument();
    expect(screen.getByText('Client refund')).toBeInTheDocument();
  });

  test('shows the empty state when there are no transactions', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: { transactions: [] } }),
    });

    render(<TransactionsList />);

    expect(await screen.findByText('No transactions found.')).toBeInTheDocument();
  });

  test('exports the filtered transactions as CSV and toasts', async () => {
    render(<TransactionsList />);
    await screen.findByText('AWS cloud bill');

    const createElementSpy = jest.spyOn(document, 'createElement');
    fireEvent.click(screen.getByRole('button', { name: /Export CSV/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Export Successful' })
      );
    });

    const anchor = createElementSpy.mock.results[0].value as HTMLAnchorElement;
    expect(anchor.getAttribute('download')).toMatch(/^review_queue_/);
    const href = decodeURIComponent(anchor.getAttribute('href') || '');
    expect(href).toContain('data:text/csv');
    expect(href).toContain('AWS cloud bill');
    expect(href).toContain('Subscription merchant');
  });

  test('exporting with an empty list toasts an error', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: { transactions: [] } }),
    });

    render(<TransactionsList />);
    await screen.findByText('No transactions found.');

    fireEvent.click(screen.getByRole('button', { name: /Export CSV/i }));

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Export Failed', description: 'No transactions to export.', variant: 'error' })
    );
  });

  test('creates a transaction via the dialog', async () => {
    let posted = false;
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        posted = true;
        return jsonOk({
          data: {
            id: 'tx_man_123',
            category: 'Software',
            confidence: 88,
            reasoning: 'Manual categorization',
          },
        });
      }
      return jsonOk(listResponse);
    });

    render(<TransactionsList />);
    await screen.findByText('AWS cloud bill');

    fireEvent.click(screen.getByRole('button', { name: /New Transaction/i }));
    expect(screen.getByText('Create Transaction')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'New office chairs' } });
    fireEvent.change(screen.getByLabelText('Merchant (Optional)'), { target: { value: 'IKEA' } });
    fireEvent.change(screen.getByLabelText('Amount ($)'), { target: { value: '350.25' } });
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2026-08-05' } });

    fireEvent.click(screen.getByRole('button', { name: /Save Transaction/i }));

    await waitFor(() => {
      expect(posted).toBe(true);
      expect(screen.getByText('New office chairs')).toBeInTheDocument();
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Transaction Created' })
    );
    expect((global.fetch as jest.Mock).mock.calls.some((c) => c[1]?.method === 'POST')).toBe(true);
  });

  test('edits a transaction through the row menu', async () => {
    let putCalled = false;
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'PUT') {
        putCalled = true;
        return jsonOk({ success: true });
      }
      return jsonOk(listResponse);
    });

    render(<TransactionsList />);
    await screen.findByText('AWS cloud bill');

    const user = userEvent.setup();
    const rowMenu = screen.getAllByRole('button').find((b) => b.querySelector('.lucide-ellipsis'));
    await user.click(rowMenu!);
    await user.click(await screen.findByText('Edit Details'));

    const descInput = await screen.findByLabelText('Description');
    expect(descInput).toHaveValue('AWS cloud bill');

    fireEvent.change(descInput, { target: { value: 'AWS cloud bill (edited)' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Changes/i }));

    await waitFor(() => {
      expect(putCalled).toBe(true);
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Transaction Updated' })
      );
    });
    expect(
      (global.fetch as jest.Mock).mock.calls.some((c) => String(c[0]).includes('/api/accounting/tx-1'))
    ).toBe(true);
  });

  test('deletes a transaction after confirmation', async () => {
    window.confirm = jest.fn(() => true);
    let deleted = false;
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'DELETE') {
        deleted = true;
        return jsonOk({ success: true });
      }
      return jsonOk(listResponse);
    });

    render(<TransactionsList />);
    await screen.findByText('AWS cloud bill');

    const user = userEvent.setup();
    const rowMenu = screen.getAllByRole('button').find((b) => b.querySelector('.lucide-ellipsis'));
    await user.click(rowMenu!);
    await user.click(await screen.findByText('Delete'));

    await waitFor(() => {
      expect(deleted).toBe(true);
      expect(screen.queryByText('AWS cloud bill')).not.toBeInTheDocument();
    });
    expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/delete/i));
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Transaction Deleted' })
    );
  });

  test('declined confirmation cancels the delete', async () => {
    window.confirm = jest.fn(() => false);
    let deleted = false;
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'DELETE') deleted = true;
      return jsonOk(listResponse);
    });

    render(<TransactionsList />);
    await screen.findByText('AWS cloud bill');

    const user = userEvent.setup();
    const rowMenu = screen.getAllByRole('button').find((b) => b.querySelector('.lucide-ellipsis'));
    await user.click(rowMenu!);
    await user.click(await screen.findByText('Delete'));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
    });
    expect(deleted).toBe(false);
    expect(screen.getByText('AWS cloud bill')).toBeInTheDocument();
  });
});
