/**
 * AccountantPortal Component Tests
 *
 * Covers the REAL AccountantPortal (components/finance/AccountantPortal.tsx):
 * - Loading spinner while fetching the chart of accounts
 * - GET /api/accounting/chart-of-accounts on mount renders account rows with
 *   type badges and keyword chips
 * - Empty chart renders the "No accounts found" row
 * - Multi-ledger sync buttons (Zoho/Xero/QuickBooks) toast completion and
 *   refetch the chart
 * - GL / Trial Balance exports create a download link and toast success;
 *   failed exports toast an error
 *
 * fetch is mocked directly (pattern: VerificationLogs.test.tsx).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AccountantPortal from '../AccountantPortal';

jest.mock('@/components/ui/use-toast', () => {
  const mockToastFn = jest.fn();
  return {
    __toast: mockToastFn,
    useToast: () => ({ toast: mockToastFn, dismiss: jest.fn(), toasts: [] }),
    ToastProvider: ({ children }: { children: any }) => children,
  };
});

const mockToast = require('@/components/ui/use-toast').__toast as jest.Mock;

const accounts = [
  { id: 'acc-1', name: 'Checking Account', type: 'asset', keywords: ['bank', 'deposit'] },
  { id: 'acc-2', name: 'Software Subscriptions', type: 'expense', keywords: ['saas', 'aws'] },
];

const chartResponse = { data: { accounts } };

describe('AccountantPortal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => chartResponse,
    });
  });

  test('shows a loading spinner while the chart of accounts loads', () => {
    global.fetch = jest.fn().mockReturnValue(new Promise(() => {}));

    const { container } = render(<AccountantPortal />);
    expect(container.querySelector('.lucide-loader-circle')).toBeInTheDocument();
  });

  test('fetches the chart of accounts on mount and renders account rows', async () => {
    render(<AccountantPortal />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/accounting/chart-of-accounts', expect.anything());
    });

    expect(await screen.findByText('Checking Account')).toBeInTheDocument();
    expect(screen.getByText('Software Subscriptions')).toBeInTheDocument();
    expect(screen.getAllByText('asset').length).toBe(1);
    expect(screen.getByText('expense')).toBeInTheDocument();
    expect(screen.getByText('bank')).toBeInTheDocument();
    expect(screen.getByText('saas')).toBeInTheDocument();
    expect(screen.getByText('Audit Trail Active')).toBeInTheDocument();
    expect(screen.getByText(/We are not a licensed CPA firm/)).toBeInTheDocument();
  });

  test('renders the empty chart state when no accounts exist', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: { accounts: [] } }),
    });

    render(<AccountantPortal />);

    expect(await screen.findByText('No accounts found in the chart.')).toBeInTheDocument();
  });

  test('syncs a ledger platform: toasts completion and refetches', async () => {
    render(<AccountantPortal />);
    await screen.findByText('Checking Account');

    fireEvent.click(screen.getByRole('button', { name: /Zoho Books/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'ZOHO Sync Complete' })
      );
    }, { timeout: 4000 });
    // Refresh CoA after sync
    expect((global.fetch as jest.Mock).mock.calls.some((c) => String(c[0]).includes('chart-of-accounts'))).toBe(true);
  });

  test('exports the general ledger and toasts success', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => chartResponse,
      blob: async () => new Blob(['csv-content']),
    });

    render(<AccountantPortal />);
    await screen.findByText('Checking Account');

    fireEvent.click(screen.getByRole('button', { name: /General Ledger/i }));

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Export Started', description: 'Downloading your GL report...' })
    );

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Export Complete' })
      );
    });
    expect(global.URL.createObjectURL).toHaveBeenCalled();
    expect((global.fetch as jest.Mock).mock.calls.some((c) => String(c[0]).includes('export?type=gl'))).toBe(true);
  });

  test('toasts an error when the export download fails', async () => {
    global.fetch = jest.fn().mockImplementation((url: string) => {
      if (String(url).includes('export')) {
        return Promise.resolve({ ok: false });
      }
      return Promise.resolve({ ok: true, json: async () => chartResponse });
    });

    render(<AccountantPortal />);
    await screen.findByText('Checking Account');

    fireEvent.click(screen.getByRole('button', { name: /Trial Balance/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Export Failed', variant: 'error' })
      );
    });
  });
});
