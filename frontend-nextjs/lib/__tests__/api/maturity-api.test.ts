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
