/**
 * CacheActions component tests.
 *
 * Covers the REAL CacheActions (components/admin/jit-verification/CacheActions.tsx):
 * - Renders the three management actions
 * - Warm Cache dialog: limit input, warmCache(limit) call, result panel with
 *   facts_processed/citations_verified, completion toast; failure closes dialog
 * - Clear Cache confirmation dialog → clearCache() + success toast
 * - Export Metrics triggers a JSON download (URL.createObjectURL) + toast
 *
 * jitVerificationAPI is mocked at module level; toast hook per repo pattern.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CacheActions } from '../CacheActions';
import { jitVerificationAPI } from '@/lib/api-admin';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

jest.mock('@/lib/api-admin', () => ({
  jitVerificationAPI: {
    clearCache: jest.fn(),
    warmCache: jest.fn(),
  },
}));

const clearCacheMock = jitVerificationAPI.clearCache as jest.Mock;
const warmCacheMock = jitVerificationAPI.warmCache as jest.Mock;

const warmResponse = {
  data: {
    status: 'ok',
    facts_processed: 3,
    citations_verified: 5,
    verified_count: 5,
    duration_seconds: 1.25,
    warmed_at: '2026-08-07T00:00:00Z',
  },
};

describe('CacheActions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clearCacheMock.mockResolvedValue({ data: { status: 'ok' } });
    warmCacheMock.mockResolvedValue(warmResponse);
  });

  it('renders the cache management card with all action buttons', () => {
    render(<CacheActions />);

    expect(screen.getByText('Cache Management')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Warm Cache/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Clear All Caches/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Export Metrics/ })).toBeInTheDocument();
  });

  it('opens the warm dialog and shows the default limit of 100', () => {
    render(<CacheActions />);

    fireEvent.click(screen.getByRole('button', { name: /Warm Cache/ }));
    expect(screen.getByText('Warm JIT Verification Cache')).toBeInTheDocument();
    expect(screen.getByLabelText(/Number of Facts to Warm: 100/)).toBeInTheDocument();
  });

  it('warms the cache with the chosen limit and renders the result panel', async () => {
    render(<CacheActions />);

    fireEvent.click(screen.getByRole('button', { name: /Warm Cache/ }));
    const dialog = screen.getByRole('dialog');
    const limitInput = within(dialog).getByLabelText(/Number of Facts to Warm: 100/);
    fireEvent.change(limitInput, { target: { value: '50' } });

    await waitFor(() => {
      expect(within(dialog).getByLabelText(/Number of Facts to Warm: 50/)).toBeInTheDocument();
    });

    fireEvent.click(within(dialog).getByRole('button', { name: /Warm Cache/ }));

    await waitFor(() => {
      expect(warmCacheMock).toHaveBeenCalledWith(50);
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Cache warming complete', description: 'Warmed 5 citations in 1.25s' })
    );

    expect(await screen.findByText('Cache Warming Complete!')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Done' })).toBeInTheDocument();
  });

  it('closes the warm dialog when warming fails', async () => {
    warmCacheMock.mockRejectedValue({ userMessage: 'warming failed' });
    render(<CacheActions />);

    fireEvent.click(screen.getByRole('button', { name: /Warm Cache/ }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /Warm Cache/ }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Failed to warm cache', description: 'warming failed', variant: 'destructive' })
      );
    });
    expect(screen.queryByText('Warm JIT Verification Cache')).not.toBeInTheDocument();
  });

  it('clears the cache after confirmation and toasts success', async () => {
    render(<CacheActions />);

    fireEvent.click(screen.getByRole('button', { name: /Clear All Caches/ }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Clear All JIT Verification Caches?')).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Clear Cache' }));

    await waitFor(() => {
      expect(clearCacheMock).toHaveBeenCalled();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Cache cleared' })
    );
  });

  it('toasts an error when clearing the cache fails', async () => {
    clearCacheMock.mockRejectedValue({ userMessage: 'clear failed' });
    render(<CacheActions />);

    fireEvent.click(screen.getByRole('button', { name: /Clear All Caches/ }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Clear Cache' }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Failed to clear cache', description: 'clear failed', variant: 'destructive' })
      );
    });
  });

  it('cancels the clear-cache dialog without calling the API', () => {
    render(<CacheActions />);

    fireEvent.click(screen.getByRole('button', { name: /Clear All Caches/ }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }));

    expect(clearCacheMock).not.toHaveBeenCalled();
    expect(screen.queryByText('Clear All JIT Verification Caches?')).not.toBeInTheDocument();
  });

  it('exports metrics as a JSON download and toasts success', () => {
    render(<CacheActions />);

    fireEvent.click(screen.getByRole('button', { name: /Export Metrics/ }));

    expect(global.URL.createObjectURL).toHaveBeenCalled();
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Metrics exported' })
    );
  });
});
