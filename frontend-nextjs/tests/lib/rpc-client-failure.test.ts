/**
 * rpc-client failure contract (lib/rpc-client.ts)
 *
 * The RPC route propagates an in-handler `success: false` to the outer
 * envelope. The shared client must:
 * - still throw on that outer failure;
 * - preserve the handler's typed result additively as `actionResult`
 *   (operation/audit metadata stays recoverable);
 * - NOT promote `body.data.error` into the global user-facing message;
 * - keep HTTP/network failures generic and out of `actionResult`.
 */
import { rpc } from '@/lib/rpc-client';

const mockPost = jest.fn();
const mockGet = jest.fn();

jest.mock('@/lib/api', () => ({
  apiClient: {
    post: (...args: unknown[]) => mockPost(...args),
    get: (...args: unknown[]) => mockGet(...args),
  },
}));

const axiosError = (overrides: Record<string, unknown>) => {
  const err: any = new Error('Request failed with status code 500');
  Object.assign(err, overrides);
  return err;
};

describe('rpc.call failure consumers', () => {
  beforeEach(() => {
    mockPost.mockReset();
    mockGet.mockReset();
  });

  it('returns data unchanged on a successful outer envelope', async () => {
    mockPost.mockResolvedValue({
      data: { success: true, data: { success: true, version: 2 } },
    });

    await expect(rpc.call('mini_app_publish', { app_id: 'app-1' })).resolves.toEqual({
      success: true,
      version: 2,
    });
  });

  it('preserves a semantic handler failure as actionResult without promoting its error', async () => {
    const handlerFailure = {
      success: false,
      error: 'SyntaxError: invalid syntax (<unknown>, line 1)',
      operation_id: 'op-42',
      audit_id: 'audit-7',
    };
    mockPost.mockResolvedValue({
      data: {
        success: false,
        action: 'mini_app_write_logic',
        data: handlerFailure,
      },
    });

    const err = (await rpc
      .call('mini_app_write_logic', { app_id: 'app-1' })
      .catch((e: Error): Error => e)) as any;

    // Still an error, still generic at the global message boundary.
    expect(err.message).toBe("Action 'mini_app_write_logic' failed");
    expect(err.message).not.toContain('SyntaxError');
    expect(err.action).toBe('mini_app_write_logic');
    expect(err.status).toBeUndefined();
    // The handler's own typed result (and its operation/audit metadata) is
    // recoverable by a caller that understands the action schema.
    expect(err.actionResult).toEqual(handlerFailure);
    expect(err.actionResult.operation_id).toBe('op-42');
    expect(err.actionResult.audit_id).toBe('audit-7');
  });

  it('keeps HTTP failure data out of the global message and actionResult', async () => {
    mockPost.mockRejectedValue(
      axiosError({
        response: {
          status: 500,
          data: {
            success: false,
            error: 'internal-store-path-/private/detail',
            error_code: 'INTERNAL',
          },
        },
      })
    );

    const err = (await rpc
      .call('documents.search', {})
      .catch((e: Error): Error => e)) as any;

    expect(err.message).toBe('RPC call failed');
    expect(err.message).not.toContain('internal-store-path');
    expect(err.status).toBe(500);
    // Raw HTTP body stays only in `details`; it is never a semantic
    // actionResult and never user-facing business text.
    expect(err.actionResult).toBeUndefined();
    expect(err.details).toEqual({
      success: false,
      error: 'internal-store-path-/private/detail',
      error_code: 'INTERNAL',
    });
  });

  it('does not manufacture an actionResult for network failures', async () => {
    mockPost.mockRejectedValue(axiosError({}));

    const err = (await rpc
      .call('documents.search', {})
      .catch((e: Error): Error => e)) as any;

    expect(err.message).toBe('RPC call failed');
    expect(err.actionResult).toBeUndefined();
  });
});
