/**
 * Creation POST retry safety — real shared interceptor + adapter counter.
 *
 * This exercises lib/api.ts's real response interceptor (no axios mock):
 * a lost/503 creation confirmation must not be auto-POSTed again, because the
 * first request may have committed. The adapter counts actual POST attempts.
 */
import apiClient from '../api';
import {
  createCustomAgent,
  createGuidedAgent,
} from '../agent-onboarding-api';

jest.setTimeout(20000);

type Adapter = (config: any) => Promise<any>;

const originalAdapter = (apiClient.defaults as any).adapter as Adapter;

function reject503(config: any) {
  const error: any = new Error('Request failed with status code 503');
  error.isAxiosError = true;
  error.config = config;
  error.response = {
    status: 503,
    statusText: 'Service Unavailable',
    data: { detail: 'temporarily unavailable' },
    headers: {},
    config,
  };
  return error;
}

describe('creation POST retry safety', () => {
  let errorSpy: jest.SpyInstance;
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    (apiClient.defaults as any).adapter = originalAdapter;
    errorSpy.mockRestore();
    logSpy.mockRestore();
  });

  it('does not auto-retry a guided creation after a 503 confirmation loss', async () => {
    let posts = 0;
    let seen: any = null;
    (apiClient.defaults as any).adapter = async (config: any) => {
      if (
        String(config.method || '').toLowerCase() === 'post' &&
        String(config.url || '').includes('/api/agents/guided')
      ) {
        posts += 1;
        seen = config;
      }
      throw reject503(config);
    };

    await expect(
      createGuidedAgent(
        'watch invoices and flag overdue ones',
        undefined,
        { operationId: 'guided-intent-1' }
      )
    ).rejects.toBeTruthy();

    expect(posts).toBe(1);
    expect(seen?.params?.operation_id).toBe('guided-intent-1');
    expect(seen?.retry).toBe(false);
  });

  it('does not auto-retry a custom hire after a 503 confirmation loss', async () => {
    let posts = 0;
    let seen: any = null;
    (apiClient.defaults as any).adapter = async (config: any) => {
      if (
        String(config.method || '').toLowerCase() === 'post' &&
        String(config.url || '').includes('/api/agents/custom')
      ) {
        posts += 1;
        seen = config;
      }
      throw reject503(config);
    };

    await expect(
      createCustomAgent(
        {
          name: 'Sales Development Rep',
          description: 'Hire for sales',
          category: 'Sales',
          configuration: {},
          schedule_config: {},
        },
        { operationId: 'hire-intent-1' }
      )
    ).rejects.toBeTruthy();

    expect(posts).toBe(1);
    expect(seen?.params?.operation_id).toBe('hire-intent-1');
    expect(seen?.retry).toBe(false);
  });
});

