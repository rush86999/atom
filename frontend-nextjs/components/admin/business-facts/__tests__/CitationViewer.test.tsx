/**
 * CitationViewer component tests.
 *
 * The jitVerificationAPI and useToast are mocked. Covers the empty-citations
 * state, citation rendering, the verify-all flow with EXISTS/MISSING results,
 * success/failure toasts, and the loading state.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CitationViewer } from '../CitationViewer';

const mockVerifyFactCitations = jest.fn();
const mockToast = jest.fn();

jest.mock('@/lib/api-admin', () => ({
  jitVerificationAPI: {
    verifyFactCitations: (...args: unknown[]) => mockVerifyFactCitations(...args),
  },
}));

jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

const CITATIONS = ['https://example.com/doc-a', 'https://example.com/doc-b'];

describe('CitationViewer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows a message when there are no citations', () => {
    render(<CitationViewer citations={[]} factId="fact-1" />);

    expect(screen.getByText('No citations associated with this fact')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /verify all/i })).not.toBeInTheDocument();
  });

  it('renders citations as links with count and verify hint', () => {
    render(<CitationViewer citations={CITATIONS} factId="fact-1" />);

    expect(screen.getByText('Citations (2)')).toBeInTheDocument();
    const link = screen.getByText('https://example.com/doc-a') as HTMLAnchorElement;
    expect(link.href).toBe('https://example.com/doc-a');
    expect(link.target).toBe('_blank');
    expect(screen.getByText('Click "Verify All" to check citation status')).toBeInTheDocument();
  });

  it('verifies citations and renders EXISTS/MISSING results with metadata', async () => {
    mockVerifyFactCitations.mockResolvedValue({
      data: {
        citation_count: 2,
        results: {
          0: { exists: true, size: 2048, checked_at: '2026-08-14T10:00:00Z' },
          1: { exists: false },
        },
      },
    });
    render(<CitationViewer citations={CITATIONS} factId="fact-1" />);

    fireEvent.click(screen.getByRole('button', { name: /verify all/i }));

    expect(mockVerifyFactCitations).toHaveBeenCalledWith('fact-1');
    expect(await screen.findByText('EXISTS')).toBeInTheDocument();
    expect(screen.getByText('MISSING')).toBeInTheDocument();
    expect(screen.getByText('2.0 KB')).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Verification complete', description: '2 citations verified' })
    );
    expect(screen.queryByText(/Click "Verify All"/)).not.toBeInTheDocument();
  });

  it('shows a destructive toast with the user message when verification fails', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockVerifyFactCitations.mockRejectedValue({ userMessage: 'Backend unreachable' });
    render(<CitationViewer citations={CITATIONS} factId="fact-1" />);

    fireEvent.click(screen.getByRole('button', { name: /verify all/i }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith({
        title: 'Verification failed',
        description: 'Backend unreachable',
        variant: 'destructive',
      })
    );
    consoleSpy.mockRestore();
  });

  it('falls back to a generic message when the error has no userMessage', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockVerifyFactCitations.mockRejectedValue(new Error('raw'));
    render(<CitationViewer citations={CITATIONS} factId="fact-1" />);

    fireEvent.click(screen.getByRole('button', { name: /verify all/i }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith({
        title: 'Verification failed',
        description: 'Failed to verify citations',
        variant: 'destructive',
      })
    );
    consoleSpy.mockRestore();
  });

  it('shows the loading state on the verify button while verifying', async () => {
    mockVerifyFactCitations.mockReturnValue(new Promise(() => {}));
    render(<CitationViewer citations={CITATIONS} factId="fact-1" />);

    fireEvent.click(screen.getByRole('button', { name: /verify all/i }));

    expect(screen.getByText('Verifying...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /verifying/i })).toBeDisabled();
  });
});
