/**
 * rpc-client tests (lib/rpc-client.ts)
 *
 * Verifies the typed RPC client contract:
 * - success passthrough (data returned)
 * - backend { success: false } bodies become errors with message + details
 * - HTTP failures are mapped to RpcError with status + backend detail
 * - 404/401/403 get user-friendly messages
 * - other failures do NOT leak axios internals ("Request failed with status
 *   code 500", "timeout of 10000ms exceeded", "Network Error") — the
 *   toRpcError docstring promises a generic message; raw axios text exposes
 *   client configuration (timeouts) and implementation details to UI
 * - listActions degrades to [] when the registry is unreachable
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

describe('rpc.call', () => {
  beforeEach(() => {
    mockPost.mockReset();
    mockGet.mockReset();
  });

  it('returns data on success', async () => {
    mockPost.mockResolvedValue({
      data: { success: true, data: { docs: [1, 2] } },
    });

    await expect(rpc.call('documents.search', { query: 'q' })).resolves.toEqual(
      { docs: [1, 2] }
    );
    expect(mockPost).toHaveBeenCalledWith('/api/rpc/documents.search', {
      params: { query: 'q' },
    });
  });

  it('throws a message-carrying RpcError when the backend body says success:false', async () => {
    mockPost.mockResolvedValue({
      data: {
        success: false,
        message: 'Parameter validation failed',
        details: { field: 'limit' },
      },
    });

    await expect(rpc.call('documents.search', {})).rejects.toMatchObject({
      message: 'Parameter validation failed',
      details: { field: 'limit' },
    });
  });

  it('maps 404 to a friendly message', async () => {
    mockPost.mockRejectedValue(
      axiosError({ response: { status: 404, data: {} } })
    );

    await expect(rpc.call('ghost.action', {})).rejects.toMatchObject({
      message: "Action 'ghost.action' is not available",
      status: 404,
    });
  });

  it('maps 401 to a friendly message', async () => {
    mockPost.mockRejectedValue(
      axiosError({ response: { status: 401, data: {} } })
    );

    await expect(rpc.call('documents.search', {})).rejects.toMatchObject({
      message: 'Authentication required',
      status: 401,
    });
  });

  it('maps 403 to a friendly message', async () => {
    mockPost.mockRejectedValue(
      axiosError({ response: { status: 403, data: {} } })
    );

    await expect(rpc.call('documents.search', {})).rejects.toMatchObject({
      message: 'Not permitted to perform this action',
      status: 403,
    });
  });

  it('does not leak axios internals for other HTTP failures', async () => {
    mockPost.mockRejectedValue(
      axiosError({
        response: { status: 500, data: { error_code: 'INTERNAL' } },
      })
    );

    const err = await rpc
      .call('documents.search', {})
      .catch((e: Error): Error => e) as Error;

    expect(err.message).toBe('RPC call failed');
    expect((err as any).status).toBe(500);
    expect((err as any).details).toEqual({ error_code: 'INTERNAL' });
    expect(err.message).not.toContain('Request failed with status code');
  });

  it('does not leak network/timeout internals when there is no response', async () => {
    mockPost.mockRejectedValue(axiosError({}));

    const err = await rpc
      .call('documents.search', {})
      .catch((e: Error): Error => e) as Error;

    expect(err.message).toBe('RPC call failed');
    expect((err as any).status).toBeUndefined();
  });

  it('preserves RpcErrors already shaped by the backend body', async () => {
    const shaped: any = new Error('already shaped');
    shaped.action = 'documents.search';
    mockPost.mockRejectedValue(shaped);

    await expect(rpc.call('documents.search', {})).rejects.toBe(shaped);
  });
});

describe('rpc.listActions', () => {
  it('returns the action list on success', async () => {
    mockGet.mockResolvedValue({
      data: { success: true, data: [{ name: 'documents.search' }] },
    });

    await expect(rpc.listActions()).resolves.toEqual([
      { name: 'documents.search' },
    ]);
  });

  it('degrades to [] when the registry is unreachable', async () => {
    mockGet.mockRejectedValue(axiosError({}));

    await expect(rpc.listActions()).resolves.toEqual([]);
  });
});
