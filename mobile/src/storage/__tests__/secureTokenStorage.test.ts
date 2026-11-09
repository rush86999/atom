/**
 * secureTokenStorage tests
 *
 * Verifies the SecureStore-first token storage contract:
 * - secureGet reads from SecureStore when present
 * - legacy AsyncStorage tokens migrate on first read (write to SecureStore,
 *   wipe the plaintext copy)
 * - SecureStore read failures must NOT fail closed: the legacy value is
 *   still readable from AsyncStorage (graceful degradation — a keystore
 *   hiccup must not lock the user out of their session)
 * - secureDelete clears both stores
 */
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { secureGet, secureSet, secureDelete, isSecureKey, readAccessTokenSnapshot, invalidateAccessToken } from '../secureTokenStorage';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
  WHEN_UNLOCKED: 'WHEN_UNLOCKED',
}));

jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
}));

const mockedSecureStore = SecureStore as jest.Mocked<typeof SecureStore>;
const mockedAsync = AsyncStorage as jest.Mocked<typeof AsyncStorage>;

describe('secureTokenStorage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('isSecureKey classifies sensitive keys', () => {
    expect(isSecureKey('auth_token')).toBe(true);
    expect(isSecureKey('atom_access_token')).toBe(true);
    expect(isSecureKey('refresh_token')).toBe(true);
    expect(isSecureKey('preferences')).toBe(false);
  });

  it('secureGet returns the SecureStore value when present', async () => {
    mockedSecureStore.getItemAsync.mockResolvedValue('secure-token');

    await expect(secureGet('auth_token')).resolves.toBe('secure-token');
    expect(mockedAsync.getItem).not.toHaveBeenCalled();
  });

  it('secureGet migrates a legacy AsyncStorage token and wipes it', async () => {
    mockedSecureStore.getItemAsync.mockResolvedValue(null);
    mockedAsync.getItem.mockResolvedValue('legacy-token');

    await expect(secureGet('auth_token')).resolves.toBe('legacy-token');
    expect(mockedSecureStore.setItemAsync).toHaveBeenCalledWith(
      'auth_token',
      'legacy-token',
      expect.anything()
    );
    expect(mockedAsync.removeItem).toHaveBeenCalledWith('auth_token');
  });

  it('secureGet falls back to AsyncStorage when SecureStore read throws', async () => {
    mockedSecureStore.getItemAsync.mockRejectedValue(
      new Error('Keychain unavailable')
    );
    mockedAsync.getItem.mockResolvedValue('legacy-token');

    // Value must still be readable (no fail-closed lockout)…
    await expect(secureGet('auth_token')).resolves.toBe('legacy-token');
    // …and migration still proceeds when the write side works.
    expect(mockedSecureStore.setItemAsync).toHaveBeenCalledWith(
      'auth_token',
      'legacy-token',
      expect.anything()
    );
    expect(mockedAsync.removeItem).toHaveBeenCalledWith('auth_token');
  });

  it('secureGet keeps the legacy value when SecureStore read AND write throw', async () => {
    mockedSecureStore.getItemAsync.mockRejectedValue(
      new Error('Keychain unavailable')
    );
    mockedSecureStore.setItemAsync.mockRejectedValue(
      new Error('Keychain unavailable')
    );
    mockedAsync.getItem.mockResolvedValue('legacy-token');

    await expect(secureGet('auth_token')).resolves.toBe('legacy-token');
    // Plaintext copy must survive until the keystore recovers.
    expect(mockedAsync.removeItem).not.toHaveBeenCalled();
  });

  it('secureGet returns null when both stores are empty', async () => {
    mockedSecureStore.getItemAsync.mockResolvedValue(null);
    mockedAsync.getItem.mockResolvedValue(null);

    await expect(secureGet('auth_token')).resolves.toBeNull();
  });

  it('secureSet writes through to SecureStore with WHEN_UNLOCKED', async () => {
    mockedSecureStore.setItemAsync.mockResolvedValue();

    await secureSet('auth_token', 'tok');

    expect(mockedSecureStore.setItemAsync).toHaveBeenCalledWith(
      'auth_token',
      'tok',
      expect.objectContaining({ keychainAccessible: 'WHEN_UNLOCKED' })
    );
  });

  it('secureDelete removes from both stores', async () => {
    mockedSecureStore.deleteItemAsync.mockResolvedValue();
    mockedAsync.removeItem.mockResolvedValue();

    await secureDelete('auth_token');

    expect(mockedSecureStore.deleteItemAsync).toHaveBeenCalledWith('auth_token');
    expect(mockedAsync.removeItem).toHaveBeenCalledWith('auth_token');
  });
});


describe('access-token request ownership', () => {
  let stored: string | null;
  beforeEach(() => {
    jest.clearAllMocks();
    stored = null;
    mockedSecureStore.getItemAsync.mockImplementation(async () => stored);
    mockedSecureStore.setItemAsync.mockImplementation(async (_key, value) => { stored = value; });
    mockedSecureStore.deleteItemAsync.mockImplementation(async () => { stored = null; });
    mockedAsync.getItem.mockResolvedValue(null);
    mockedAsync.removeItem.mockResolvedValue();
  });

  it('does not invalidate a replacement login even if the token bytes repeat', async () => {
    await secureSet('atom_access_token', 'same-value');
    const old = await readAccessTokenSnapshot();
    await secureSet('atom_access_token', 'same-value');
    await expect(invalidateAccessToken(old)).resolves.toBe(false);
    expect(stored).toBe('same-value');
    expect(mockedSecureStore.deleteItemAsync).not.toHaveBeenCalled();
  });

  it('invalidates only the current rejected request once', async () => {
    await secureSet('atom_access_token', 'current');
    const current = await readAccessTokenSnapshot();
    await expect(invalidateAccessToken(current)).resolves.toBe(true);
    await expect(invalidateAccessToken(current)).resolves.toBe(false);
    expect(stored).toBeNull();
    expect(mockedSecureStore.deleteItemAsync).toHaveBeenCalledTimes(2);
  });

  it('orders a new login after an in-flight invalidation without deleting it', async () => {
    await secureSet('atom_access_token', 'old');
    const old = await readAccessTokenSnapshot();
    let release: () => void = () => undefined;
    const gate = new Promise<void>(resolve => { release = resolve; });
    mockedSecureStore.deleteItemAsync.mockImplementationOnce(async () => { await gate; stored = null; });
    const invalidation = invalidateAccessToken(old);
    const login = secureSet('atom_access_token', 'new');
    release();
    await expect(invalidation).resolves.toBe(true);
    await login;
    expect(stored).toBe('new');
  });

  it('releases serialization after a failed native write', async () => {
    mockedSecureStore.setItemAsync.mockRejectedValueOnce(new Error('controlled write failure'));
    await expect(secureSet('atom_access_token', 'failed')).rejects.toThrow('controlled write failure');
    await secureSet('atom_access_token', 'next');
    expect((await readAccessTokenSnapshot()).token).toBe('next');
  });
});
