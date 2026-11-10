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
        verification: { status: 'verified', effect: 'committed' },
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
        verification: { status: 'verified', effect: 'committed' },
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
