/**
 * TeachingNotice — the inline "train the agent from chat" card.
 *
 * Locks the contract the two chat surfaces depend on:
 * - `/teach` confirmations render as a saved lesson
 * - a DETECTED cue renders as a one-click confirmation and writes nothing
 *   until the human clicks Save (lessons are permanent prompt instructions)
 * - no attached agent -> the picker, and picking one saves to THAT agent
 * - inline save goes through the existing teachAgent channel
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

jest.mock('@/lib/maturity-api', () => ({
  __esModule: true,
  teachAgent: jest.fn(),
  deleteTeachingPoint: jest.fn(),
}));

// Role drives UI visibility only (the backend gates removal at TEAM_LEAD+);
// mutable so a test can flip the viewer between supervisor and member.
let mockIsSupervisor = false;
jest.mock('@/lib/user-role', () => ({
  __esModule: true,
  useUserRole: () => ({
    role: mockIsSupervisor ? 'team_lead' : 'member',
    userId: 'u1',
    level: mockIsSupervisor ? 4 : 3,
    isSupervisor: mockIsSupervisor,
    isAdmin: false,
    loading: false,
  }),
}));

import { teachAgent, deleteTeachingPoint } from '@/lib/maturity-api';
import { TeachingNotice, TeachingNoticeData } from '../TeachingNotice';

const mockTeach = teachAgent as jest.Mock;
const mockDelete = deleteTeachingPoint as jest.Mock;

const notice = (overrides: Partial<TeachingNoticeData> = {}): TeachingNoticeData => ({
  status: 'suggested',
  lesson: 'Always CC the lead on quotes',
  message: 'Save this as a permanent lesson for Learner?',
  agent: { id: 'a1', name: 'Learner', status: 'student' },
  ...overrides,
});

beforeEach(() => {
  mockTeach.mockReset();
  mockTeach.mockResolvedValue({ status: 'ok' });
  mockDelete.mockReset();
  mockDelete.mockResolvedValue(undefined);
  mockIsSupervisor = false;
});

describe('TeachingNotice', () => {
  it('renders a save confirmation for a lesson taught with /teach', () => {
    render(<TeachingNotice notice={notice({
      status: 'saved',
      message: '✓ Learned — Learner will apply this to all of their work.',
    })} />);

    const card = screen.getByTestId('teaching-saved');
    expect(card).toHaveTextContent('Learner');
    expect(card).toHaveTextContent('Always CC the lead on quotes');
  });

  it('renders a detected cue as a confirmation, not a saved lesson', () => {
    render(<TeachingNotice notice={notice()} />);

    expect(screen.getByTestId('teaching-suggestion')).toHaveTextContent('Always CC the lead on quotes');
    // Nothing is written until the human confirms.
    expect(mockTeach).not.toHaveBeenCalled();
  });

  it('saves the lesson through teachAgent on confirm and flips to saved', async () => {
    render(<TeachingNotice notice={notice({ canvas_id: 'cv-1' })} />);

    fireEvent.click(screen.getByTestId('teaching-save'));

    await waitFor(() => expect(mockTeach).toHaveBeenCalledWith(
      'a1', 'Always CC the lead on quotes', undefined, 'cv-1',
    ));
    expect(await screen.findByTestId('teaching-saved')).toBeInTheDocument();
    expect(screen.queryByTestId('teaching-suggestion')).not.toBeInTheDocument();
  });

  it('dismissing writes nothing', () => {
    render(<TeachingNotice notice={notice()} />);

    fireEvent.click(screen.getByTestId('teaching-dismiss'));

    expect(mockTeach).not.toHaveBeenCalled();
    expect(screen.queryByTestId('teaching-suggestion')).not.toBeInTheDocument();
  });

  it('offers the agent picker when no agent is attached and saves to the pick', async () => {
    render(<TeachingNotice notice={notice({
      status: 'needs_agent',
      agent: undefined,
      message: 'Pick one below.',
      agents: [
        { id: 'a1', name: 'Sales Assistant', status: 'student' },
        { id: 'a2', name: 'Finance Intern', status: 'intern' },
      ],
    })} />);

    expect(screen.getByTestId('teaching-needs-agent')).toHaveTextContent('Pick one below.');
    fireEvent.click(screen.getByTestId('teaching-agent-option-a2'));

    await waitFor(() => expect(mockTeach).toHaveBeenCalledWith(
      'a2', 'Always CC the lead on quotes', undefined, undefined,
    ));
    expect(await screen.findByTestId('teaching-saved')).toBeInTheDocument();
  });

  it('surfaces a save failure honestly instead of claiming success', async () => {
    mockTeach.mockRejectedValue(new Error('boom'));
    render(<TeachingNotice notice={notice()} />);

    fireEvent.click(screen.getByTestId('teaching-save'));

    await waitFor(() => expect(
      screen.getByTestId('teaching-notice'),
    ).toHaveTextContent("couldn't save"));
    expect(screen.queryByTestId('teaching-saved')).not.toBeInTheDocument();
  });

  it('reports an already-known lesson as a duplicate', () => {
    render(<TeachingNotice notice={notice({ status: 'duplicate', message: "That's already one of Learner's lessons." })} />);
    expect(screen.getByTestId('teaching-duplicate')).toHaveTextContent(
      "That's already one of Learner's lessons.",
    );
  });
});

/**
 * Inline Undo. Deletion is a training-state mutation (the lesson stops
 * shaping work from the next turn on), so the backend gates it at TEAM_LEAD+.
 * The card must offer Undo only to a supervisor AND only when it holds the
 * teaching-point handle — a member would just collect a 403.
 */
