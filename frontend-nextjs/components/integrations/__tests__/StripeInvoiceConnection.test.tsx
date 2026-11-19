/**
 * StripeInvoiceConnection component tests.
 *
 * Covers the Stripe invoice verification setup card: key masking, the
 * authenticated api-client request shape, clearing the restricted key on
 * success, surfacing the verified account/mode, and safe failures that never
 * leak the key.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import StripeInvoiceConnection from '../StripeInvoiceConnection';

jest.mock('@/lib/api-client', () => ({
  apiClient: { post: jest.fn() },
}), { virtual: true });

const mockApiPost = (jest.requireMock('@/lib/api-client') as any).apiClient.post as jest.Mock;

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

describe('StripeInvoiceConnection', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiPost.mockResolvedValue({
      data: { connection_id: 'conn_1', account: 'acct_123', mode: 'test' },
    });
  });

  it('renders the setup card with a masked restricted key field', () => {
    render(<StripeInvoiceConnection />);

    expect(screen.getByText('Stripe Invoice Verification')).toBeInTheDocument();
    expect(screen.getByLabelText(/Stripe Restricted Key/)).toHaveAttribute('type', 'password');
    expect(screen.getByLabelText(/Stripe Account ID/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Verify Stripe Invoice Connection/ })).toBeInTheDocument();
  });

  it('verifies through the authenticated api client, clears the key, and shows account/mode', async () => {
    render(<StripeInvoiceConnection />);

    const restrictedKey = screen.getByLabelText(/Stripe Restricted Key/) as HTMLInputElement;
    const accountId = screen.getByLabelText(/Stripe Account ID/) as HTMLInputElement;
    fireEvent.change(restrictedKey, { target: { value: 'rk_test_secret_value' } });
    fireEvent.change(accountId, { target: { value: 'acct_123' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Stripe Invoice Connection/ }));

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        '/api/integrations/stripe/invoice-connection',
        { restricted_key: 'rk_test_secret_value', account_id: 'acct_123' },
        { retry: false }
      );
    });
    await waitFor(() => {
      expect(restrictedKey.value).toBe('');
      expect(screen.getByText('acct_123')).toBeInTheDocument();
      expect(screen.getByText('test')).toBeInTheDocument();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Stripe invoice connection verified.', variant: 'success' })
    );
    expect(JSON.stringify(mockToast.toast.mock.calls)).not.toContain('rk_test_secret_value');
    expect(document.body.textContent).not.toContain('rk_test_secret_value');
  });

  it('accepts a live mode invoice connection when the account matches', async () => {
    mockApiPost.mockResolvedValueOnce({
      data: { connection_id: 'conn_live', account: 'acct_123', mode: 'live' },
    });
    render(<StripeInvoiceConnection />);

    fireEvent.change(screen.getByLabelText(/Stripe Restricted Key/), { target: { value: 'rk_live_secret' } });
    fireEvent.change(screen.getByLabelText(/Stripe Account ID/), { target: { value: 'acct_123' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Stripe Invoice Connection/ }));

    await waitFor(() => {
      expect(screen.getByText('live')).toBeInTheDocument();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Stripe invoice connection verified.', variant: 'success' })
    );
    expect(document.body.textContent).not.toContain('rk_live_secret');
  });

  it.each([
    ['a blank connection id', { connection_id: '   ', account: 'acct_123', mode: 'test' }],
    ['a mismatched account', { connection_id: 'conn_1', account: 'acct_other', mode: 'test' }],
    ['an unsupported mode', { connection_id: 'conn_1', account: 'acct_123', mode: 'sandbox' }],
  ])('rejects an invoice connection response with %s', async (_label, data) => {
    mockApiPost.mockResolvedValueOnce({ data });
    render(<StripeInvoiceConnection />);

    const restrictedKey = screen.getByLabelText(/Stripe Restricted Key/) as HTMLInputElement;
    fireEvent.change(restrictedKey, { target: { value: 'rk_test_secret_value' } });
    fireEvent.change(screen.getByLabelText(/Stripe Account ID/), { target: { value: 'acct_123' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Stripe Invoice Connection/ }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Failed to verify Stripe invoice connection.',
          variant: 'error',
        })
      );
    });
    expect(mockToast.toast).not.toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Stripe invoice connection verified.' })
    );
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(restrictedKey.value).toBe('rk_test_secret_value');
    expect(JSON.stringify(mockToast.toast.mock.calls)).not.toContain('rk_test_secret_value');
    expect(document.body.textContent).not.toContain('rk_test_secret_value');
  });

  it('shows a safe verification failure without exposing or clearing the key', async () => {
    mockApiPost.mockRejectedValueOnce(new Error('rejected rk_test_secret_value'));
    render(<StripeInvoiceConnection />);

    const restrictedKey = screen.getByLabelText(/Stripe Restricted Key/) as HTMLInputElement;
    fireEvent.change(restrictedKey, { target: { value: 'rk_test_secret_value' } });
    fireEvent.change(screen.getByLabelText(/Stripe Account ID/), { target: { value: 'acct_123' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Stripe Invoice Connection/ }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Failed to verify Stripe invoice connection.',
          variant: 'error',
        })
      );
    });
    expect(restrictedKey.value).toBe('rk_test_secret_value');
    expect(JSON.stringify(mockToast.toast.mock.calls)).not.toContain('rk_test_secret_value');
    expect(document.body.textContent).not.toContain('rk_test_secret_value');
  });

  it('requires both values before calling the API', async () => {
    render(<StripeInvoiceConnection />);

    fireEvent.change(screen.getByLabelText(/Stripe Restricted Key/), { target: { value: 'rk_test_secret_value' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Stripe Invoice Connection/ }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Stripe restricted key and account ID are required.',
          variant: 'error',
        })
      );
    });
    expect(mockApiPost).not.toHaveBeenCalled();
    expect(JSON.stringify(mockToast.toast.mock.calls)).not.toContain('rk_test_secret_value');
  });
});
