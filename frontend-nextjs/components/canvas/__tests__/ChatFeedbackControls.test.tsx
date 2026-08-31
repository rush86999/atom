/**
 * ChatFeedbackControls tests (canvas co-editor chat feedback row)
 *
 * Verifies the AgentWorkspace step-feedback conventions the canvas port
 * must keep: aria-labeled thumbs + note, chosen-state coloring, and the
 * corrective-note contract (note submits as thumbs_down + text).
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ChatFeedbackControls } from '../ChatFeedbackControls';

describe('ChatFeedbackControls', () => {
  test('thumbs clicks report their type', () => {
    const onFeedback = jest.fn();
    render(<ChatFeedbackControls onFeedback={onFeedback} />);

    fireEvent.click(screen.getByLabelText('Thumbs up'));
    expect(onFeedback).toHaveBeenCalledWith('thumbs_up');

    fireEvent.click(screen.getByLabelText('Thumbs down'));
    expect(onFeedback).toHaveBeenCalledWith('thumbs_down');
  });

  test('chosen state colors the matching thumb', () => {
    render(<ChatFeedbackControls selected="thumbs_down" onFeedback={jest.fn()} />);

    const downIcon = screen.getByLabelText('Thumbs down').querySelector('svg');
    const upIcon = screen.getByLabelText('Thumbs up').querySelector('svg');
    expect(downIcon).toHaveClass('text-red-500');
    expect(upIcon).not.toHaveClass('text-green-500');
  });

  test('note flow submits corrective feedback (thumbs_down + text)', () => {
    const onFeedback = jest.fn();
    render(<ChatFeedbackControls onFeedback={onFeedback} />);

    fireEvent.click(screen.getByLabelText('Add note'));
    const input = screen.getByLabelText('Feedback note');
    fireEvent.change(input, { target: { value: 'Use bullet points, not prose' } });
    fireEvent.click(screen.getByLabelText('Send feedback note'));

    expect(onFeedback).toHaveBeenCalledWith('thumbs_down', 'Use bullet points, not prose');
    // The note box closes after submit.
    expect(screen.queryByLabelText('Feedback note')).not.toBeInTheDocument();
  });

  test('note submits on Enter and empty notes are dropped', () => {
    const onFeedback = jest.fn();
    render(<ChatFeedbackControls onFeedback={onFeedback} />);

    fireEvent.click(screen.getByLabelText('Add note'));
    const input = screen.getByLabelText('Feedback note');
    fireEvent.keyDown(input, { key: 'Enter' });
    // Empty text closes the box without emitting feedback.
    expect(onFeedback).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('Feedback note')).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Add note'));
    const reopened = screen.getByLabelText('Feedback note');
    fireEvent.change(reopened, { target: { value: 'keep it shorter' } });
    fireEvent.keyDown(reopened, { key: 'Enter' });
    expect(onFeedback).toHaveBeenCalledWith('thumbs_down', 'keep it shorter');
  });

  test('toggling the note button closes the box', () => {
    render(<ChatFeedbackControls onFeedback={jest.fn()} />);

    fireEvent.click(screen.getByLabelText('Add note'));
    expect(screen.getByLabelText('Feedback note')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Add note'));
    expect(screen.queryByLabelText('Feedback note')).not.toBeInTheDocument();
  });
});
