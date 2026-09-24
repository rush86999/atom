import {
  buildActionProposalPreview,
  redactActionProposalValue,
} from '../action-proposal-preview';

describe('action proposal preview', () => {
  test('keeps review evidence while recursively redacting credentials', () => {
    const proposal = {
      id: 'p1',
      agent_id: 'agent-1',
      agent_name: 'Sales Agent',
      title: 'Review lead',
      description: null,
      proposal_type: 'action',
      status: 'pending_approval',
      proposed_action: {
        action_type: 'agent_execute',
        prompt: 'Classify the incoming lead',
        parameters: {
          source: 'inbox',
          password: 'do-not-show',
          nested: { api_token: 'token-do-not-show' },
        },
        source_content: 'Customer replied: please follow up',
      },
      reasoning: null,
      reversible: null,
      created_at: null,
      approved_by: null,
      approved_at: null,
      tenant_id: null,
    } as any;

    const preview = buildActionProposalPreview(proposal);

    expect(preview.targetAgent).toBe('Sales Agent');
    expect(preview.actionType).toBe('agent_execute');
    expect(preview.prompt).toContain('Classify the incoming lead');
    expect(preview.parameters).toContain('inbox');
    expect(preview.sourceContent).toContain('Customer replied');
    expect(preview.payloadText).toContain('[REDACTED]');
    expect(preview.payloadText).not.toContain('do-not-show');
  });

  test('bounds large payload text and handles circular values', () => {
    const value: any = { prompt: 'x'.repeat(2_000) };
    value.self = value;
    value.password = 'hidden';

    const redacted = redactActionProposalValue(value) as any;
    const text = JSON.stringify(redacted);

    expect(redacted.password).toBe('[REDACTED]');
    expect(redacted.self).toBe('[CIRCULAR]');
    expect(text.length).toBeLessThan(4_000);
  });
});
