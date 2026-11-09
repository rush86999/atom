/** Real Axios interceptor/config ownership, with controlled transport and keychain. */
import { AxiosError, AxiosAdapter, AxiosRequestConfig } from 'axios';
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiService } from '../../services/api';
import { secureSet, secureDelete, readAccessTokenSnapshot } from '../../storage/secureTokenStorage';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(), setItemAsync: jest.fn(), deleteItemAsync: jest.fn(),
  WHEN_UNLOCKED: 'WHEN_UNLOCKED',
}));
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(), removeItem: jest.fn(),
}));

describe('real Axios session request binding', () => {
  const store = new Map<string, string>();
  beforeEach(async () => {
    jest.clearAllMocks();
    store.clear();
    (SecureStore.getItemAsync as jest.Mock).mockImplementation(async key => store.get(key) ?? null);
    (SecureStore.setItemAsync as jest.Mock).mockImplementation(async (key, value) => { store.set(key, value); });
    (SecureStore.deleteItemAsync as jest.Mock).mockImplementation(async key => { store.delete(key); });
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);
    (AsyncStorage.removeItem as jest.Mock).mockResolvedValue(undefined);
    await secureSet('atom_access_token', 'controlled-fixture-generation');
    store.clear();
    jest.clearAllMocks();
  });

  test.each(['different-account', 'same-token-replacement', 'logout'])('bound POST refuses %s before controlled transport', async change => {
    await secureSet('atom_access_token', 'bound-owner');
    const expected = await readAccessTokenSnapshot();
    if (change === 'logout') await secureDelete('atom_access_token');
    else await secureSet('atom_access_token', change === 'same-token-replacement' ? 'bound-owner' : 'replacement-owner');
    let dispatched = 0;
    const adapter: AxiosAdapter = async config => {
      dispatched += 1;
      return { config, status: 200, statusText: 'OK', headers: {}, data: { accepted: true } };
    };
    const config: AxiosRequestConfig & { expectedAccessTokenSnapshot: typeof expected } = { adapter, expectedAccessTokenSnapshot: expected };
    expect((await apiService.post('/controlled/bound-write', { observed: 0 }, config)).success).toBe(false);
    expect(dispatched).toBe(0);
  });

  test('bound POST on the exact current session keeps ordinary success behavior', async () => {
    await secureSet('atom_access_token', 'bound-owner');
    const expected = await readAccessTokenSnapshot();
    let dispatched = 0;
    const adapter: AxiosAdapter = async config => {
      dispatched += 1;
      expect(config.headers.Authorization).toBe('Bearer bound-owner');
      return { config, status: 200, statusText: 'OK', headers: {}, data: { accepted: true } };
    };
    const config: AxiosRequestConfig & { expectedAccessTokenSnapshot: typeof expected } = { adapter, expectedAccessTokenSnapshot: expected };
    expect((await apiService.post('/controlled/bound-write', { observed: 0 }, config)).success).toBe(true);
    expect(dispatched).toBe(1);
  });

  test('first real request reads the stored token without warming the API cache', async () => {
    store.set('atom_access_token', 'restored');
    const adapter: AxiosAdapter = async config => {
      expect(config.headers.Authorization).toBe('Bearer restored');
      return { config, status: 200, statusText: 'OK', headers: {}, data: { ok: true } };
    };
    await expect(apiService.get('/controlled', { adapter })).resolves.toEqual({ success: true, data: { ok: true } });
  });

  test('same-token replacement survives the old request error through real Axios', async () => {
    await secureSet('atom_access_token', 'same-token');
    const adapter: AxiosAdapter = async config => {
      await secureSet('atom_access_token', 'same-token');
      throw new AxiosError('controlled unauthorized', 'ERR_BAD_REQUEST', config, undefined,
        { config, status: 401, statusText: 'Unauthorized', headers: {}, data: {} });
    };
    expect((await apiService.get('/controlled', { adapter })).success).toBe(false);
    expect(store.get('atom_access_token')).toBe('same-token');
    expect(SecureStore.deleteItemAsync).not.toHaveBeenCalled();
  });

  test('current request rejection invalidates its exact session', async () => {
    await secureSet('atom_access_token', 'current');
    const adapter: AxiosAdapter = async config => {
      throw new AxiosError('controlled unauthorized', 'ERR_BAD_REQUEST', config, undefined,
        { config, status: 401, statusText: 'Unauthorized', headers: {}, data: {} });
    };
    expect((await apiService.get('/controlled', { adapter })).success).toBe(false);
    expect(store.has('atom_access_token')).toBe(false);
  });

  test('canonical logout is observed by the next real request', async () => {
    await apiService.setToken('old');
    await secureDelete('atom_access_token');
    const adapter: AxiosAdapter = async config => {
      expect(config.headers.Authorization).toBeUndefined();
      return { config, status: 200, statusText: 'OK', headers: {}, data: {} };
    };
    expect((await apiService.get('/controlled', { adapter })).success).toBe(true);
  });

  test('an unauthenticated request cannot clear a login made before its 401 arrives', async () => {
    const adapter: AxiosAdapter = async config => {
      expect(config.headers.Authorization).toBeUndefined();
      await secureSet('atom_access_token', 'new-login');
      throw new AxiosError('controlled unauthorized', 'ERR_BAD_REQUEST', config, undefined,
        { config, status: 401, statusText: 'Unauthorized', headers: {}, data: {} });
    };
    expect((await apiService.get('/controlled', { adapter })).success).toBe(false);
    expect(store.get('atom_access_token')).toBe('new-login');
    expect(SecureStore.deleteItemAsync).not.toHaveBeenCalled();
  });
});
