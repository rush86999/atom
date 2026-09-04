/**
 * TrainingPanel tests (canvas training surface)
 *
 * Mocks lib/maturity-api + api-client and verifies the in-canvas supervisor
 * journey contract: context-driven rendering (agent card, evidence, lesson
 * editor), teach, suggested task (training-chat convention), evidence-gated
 * completion, pending-proposal approval, graduation promote, and the
 * non-supervisor / no-agent degraded states.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockApi = {
  getCanvasTrainingContext: jest.fn(),
  getAgentGraduationProgress: jest.fn(),
  getGraduationReadiness: jest.fn(),
  teachAgent: jest.fn(),
  updateTrainingGuidance: jest.fn(),
  completeTrainingSession: jest.fn(),
  approveTrainingProposal: jest.fn(),
  rejectTrainingProposal: jest.fn(),
  promoteAgent: jest.fn(),
};

jest.mock('@/lib/maturity-api', () => ({
  __esModule: true,
  ...mockApi,
}));

const mockPost = jest.fn();

jest.mock('@/lib/api-client', () => ({
  __esModule: true,
  apiClient: {
    post: (...args: unknown[]) => mockPost(...args),
  },
}));

jest.mock('@/lib/identity', () => ({
  __esModule: true,
  getCurrentUserId: () => 'user-1',
}));

import { TrainingPanel } from '../TrainingPanel';

const EVIDENCE_OK = {
  episodes: 3,
  successes: 3,
  success_ratio: 1,
  window_started_at: null,
  required_episodes: 3,
};

const EVIDENCE_LOW = { ...EVIDENCE_OK, episodes: 1, successes: 1, success_ratio: 1 };

function makeContext(overrides: Record<string, unknown> = {}) {
  return {
    canvas_id: 'cv-1',
    agent: {
      id: 'agent-1',
      name: 'Hire One',
      tier: 'student',
      confidence: 0.3,
      domain: 'email',
    },
    linked_session: {
      id: 'sess-1',
      agent_id: 'agent-1',
      status: 'in_progress',
      started_at: null,
      completed_at: null,
      lesson_plan: { objective: 'Triage inbox', tasks: ['Read the inbox'] },
      supervisor_note: null,
      canvas_id: 'cv-1',
      promoted_to_intern: false,
      performance_score: null,
      evidence: EVIDENCE_OK,
    },
    pending_proposal: null,
    viewer_is_supervisor: true,
    ...overrides,
  };
}

beforeEach(() => {
  jest.resetAllMocks();
  mockApi.getCanvasTrainingContext.mockResolvedValue(makeContext());
  mockApi.getAgentGraduationProgress.mockResolvedValue({
    current_tier: 'student',
    next_tier: 'intern',
    episode_count: 4,
    next_threshold_episodes: 10,
  });
  mockApi.getGraduationReadiness.mockResolvedValue({
    ready: false,
    score: 41,
    gaps: ['needs more clean runs'],
    recommendation: 'Keep training',
  });
  mockPost.mockResolvedValue({ data: { success: true, message: 'on it' } });
});

describe('TrainingPanel', () => {
  test('renders agent card, progress, evidence, and lesson editor for a supervisor', async () => {
    render(<TrainingPanel canvasId="cv-1" />);

    await waitFor(() =>
      expect(screen.getByTestId('training-agent-name')).toHaveTextContent('Hire One')
    );
    expect(screen.getByTestId('training-tier-badge')).toHaveTextContent('student');
    expect(screen.getByTestId('training-progress')).toHaveTextContent('4/10');
    expect(screen.getByTestId('session-evidence-counter')).toHaveTextContent('3');
    expect(screen.getByTestId('lesson-objective-input')).toHaveValue('Triage inbox');
    expect(screen.getByTestId('canvas-complete-training-form')).toBeInTheDocument();
    expect(screen.getByTestId('teach-section')).toBeInTheDocument();
    expect(screen.getByTestId('graduation-section')).toBeInTheDocument();
    expect(mockApi.getCanvasTrainingContext).toHaveBeenCalledWith('cv-1', undefined);
  });

  test('teach sends the lesson through the learning channel', async () => {
    mockApi.teachAgent.mockResolvedValue({ status: 'ok' });
    render(<TrainingPanel canvasId="cv-1" />);
    await waitFor(() => screen.getByTestId('teach-lesson-input'));

    fireEvent.change(screen.getByTestId('teach-lesson-input'), {
      target: { value: 'Always cc the team lead on replies' },
    });
    fireEvent.click(screen.getByTestId('teach-submit'));

    await waitFor(() =>
      expect(mockApi.teachAgent).toHaveBeenCalledWith(
        'agent-1',
        'Always cc the team lead on replies',
        undefined,
        'cv-1'
      )
    );
    await waitFor(() =>
      expect(screen.getByText(/confidence grew/)).toBeInTheDocument()
    );
  });

  test('suggested task goes to the training chat and lands in the lesson plan', async () => {
    mockApi.updateTrainingGuidance.mockResolvedValue({ success: true });
    render(<TrainingPanel canvasId="cv-1" />);
    await waitFor(() => screen.getByTestId('suggest-task-input'));

    fireEvent.change(screen.getByTestId('suggest-task-input'), {
      target: { value: 'Triage today’s inbox' },
    });
    fireEvent.click(screen.getByTestId('suggest-task-send'));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith(
      '/api/chat/message',
      expect.objectContaining({
        message: 'Supervisor task: Triage today’s inbox',
        session_id: 'training-chat-sess-1',
        agent_id: 'agent-1',
        user_id: 'user-1',
      }),
      // Agent-loop calls take minutes, not the 10s axios default — the
      // per-request override from the timeout fix.
      { timeout: 120000, retry: false }
    ));
    await waitFor(() =>
      expect(mockApi.updateTrainingGuidance).toHaveBeenCalledWith(
        'sess-1',
        expect.objectContaining({
          tasks: ['Read the inbox', 'Supervisor task: Triage today’s inbox'],
        }),
        expect.stringContaining('Triage today’s inbox')
      )
    );
  });

  test('completion is gated on recorded evidence', async () => {
    mockApi.getCanvasTrainingContext.mockResolvedValue(
      makeContext({
        linked_session: { ...makeContext().linked_session!, evidence: EVIDENCE_LOW },
      })
    );
    render(<TrainingPanel canvasId="cv-1" />);

    await waitFor(() => screen.getByTestId('complete-session-button'));
    expect(screen.getByTestId('complete-session-button')).toBeDisabled();
    expect(mockApi.completeTrainingSession).not.toHaveBeenCalled();
  });

  test('completing the session surfaces the promotion result', async () => {
    mockApi.completeTrainingSession.mockResolvedValue({
      session_id: 'sess-1',
      promoted_to_intern: true,
      confidence_boost: 0.2,
      new_confidence: 0.5,
    });
    render(<TrainingPanel canvasId="cv-1" />);
    await waitFor(() => screen.getByTestId('complete-session-button'));

    fireEvent.change(screen.getByTestId('complete-feedback-input'), {
      target: { value: 'Solid supervised pass' },
    });
    fireEvent.change(screen.getByTestId('complete-capabilities-input'), {
      target: { value: 'email triage, calendar' },
    });
    fireEvent.click(screen.getByTestId('complete-session-button'));

    await waitFor(() =>
      expect(mockApi.completeTrainingSession).toHaveBeenCalledWith('sess-1', {
        performance_score: 0.8,
        supervisor_feedback: 'Solid supervised pass',
        capabilities_developed: ['email triage', 'calendar'],
      })
    );
    await waitFor(() =>
      expect(screen.getByText(/promoted to INTERN/)).toBeInTheDocument()
    );
  });

  test('pending proposal can be approved without leaving the canvas', async () => {
    mockApi.getCanvasTrainingContext.mockResolvedValue(
      makeContext({ linked_session: null, pending_proposal: {
        id: 'prop-1',
        agent_id: 'agent-1',
        agent_name: 'Hire One',
        title: 'Training: email triage',
        description: null,
        status: 'pending_approval',
        capability_gaps: ['email'],
        learning_objectives: [],
        estimated_duration_hours: 4,
        created_at: null,
        approved_by: null,
        approved_at: null,
      } })
    );
    mockApi.approveTrainingProposal.mockResolvedValue({ session_id: 'sess-2', proposal_id: 'prop-1' });
    render(<TrainingPanel canvasId="cv-1" />);

    await waitFor(() => screen.getByTestId('pending-proposal-card'));
    fireEvent.click(screen.getByTestId('approve-proposal'));

    await waitFor(() =>
      expect(mockApi.approveTrainingProposal).toHaveBeenCalledWith('prop-1')
    );
    await waitFor(() => expect(screen.getByText(/Training approved/)).toBeInTheDocument());
  });

  test('promote asks for confirmation and calls the graduation endpoint', async () => {
    jest.spyOn(window, 'confirm').mockReturnValue(true);
    mockApi.promoteAgent.mockResolvedValue({ agent_id: 'agent-1', new_maturity: 'intern', promoted: true });
    render(<TrainingPanel canvasId="cv-1" />);
    await waitFor(() => screen.getByTestId('promote-agent-button'));

    expect(screen.getByTestId('readiness-score')).toHaveTextContent('41/100');
    fireEvent.click(screen.getByTestId('promote-agent-button'));

    await waitFor(() =>
      expect(mockApi.promoteAgent).toHaveBeenCalledWith('agent-1', 'intern')
    );
    await waitFor(() =>
      expect(screen.getByText(/graduated to INTERN/)).toBeInTheDocument()
    );
  });

  test('non-supervisor viewers get teach + progress only', async () => {
    mockApi.getCanvasTrainingContext.mockResolvedValue(
      makeContext({ viewer_is_supervisor: false })
    );
    render(<TrainingPanel canvasId="cv-1" />);

    await waitFor(() => screen.getByTestId('training-agent-name'));
    expect(screen.getByTestId('teach-section')).toBeInTheDocument();
    expect(screen.queryByTestId('canvas-complete-training-form')).not.toBeInTheDocument();
    expect(screen.queryByTestId('graduation-section')).not.toBeInTheDocument();
    expect(screen.queryByTestId('lesson-save')).not.toBeInTheDocument();
    // The lesson is still visible read-only.
    expect(screen.getByText(/Triage inbox/)).toBeInTheDocument();
    expect(mockApi.getGraduationReadiness).not.toHaveBeenCalled();
  });

  test('canvas with no linked agent renders the empty state', async () => {
    mockApi.getCanvasTrainingContext.mockResolvedValue(
      makeContext({ agent: null, linked_session: null })
    );
    render(<TrainingPanel canvasId="cv-1" />);

    await waitFor(() => screen.getByTestId('training-no-agent'));
    expect(screen.queryByTestId('teach-section')).not.toBeInTheDocument();
  });
});

describe('TrainingPanel teaching points', () => {
  test('renders the journal: count, taught/observed badges, newest first', async () => {
    mockApi.getCanvasTrainingContext.mockResolvedValue(makeContext({
      teaching_points: [
        { source: 'observation', topic: 'human_correction', text: 'Supervisor fixed the greeting.', learned_at: '2026-08-31T09:00:00+00:00' },
        { source: 'teacher', topic: 'email tone', text: 'Keep refund emails short.', learned_at: '2026-08-30T10:00:00+00:00' },
      ],
    }));
    render(<TrainingPanel canvasId="cv-1" />);

    await waitFor(() =>
      expect(screen.getByTestId('teaching-points-section')).toBeInTheDocument()
    );
    expect(screen.getByTestId('teaching-points-count')).toHaveTextContent('2 recorded');
    const points = screen.getAllByTestId('teaching-point');
    expect(points).toHaveLength(2);
    expect(points[0]).toHaveTextContent('observed');
    expect(points[0]).toHaveTextContent('human_correction');
    expect(points[1]).toHaveTextContent('taught');
    expect(points[1]).toHaveTextContent('Keep refund emails short.');
  });

  test('teaching points show the canvas they were taught on', async () => {
    mockApi.getCanvasTrainingContext.mockResolvedValue(makeContext({
      teaching_points: [
        {
          source: 'teacher',
          topic: 'budget',
          text: 'Costs always go in row 3.',
          learned_at: '2026-09-01T10:00:00+00:00',
          canvas: { canvas_id: 'cv-9', name: 'Q3 Budget', canvas_type: 'sheet', label: 'Sheet' },
        },
        { source: 'observation', topic: 'human_correction', text: 'No canvas on this one.', learned_at: '2026-08-31T09:00:00+00:00' },
      ],
    }));
    render(<TrainingPanel canvasId="cv-1" />);

    const points = await waitFor(() => screen.getAllByTestId('teaching-point'));
    expect(points[0]).toHaveTextContent('canvas "Q3 Budget" (Sheet)');
    expect(screen.getAllByTestId('teaching-point-canvas')).toHaveLength(1);
  });

  test('teaching a lesson refreshes the journal so the new point shows', async () => {
    mockApi.getCanvasTrainingContext
      .mockResolvedValueOnce(makeContext())            // initial: no points yet
      .mockResolvedValue(makeContext({                 // after teach: point landed
        teaching_points: [
          { source: 'teacher', topic: 'general', text: 'Always cc the team lead on replies', learned_at: '2026-08-31T12:00:00+00:00' },
        ],
      }));
    mockApi.teachAgent.mockResolvedValue({ status: 'ok' });
    render(<TrainingPanel canvasId="cv-1" />);
    await waitFor(() => screen.getByTestId('teach-lesson-input'));
    expect(screen.queryByTestId('teaching-points-section')).not.toBeInTheDocument();

    fireEvent.change(screen.getByTestId('teach-lesson-input'), {
      target: { value: 'Always cc the team lead on replies' },
    });
    fireEvent.click(screen.getByTestId('teach-submit'));

    await waitFor(() =>
      expect(screen.getByTestId('teaching-points-section')).toBeInTheDocument()
    );
    expect(screen.getByTestId('teaching-point')).toHaveTextContent('Always cc the team lead on replies');
  });

  test('a context refresh does not clobber unsaved lesson-plan edits', async () => {
    mockApi.teachAgent.mockResolvedValue({ status: 'ok' });
    render(<TrainingPanel canvasId="cv-1" />);
    await waitFor(() => screen.getByTestId('lesson-objective-input'));

    // Supervisor types an unsaved edit…
    fireEvent.change(screen.getByTestId('lesson-objective-input'), {
      target: { value: 'Rewritten objective (unsaved)' },
    });
    // …then teach fires a background load() of the SAME session.
    fireEvent.change(screen.getByTestId('teach-lesson-input'), {
      target: { value: 'A brand new lesson for the hire' },
    });
    fireEvent.click(screen.getByTestId('teach-submit'));

    await waitFor(() =>
      expect(mockApi.getCanvasTrainingContext).toHaveBeenCalledTimes(2)
    );
    expect(screen.getByTestId('lesson-objective-input')).toHaveValue('Rewritten objective (unsaved)');
  });
});
