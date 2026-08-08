/**
 * CitationVerificationPanel component tests.
 *
 * Covers the REAL CitationVerificationPanel (components/admin/jit-verification/CitationVerificationPanel.tsx)
 * end-to-end with jitVerificationAPI mocked:
 * - Empty state + disabled Verify button with no citations
 * - Comma/newline citation parsing → verifyCitations() payload with force_refresh
 * - Summary cards (Total/Verified/Failed), status tabs with counts
 * - Filtering by status tab, Copy Results (clipboard), Export JSON (download), Clear Results
 * - Force refresh toggle → warning alert + force_refresh: true in payload
 * - API failure → destructive toast
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CitationVerificationPanel } from '../CitationVerificationPanel';
import { jitVerificationAPI } from '@/lib/api-admin';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

jest.mock('@/lib/api-admin', () => ({
  jitVerificationAPI: {
    verifyCitations: jest.fn(),
  },
}));

const verifyCitationsMock = jitVerificationAPI.verifyCitations as jest.Mock;

const verifyResponse = {
  data: {
    results: [
      {
        exists: true,
        checked_at: '2026-08-07T10:00:00Z',
        citation: 'https://bucket.s3.amazonaws.com/policy.pdf',
        size: 2048,
      },
      {
        exists: false,
        checked_at: '2026-08-07T10:00:00Z',
        citation: 'https://bucket.s3.amazonaws.com/missing.pdf',
      },
    ],
    total_count: 2,
    verified_count: 1,
    failed_count: 1,
    duration_seconds: 0.35,
  },
};

describe('CitationVerificationPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    verifyCitationsMock.mockResolvedValue(verifyResponse);
  });

  it('renders the input card and empty state, with Verify disabled when no citations', () => {
    render(<CitationVerificationPanel />);

    expect(screen.getAllByText('Verify Citations').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('No citations entered')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Verify Citations/ })).toBeDisabled();
  });

  it('verifies comma-separated citations and renders summary + results', async () => {
    render(<CitationVerificationPanel />);

    const textarea = screen.getByLabelText('Citations');
    fireEvent.change(textarea, {
      target: { value: 'https://bucket.s3.amazonaws.com/policy.pdf, https://bucket.s3.amazonaws.com/missing.pdf' },
    });

    expect(screen.getByText('2 citations')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Verify Citations/ })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: /Verify Citations/ }));

    await waitFor(() => {
      expect(verifyCitationsMock).toHaveBeenCalledWith({
        citations: [
          'https://bucket.s3.amazonaws.com/policy.pdf',
          'https://bucket.s3.amazonaws.com/missing.pdf',
        ],
        force_refresh: false,
      });
    });

    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Verification complete', description: 'Verified 1 of 2 citations in 0.35s' })
    );

    // Summary cards
    expect(screen.getByText('Total')).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('1 of 2 citations verified successfully')).toBeInTheDocument();

    // Tabs with counts (custom Tabs render plain buttons, not role=tab)
    expect(screen.getByRole('button', { name: 'All (2)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Verified (1)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Failed (1)' })).toBeInTheDocument();

    // Results list
    expect(screen.getByText('EXISTS')).toBeInTheDocument();
    expect(screen.getByText('MISSING')).toBeInTheDocument();
    expect(screen.getByText('https://bucket.s3.amazonaws.com/policy.pdf')).toBeInTheDocument();
    expect(screen.getByText('2.0 KB')).toBeInTheDocument();
  });

  it('filters results by status tab', async () => {
    render(<CitationVerificationPanel />);

    fireEvent.change(screen.getByLabelText('Citations'), {
      target: { value: 'https://a.com, https://b.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Verify Citations/ }));

    fireEvent.click(await screen.findByRole('button', { name: 'Verified (1)' }));
    expect(screen.getByText('EXISTS')).toBeInTheDocument();
    expect(screen.queryByText('MISSING')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Failed (1)' }));
    expect(screen.getByText('MISSING')).toBeInTheDocument();
    expect(screen.queryByText('EXISTS')).not.toBeInTheDocument();
  });

  it('shows the force-refresh warning and sends force_refresh: true', async () => {
    render(<CitationVerificationPanel />);

    expect(screen.queryByText(/Force refresh enabled/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('switch'));

    expect(screen.getByText(/Force refresh enabled: Citations will be verified directly/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Citations'), { target: { value: 'https://a.com' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Citations/ }));

    await waitFor(() => {
      expect(verifyCitationsMock).toHaveBeenCalledWith({
        citations: ['https://a.com'],
        force_refresh: true,
      });
    });
  });

  it('copies results to the clipboard and toasts', async () => {
    render(<CitationVerificationPanel />);

    fireEvent.change(screen.getByLabelText('Citations'), { target: { value: 'https://a.com, https://b.com' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Citations/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Copy Results/ }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        'https://bucket.s3.amazonaws.com/policy.pdf: ✅ EXISTS\nhttps://bucket.s3.amazonaws.com/missing.pdf: ❌ MISSING'
      );
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Copied to clipboard' })
    );
  });

  it('exports results as JSON and toasts', async () => {
    render(<CitationVerificationPanel />);

    fireEvent.change(screen.getByLabelText('Citations'), { target: { value: 'https://a.com' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Citations/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Export JSON/ }));

    await waitFor(() => {
      expect(global.URL.createObjectURL).toHaveBeenCalled();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Exported' }));
  });

  it('clears results and returns to the pre-verification state', async () => {
    render(<CitationVerificationPanel />);

    fireEvent.change(screen.getByLabelText('Citations'), { target: { value: 'https://a.com' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Citations/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Clear Results/ }));

    expect(screen.queryByText('Verification Results')).not.toBeInTheDocument();
    // Input text is intentionally preserved after clearing results
    expect((screen.getByLabelText('Citations') as HTMLTextAreaElement).value).toBe('https://a.com');
  });

  it('toasts a destructive error when verification fails', async () => {
    verifyCitationsMock.mockRejectedValue({ userMessage: 'verification service down' });
    render(<CitationVerificationPanel />);

    fireEvent.change(screen.getByLabelText('Citations'), { target: { value: 'https://a.com' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Citations/ }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Verification failed', description: 'verification service down', variant: 'destructive' })
      );
    });
  });
});
