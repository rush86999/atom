/**
 * ChatMessage error-variant render tests.
 *
 * Verifies that a message with type "error" (e.g. a budget-exceeded halt)
 * renders as a visually distinct error block — not a normal assistant bubble.
 * This is the machine-readable budget-failure UI that useChatInterface surfaces
 * when the backend returns error_code="budget_exceeded".
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { ChatMessage, ChatMessageData } from '../ChatMessage';

describe('ChatMessage error variant', () => {
  const baseActionClick = () => {};

  it('renders an error message with distinct alert styling', () => {
    const errorMsg: ChatMessageData = {
      id: 'budget-1',
      type: 'error',
      content: 'Budget limit reached — execution halted.',
      timestamp: new Date(),
    };

    render(<ChatMessage message={errorMsg} onActionClick={baseActionClick} />);

    // The content must be present.
    expect(screen.getByText(/Budget limit reached/i)).toBeInTheDocument();

    // The error variant must be marked with role="alert" so it is both
    // accessible and queryable as distinct from a normal assistant bubble.
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('renders an "Error" badge on the error variant', () => {
    const errorMsg: ChatMessageData = {
      id: 'budget-2',
      type: 'error',
      content: 'Budget limit reached.',
      timestamp: new Date(),
    };

    render(<ChatMessage message={errorMsg} onActionClick={baseActionClick} />);

    // A visible "Error" label distinguishes it from a normal message at a glance.
    expect(screen.getByText(/error/i)).toBeInTheDocument();
  });

  it('does NOT render the error alert for a normal assistant message', () => {
    const assistantMsg: ChatMessageData = {
      id: 'ok-1',
      type: 'assistant',
      content: 'Done! Created the task.',
      timestamp: new Date(),
    };

    render(<ChatMessage message={assistantMsg} onActionClick={baseActionClick} />);

    expect(screen.getByText(/Done! Created the task/i)).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
