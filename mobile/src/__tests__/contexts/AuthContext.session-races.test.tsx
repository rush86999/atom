/** Controlled HTTP timing through the real provider and shared token helper. */
import React from 'react';
import { Text } from 'react-native';
import { render, act, waitFor } from '@testing-library/react-native';
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AuthProvider, useAuth } from '../../contexts/AuthContext';
import { secureSet } from '../../storage/secureTokenStorage';

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

});
