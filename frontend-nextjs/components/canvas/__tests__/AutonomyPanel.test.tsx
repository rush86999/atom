/**
 * AutonomyPanel tests (canvas right-panel Autonomy tab)
 *
 * The panel is the tenant's per-topic autonomy control surface. This covers
 * the three-mode contract (human_always / auto_if_mature /
 * auto_until_corrected — the 2026-09-04 third choice), the live gate, and the
 * optional owner-global "never autonomous" task baskets (difficulty /
 * category / domain rules with per-rule revision handling).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import axe from '../../../tests/accessibility-config';

const mockApi = {
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
};

jest.mock('@/lib/api-client', () => ({
  apiClient: mockApi,
}));

import { AutonomyPanel } from '../AutonomyPanel';

const TOPICS = [
  {
    topic: 'send_email',
    label: 'Send email',
    description: 'Sending emails on your behalf (external, irreversible)',
    default_mode: 'human_always',
    mode: 'human_always',
    canvas_relevant: true,
    gate: {
      outcome: 'propose',
      reason: 'You asked to approve every send email — the hire proposes only.',
      maturity: { known: true, maturity_level: 'supervised', required: 'supervised', ok: true },
      trust: { enabled: false, trust: null, threshold: 0.6, cold_start: null, ok: true },
      cycle: null,
    },
  },
  {
    topic: 'canvas_edit',
    label: 'Canvas edits',
    description: 'Editing drafts and documents on canvases',
    default_mode: 'auto_if_mature',
    mode: 'auto_until_corrected',
    canvas_relevant: false,
    gate: {
      outcome: 'propose',
      reason:
        'A human correction reset the canvas edits autonomy cycle — re-earned capability tier student so far, needs intern again (verified work re-graduates it).',
      maturity: { known: true, maturity_level: 'supervised', required: 'intern', ok: true },
      trust: { enabled: false, trust: null, threshold: 0.6, cold_start: null, ok: true },
      cycle: { reset: true, tier: 'student', required: 'intern', ok: false, reason: null },
    },
  },
];

const DIMENSIONS = {
  difficulty: ['simple', 'moderate', 'complex', 'advanced'],
  category: ['code', 'math', 'qa', 'extraction', 'planning', 'prose'],
  domain: ['finance', 'hr', 'marketing', 'operations', 'sales', 'support'],
};

function makeRule(overrides: Record<string, any> = {}) {
  return {
    id: 'nar_1',
    name: 'Month-end financial reconciliation',
    enabled: true,
    match: {
      difficulty: ['advanced'],
      category: ['extraction', 'math'],
      domain: ['finance'],
    },
    scope: { user_id: 'user-1', workspace_id: null, tenant_id: null },
    revision: 1,
    created_at: '2026-11-16T12:00:00+00:00',
    updated_at: '2026-11-16T12:00:00+00:00',
    ...overrides,
  };
}

function topicGate(never: Record<string, any>, overrides: Record<string, any> = {}) {
  return {
    outcome: 'propose',
    reason: 'The hire proposes only.',
    maturity: { known: true, maturity_level: 'supervised', required: 'supervised', ok: true },
    trust: { enabled: false, trust: null, threshold: 0.6, cold_start: null, ok: true },
    cycle: null,
    never_autonomous: never,
    ...overrides,
  };
}

function installRoutes({
  topics = TOPICS,
  rules = [] as any[],
  dimensions = DIMENSIONS,
  rulesFailure,
  rulesResponse,
}: {
  topics?: any[];
  rules?: any[];
  dimensions?: any;
  rulesFailure?: any;
  rulesResponse?: any;
} = {}) {
  mockApi.get.mockImplementation(async (url: string) => {
    if (String(url) === '/api/autonomy/never-rules') {
      if (rulesFailure) throw rulesFailure;
      if (rulesResponse !== undefined) return { data: rulesResponse };
      return {
        data: {
          rules,
          count: rules.length,
          dimensions,
          scope: { user_id: 'user-1', workspace_id: null, tenant_id: null },
        },
      };
    }
    if (String(url).startsWith('/api/autonomy/topics')) {
      return { data: { topics } };
    }
    return { data: {} };
  });
}

function httpError(status: number, data: any = {}) {
  return Object.assign(new Error(`HTTP ${status}`), { response: { status, data } });
}

beforeEach(() => {
  jest.resetAllMocks();
  installRoutes();
  mockApi.post.mockResolvedValue({ data: { success: true } });
  mockApi.put.mockResolvedValue({ data: { success: true } });
  mockApi.delete.mockResolvedValue({ data: { success: true, deleted: true } });
});

describe('AutonomyPanel', () => {
  test('renders the three tenant-selectable modes per topic', async () => {
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-send_email'));
    expect(screen.getByTestId('autonomy-send_email-hitl')).toBeInTheDocument();
    expect(screen.getByTestId('autonomy-send_email-auto')).toBeInTheDocument();
    expect(screen.getByTestId('autonomy-send_email-cycle')).toBeInTheDocument();
  });

  test('selecting auto-until-corrected PUTs the new mode and refreshes', async () => {
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-send_email-cycle'));
    fireEvent.click(screen.getByTestId('autonomy-send_email-cycle'));

    await waitFor(() =>
      expect(mockApi.put).toHaveBeenCalledWith('/api/autonomy/topics/send_email', {
        mode: 'auto_until_corrected',
      })
    );
    // Silent gate refresh after the mode change (rules GET is a separate call).
    await waitFor(() =>
      expect(
        mockApi.get.mock.calls.filter(([url]) => String(url).startsWith('/api/autonomy/topics'))
          .length
      ).toBe(2)
    );
  });

  test('a reset cycle is visible in the gate detail', async () => {
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByText(/cycle student/i));
    expect(screen.getByText(/reset by a correction/i)).toBeInTheDocument();
  });

  test('empty rule list is opt-in and leaves topic controls untouched', async () => {
    installRoutes({ rules: [] });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-empty'));
    expect(screen.getByTestId('autonomy-send_email')).toBeInTheDocument();
    expect(screen.getByTestId('autonomy-general-section')).toBeInTheDocument();
    expect(screen.getByTestId('autonomy-never-unknown-note')).toBeInTheDocument();
    expect(screen.getByTestId('autonomy-never-add')).toBeInTheDocument();
    expect(mockApi.post).not.toHaveBeenCalled();
    expect(mockApi.put).not.toHaveBeenCalled();
    expect(mockApi.delete).not.toHaveBeenCalled();
  });

  test('existing rules render names, selected alternatives, and disabled state', async () => {
    const enabled = makeRule({ id: 'nar_1', name: 'Month-end reconciliation', revision: 2 });
    const disabled = makeRule({
      id: 'nar_2',
      name: 'Support replies',
      enabled: false,
      revision: 4,
      match: {
        difficulty: ['simple', 'moderate'],
        category: ['math', 'prose'],
        domain: ['finance', 'legal-ops'],
      },
    });
    installRoutes({ rules: [enabled, disabled] });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-rule-0'));
    expect(screen.getByTestId('autonomy-never-rule-0-name')).toHaveValue(
      'Month-end reconciliation'
    );
    expect(screen.getByTestId('autonomy-never-rule-0-difficulty-advanced')).toBeChecked();
    expect(screen.getByTestId('autonomy-never-rule-0-category-extraction')).toBeChecked();
    expect(screen.getByTestId('autonomy-never-rule-0-category-math')).toBeChecked();
    expect(screen.getByTestId('autonomy-never-rule-0-domain-finance')).toBeChecked();

    // A multi-value rule is not collapsed to one value.
    expect(screen.getByTestId('autonomy-never-rule-1-difficulty-simple')).toBeChecked();
    expect(screen.getByTestId('autonomy-never-rule-1-difficulty-moderate')).toBeChecked();
    expect(screen.getByTestId('autonomy-never-rule-1-category-math')).toBeChecked();
    expect(screen.getByTestId('autonomy-never-rule-1-category-prose')).toBeChecked();
    // A stored slug that is not in the current suggestions is still selected.
    expect(screen.getByTestId('autonomy-never-rule-1-domain-legal-ops')).toBeChecked();
    expect(screen.getByText(/legal-ops \(not suggested\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Disabled — this rule never matches/i)).toBeInTheDocument();
  });

  test('creates a named rule with alternative values and no topic writes', async () => {
    installRoutes({ rules: [] });
    mockApi.post.mockResolvedValue({
      data: {
        success: true,
        rule: makeRule({
          id: 'nar_new',
          name: 'Month-end reconciliation',
          revision: 1,
          match: {
            difficulty: ['advanced'],
            category: ['extraction', 'math'],
            domain: ['finance'],
          },
        }),
      },
    });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-add'));
    fireEvent.click(screen.getByTestId('autonomy-never-add'));
    fireEvent.change(screen.getByTestId('autonomy-never-rule-0-name'), {
      target: { value: 'Month-end reconciliation' },
    });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-difficulty-advanced'));
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-category-extraction'));
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-category-math'));
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-domain-finance'));
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-save'));

    await waitFor(() =>
      expect(mockApi.post).toHaveBeenCalledWith(
        '/api/autonomy/never-rules',
        {
          name: 'Month-end reconciliation',
          enabled: true,
          match: {
            difficulty: ['advanced'],
            category: ['extraction', 'math'],
            domain: ['finance'],
          },
        },
        { retry: false }
      )
    );
    await waitFor(() => expect(screen.getByTestId('autonomy-never-status')).toHaveTextContent(/created/i));
    expect(screen.getByTestId('autonomy-never-rule-0-name')).toHaveValue(
      'Month-end reconciliation'
    );
    expect(screen.getByTestId('autonomy-never-add')).not.toBeDisabled();
    expect(
      mockApi.put.mock.calls.filter(([url]) => String(url).startsWith('/api/autonomy/topics'))
    ).toHaveLength(0);
  });

  test('validates and adds a custom business-domain slug', async () => {
    installRoutes({ rules: [] });
    mockApi.post.mockResolvedValue({
      data: {
        success: true,
        rule: makeRule({
          id: 'nar_custom',
          name: 'Custom domain basket',
          match: { difficulty: ['simple'], domain: ['legal-ops'] },
        }),
      },
    });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-add'));
    fireEvent.click(screen.getByTestId('autonomy-never-add'));
    fireEvent.change(screen.getByTestId('autonomy-never-rule-0-name'), {
      target: { value: 'Custom domain basket' },
    });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-difficulty-simple'));

    const domainInput = screen.getByTestId('autonomy-never-rule-0-domain-input');
    fireEvent.change(domainInput, { target: { value: 'Not A Slug' } });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-domain-add'));
    expect(screen.getByText(/Use a lower-case slug/i)).toBeInTheDocument();
    expect(
      screen.queryByTestId('autonomy-never-rule-0-domain-not-a-slug')
    ).not.toBeInTheDocument();

    // Input is normalized to the contract's lower-case slug form.
    fireEvent.change(domainInput, { target: { value: 'Legal-Ops' } });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-domain-add'));
    expect(screen.getByTestId('autonomy-never-rule-0-domain-legal-ops')).toBeChecked();
    expect(screen.queryByText(/Use a lower-case slug/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-save'));
    await waitFor(() =>
      expect(mockApi.post).toHaveBeenCalledWith(
        '/api/autonomy/never-rules',
        {
          name: 'Custom domain basket',
          enabled: true,
          match: { difficulty: ['simple'], domain: ['legal-ops'] },
        },
        { retry: false }
      )
    );
  });

  test('edits an existing rule with its revision and preserves alternatives', async () => {
    installRoutes({ rules: [makeRule({ revision: 7 })] });
    mockApi.put.mockResolvedValue({
      data: {
        success: true,
        rule: makeRule({ name: 'Updated basket', enabled: false, revision: 8 }),
      },
    });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-rule-0'));
    fireEvent.change(screen.getByTestId('autonomy-never-rule-0-name'), {
      target: { value: 'Updated basket' },
    });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-enabled'));
    expect(screen.getByTestId('autonomy-never-rule-0-enabled')).toHaveAttribute(
      'data-state',
      'unchecked'
    );
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-save'));

    await waitFor(() =>
      expect(mockApi.put).toHaveBeenCalledWith(
        '/api/autonomy/never-rules/nar_1',
        {
          name: 'Updated basket',
          enabled: false,
          match: {
            difficulty: ['advanced'],
            category: ['extraction', 'math'],
            domain: ['finance'],
          },
          expected_revision: 7,
        },
        { retry: false }
      )
    );
    await waitFor(() => expect(screen.getByTestId('autonomy-never-status')).toHaveTextContent(/saved/i));
    expect(
      mockApi.put.mock.calls.filter(([url]) => String(url).startsWith('/api/autonomy/topics'))
    ).toHaveLength(0);
  });

  test('cancel restores the last saved rule without a write', async () => {
    installRoutes({ rules: [makeRule()] });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-rule-0'));
    fireEvent.change(screen.getByTestId('autonomy-never-rule-0-name'), {
      target: { value: 'Unsaved edit' },
    });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-cancel'));

    expect(screen.getByTestId('autonomy-never-rule-0-name')).toHaveValue(
      'Month-end financial reconciliation'
    );
    expect(mockApi.post).not.toHaveBeenCalled();
    expect(mockApi.put).not.toHaveBeenCalled();
    expect(mockApi.delete).not.toHaveBeenCalled();
  });

  test('delete confirms, recommends disabling instead, and removes the card', async () => {
    installRoutes({ rules: [makeRule()] });
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-rule-0'));
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-delete'));

    await waitFor(() =>
      expect(mockApi.delete).toHaveBeenCalledWith('/api/autonomy/never-rules/nar_1', {
        retry: false,
      })
    );
    expect(String(confirmSpy.mock.calls[0][0])).toMatch(/disable it instead/i);
    await waitFor(() => expect(screen.queryByTestId('autonomy-never-rule-0')).not.toBeInTheDocument());
    expect(screen.getByTestId('autonomy-never-empty')).toBeInTheDocument();
    expect(screen.getByTestId('autonomy-never-status')).toHaveTextContent(/deleted/i);
    confirmSpy.mockRestore();
  });

  test('validation blocks a blank name and a filterless catch-all', async () => {
    installRoutes({ rules: [] });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-add'));
    fireEvent.click(screen.getByTestId('autonomy-never-add'));
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-save'));

    expect(screen.getByText('Give this rule a name.')).toBeInTheDocument();
    expect(screen.getByText(/Pick at least one difficulty, category, or domain/i)).toBeInTheDocument();
    expect(mockApi.post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByTestId('autonomy-never-rule-0-name'), {
      target: { value: 'Named but unfiltered' },
    });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-save'));
    expect(screen.getByText(/Pick at least one difficulty, category, or domain/i)).toBeInTheDocument();
    expect(mockApi.post).not.toHaveBeenCalled();
  });

  test('a rejected save keeps the draft and never claims success', async () => {
    installRoutes({ rules: [makeRule()] });
    mockApi.put.mockRejectedValue(
      httpError(400, { detail: 'name must be 1-120 characters' })
    );
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-rule-0'));
    fireEvent.change(screen.getByTestId('autonomy-never-rule-0-name'), {
      target: { value: 'Still here' },
    });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-save'));

    await waitFor(() =>
      expect(screen.getByText(/Could not save this rule. name must be 1-120 characters/i)).toBeInTheDocument()
    );
    expect(screen.getByTestId('autonomy-never-rule-0-name')).toHaveValue('Still here');
    expect(screen.getByTestId('autonomy-never-status')).not.toHaveTextContent(/saved/i);
    expect(mockApi.post).not.toHaveBeenCalled();
  });

  test('a 404 on save treats the rule as gone and refreshes the list', async () => {
    installRoutes({ rules: [makeRule()] });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-rule-0'));
    // The rule vanished server-side (another tab/owner deletion).
    installRoutes({ rules: [] });
    mockApi.put.mockRejectedValue(httpError(404, { detail: 'Rule not found' }));

    fireEvent.change(screen.getByTestId('autonomy-never-rule-0-name'), {
      target: { value: 'Stale edit' },
    });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-save'));

    await waitFor(() =>
      expect(screen.getByTestId('autonomy-never-error')).toHaveTextContent(
        /This rule is no longer available/i
      )
    );
    expect(screen.queryByTestId('autonomy-never-rule-0')).not.toBeInTheDocument();
    expect(screen.queryByTestId('autonomy-never-empty')).not.toBeInTheDocument();
    expect(screen.getByTestId('autonomy-never-status')).not.toHaveTextContent(/saved/i);
    expect(
      mockApi.get.mock.calls.filter(([url]) => String(url) === '/api/autonomy/never-rules').length
    ).toBeGreaterThanOrEqual(2);
  });

  test('a 409 conflict preserves the draft, disables Save, and reloads explicitly', async () => {
    installRoutes({ rules: [makeRule({ revision: 1 })] });
    mockApi.put.mockRejectedValueOnce(
      httpError(409, { detail: 'rule_revision_conflict', current_revision: 2 })
    );
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-rule-0'));
    fireEvent.change(screen.getByTestId('autonomy-never-rule-0-name'), {
      target: { value: 'My unsaved edit' },
    });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-save'));

    await waitFor(() => expect(screen.getByTestId('autonomy-never-conflict')).toBeInTheDocument());
    expect(screen.getByTestId('autonomy-never-conflict')).toHaveTextContent(/Server revision: 2/);
    expect(screen.getByTestId('autonomy-never-rule-0-name')).toHaveValue('My unsaved edit');
    expect(screen.getByTestId('autonomy-never-rule-0-save')).toBeDisabled();
    expect(screen.getByTestId('autonomy-never-status')).not.toHaveTextContent(/saved/i);
    expect(mockApi.put).toHaveBeenCalledTimes(1);

    installRoutes({
      rules: [makeRule({ revision: 2, name: 'Changed elsewhere' })],
    });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-reload'));

    await waitFor(() =>
      expect(screen.getByTestId('autonomy-never-rule-0-name')).toHaveValue('Changed elsewhere')
    );
    expect(screen.queryByTestId('autonomy-never-conflict')).not.toBeInTheDocument();
    expect(screen.getByTestId('autonomy-never-status')).toHaveTextContent(/reloaded/i);
    expect(
      mockApi.get.mock.calls.filter(([url]) => String(url) === '/api/autonomy/never-rules').length
    ).toBeGreaterThanOrEqual(2);
  });

  test('unknown stored values survive an edit instead of being dropped', async () => {
    installRoutes({
      rules: [
        makeRule({
          match: {
            difficulty: ['advanced', 'exotic'],
            category: ['math', 'legacy_task'],
            domain: ['finance'],
          },
        }),
      ],
    });
    mockApi.put.mockResolvedValue({ data: { success: true, rule: makeRule() } });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-rule-0'));
    expect(screen.getByTestId('autonomy-never-rule-0-difficulty-exotic')).toBeChecked();
    expect(screen.getByTestId('autonomy-never-rule-0-category-legacy_task')).toBeChecked();
    fireEvent.change(screen.getByTestId('autonomy-never-rule-0-name'), {
      target: { value: 'Renamed' },
    });
    fireEvent.click(screen.getByTestId('autonomy-never-rule-0-save'));

    await waitFor(() =>
      expect(mockApi.put).toHaveBeenCalledWith(
        '/api/autonomy/never-rules/nar_1',
        expect.objectContaining({
          match: {
            difficulty: ['advanced', 'exotic'],
            category: ['math', 'legacy_task'],
            domain: ['finance'],
          },
        }),
        { retry: false }
      )
    );
  });

  test('load failure is an error with retry, not an empty list', async () => {
    installRoutes({ rulesFailure: httpError(500) });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => expect(screen.getByTestId('autonomy-never-error')).toBeInTheDocument());
    expect(screen.getByTestId('autonomy-never-error')).toHaveTextContent(/Could not load task rules/i);
    expect(screen.getByTestId('autonomy-never-retry')).toBeInTheDocument();
    expect(screen.queryByTestId('autonomy-never-empty')).not.toBeInTheDocument();
    expect(screen.getByTestId('autonomy-send_email')).toBeInTheDocument();

    installRoutes({ rules: [] });
    fireEvent.click(screen.getByTestId('autonomy-never-retry'));
    await waitFor(() => expect(screen.getByTestId('autonomy-never-empty')).toBeInTheDocument());
  });

  test.each([
    ['a missing collection (404)', httpError(404), undefined],
    [
      'a malformed 200',
      undefined,
      { rules: 'nope', dimensions: DIMENSIONS },
    ],
  ])('unsupported rule API is distinct from an empty list: %s', async (_label, failure, response) => {
    installRoutes({ rulesFailure: failure, rulesResponse: response });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() =>
      expect(screen.getByTestId('autonomy-never-unsupported')).toBeInTheDocument()
    );
    expect(screen.getByTestId('autonomy-never-unsupported')).toHaveTextContent(
      /aren’t available in this build/i
    );
    expect(screen.queryByTestId('autonomy-never-empty')).not.toBeInTheDocument();
    expect(screen.queryByTestId('autonomy-never-add')).not.toBeInTheDocument();
  });

  test('403 renders a read-only owner-only state with no Add control', async () => {
    installRoutes({ rulesFailure: httpError(403) });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => expect(screen.getByTestId('autonomy-never-forbidden')).toBeInTheDocument());
    expect(screen.getByTestId('autonomy-never-forbidden')).toHaveTextContent(
      /Only the signed-in owner/i
    );
    expect(screen.queryByTestId('autonomy-never-add')).not.toBeInTheDocument();
    expect(screen.queryByTestId('autonomy-never-empty')).not.toBeInTheDocument();
  });

  test('a definite rule match vetoes autonomy even when the raw gate says execute', async () => {
    installRoutes({
      topics: [
        {
          ...TOPICS[0],
          gate: topicGate(
            {
              applicable: true,
              matched: true,
              potential: false,
              outcome: 'review',
              rule_ids: ['nar_1'],
              rule_names: ['Month-end reconciliation'],
              reason: 'Never-autonomous rule “Month-end reconciliation” matched this task.',
              profile: { difficulty: 'advanced', category: 'extraction', domain: 'finance' },
            },
            { outcome: 'execute', reason: 'Policy allows autonomy — executes directly.' }
          ),
        },
      ],
    });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => expect(screen.getByTestId('autonomy-gate-never')).toBeInTheDocument());
    expect(screen.getByTestId('autonomy-gate-never')).toHaveTextContent(
      /This task matches a never-autonomous rule: Month-end reconciliation/i
    );
    expect(screen.getByTestId('autonomy-gate-never')).toHaveTextContent(
      /A human must approve this execution/i
    );
    expect(screen.queryByText(/Acts autonomously today/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId('autonomy-gate-execute')).not.toBeInTheDocument();
    expect(screen.getByTestId('autonomy-gate-propose')).toBeInTheDocument();
    expect(screen.getByTestId('autonomy-gate-profile')).toHaveTextContent(
      /difficulty advanced · category extraction · domain finance/i
    );
  });

  test('a potential match asks for review and shows missing metadata as not classified', async () => {
    installRoutes({
      topics: [
        {
          ...TOPICS[0],
          gate: topicGate({
            applicable: true,
            matched: true,
            potential: true,
            outcome: 'review',
            rule_ids: ['nar_1'],
            rule_names: ['Month-end reconciliation'],
            reason: 'Task classification data was unavailable.',
            profile: { difficulty: 'advanced', category: null, domain: null },
          }),
        },
      ],
    });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    const banner = await screen.findByTestId('autonomy-gate-never');
    expect(banner).toHaveTextContent(/may apply/i);
    expect(banner).toHaveTextContent(/task classification data is unavailable/i);
    expect(banner).toHaveTextContent(/A human must review/i);
    expect(screen.getByTestId('autonomy-gate-profile')).toHaveTextContent(
      /category not classified · domain not classified/i
    );
    // The gate itself never claims a non-match when the field is unknown.
    expect(within(banner).queryByText(/doesn.t match/i)).not.toBeInTheDocument();
  });

  test('a non-matching rule leaves the existing gate chip and adds no banner', async () => {
    installRoutes({
      topics: [
        {
          ...TOPICS[0],
          gate: topicGate({
            applicable: true,
            matched: false,
            potential: false,
            outcome: 'unaffected',
            rule_ids: [],
            rule_names: [],
            reason: 'No never-autonomous rule matched this task.',
            profile: { difficulty: 'simple', category: 'code', domain: 'sales' },
          }),
        },
      ],
    });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => expect(screen.getByTestId('autonomy-gate-propose')).toBeInTheDocument());
    expect(screen.queryByTestId('autonomy-gate-never')).not.toBeInTheDocument();
  });

  test('policy-store failure requires review without naming a matched rule', async () => {
    installRoutes({
      topics: [
        {
          ...TOPICS[0],
          gate: topicGate({
            applicable: true,
            matched: false,
            potential: false,
            outcome: 'review',
            rule_ids: [],
            rule_names: [],
            reason: 'never_autonomous_policy_unavailable',
          }),
        },
      ],
    });
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    const banner = await screen.findByTestId('autonomy-gate-never');
    expect(banner).toHaveTextContent(
      /Autonomy policy is unavailable; execution requires human review/i
    );
    expect(within(banner).queryByText(/Month-end/i)).not.toBeInTheDocument();
    expect(within(banner).queryByText(/matches a never-autonomous rule/i)).not.toBeInTheDocument();
  });

  test('rule controls have accessible names and no axe violations', async () => {
    installRoutes({ rules: [makeRule({ enabled: false })] });
    const { container } = render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-never-rule-0'));
    expect(screen.getByRole('switch', { name: /Enable rule 1/i })).toBeInTheDocument();
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Delete rule 1/i })).toBeInTheDocument();

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
