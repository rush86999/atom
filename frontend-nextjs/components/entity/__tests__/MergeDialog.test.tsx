/**
 * MergeDialog Component Tests
 *
 * Covers the REAL MergeDialog (components/entity/MergeDialog.tsx):
 * - Renders nothing when no proposal is passed
 * - Shows source → target header, overall confidence %, and AI summary
 * - Renders one FieldDecisionRow per decision with source/suggested/target
 *   value pills (objects stringified, nulls shown as "null")
 * - Clicking a pill changes the chosen value; the updated decisions are what
 *   onApply receives
 * - Expanding a row reveals the decision reason
 * - Low-confidence suggested decisions still chosen show the amber conflict
 *   warning (real conflictsRemaining computation)
 * - Quick Apply calls onApply(proposal, decisions); on success shows the
 *   "Merge Applied!" overlay, toasts, and auto-closes
 * - onApply rejection toasts "Merge failed" and keeps the dialog open
 * - Cancel invokes onClose
 *
 * react-hot-toast is mocked; Radix Dialog renders content from the open prop.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import MergeDialog, { MergeProposal, FieldMergeDecision } from '../MergeDialog';

jest.mock('react-hot-toast', () => ({
  toast: { success: jest.fn(), error: jest.fn(), loading: jest.fn(), dismiss: jest.fn() },
}));

const mockToast = require('react-hot-toast').toast as {
  success: jest.Mock;
  error: jest.Mock;
  loading: jest.Mock;
  dismiss: jest.Mock;
};

const decisions: FieldMergeDecision[] = [
  {
    field: 'name',
    source_value: 'Acme Inc',
    target_value: 'Acme Corp',
    suggested_value: 'Acme Corporation',
    confidence: 0.92,
    reason: 'Most recent record references this legal name',
    chosen: 'suggested',
  },
  {
    field: 'tax_id',
    source_value: 12345,
    target_value: null,
    suggested_value: null,
    confidence: 0.3,
    reason: 'Only one record carries a tax id',
    chosen: 'suggested',
  },
  {
    field: 'tags',
    source_value: ['a', 'b'],
    target_value: ['b'],
    suggested_value: ['a', 'b'],
    confidence: 0.6,
    reason: 'Union of both records',
    chosen: 'suggested',
  },
];

const proposal: MergeProposal = {
  id: 'merge-1',
  source_label: 'Acme Inc',
  target_label: 'Acme Corp',
  entity_type: 'company',
  overall_confidence: 0.62,
  field_decisions: decisions,
  conflict_count: 1,
  ai_summary: 'Both records describe the same company and can be merged.',
};

describe('MergeDialog', () => {
  const mockOnApply = jest.fn();
  const mockOnClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  const renderDialog = (over: Partial<typeof proposal> = {}, applyImpl?: () => Promise<void>) => {
    mockOnApply.mockImplementation(applyImpl || (async () => {}));
    return render(
      <MergeDialog
        open={true}
        proposal={{ ...proposal, ...over }}
        onApply={mockOnApply}
        onClose={mockOnClose}
      />
    );
  };

  test('renders nothing when no proposal is provided', () => {
    render(<MergeDialog open={true} proposal={null} onApply={mockOnApply} onClose={mockOnClose} />);
    expect(screen.queryByText('Entity Merge Proposal')).not.toBeInTheDocument();
  });

  test('renders the header, confidence, AI summary, and field rows', () => {
    renderDialog();

    expect(screen.getByText('Entity Merge Proposal')).toBeInTheDocument();
    // Header line: source → target (the arrow lives in a nested span, so use
    // the raw textContent; exact-match pills are the ValuePill buttons)
    expect(
      screen.getByText(
        (_, el) => el?.tagName === 'P' && !!el.textContent?.includes('Acme Inc → Acme Corp')
      )
    ).toBeInTheDocument();
    expect(screen.getAllByText('Acme Inc').length).toBe(1); // the source pill
    expect(screen.getAllByText('Acme Corp').length).toBe(1); // the target pill
    expect(screen.getByText(/Both records describe the same company/)).toBeInTheDocument();
    expect(screen.getByText('Overall Confidence')).toBeInTheDocument();
    expect(screen.getByText('62%')).toBeInTheDocument();

    // Column labels + value pills
    expect(screen.getByText('SOURCE')).toBeInTheDocument();
    expect(screen.getByText('AI SUGGESTED')).toBeInTheDocument();
    expect(screen.getByText('TARGET')).toBeInTheDocument();
    expect(screen.getByText('Acme Corporation')).toBeInTheDocument();
    // Object values are stringified — tags row has source + suggested both
    // ["a","b"]; nulls shown as "null"
    expect(screen.getAllByText('["a","b"]').length).toBe(2);
    expect(screen.getAllByText('null').length).toBeGreaterThanOrEqual(1);

    expect(screen.getByText('3 fields · 1 conflict')).toBeInTheDocument();
  });

  test('clicking a value pill changes the chosen decision passed to onApply', async () => {
    renderDialog();

    // name row: switch from suggested to source (the source pill)
    fireEvent.click(screen.getAllByText('Acme Inc')[0]);

    fireEvent.click(screen.getByRole('button', { name: /Quick Apply/i }));

    await waitFor(() => {
      expect(mockOnApply).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'merge-1' }),
        expect.arrayContaining([
          expect.objectContaining({ field: 'name', chosen: 'source' }),
          expect.objectContaining({ field: 'tax_id', chosen: 'suggested' }),
          expect.objectContaining({ field: 'tags', chosen: 'suggested' }),
        ])
      );
    });
  });

  test('expanding a row reveals the decision reason', () => {
    renderDialog();
    expect(screen.queryByText('Most recent record references this legal name')).not.toBeInTheDocument();

    const expandButtons = screen.getAllByRole('button');
    // The expand chevron buttons are the plain buttons without text content
    const expand = expandButtons.find((b) => b.querySelector('.lucide-chevron-right'));
    fireEvent.click(expand!);

    expect(screen.getByText('Most recent record references this legal name')).toBeInTheDocument();
  });

  test('shows the conflict warning for low-confidence suggested choices', async () => {
    // tax_id has confidence 0.3 with differing values and chosen === suggested
    renderDialog();
    expect(await screen.findByText(/1 low-confidence field may need manual review/i)).toBeInTheDocument();
  });

  test('hides the conflict warning once a low-confidence conflict is resolved', async () => {
    renderDialog();
    expect(await screen.findByText(/1 low-confidence field may need manual review/i)).toBeInTheDocument();

    // tax_id row pills: source=12345, suggested=null, target=null — pick the
    // target pill (second "null") so chosen leaves the AI suggestion
    fireEvent.click(screen.getAllByText('null')[1]);

    expect(screen.queryByText(/low-confidence field/)).not.toBeInTheDocument();
  });

  test('successful apply shows the overlay, toasts, and auto-closes', async () => {
    renderDialog();

    fireEvent.click(screen.getByRole('button', { name: /Quick Apply/i }));

    expect(await screen.findByText('Merge Applied!')).toBeInTheDocument();
    expect(mockToast.success).toHaveBeenCalledWith('Merged "Acme Inc" → "Acme Corp"');
    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  test('failed apply toasts the error and keeps the dialog open', async () => {
    renderDialog({}, async () => {
      throw new Error('backend rejected');
    });

    fireEvent.click(screen.getByRole('button', { name: /Quick Apply/i }));

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('backend rejected');
    });
    expect(screen.getByText('Entity Merge Proposal')).toBeInTheDocument();
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  test('cancel invokes onClose', () => {
    renderDialog();
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    expect(mockOnClose).toHaveBeenCalled();
  });
});
