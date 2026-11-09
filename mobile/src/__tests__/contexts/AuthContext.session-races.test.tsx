/** Controlled HTTP timing through the real provider and shared token helper. */
import React from 'react';
import { AxiosError, AxiosAdapter } from 'axios';
import { apiService } from '../../services/api';
import { Text } from 'react-native';
import { render, act, waitFor } from '@testing-library/react-native';
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AuthProvider, useAuth } from '../../contexts/AuthContext';
import { secureSet, secureGet, readAccessTokenSnapshot, invalidateAccessToken } from '../../storage/secureTokenStorage';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(), setItemAsync: jest.fn(), deleteItemAsync: jest.fn(),
  WHEN_UNLOCKED: 'WHEN_UNLOCKED',
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}
const response = (token: string) => ({ ok: true, json: async () => ({
  access_token: token, refresh_token: `${token}-refresh`,
  expires_at: new Date(Date.now() + 3600000).toISOString(),
  user: { id: 'controlled-user', email: 'controlled@example.test' },
}) });

describe('AuthContext delayed session responses', () => {
  const store = new Map<string, string>();
  let auth: ReturnType<typeof useAuth>;
  const credentials = { email: 'controlled@example.test', password: 'controlled-test-only' };
  const Capture = () => {
    auth = useAuth();
    return <Text testID="authenticated">{String(auth.isAuthenticated)}</Text>;
  };
  beforeEach(() => {
    jest.clearAllMocks();
    store.clear();
    (SecureStore.getItemAsync as jest.Mock).mockImplementation(async key => store.get(key) ?? null);
    (SecureStore.setItemAsync as jest.Mock).mockImplementation(async (key, value) => { store.set(key, value); });
    (SecureStore.deleteItemAsync as jest.Mock).mockImplementation(async key => { store.delete(key); });
    (AsyncStorage.getItem as jest.Mock).mockImplementation(async key => store.get(key) ?? null);
    (AsyncStorage.setItem as jest.Mock).mockImplementation(async (key, value) => { store.set(key, value); });
    (AsyncStorage.removeItem as jest.Mock).mockImplementation(async key => { store.delete(key); });
    global.fetch = jest.fn().mockResolvedValue(response('ordinary'));
  });
  const mount = async () => {
    render(<AuthProvider><Capture /></AuthProvider>);
    await waitFor(() => expect(auth.isLoading).toBe(false));
  };
  const seed = async () => {
    await secureSet('atom_access_token', 'original');
    store.set('atom_refresh_token', 'original-refresh');
    store.set('atom_token_expiry', String(Date.now() + 3600000));
    store.set('atom_user_data', JSON.stringify({ id: 'controlled-user' }));
  };

  test('late login cannot reauthenticate after owner logout', async () => {
    await mount();
    const delayed = deferred<ReturnType<typeof response>>();
    (global.fetch as jest.Mock).mockReturnValueOnce(delayed.promise);
    let login!: ReturnType<typeof auth.login>;
    act(() => { login = auth.login(credentials); });
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    await act(async () => { await auth.logout(); });
    await act(async () => { delayed.resolve(response('late-login')); await login; });
    expect(auth.isAuthenticated).toBe(false);
    expect(store.has('atom_access_token')).toBe(false);
    expect(store.has('atom_user_data')).toBe(false);
  });

  test('late refresh cannot restore credentials after owner logout', async () => {
    await seed();
    await mount();
    expect(auth.isAuthenticated).toBe(true);
    const delayed = deferred<ReturnType<typeof response>>();
    (global.fetch as jest.Mock).mockReturnValueOnce(delayed.promise);
    let refresh!: Promise<boolean>;
    act(() => { refresh = auth.refreshToken(); });
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    await act(async () => { await auth.logout(); });
    let refreshed: boolean | undefined;
    await act(async () => { delayed.resolve(response('late-refresh')); refreshed = await refresh; });
    expect(refreshed).toBe(false);
    expect(store.has('atom_access_token')).toBe(false);
    expect(auth.isAuthenticated).toBe(false);
  });

  test('logout clears local authority while its backend response is still pending', async () => {
    await seed();
    await mount();
    expect(auth.isAuthenticated).toBe(true);
    const delayed = deferred<ReturnType<typeof response>>();
    (global.fetch as jest.Mock).mockReturnValueOnce(delayed.promise);
    let logout!: Promise<void>;
    act(() => { logout = auth.logout(); });
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    try {
      expect(store.has('atom_access_token')).toBe(false);
      expect(auth.isAuthenticated).toBe(false);
    } finally {
      await act(async () => { delayed.resolve(response('logout')); await logout; });
    }
  });
  test('a delayed refresh cannot replace a newer successful login', async () => {
    await seed();
    await mount();
    expect(auth.isAuthenticated).toBe(true);
    const delayed = deferred<ReturnType<typeof response>>();
    (global.fetch as jest.Mock).mockReturnValueOnce(delayed.promise);
    let refresh!: Promise<boolean>;
    act(() => { refresh = auth.refreshToken(); });
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    (global.fetch as jest.Mock).mockResolvedValueOnce(response('new-login'));
    await act(async () => { expect((await auth.login(credentials)).success).toBe(true); });
    let refreshed: boolean | undefined;
    await act(async () => { delayed.resolve(response('old-refresh')); refreshed = await refresh; });
    expect(refreshed).toBe(false);
    expect(store.get('atom_access_token')).toBe('new-login');
    expect(store.get('atom_refresh_token')).toBe('new-login-refresh');
    expect(auth.isAuthenticated).toBe(true);
  });

  test('login stores the authoritative server expiry rather than inventing a day', async () => {
    await mount();
    const expiry = new Date(Date.now() + 900000).toISOString();
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => ({
      access_token: 'short-session', refresh_token: 'short-refresh', expires_at: expiry,
      user: { id: 'controlled-user' },
    }) });
    await act(async () => { expect((await auth.login(credentials)).success).toBe(true); });
    expect(store.get('atom_token_expiry')).toBe(String(Date.parse(expiry)));
  });

  test('refresh uses the mobile device-bound endpoint and its server expiry', async () => {
    await seed();
    await mount();
    const expiry = new Date(Date.now() + 1200000).toISOString();
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => ({
      access_token: 'refreshed', refresh_token: 'rotated', expires_at: expiry,
    }) });
    await act(async () => { expect(await auth.refreshToken()).toBe(true); });
    expect(global.fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/auth\/mobile\/refresh$/),
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ refresh_token: 'original-refresh' }) }));
    expect(store.get('atom_token_expiry')).toBe(String(Date.parse(expiry)));
  });

  test('concurrent refresh callers share one dispatched request and result', async () => {
    await seed();
    await mount();
    const delayed = deferred<ReturnType<typeof response>>();
    (global.fetch as jest.Mock).mockReturnValue(delayed.promise);
    let first!: Promise<boolean>;
    let second!: Promise<boolean>;
    act(() => { first = auth.refreshToken(); second = auth.refreshToken(); });
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    let results: boolean[] = [];
    await act(async () => { delayed.resolve(response('one-refresh')); results = await Promise.all([first, second]); });
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(results).toEqual([true, true]);
  });

  test.each([undefined, '', 'not-a-date', '2020-01-01T00:00:00Z'])(
    'login refuses missing or invalid server expiry %s without storing credentials', async expiry => {
      await mount();
      (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => ({
        access_token: 'invalid-expiry-token', refresh_token: 'invalid-refresh', expires_at: expiry,
      }) });
      await act(async () => { expect((await auth.login(credentials)).success).toBe(false); });
      expect(store.has('atom_access_token')).toBe(false);
      expect(auth.isAuthenticated).toBe(false);
    });

  test('current-session invalidation removes the mounted authenticated UI state', async () => {
    await seed();
    await mount();
    expect(auth.isAuthenticated).toBe(true);
    const current = await readAccessTokenSnapshot();
    await act(async () => { expect(await invalidateAccessToken(current)).toBe(true); });
    expect(store.has('atom_access_token')).toBe(false);
    expect(auth.isAuthenticated).toBe(false);
    expect(auth.user).toBeNull();
  });

  test('a delayed startup profile cannot restore authentication after logout', async () => {
    await seed();
    const delayed = deferred<string | null>();
    (AsyncStorage.getItem as jest.Mock).mockImplementation(async key =>
      key === 'atom_user_data' ? delayed.promise : store.get(key) ?? null);
    render(<AuthProvider><Capture /></AuthProvider>);
    await waitFor(() => expect(AsyncStorage.getItem).toHaveBeenCalledWith('atom_user_data'));
    await act(async () => { await auth.logout(); });
    await act(async () => { delayed.resolve(JSON.stringify({ id: 'controlled-user' })); });
    await waitFor(() => expect(auth.isLoading).toBe(false));
    expect(store.has('atom_access_token')).toBe(false);
    expect(auth.isAuthenticated).toBe(false);
    expect(auth.user).toBeNull();
  });

  test('real Axios unauthorized response clears mounted provider identity', async () => {
    await seed();
    await mount();
    expect(auth.isAuthenticated).toBe(true);
    const adapter: AxiosAdapter = async config => {
      throw new AxiosError('controlled unauthorized', 'ERR_BAD_REQUEST', config, undefined,
        { config, status: 401, statusText: 'Unauthorized', headers: {}, data: {} });
    };
    await act(async () => { expect((await apiService.get('/controlled', { adapter })).success).toBe(false); });
    expect(auth.isAuthenticated).toBe(false);
    expect(auth.user).toBeNull();
    expect(store.has('atom_access_token')).toBe(false);
  });

  test('expired startup session becomes authenticated after a valid mobile refresh', async () => {
    await seed();
    store.set('atom_token_expiry', String(Date.now() - 1000));
    await mount();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(store.get('atom_access_token')).toBe('ordinary');
    expect(auth.isAuthenticated).toBe(true);
    expect(auth.user).toEqual({ id: 'controlled-user' });
  });

  test('a stale malformed startup profile cannot clear a newer successful login', async () => {
    await seed();
    const delayed = deferred<string | null>();
    let startupRead = true;
    (AsyncStorage.getItem as jest.Mock).mockImplementation(async key => {
      if (key === 'atom_user_data' && startupRead) { startupRead = false; return delayed.promise; }
      return store.get(key) ?? null;
    });
    render(<AuthProvider><Capture /></AuthProvider>);
    await waitFor(() => expect(AsyncStorage.getItem).toHaveBeenCalledWith('atom_user_data'));
    await act(async () => { expect((await auth.login(credentials)).success).toBe(true); });
    await act(async () => { delayed.resolve('{not-json'); });
    await waitFor(() => expect(auth.isLoading).toBe(false));
    expect(auth.isAuthenticated).toBe(true);
    expect(store.get('atom_access_token')).toBe('ordinary');
    expect(auth.user?.id).toBe('controlled-user');
  });

  test('a failed login profile save revokes the previously mounted identity', async () => {
    await seed();
    await mount();
    expect(auth.isAuthenticated).toBe(true);
    (AsyncStorage.setItem as jest.Mock).mockRejectedValueOnce(new Error('controlled profile save failure'));
    await act(async () => { expect((await auth.login(credentials)).success).toBe(false); });
    await expect(secureGet('atom_access_token')).resolves.toBeNull();
    expect(auth.isAuthenticated).toBe(false);
    expect(auth.user).toBeNull();
  });

  test('a failed refresh token write revokes the previously mounted identity', async () => {
    await seed();
    await mount();
    expect(auth.isAuthenticated).toBe(true);
    (SecureStore.setItemAsync as jest.Mock).mockRejectedValueOnce(new Error('controlled token save failure'));
    await act(async () => { expect(await auth.refreshToken()).toBe(false); });
    await expect(secureGet('atom_access_token')).resolves.toBeNull();
    expect(auth.isAuthenticated).toBe(false);
    expect(auth.user).toBeNull();
  });

  test('a leftover refresh token cannot revive a locally revoked session', async () => {
    await seed();
    await mount();
    (SecureStore.deleteItemAsync as jest.Mock).mockImplementation(async key => {
      if (key === 'atom_refresh_token') throw new Error('controlled refresh cleanup failure');
      store.delete(key);
    });
    await act(async () => { await expect(auth.logout()).rejects.toThrow('controlled refresh cleanup failure'); });
    expect(auth.isAuthenticated).toBe(false);
    expect(store.has('atom_access_token')).toBe(false);
    expect(store.get('atom_refresh_token')).toBe('original-refresh');
    (global.fetch as jest.Mock).mockClear();
    await act(async () => { expect(await auth.refreshToken()).toBe(false); });
    expect(global.fetch).not.toHaveBeenCalled();
    await expect(secureGet('atom_access_token')).resolves.toBeNull();
  });

  test('an old refresh cannot dispatch a replacement login refresh credential', async () => {
    await seed();
    await mount();
    const delayed = deferred<string | null>();
    let refreshRead = false;
    (SecureStore.getItemAsync as jest.Mock).mockImplementation(async key => {
      if (key === 'atom_refresh_token' && !refreshRead) {
        refreshRead = true;
        return delayed.promise;
      }
      return store.get(key) ?? null;
    });
    let pending!: Promise<boolean>;
    act(() => { pending = auth.refreshToken(); });
    await waitFor(() => expect(refreshRead).toBe(true));
    (global.fetch as jest.Mock).mockResolvedValueOnce(response('replacement'));
    await act(async () => { expect((await auth.login(credentials)).success).toBe(true); });
    await act(async () => { delayed.resolve('replacement-refresh'); await pending; });
    const refreshCalls = (global.fetch as jest.Mock).mock.calls.filter(([url]) => String(url).endsWith('/mobile/refresh'));
    expect(refreshCalls).toHaveLength(0);
    expect(store.get('atom_access_token')).toBe('replacement');
  });

});
