/**
 * AutoDevReviewPanel tests — the supervisor journey for the evolution
 * harness: pending fix proposals (Memento skills / AlphaEvolver tool
 * mutations) render with approve/reject, approved-but-not-applied skills get
 * a separate explicit typed Apply step, tool-error patterns surface for the
 * selected agent, and empty states explain the contract.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockGet = jest.fn();
const mockPost = jest.fn();

// The panel reads frames through the socket's `onMessage` listener, so the mock
// delivers to listeners as well as to the state slot.
import { wsMock } from '../../../tests/helpers/wsMock';

jest.mock('@/hooks/useWebSocket', () => ({
  __esModule: true,
  useWebSocket: require('../../../tests/helpers/wsMock').createWebSocketMock(),
}));

jest.mock('@/lib/api', () => ({
  __esModule: true,
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}));

import { AutoDevReviewPanel } from '../AutoDevReviewPanel';

const PENDING_MUTATION = {
  kind: 'mutation',
  id: 'mut-1',
  agent_id: null,
  name: 'outlook.search_emails',
  description: 'Proposed fix for recurring tool failure in outlook.search_emails',
  failure: "tool_error: 400 Syntax error: character '@' is not valid",
  code: 'def search_emails(...): ...',
  status: 'pending',
  created_at: '2026-09-02T12:00:00Z',
};

const PENDING_SKILL = {
  kind: 'skill',
  id: 'skill-1',
  agent_id: 'agent-1',
  name: 'repair_outlook_search',
  description: 'repair outlook customer email search failures',
  failure: 'outlook search failed on the customer email',
  code: 'def repair_outlook_search():\n    return []',
  status: 'pending',
  created_at: '2026-09-02T11:00:00Z',
};

const VALIDATED_SKILL = {
  ...PENDING_SKILL,
  status: 'validated',
  reviewed: true,
  apply_eligible: true,
  created_at: '2026-09-02T13:00:00Z',
};

// Machine validation writes `validated` without a human review binding.
const MACHINE_VALIDATED_SKILL = {
  ...PENDING_SKILL,
  id: 'skill-machine',
  status: 'validated',
  reviewed: false,
  apply_eligible: false,
};

// A review exists but no longer matches the current material/scope.
const STALE_BINDING_SKILL = {
  ...PENDING_SKILL,
  id: 'skill-stale',
  status: 'validated',
  reviewed: true,
  apply_eligible: false,
};

const VALIDATED_MUTATION = {
  ...PENDING_MUTATION,
  id: 'mut-validated',
  status: 'validated',
};

const TOOL_ERRORS_RESPONSE = {
  data: {
    tool_errors: [
      {
        signature: 'outlook.search_emails',
        count: 3,
        last_error: "tool_error: 400 Syntax error: character '@' is not valid",
        last_seen: '2026-09-02T12:00:00+00:00',
      },
    ],
    count: 1,
  },
};

const GUIDANCE_RESPONSE = {
  data: {
    guidance: [
      {
        id: 'g1',
        agent_id: 'agent-1',
        kind: 'tool_error_pattern',
        title: 'outlook.search_emails has failed 3× recently',
        detail: "tool_error: 400 Syntax error: character '@' is not valid",
        importance: 2,
        timestamp: '2026-09-02T12:00:00Z',
      },
    ],
    count: 1,
  },
};

const candidateResponse = (candidates: any[]) => ({
  data: { data: { candidates, count: candidates.length } },
});

function mockLists({
  pending = [] as any[],
  validated = [] as any[],
}: { pending?: any[]; validated?: any[] } = {}) {
  mockGet.mockImplementation((url: string) => {
    const target = String(url);
    if (target.includes('/api/autodev/candidates')) {
      const rows = target.includes('status=validated') ? validated : pending;
      return Promise.resolve(candidateResponse(rows));
    }
    if (target.includes('/guidance')) {
      return Promise.resolve({ data: { data: { guidance: [], count: 0 } } });
    }
    return Promise.resolve({ data: { data: { tool_errors: [], count: 0 } } });
  });
}

const candidateGetCalls = (status: string) =>
  mockGet.mock.calls.filter(
    ([url]) => String(url).includes('/api/autodev/candidates?') &&
      String(url).includes(`status=${status}`)
  );

describe('AutoDevReviewPanel', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    wsMock().reset();
  });

  it('renders pending fix proposals and approves them', async () => {
    mockGet.mockImplementation((url: string) => {
      const target = String(url);
      if (target.includes('/candidates')) {
        return Promise.resolve(candidateResponse([PENDING_MUTATION]));
      }
      if (target.includes('/guidance')) {
        return Promise.resolve({ data: GUIDANCE_RESPONSE });
      }
      return Promise.resolve({ data: TOOL_ERRORS_RESPONSE });
    });
    mockPost.mockResolvedValue({ data: { success: true } });

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getAllByText('outlook.search_emails').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText(/400 Syntax error/).length).toBeGreaterThan(0);
    expect(screen.getByText(/has failed 3/)).toBeInTheDocument();
    // A pending tool mutation keeps its approve/reject lifecycle and has no
    // typed prompt-skill Apply path.
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Approve'));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/autodev/mutations/mut-1/approve');
    });
  });

  it('surfaces recent tool errors for the selected agent', async () => {
    mockGet.mockImplementation((url: string) => {
      if (String(url).includes('/candidates')) {
        return Promise.resolve(candidateResponse([]));
      }
      return Promise.resolve({ data: TOOL_ERRORS_RESPONSE });
    });

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByText('outlook.search_emails')).toBeInTheDocument();
      expect(screen.getByText('3×')).toBeInTheDocument();
    });
  });

  it('shows the nothing-pending contract when empty', async () => {
    mockLists();

    render(<AutoDevReviewPanel />);

    await waitFor(() => {
      expect(
        screen.getByText(/No pending fixes/)
      ).toBeInTheDocument();
    });
    expect(screen.queryByText('Recent tool errors')).not.toBeInTheDocument();
    expect(screen.queryByTestId('autodev-approved-skills')).not.toBeInTheDocument();
  });

  it('requests pending and approved lists in the selected employee scope', async () => {
    mockLists();

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith(
        '/api/autodev/candidates?status=pending&agent_id=agent-1'
      );
      expect(mockGet).toHaveBeenCalledWith(
        '/api/autodev/candidates?status=validated&agent_id=agent-1'
      );
    });
  });

  it('keeps approval separate from application (approve does not apply)', async () => {
    let approved = false;
    mockGet.mockImplementation((url: string) => {
      const target = String(url);
      if (target.includes('/api/autodev/candidates')) {
        const rows = target.includes('status=validated')
          ? (approved ? [VALIDATED_SKILL] : [])
          : (approved ? [] : [PENDING_SKILL]);
        return Promise.resolve(candidateResponse(rows));
      }
      if (target.includes('/guidance')) {
        return Promise.resolve({ data: { data: { guidance: [], count: 0 } } });
      }
      return Promise.resolve({ data: { data: { tool_errors: [], count: 0 } } });
    });
    mockPost.mockImplementation((url: string) => {
      if (String(url) === '/api/autodev/skills/skill-1/approve') {
        approved = true;
        return Promise.resolve({
          data: { data: { id: 'skill-1', status: 'validated' } },
        });
      }
      return Promise.resolve({ data: { success: true } });
    });

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByText('repair_outlook_search')).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/autodev/skills/skill-1/approve');
      expect(screen.getByRole('button', { name: 'Apply' })).toBeInTheDocument();
    });
    // Approval records the review; it never triggers the typed apply endpoint
    // (or any execution path) on the reviewer's behalf.
    expect(
      mockPost.mock.calls.some(([url]) => String(url).endsWith('/apply'))
    ).toBe(false);
    expect(
      mockPost.mock.calls.some(([url]) => /execute|run/.test(String(url)))
    ).toBe(false);
  });

  it('keeps machine-validated skills reviewable when eligibility is false or absent', async () => {
    const unflagged = {
      ...PENDING_SKILL,
      id: 'skill-unflagged',
      status: 'validated',
    };
    mockLists({ validated: [MACHINE_VALIDATED_SKILL, unflagged] });

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByTestId('autodev-approved-skill-skill-machine')).toBeInTheDocument();
      expect(screen.getByTestId('autodev-approved-skill-skill-unflagged')).toBeInTheDocument();
    });
    // Neither false nor a missing flag is treated as permission to apply.
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Approve' })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: 'Reject' })).toHaveLength(2);

    fireEvent.click(screen.getAllByRole('button', { name: 'Approve' })[0]);

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/autodev/skills/skill-machine/approve');
    });
  });

  it('re-reviews a stale-binding skill and offers Apply only after the fresh approval', async () => {
    let reReviewed = false;
    mockGet.mockImplementation((url: string) => {
      const target = String(url);
      if (target.includes('/api/autodev/candidates')) {
        const rows = target.includes('status=validated')
          ? [reReviewed ? { ...STALE_BINDING_SKILL, apply_eligible: true } : STALE_BINDING_SKILL]
          : [];
        return Promise.resolve(candidateResponse(rows));
      }
      if (target.includes('/guidance')) {
        return Promise.resolve({ data: { data: { guidance: [], count: 0 } } });
      }
      return Promise.resolve({ data: { data: { tool_errors: [], count: 0 } } });
    });
    mockPost.mockImplementation((url: string) => {
      if (String(url) === '/api/autodev/skills/skill-stale/approve') {
        reReviewed = true;
      }
      return Promise.resolve({ data: { success: true } });
    });

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByTestId('autodev-approved-skill-skill-stale')).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/autodev/skills/skill-stale/approve');
      expect(screen.getByRole('button', { name: 'Apply' })).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
  });

  it('applies a validated skill through the typed endpoint and refreshes truthfully', async () => {
    let applied = false;
    mockGet.mockImplementation((url: string) => {
      const target = String(url);
      if (target.includes('/api/autodev/candidates')) {
        const rows = target.includes('status=validated')
          ? (applied ? [] : [VALIDATED_SKILL])
          : [];
        return Promise.resolve(candidateResponse(rows));
      }
      if (target.includes('/guidance')) {
        return Promise.resolve({ data: { data: { guidance: [], count: 0 } } });
      }
      return Promise.resolve({ data: { data: { tool_errors: [], count: 0 } } });
    });
    mockPost.mockImplementation((url: string) => {
      if (String(url) === '/api/autodev/skills/skill-1/apply') {
        applied = true;
        return Promise.resolve({
          data: { data: { status: 'promoted', already_applied: false } },
        });
      }
      return Promise.resolve({ data: { success: true } });
    });

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByTestId('autodev-approved-skills')).toBeInTheDocument();
      expect(screen.getByText('repair_outlook_search')).toBeInTheDocument();
    });
    expect(candidateGetCalls('validated')).toHaveLength(1);

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/autodev/skills/skill-1/apply');
      expect(
        screen.getByText(/applied as a typed prompt skill/i)
      ).toBeInTheDocument();
    });
    // The row is removed only because the refreshed server list no longer
    // carries it — not optimistically.
    await waitFor(() => {
      expect(
        screen.queryByTestId('autodev-approved-skill-skill-1')
      ).not.toBeInTheDocument();
    });
    expect(candidateGetCalls('validated')).toHaveLength(2);
    expect(mockPost).toHaveBeenCalledTimes(1);
  });

  it('reports an already-applied result without claiming a new application', async () => {
    mockLists({ validated: [VALIDATED_SKILL] });
    mockPost.mockResolvedValue({
      data: { data: { status: 'promoted', already_applied: true } },
    });

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Apply' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => {
      expect(screen.getByText(/already applied/i)).toBeInTheDocument();
    });
  });

  it('shows a refusal, keeps the approved skill, and refreshes from the server', async () => {
    mockLists({ validated: [VALIDATED_SKILL] });
    mockPost.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: 'stale_review: reviewed material changed' },
      },
    });

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(
        screen.getByTestId('autodev-approved-skill-skill-1')
      ).toBeInTheDocument();
    });
    expect(candidateGetCalls('validated')).toHaveLength(1);

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => {
      expect(
        screen.getByText(/stale_review: reviewed material changed/)
      ).toBeInTheDocument();
    });
    // The refusal is not converted into an optimistic success, and the list
    // is re-read so the card reflects server truth.
    expect(candidateGetCalls('validated')).toHaveLength(2);
    expect(
      screen.getByTestId('autodev-approved-skill-skill-1')
    ).toBeInTheDocument();
    expect(
      mockPost.mock.calls.some(([url]) => String(url).endsWith('/approve'))
    ).toBe(false);
  });

  it('does not offer typed apply for a validated tool mutation', async () => {
    mockLists({ validated: [VALIDATED_MUTATION] });

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByText(/No pending fixes/)).toBeInTheDocument();
    });
    expect(screen.queryByTestId('autodev-approved-skills')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument();
  });

  it('shows the agent display name on workspace-wide pending and validated skills', async () => {
    const otherSkill = {
      ...PENDING_SKILL,
      id: 'skill-2',
      agent_id: 'agent-2',
      name: 'repair_calendar_conflicts',
    };
    mockLists({
      pending: [PENDING_SKILL, otherSkill],
      validated: [VALIDATED_SKILL],
    });

    render(
      <AutoDevReviewPanel
        agentNames={{
          'agent-1': 'Ada Lovelace',
          'agent-2': 'Grace Hopper',
        }}
      />
    );

    await waitFor(() => {
      // Pending and validated cards both carry the reviewer-facing name.
      expect(screen.getAllByText('Agent: Ada Lovelace')).toHaveLength(2);
      expect(screen.getByText('Agent: Grace Hopper')).toBeInTheDocument();
    });
    // Opaque agent IDs stay out of the reviewer UI.
    expect(screen.queryByText(/agent-1|agent-2/)).not.toBeInTheDocument();
  });

  it('falls back gracefully without leaking an agent ID when no name is known', async () => {
    mockLists({ pending: [PENDING_SKILL], validated: [VALIDATED_SKILL] });

    render(<AutoDevReviewPanel agentNames={{ 'someone-else': 'Grace Hopper' }} />);

    await waitFor(() => {
      expect(screen.getAllByText('Agent: Unnamed agent')).toHaveLength(2);
    });
    expect(screen.queryByText(/agent-1/)).not.toBeInTheDocument();
    // A missing name never blocks the review action.
    expect(screen.getByRole('button', { name: 'Apply' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Approve' }).length).toBeGreaterThan(0);
  });
});
