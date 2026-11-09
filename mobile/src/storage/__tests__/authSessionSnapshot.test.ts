/** Canonical session/profile observations share the existing serializer. */
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { clearAuthSession, commitAuthSession, isAccessTokenSnapshotCurrent, readAccessTokenSnapshot, readAuthSessionSnapshot, secureSet } from '../secureTokenStorage';

jest.mock('expo-secure-store', () => ({ getItemAsync: jest.fn(), setItemAsync: jest.fn(), deleteItemAsync: jest.fn(), WHEN_UNLOCKED: 'WHEN_UNLOCKED' }));
jest.mock('@react-native-async-storage/async-storage', () => ({ getItem: jest.fn(), setItem: jest.fn(), removeItem: jest.fn() }));
const secure = new Map<string, string>();
const ordinary = new Map<string, string>();
const ownerA = JSON.stringify({ id: 'owner-A', workspace_id: 'workspace-A' });
const ownerB = JSON.stringify({ id: 'owner-B', workspace_id: 'workspace-B' });

describe('Canonical auth session snapshot', () => {
  beforeEach(async () => {
    jest.mocked(SecureStore.getItemAsync).mockReset().mockImplementation(async key => secure.get(key) ?? null);
    jest.mocked(SecureStore.setItemAsync).mockReset().mockImplementation(async (key, value) => { secure.set(key, value); });
    jest.mocked(SecureStore.deleteItemAsync).mockReset().mockImplementation(async key => { secure.delete(key); });
    jest.mocked(AsyncStorage.getItem).mockReset().mockImplementation(async key => ordinary.get(key) ?? null);
    jest.mocked(AsyncStorage.setItem).mockReset().mockImplementation(async (key, value) => { ordinary.set(key, value); });
    jest.mocked(AsyncStorage.removeItem).mockReset().mockImplementation(async key => { ordinary.delete(key); });
    await clearAuthSession();
    secure.clear(); ordinary.clear();
    await commitAuthSession(await readAccessTokenSnapshot(), { token: 'controlled-A', expiresAt: '1893456000000', userData: ownerA });
    await secureSet('atom_device_id', 'device-A');
  });

  test('reads the exact committed token/profile/device without defaults', async () => {
    const snapshot = await readAuthSessionSnapshot();
    expect(snapshot).toMatchObject({ token: 'controlled-A', userData: ownerA, deviceId: 'device-A' });
    expect(isAccessTokenSnapshotCurrent(snapshot)).toBe(true);
  });

  test('a delayed profile read cannot mix token A with queued login B', async () => {
    const expected = await readAccessTokenSnapshot();
    let release: (() => void) | undefined;
    const profile = new Promise<string | null>(resolve => { release = () => resolve(ownerA); });
    const started = new Promise<void>(resolve => { jest.mocked(AsyncStorage.getItem).mockImplementationOnce(() => { resolve(); return profile; }); });
    const reading = readAuthSessionSnapshot();
    await started;
    const replacing = commitAuthSession(expected, { token: 'controlled-B', expiresAt: '1893456000000', userData: ownerB });
    if (!release) throw new Error('Controlled profile read did not start');
    release();
    const before = await reading;
    expect(before).toMatchObject({ token: 'controlled-A', userData: ownerA });
    expect(await replacing).toBe(true);
    expect(isAccessTokenSnapshotCurrent(before)).toBe(false);
    expect(await readAuthSessionSnapshot()).toMatchObject({ token: 'controlled-B', userData: ownerB });
  });

  test('revoked sessions never regain a token from the snapshot', async () => {
    await clearAuthSession();
    expect(await readAuthSessionSnapshot()).toMatchObject({ token: null, userData: null });
  });

  test('unreadable profile is not fabricated as an empty or current owner', async () => {
    jest.mocked(AsyncStorage.getItem).mockRejectedValueOnce(new Error('Controlled profile unavailable'));
    await expect(readAuthSessionSnapshot()).rejects.toThrow('Controlled profile unavailable');
  });
});