describe('creation response integrity', () => {
  afterEach(() => {
    (apiClient.defaults as any).adapter = originalAdapter;
  });

  function respond(payload: any, status = 200) {
    (apiClient.defaults as any).adapter = async (config: any) => ({
      data: payload,
      status,
      statusText: 'OK',
      headers: {},
      config,
    });
  }

  it('returns a guided verified result and preserves the receipt', async () => {
    respond({
      success: true,
      data: {
        agent_id: 'agent-verified',
        name: 'Verified Agent',
        category: 'Operations',
        maturity: 'student',
        created_by: 'employee',
        operation_id: 'agent:create:intent-1',
        audit_id: 'agent:create:intent-1',
        verification: { status: 'verified', effect: 'committed', audit_id: 'agent:create:intent-1' },
      },
    });
    const result = await createGuidedAgent(
      'watch invoices and flag overdue ones', undefined,
      { operationId: 'intent-1' }
    );
    expect('agent_id' in result && result.agent_id).toBe('agent-verified');
    expect('operation_id' in result && result.operation_id).toBe(
      'agent:create:intent-1'
    );
    expect('verification' in result && result.verification?.status).toBe(
      'verified'
    );
  });

  it('returns guided pending without inventing an agent id', async () => {
    respond({
      success: true,
      data: {
        status: 'pending_approval',
        hitl_action_id: 'hitl-1',
        reason: 'Trust policy requires human approval',
      },
    }, 202);
    const result = await createGuidedAgent(
      'watch invoices and flag overdue ones'
    );
    expect('status' in result && result.status).toBe('pending_approval');
    expect('agent_id' in result).toBe(false);
  });

  it('rejects a 2xx success:false instead of treating it as verified', async () => {
    respond({ success: false, data: { agent_id: 'agent-false' } });
    await expect(
      createGuidedAgent('watch invoices and flag overdue ones')
    ).rejects.toMatchObject({ code: 'CREATION_NOT_ACCEPTED' });
  });

  it('rejects a 2xx guided response with no exact agent id', async () => {
    respond({
      success: true,
      data: { verification: { status: 'verified', effect: 'committed' } },
    });
    await expect(
      createGuidedAgent('watch invoices and flag overdue ones')
    ).rejects.toMatchObject({ code: 'UNVERIFIED_CREATE' });
  });

  it('rejects a 2xx guided response without verified verification', async () => {
    respond({
      success: true,
      data: {
        agent_id: 'agent-unverified',
        name: 'Maybe',
        category: 'Ops',
        maturity: 'student',
        created_by: 'employee',
        verification: { status: 'committed_unverified', effect: 'committed' },
      },
    });
    await expect(
      createGuidedAgent('watch invoices and flag overdue ones')
    ).rejects.toMatchObject({ code: 'UNVERIFIED_CREATE' });
  });

  it('returns a custom verified result and rejects malformed/unverified 2xx', async () => {
    respond({
      success: true,
      data: {
        agent_id: 'custom-verified',
        agent_name: 'Custom Verified',
        category: 'Sales',
        operation_id: 'agent:create:hire-1',
        audit_id: 'agent:create:hire-1',
        verification: { status: 'verified', effect: 'committed', audit_id: 'agent:create:hire-1' },
      },
    });
    const ok = await createCustomAgent(
      {
        name: 'Custom Verified', category: 'Sales',
        configuration: {}, schedule_config: {},
      },
      { operationId: 'hire-1' }
    );
    expect(ok.agent_id).toBe('custom-verified');

    respond({ success: false, data: { agent_id: 'ignored' } });
    await expect(createCustomAgent({
      name: 'No', category: 'Sales', configuration: {}, schedule_config: {},
    })).rejects.toMatchObject({ code: 'CREATION_NOT_ACCEPTED' });

    respond({
      success: true,
      data: { agent_id: 'custom-unverified' },
    });
    await expect(createCustomAgent({
      name: 'No', category: 'Sales', configuration: {}, schedule_config: {},
    })).rejects.toMatchObject({ code: 'UNVERIFIED_CREATE' });
  });
});

