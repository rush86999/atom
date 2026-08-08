/**
 * TopCitations component tests.
 *
 * Covers the REAL TopCitations (components/admin/jit-verification/TopCitations.tsx):
 * - Loading spinner before the API resolves
 * - Leaderboard rows with rank, citation links, access counts, summary stats
 * - Clicking a citation opens the CitationDetail dialog
 * - Empty response renders the "No citation data" empty state
 * - API failure toasts destructively
 *
 * jitVerificationAPI.getTopCitations is mocked at module level.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { TopCitations } from '../TopCitations';
import { jitVerificationAPI } from '@/lib/api-admin';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

jest.mock('@/lib/api-admin', () => ({
  jitVerificationAPI: {
    getTopCitations: jest.fn(),
  },
}));

const getTopCitationsMock = jitVerificationAPI.getTopCitations as jest.Mock;

const topCitations = [
  { citation: 'https://bucket.s3.amazonaws.com/policy.pdf', access_count: 42 },
  { citation: 'https://bucket.s3.amazonaws.com/handbook.pdf', access_count: 30 },
  { citation: 'https://bucket.s3.amazonaws.com/org-chart.pdf', access_count: 12 },
];

describe('TopCitations', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getTopCitationsMock.mockResolvedValue({
      data: {
        top_citations: topCitations,
        total_unique_citations: 3,
        retrieved_at: '2026-08-07T10:00:00Z',
      },
    });
  });

  it('shows a loading spinner before data arrives', () => {
    getTopCitationsMock.mockReturnValue(new Promise(() => {}));
    const { container } = render(<TopCitations />);

    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
    expect(screen.queryByText('Top Citations by Access Frequency')).not.toBeInTheDocument();
  });

  it('renders the leaderboard with rank, summary stats, and access counts', async () => {
    render(<TopCitations />);

    expect(await screen.findByText('Top Citations by Access Frequency')).toBeInTheDocument();
    expect(getTopCitationsMock).toHaveBeenCalledWith(20);

    // Summary cards
    expect(screen.getByText('3 citations')).toBeInTheDocument();
    expect(screen.getByText('Total Citations')).toBeInTheDocument();
    expect(screen.getByText('Total Accesses')).toBeInTheDocument();
    expect(screen.getByText('84')).toBeInTheDocument(); // 42 + 30 + 12
    expect(screen.getByText('Most Accessed')).toBeInTheDocument();

    // Rows
    expect(screen.getByText('https://bucket.s3.amazonaws.com/policy.pdf')).toBeInTheDocument();
    expect(screen.getByText('42x')).toBeInTheDocument();
    expect(screen.getByText('30x')).toBeInTheDocument();
    expect(screen.getByText('12x')).toBeInTheDocument();
    // Ranks 1, 2, 3 (rank 3 shares its "3" with the Total Citations card)
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(1);
  });

  it('opens the citation detail dialog when a row is clicked', async () => {
    render(<TopCitations />);

    // The citation URL anchor stopPropagation()s, so click the row via its access-count cell
    fireEvent.click(await screen.findByText('42x'));

    expect(await screen.findByText('Citation Details')).toBeInTheDocument();
    expect(screen.getAllByText('Total Accesses').length).toBeGreaterThanOrEqual(1); // summary card + dialog
    expect(screen.getAllByText('42').length).toBeGreaterThanOrEqual(1); // summary card + dialog count
    expect(screen.getByText('policy.pdf')).toBeInTheDocument(); // filename from URL
    expect(screen.getByText('Normal')).toBeInTheDocument(); // 42 accesses -> Normal rank
  });

  it('renders the empty state when no citations are returned', async () => {
    getTopCitationsMock.mockResolvedValue({ data: { top_citations: [] } });
    render(<TopCitations />);

    expect(await screen.findByText('No citation data')).toBeInTheDocument();
    expect(screen.getByText('0 citations')).toBeInTheDocument();
    expect(screen.queryByText('Access Leaderboard')).toBeInTheDocument();
  });

  it('toasts an error when the fetch fails', async () => {
    getTopCitationsMock.mockRejectedValue({ userMessage: 'top citations unavailable' });
    render(<TopCitations />);

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error loading top citations', description: 'top citations unavailable', variant: 'destructive' })
      );
    });
  });
});
