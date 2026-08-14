/**
 * lib/backendAuth tests — loginWithBackend error mapping and
 * persistBackendToken storage behavior.
 */

import { loginWithBackend, persistBackendToken } from '../backendAuth';

const mockFetch = jest.fn();

describe('lib/backendAuth', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
  });

  const jsonResponse = (ok: boolean, data: any, status = ok ? 200 : 401) => ({
    ok,
    status,
    json: async () => data,
  });

  it('logs in and returns the response with access_token', async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, { access_token: 'at-1', token_type: 'bearer' }));
    const result = await loginWithBackend('a@b.c', 'pw');
    expect(result.access_token).toBe('at-1');
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/auth/login',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ username: 'a@b.c', password: 'pw' }),
      },
    );
  });

  it('includes the totp code when provided', async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, { access_token: 'at' }));
    await loginWithBackend('a@b.c', 'pw', '123456');
    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.totp_code).toBe('123456');
  });

  it('maps network failures to a friendly message', async () => {
    mockFetch.mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(loginWithBackend('a@b.c', 'pw')).rejects.toThrow(
      'Unable to connect to the server. Please check your internet connection and try again.',
    );
  });

  it('throws the backend detail on failed login', async () => {
    mockFetch.mockResolvedValue(jsonResponse(false, { detail: 'Invalid email or password' }));
    await expect(loginWithBackend('a@b.c', 'wrong')).rejects.toThrow('Invalid email or password');
  });

  it('throws a generic message when the failed login has no detail', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 401, json: async () => ({}) });
    await expect(loginWithBackend('a@b.c', 'wrong')).rejects.toThrow('Invalid email or password');
  });

  it('tolerates a non-JSON error response', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => { throw new Error('not json'); },
    });
    await expect(loginWithBackend('a@b.c', 'pw')).rejects.toThrow('Invalid email or password');
  });

  it('returns the response when 2FA is required', async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(true, { two_factor_required: true, access_token: undefined }),
    );
    const result = await loginWithBackend('a@b.c', 'pw');
    expect(result.two_factor_required).toBe(true);
  });

  it('throws when the response lacks an access token', async () => {
    mockFetch.mockResolvedValue(jsonResponse(true, {}));
    await expect(loginWithBackend('a@b.c', 'pw')).rejects.toThrow(
      'Login response did not include an access token',
    );
  });
});

describe('lib/backendAuth persistBackendToken', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.localStorage.clear();
    document.cookie = 'auth_token=; path=/; max-age=0';
    document.cookie = 'next-auth.session-token=; path=/; max-age=0';
  });

  it('persists the token to localStorage and cookies in the browser', () => {
    persistBackendToken('tok-1');
    expect(global.localStorage.getItem('auth_token')).toBe('tok-1');
    expect(global.localStorage.getItem('token')).toBe('tok-1');
    expect(global.localStorage.getItem('atom_explicit_logout')).toBeNull();
    expect(document.cookie).toContain('auth_token=tok-1');
    expect(document.cookie).toContain('next-auth.session-token=tok-1');
  });
});
