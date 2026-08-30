/**
 * Maturity API client tests (lib/maturity-api.ts)
 *
 * Mocks apiClient.fetch and asserts URL/method/payload contract for the
 * restored /api/maturity/* supervisor surface (R81).
 */

const mockFetch = jest.fn();

jest.mock('../../api-client', () => ({
  __esModule: true,
  apiClient: {
    fetch: (...args: unknown[]) => mockFetch(...args),
  },
}));

import {
  listTrainingProposals,
  approveTrainingProposal,
  rejectTrainingProposal,
  completeTrainingSession,
  listActionProposals,
  approveActionProposal,
  getCanvasTrainingContext,
  teachAgent,
  updateTrainingGuidance,
  getGraduationReadiness,
  promoteAgent,
  getAgentGraduationProgress,
} from '../../maturity-api';

function jsonResponse(body: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => body,
  };
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe('maturity-api training proposals', () => {
  test('listTrainingProposals builds filters and unwraps payload', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ proposals: [{ id: 'p1', agent_id: 'a1' }] })
    );

    const out = await listTrainingProposals({ agentId: 'a1', limit: 10 });

    expect(out).toHaveLength(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('/api/maturity/training/proposals');
    expect(url).toContain('agent_id=a1');
    expect(url).toContain('limit=10');
  });

  test('approveTrainingProposal posts approve:true', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ session_id: 's1', proposal_id: 'p1' })
    );

    const out = await approveTrainingProposal('p1');

    expect(out.session_id).toBe('s1');
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/maturity/training/proposals/p1/approve');
    expect((init as RequestInit).method).toBe('POST');
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      approve: true,
      duration_override: undefined,
    });
  });

  test('rejectTrainingProposal throws on non-ok', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ detail: 'nope' }, false, 400));
    await expect(rejectTrainingProposal('p1', 'bad')).rejects.toThrow('400');
  });

  test('completeTrainingSession posts defaults + payload', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ session_id: 's1', promoted_to_intern: true })
    );

    const out = await completeTrainingSession('s1', {
      performance_score: 0.9,
      supervisor_feedback: 'great',
      errors_count: 0,
      tasks_completed: 5,
      total_tasks: 5,
    });

    expect(out.promoted_to_intern).toBe(true);
    const [, init] = mockFetch.mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.capabilities_developed).toEqual([]);
    expect(body.performance_score).toBe(0.9);
  });
});

describe('maturity-api action proposals', () => {
  test('listActionProposals unwraps payload', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ proposals: [{ id: 'pr1', agent_id: 'a1' }] })
    );
    const out = await listActionProposals({ statusFilter: 'PENDING_APPROVAL' });
    expect(out[0].id).toBe('pr1');
    expect(mockFetch.mock.calls[0][0]).toContain('status_filter=PENDING_APPROVAL');
  });

  test('approveActionProposal returns execution result', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ execution_result: { success: true } })
    );
    const out = await approveActionProposal('pr1');
    expect(out.execution_result).toEqual({ success: true });
    expect(mockFetch.mock.calls[0][0]).toBe('/api/maturity/proposals/pr1/approve');
  });
});

describe('maturity-api canvas training surface', () => {
  test('getCanvasTrainingContext passes canvas + agent hint', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        canvas_id: 'cv-1',
        agent: { id: 'a1', name: 'Hire', tier: 'student', confidence: 0.3, domain: 'email' },
        linked_session: null,
        pending_proposal: null,
        viewer_is_supervisor: true,
      })
    );

    const out = await getCanvasTrainingContext('cv-1', 'a1');

    expect(out.agent?.id).toBe('a1');
    expect(out.viewer_is_supervisor).toBe(true);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('/api/maturity/training/context');
    expect(url).toContain('canvas_id=cv-1');
    expect(url).toContain('agent_id=a1');
  });

  test('teachAgent posts the lesson to /api/agents/{id}/teach', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ status: 'ok' }));

    const out = await teachAgent('a1', 'Always cc the lead', 'email');

    expect(out.status).toBe('ok');
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/agents/a1/teach');
    expect((init as RequestInit).method).toBe('POST');
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      lesson: 'Always cc the lead',
      topic: 'email',
    });
  });

  test('updateTrainingGuidance patches the lesson plan', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, lesson_plan: {} }));

    await updateTrainingGuidance('s1', { objective: 'Triage' }, 'note');

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/maturity/training/sessions/s1/guidance');
    expect((init as RequestInit).method).toBe('PATCH');
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      lesson_plan: { objective: 'Triage' },
      supervisor_note: 'note',
    });
  });

  test('getGraduationReadiness targets the next maturity', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ ready: true, score: 91 }));

    const out = await getGraduationReadiness('a1', 'SUPERVISED');

    expect(out.score).toBe(91);
    expect(mockFetch.mock.calls[0][0]).toBe(
      '/api/episodes/graduation/readiness/a1?target_maturity=SUPERVISED'
    );
  });

  test('promoteAgent posts with query params, not a JSON body', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ agent_id: 'a1', new_maturity: 'intern', promoted: true })
    );

    const out = await promoteAgent('a1', 'intern');

    expect(out.promoted).toBe(true);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/episodes/graduation/promote?agent_id=a1&new_maturity=intern');
    expect((init as RequestInit).method).toBe('POST');
    expect((init as RequestInit).body).toBeUndefined();
  });

  test('getAgentGraduationProgress hits the shared agents surface', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ current_tier: 'student', next_tier: 'intern', episode_count: 4 })
    );

    const out = await getAgentGraduationProgress('a1');

    expect(out.episode_count).toBe(4);
    expect(mockFetch.mock.calls[0][0]).toBe('/api/agents/a1/graduation-progress');
  });
});