describe('TeachingNotice undo (supervisor-only)', () => {
  const saved = (overrides: Partial<TeachingNoticeData> = {}) => notice({
    status: 'saved',
    message: '✓ Learned.',
    teaching_point_id: 'tp-1',
    ...overrides,
  });

  it('hides Undo from a non-supervisor', () => {
    mockIsSupervisor = false;
    render(<TeachingNotice notice={saved()} />);
    expect(screen.queryByTestId('teaching-undo')).not.toBeInTheDocument();
  });

  it('hides Undo when the card has no teaching-point handle', () => {
    mockIsSupervisor = true;
    render(<TeachingNotice notice={saved({ teaching_point_id: null })} />);
    expect(screen.queryByTestId('teaching-undo')).not.toBeInTheDocument();
  });

  it('removes the lesson and reports it for a supervisor', async () => {
    mockIsSupervisor = true;
    render(<TeachingNotice notice={saved()} />);

    fireEvent.click(screen.getByTestId('teaching-undo'));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith('a1', 'tp-1'));
    expect(await screen.findByTestId('teaching-undone')).toHaveTextContent("won't use it");
    expect(screen.queryByTestId('teaching-saved')).not.toBeInTheDocument();
  });

  it('surfaces a failed undo instead of pretending it worked', async () => {
    mockIsSupervisor = true;
    mockDelete.mockRejectedValue(new Error('Only supervisors can delete a teaching point'));
    render(<TeachingNotice notice={saved()} />);

    fireEvent.click(screen.getByTestId('teaching-undo'));

    await waitFor(() => expect(screen.getByTestId('teaching-undo-error')).toHaveTextContent(
      'Only supervisors can delete a teaching point',
    ));
    expect(screen.getByTestId('teaching-saved')).toBeInTheDocument();
    expect(screen.queryByTestId('teaching-undone')).not.toBeInTheDocument();
  });

  it('carries the teaching-point handle returned by an inline save', async () => {
    // The confirm-first card must gain Undo after the click that creates the
    // lesson — that requires /teach to return teaching_point_id.
    mockIsSupervisor = true;
    mockTeach.mockResolvedValue({ status: 'ok', teaching_point_id: 'tp-new' });
    render(<TeachingNotice notice={notice()} />);

    fireEvent.click(screen.getByTestId('teaching-save'));
    await screen.findByTestId('teaching-saved');

    fireEvent.click(screen.getByTestId('teaching-undo'));
    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith('a1', 'tp-new'));
  });
});

/**
 * Goal-scoped lessons (2026-09-11). "Some teaching points are goal specific
 * and other can be generalized" — when a lesson lands on ONE goal, the card
 * must say so and offer the one-click widen; the backend allows widening
 * (goal → global) but blocks narrowing, so this direction always works.
 */
describe('TeachingNotice goal scope', () => {
  const scoped = (overrides: Partial<TeachingNoticeData> = {}) => notice({
    status: 'saved',
    message: '✓ Learned — scoped to this goal.',
    teaching_point_id: 'tp-1',
    scope: 'goal',
    goal_id: 'g1',
    goal_title: 'Acme quote',
    ...overrides,
  });

  it('names the goal it is scoped to', () => {
    render(<TeachingNotice notice={scoped()} />);
    const scope = screen.getByTestId('teaching-scope');
    expect(scope).toHaveTextContent('Acme quote');
    expect(scope).toHaveTextContent('this goal');
  });

  it('marks an INFERRED scope as inferred', () => {
    render(<TeachingNotice notice={scoped({ goal_inferred: true })} />);
    expect(screen.getByTestId('teaching-scope')).toHaveTextContent('inferred');
  });

  it('says nothing about scope for a global lesson', () => {
    render(<TeachingNotice notice={notice({
      status: 'saved', message: '✓ Learned.', scope: 'global',
    })} />);
    expect(screen.queryByTestId('teaching-scope')).not.toBeInTheDocument();
  });

  it('widens a goal lesson to all work through teachAgent', async () => {
    mockIsSupervisor = true;
    render(<TeachingNotice notice={scoped()} />);

    fireEvent.click(screen.getByTestId('teaching-widen'));

    // Global re-teach: no scope/goal arguments.
    await waitFor(() => expect(mockTeach).toHaveBeenCalledWith(
      'a1', 'Always CC the lead on quotes'));
    await waitFor(() => expect(
      screen.queryByTestId('teaching-scope'),
    ).not.toBeInTheDocument());
  });

  it('surfaces a failed widen instead of pretending', async () => {
    mockIsSupervisor = true;
    mockTeach.mockRejectedValue(new Error('nope'));
    render(<TeachingNotice notice={scoped()} />);

    fireEvent.click(screen.getByTestId('teaching-widen'));

    await waitFor(() => expect(
      screen.getByTestId('teaching-undo-error'),
    ).toHaveTextContent('nope'));
    expect(screen.getByTestId('teaching-scope')).toBeInTheDocument();
  });
});
