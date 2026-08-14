/**
 * MatchConfidenceReviewer component tests.
 *
 * Uses the real lib/matchConfidence helpers. Covers the level badge, the
 * chosen-first candidate ordering, the modification flow for non-high
 * confidence levels, approve/reject callbacks, and the rejection reason.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MatchConfidenceReviewer } from '../MatchConfidenceReviewer';
import type { MatchConfidence } from '../types';

const CANDIDATES = [
  {
    selector: 'button.submit',
    match_count: 2,
    is_text_only: false,
    appeared_after_ms: 10,
    tag_hint: 'button',
    attributes: {},
  },
  {
    selector: '#login-form > button',
    match_count: 1,
    is_text_only: false,
    appeared_after_ms: 25,
    tag_hint: 'button',
    attributes: {},
  },
];

const partialConfidence: MatchConfidence = {
  level: 'partial',
  score: 0.65,
  rationale: 'Multiple candidates matched',
  chosen_index: 1,
  candidates: CANDIDATES,
};

describe('MatchConfidenceReviewer', () => {
  const onApprove = jest.fn();
  const onReject = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the level badge, score and rationale', () => {
    render(
      <MatchConfidenceReviewer
        proposalId="p1"
        matchConfidence={partialConfidence}
        onApprove={onApprove}
        onReject={onReject}
      />
    );

    expect(screen.getByTestId('match-confidence-reviewer-p1')).toBeInTheDocument();
    expect(screen.getByLabelText('match-level-partial')).toHaveTextContent('PARTIAL · 0.65');
    expect(screen.getByText('Multiple candidates matched')).toBeInTheDocument();
  });

  it('lists candidates with the chosen one first and starred', () => {
    render(
      <MatchConfidenceReviewer
        proposalId="p1"
        matchConfidence={partialConfidence}
        onApprove={onApprove}
        onReject={onReject}
      />
    );

    const list = screen.getByLabelText('candidate-list');
    expect(list.textContent).toContain('★');
    expect(list.textContent?.indexOf('#login-form > button')).toBeLessThan(
      list.textContent!.indexOf('button.submit')
    );
    expect(screen.getByText('(2 matches)')).toBeInTheDocument();
    expect(screen.getByText('(1 match)')).toBeInTheDocument();
  });

  it('approves without modifications when confidence is high', () => {
    const highConfidence: MatchConfidence = {
      level: 'high',
      score: 0.95,
      rationale: 'Clear match',
      chosen_index: 0,
      candidates: CANDIDATES,
    };
    render(
      <MatchConfidenceReviewer
        proposalId="p1"
        matchConfidence={highConfidence}
        onApprove={onApprove}
        onReject={onReject}
      />
    );

    expect(screen.queryByLabelText('modify-selector-input')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    expect(onApprove).toHaveBeenCalledWith('p1', undefined);
  });

  it('shows the modify input pre-filled with the chosen selector for partial confidence', () => {
    render(
      <MatchConfidenceReviewer
        proposalId="p1"
        matchConfidence={partialConfidence}
        onApprove={onApprove}
        onReject={onReject}
      />
    );

    const input = screen.getByLabelText('modify-selector-input') as HTMLInputElement;
    expect(input.value).toBe('#login-form > button');
  });

  it('disables approve with modification while the selector is empty', () => {
    render(
      <MatchConfidenceReviewer
        proposalId="p1"
        matchConfidence={partialConfidence}
        onApprove={onApprove}
        onReject={onReject}
      />
    );

    const input = screen.getByLabelText('modify-selector-input');
    fireEvent.change(input, { target: { value: '   ' } });

    const approveButton = screen.getByRole('button', { name: 'Approve with modification' });
    expect(approveButton).toBeDisabled();
    fireEvent.click(approveButton);
    expect(onApprove).not.toHaveBeenCalled();
  });

  it('approves with a trimmed selector modification', () => {
    render(
      <MatchConfidenceReviewer
        proposalId="p1"
        matchConfidence={partialConfidence}
        onApprove={onApprove}
        onReject={onReject}
      />
    );

    const input = screen.getByLabelText('modify-selector-input');
    fireEvent.change(input, { target: { value: '  button.primary  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Approve with modification' }));

    expect(onApprove).toHaveBeenCalledWith('p1', { selector: 'button.primary' });
  });

  it('rejects with the default reason when no reason is given', () => {
    render(
      <MatchConfidenceReviewer
        proposalId="p1"
        matchConfidence={partialConfidence}
        onApprove={onApprove}
        onReject={onReject}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));
    expect(onReject).toHaveBeenCalledWith('p1', 'Reviewer rejected selector');
  });

  it('allows a custom rejection reason after cancelling the modification', () => {
    render(
      <MatchConfidenceReviewer
        proposalId="p1"
        matchConfidence={partialConfidence}
        onApprove={onApprove}
        onReject={onReject}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Cancel modification' }));
    const reasonInput = screen.getByLabelText('reject-reason-input');
    fireEvent.change(reasonInput, { target: { value: 'Selector too brittle' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));

    expect(onReject).toHaveBeenCalledWith('p1', 'Selector too brittle');
  });

  it('toggles the modify selector input on and off', () => {
    render(
      <MatchConfidenceReviewer
        proposalId="p1"
        matchConfidence={partialConfidence}
        onApprove={onApprove}
        onReject={onReject}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Cancel modification' }));
    expect(screen.queryByLabelText('modify-selector-input')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Modify selector' }));
    expect(screen.getByLabelText('modify-selector-input')).toBeInTheDocument();
  });
});