describe('creation receipt binding', () => {
  afterEach(() => {
    (apiClient.defaults as any).adapter = originalAdapter;
  });

  function respond(data: any, status = 200) {
    (apiClient.defaults as any).adapter = async (config: any) => ({
      data: { success: true, data },
      status,
      statusText: 'OK',
      headers: {},
      config,
    });
  }

  const guidedPayload = {
    goal: 'watch invoices and flag overdue ones',
  };
  const customPayload = {
    name: 'Receipt Binding Hire',
    description: 'Controlled receipt-binding twin',
    category: 'Operations',
    configuration: {},
    schedule_config: {},
  };

  function guidedData(receipt: any = {}) {
    return {
      agent_id: 'agent-receipt-guided',
      name: 'Receipt Guided',
      category: 'Operations',
      maturity: 'student',
      created_by: 'employee',
      ...receipt,
    };
  }

  function customData(receipt: any = {}) {
    return {
      agent_id: 'agent-receipt-custom',
      agent_name: 'Receipt Custom',
      category: 'Operations',
      ...receipt,
    };
  }

  const intent = 'intent-receipt-1';
  const expected = `agent:create:${intent}`;
  const exactReceipt = {
    operation_id: expected,
    audit_id: expected,
    verification: {
      status: 'verified',
      effect: 'committed',
      audit_id: expected,
    },
  };

  const invalidReceipts: Array<[string, any]> = [
    ['wrong operation identity', {
      operation_id: 'agent:create:other-intent',
      audit_id: 'agent:create:other-intent',
      verification: {
        status: 'verified', effect: 'committed',
        audit_id: 'agent:create:other-intent',
      },
    }],
    ['missing operation and audit', {
      verification: {
        status: 'verified', effect: 'committed', audit_id: expected,
      },
    }],
    ['operation/audit disagreement', {
      operation_id: expected,
      audit_id: 'agent:create:other-audit',
      verification: {
        status: 'verified', effect: 'committed', audit_id: expected,
      },
    }],
    ['missing verification audit', {
      operation_id: expected,
      audit_id: expected,
      verification: {
        status: 'verified', effect: 'committed',
      },
    }],
    ['verification audit disagreement', {
      operation_id: expected,
      audit_id: expected,
      verification: {
        status: 'verified', effect: 'committed',
        audit_id: 'agent:create:other-audit',
      },
    }],
    ['contradictory effect', {
      operation_id: expected,
      audit_id: expected,
      verification: {
        status: 'verified', effect: 'none', audit_id: expected,
      },
    }],
  ];

  it.each(invalidReceipts)(
    'rejects guided %s instead of treating it as created',
    async (_label, receipt) => {
      respond(guidedData(receipt));
      await expect(
        createGuidedAgent(guidedPayload.goal, undefined, { operationId: intent })
      ).rejects.toMatchObject({ code: 'UNVERIFIED_CREATE' });
    }
  );

  it.each(invalidReceipts)(
    'rejects custom %s instead of treating it as hired',
    async (_label, receipt) => {
      respond(customData(receipt));
      await expect(
        createCustomAgent(customPayload, { operationId: intent })
      ).rejects.toMatchObject({ code: 'UNVERIFIED_CREATE' });
    }
  );

  it('accepts a guided verified twin with the exact submitted receipt', async () => {
    respond(guidedData(exactReceipt));
    const result = await createGuidedAgent(
      guidedPayload.goal, undefined, { operationId: intent }
    );
    expect('agent_id' in result && result.agent_id).toBe('agent-receipt-guided');
  });

  it('accepts a custom already_applied twin with committed effect', async () => {
    respond(customData({
      ...exactReceipt,
      verification: {
        status: 'already_applied',
        effect: 'committed',
        audit_id: expected,
        replay: 'do_not_repeat',
      },
    }));
    const result = await createCustomAgent(customPayload, { operationId: intent });
    expect(result.agent_id).toBe('agent-receipt-custom');
  });

  it('binds an internally generated operation id when the caller supplies none', async () => {
    let seenQuery = '';
    (apiClient.defaults as any).adapter = async (config: any) => {
      seenQuery = String(config.params?.operation_id || '');
      return {
        data: {
          success: true,
          data: customData({
            operation_id: `agent:create:${seenQuery}`,
            audit_id: `agent:create:${seenQuery}`,
            verification: {
              status: 'verified', effect: 'committed',
              audit_id: `agent:create:${seenQuery}`,
            },
          }),
        },
        status: 201,
        statusText: 'Created',
        headers: {},
        config,
      };
    };
    const result = await createCustomAgent(customPayload);
    expect(seenQuery).toMatch(/.+/);
    expect(result.agent_id).toBe('agent-receipt-custom');
  });

  it('rejects a wrong-operation receipt through the real interceptor with one POST', async () => {
    let posts = 0;
    (apiClient.defaults as any).adapter = async (config: any) => {
      posts += 1;
      return {
        data: {
          success: true,
          data: guidedData({
            operation_id: 'agent:create:other-intent',
            audit_id: 'agent:create:other-intent',
            verification: {
              status: 'verified', effect: 'committed',
              audit_id: 'agent:create:other-intent',
            },
          }),
        },
        status: 201,
        statusText: 'Created',
        headers: {},
        config,
      };
    };
    await expect(
      createGuidedAgent(guidedPayload.goal, undefined, { operationId: intent })
    ).rejects.toMatchObject({ code: 'UNVERIFIED_CREATE' });
    expect(posts).toBe(1);
  });

  it('rejects a contradictory-effect hire through the real interceptor with one POST', async () => {
    let posts = 0;
    (apiClient.defaults as any).adapter = async (config: any) => {
      posts += 1;
      return {
        data: {
          success: true,
          data: customData({
            ...exactReceipt,
            verification: {
              status: 'verified', effect: 'none', audit_id: expected,
            },
          }),
        },
        status: 201,
        statusText: 'Created',
        headers: {},
        config,
      };
    };
    await expect(
      createCustomAgent(customPayload, { operationId: intent })
    ).rejects.toMatchObject({ code: 'UNVERIFIED_CREATE' });
    expect(posts).toBe(1);
  });
});
