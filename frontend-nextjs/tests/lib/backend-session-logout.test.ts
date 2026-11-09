jest.mock('next-auth', () => ({ __esModule: true, default: jest.fn() }));
jest.mock('@/lib/db', () => ({ query: jest.fn() }));
jest.mock('@/lib/api', () => ({ USE_BACKEND_API: true, adminAPI: {}, tenantAPI: {} }));

import { createBackendSignOutEvent } from '@/lib/backend-session-logout';
import { authOptions as normalOptions } from '@/pages/api/auth/[...nextauth]';
import { authOptions as sharedOptions } from '@/lib/auth';

const backendToken = 'synthetic-session-only';
const response = (body: unknown, ok = true, status = 200) => ({ ok, status, json: async () => body });

describe('backend termination on ordinary NextAuth sign-out', () => {
  let warn: jest.SpyInstance;
  let originalFetch: typeof fetch;
  const originalBase = process.env.NEXT_PUBLIC_API_URL;
  beforeEach(() => {
    originalFetch = global.fetch;
    global.fetch = jest.fn().mockResolvedValue(response({ success: true, verification: { status: 'verified' } }));
    warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
    process.env.NEXT_PUBLIC_API_URL = 'http://configured-backend.invalid';
  });
  afterEach(() => {
    global.fetch = originalFetch;
    warn.mockRestore();
    jest.useRealTimers();
    if (originalBase === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = originalBase;
  });

  it('sends exactly the server-owned backend token to its configured issuer', async () => {
    await createBackendSignOutEvent(() => 'http://owned-backend.invalid/')({ token: { backendToken } });
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith('http://owned-backend.invalid/api/auth/logout', expect.objectContaining({
      method: 'POST', headers: { Authorization: `Bearer ${backendToken}`, Accept: 'application/json' }, signal: expect.objectContaining({ aborted: false, addEventListener: expect.any(Function) }),
    }));
    expect(warn).not.toHaveBeenCalled();
  });

  it.each([normalOptions, sharedOptions])('wires an existing auth configuration through the shared consumer', async (options) => {
    await options.events!.signOut!({ token: { backendToken } });
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith('http://configured-backend.invalid/api/auth/logout', expect.objectContaining({ method: 'POST' }));
  });

  it.each([{}, { token: null }, { token: {} }, { session: {} }])('does not invent a backend identity from %j', async (message) => {
    await createBackendSignOutEvent(() => 'http://owned-backend.invalid')(message);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it.each([
    { success: true },
    { success: true, verification: { status: 'unavailable' } },
    { success: false, verification: { status: 'verified' } },
  ])('does not credit parsing or unverified completion as server sign-out', async (body) => {
    (global.fetch as jest.Mock).mockResolvedValue(response(body));
    await expect(createBackendSignOutEvent(() => 'http://owned-backend.invalid')({ token: { backendToken } })).resolves.toBeUndefined();
    expect(warn).toHaveBeenCalledWith('Server sign-out could not be confirmed.', { code: 'server_logout_unverified', status: 200 });
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(warn.mock.calls)).not.toContain(backendToken);
  });

  it('keeps local sign-out possible on a backend refusal without retry', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(response({ detail: backendToken }, false, 503));
    await expect(createBackendSignOutEvent(() => 'http://owned-backend.invalid')({ token: { backendToken } })).resolves.toBeUndefined();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(warn.mock.calls)).not.toContain(backendToken);
  });

  it('does not expose exception text containing credential material', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error(backendToken));
    await expect(createBackendSignOutEvent(() => 'http://owned-backend.invalid')({ token: { backendToken } })).resolves.toBeUndefined();
    expect(warn).toHaveBeenCalledWith('Server sign-out could not be confirmed.', { code: 'server_logout_unavailable' });
    expect(JSON.stringify(warn.mock.calls)).not.toContain(backendToken);
  });

  it('bounds the event await and leaves no timer or automatic retry', async () => {
    jest.useFakeTimers();
    (global.fetch as jest.Mock).mockImplementation((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(new Error(backendToken)));
    }));
    const pending = createBackendSignOutEvent(() => 'http://owned-backend.invalid')({ token: { backendToken } });
    jest.advanceTimersByTime(5000);
    await expect(pending).resolves.toBeUndefined();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect((global.fetch as jest.Mock).mock.calls[0][1].signal.aborted).toBe(true);
    expect(jest.getTimerCount()).toBe(0);
    expect(JSON.stringify(warn.mock.calls)).not.toContain(backendToken);
  });
});
