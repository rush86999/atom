/**
 * storageTestHelpers Unit Tests
 *
 * Covers token/state helpers and the full scenario suite (auth, device,
 * biometric, corruption) against the jest.setup in-memory mocks.
 */

import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  mockSecureStoreState,
  mockAsyncStorageState,
  mockMMKVState,
  getAllStoredState,
  clearAllStorage,
  createValidToken,
  createExpiredToken,
  createExpiringSoonToken,
  parseTokenExpiry,
  calculateTokenExpiry,
  createMockUser,
  createMockDevice,
  createMockCapabilities,
  setupAuthenticatedState,
  setupUnauthenticatedState,
  setupRegisteredDevice,
  setupPartialAuthState,
  setupWebSocketRooms,
  setupBiometricState,
  setupFreshInstall,
  setupReturningUser,
  setupExpiredSession,
  setupCorruptedStorage,
  verifyAuthState,
  verifyDeviceState,
} from '../storageTestHelpers';

describe('storageTestHelpers', () => {
  beforeAll(() => {
    // Trigger the jest.setup react-native-mmkv mock factory, which installs
    // global.__mmkvGlobalInstance on first require.
    jest.requireMock('react-native-mmkv');
  });

  beforeEach(async () => {
    await clearAllStorage();
  });

  afterEach(async () => {
    await clearAllStorage();
  });

  describe('mockSecureStoreState', () => {
    it('seeds values and supports set/delete via the mocked APIs', async () => {
      await mockSecureStoreState({ atom_access_token: 'tok-1' });
      expect(await SecureStore.getItemAsync('atom_access_token')).toBe('tok-1');
      expect(await SecureStore.getItemAsync('atom_refresh_token')).toBeNull();

      await SecureStore.setItemAsync('atom_access_token', 'tok-2');
      expect(await SecureStore.getItemAsync('atom_access_token')).toBe('tok-2');

      await SecureStore.deleteItemAsync('atom_access_token');
      expect(await SecureStore.getItemAsync('atom_access_token')).toBeNull();
    });
  });

  describe('mockAsyncStorageState', () => {
    it('seeds values and supports set/remove/getAllKeys', async () => {
      await mockAsyncStorageState({ atom_user_data: '{"name":"A"}' });
      expect(await AsyncStorage.getItem('atom_user_data')).toBe('{"name":"A"}');
      expect(await AsyncStorage.getAllKeys()).toEqual(['atom_user_data']);

      await AsyncStorage.setItem('atom_device_id', 'd1');
      await AsyncStorage.removeItem('atom_user_data');
      expect(await AsyncStorage.getItem('atom_user_data')).toBeNull();
      expect(await AsyncStorage.getAllKeys()).toEqual(['atom_device_id']);
    });
  });

  describe('mockMMKVState', () => {
    it('clears and seeds the global MMKV instance', async () => {
      const instance = (global as any).__mmkvGlobalInstance;
      instance.set('stale', 1);

      await mockMMKVState({ theme: 'dark', count: 3 });
      expect(instance.getString('theme')).toBe('dark');
      expect(instance.getNumber('count')).toBe(3);
      expect(instance.contains('stale')).toBe(false);
    });

    it('warns and no-ops without the global instance', async () => {
      const instance = (global as any).__mmkvGlobalInstance;
      (global as any).__mmkvGlobalInstance = undefined;
      const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
      try {
        await mockMMKVState({ theme: 'dark' });
        expect(warn).toHaveBeenCalled();
      } finally {
        (global as any).__mmkvGlobalInstance = instance;
        warn.mockRestore();
      }
    });
  });

  describe('getAllStoredState and clearAllStorage', () => {
    it('aggregates state across all three storage systems', async () => {
      await mockSecureStoreState({ atom_access_token: 'tok' });
      await mockAsyncStorageState({ atom_device_id: 'd1' });
      await mockMMKVState({ theme: 'light' });

      const state = await getAllStoredState();
      expect(state.secureStore.atom_access_token).toBe('tok');
      expect(state.asyncStorage.atom_device_id).toBe('d1');
      expect(state.mmkv.theme).toBe('light');
    });

    it('skips missing keys and missing MMKV instance', async () => {
      const instance = (global as any).__mmkvGlobalInstance;
      (global as any).__mmkvGlobalInstance = undefined;
      try {
        const state = await getAllStoredState();
        expect(state.secureStore).toEqual({});
        expect(state.asyncStorage).toEqual({});
        expect(state.mmkv).toEqual({});
      } finally {
        (global as any).__mmkvGlobalInstance = instance;
      }
    });

    it('clearAllStorage empties every storage system', async () => {
      await mockSecureStoreState({ atom_access_token: 'tok' });
      await mockAsyncStorageState({ atom_device_id: 'd1' });
      await mockMMKVState({ theme: 'light' });

      await clearAllStorage();
      const state = await getAllStoredState();
      expect(state.secureStore).toEqual({});
      expect(state.asyncStorage).toEqual({});
      expect(state.mmkv).toEqual({});
    });
  });

  describe('token helpers', () => {
    it('createValidToken embeds a future expiry', () => {
      const token = createValidToken(24);
      expect(parseTokenExpiry(token)).toBeGreaterThan(Date.now());
    });

    it('createExpiredToken embeds a past expiry', () => {
      const token = createExpiredToken();
      expect(parseTokenExpiry(token)).toBeLessThan(Date.now());
    });

    it('createExpiringSoonToken embeds a 4-minute expiry', () => {
      const token = createExpiringSoonToken();
      expect(parseTokenExpiry(token)).toBeGreaterThan(Date.now() - 1000);
      expect(parseTokenExpiry(token)).toBeLessThan(Date.now() + 5 * 60 * 1000);
    });

    it('parseTokenExpiry falls back to 24h for malformed tokens', () => {
      const fallback = parseTokenExpiry('garbage-token');
      expect(fallback).toBeGreaterThan(Date.now());
    });

    it('calculateTokenExpiry returns a numeric string', () => {
      expect(calculateTokenExpiry(24)).toMatch(/^\d+$/);
    });
  });

  describe('mock object factories', () => {
    it('createMockUser applies overrides', () => {
      const user = createMockUser({ name: 'Custom' });
      expect(user.name).toBe('Custom');
      expect(user.id).toBe('user_123');
    });

    it('createMockDevice applies overrides', () => {
      const device = createMockDevice({ platform: 'android' });
      expect(device.platform).toBe('android');
      expect(device.device_token).toBe('device_token_123');
    });

    it('createMockCapabilities applies overrides', () => {
      const caps = createMockCapabilities({ camera: true });
      expect(caps.camera).toBe(true);
      expect(caps.location).toBe(false);
    });
  });

  describe('scenario setup helpers', () => {
    it('setupAuthenticatedState stores tokens, user and device', async () => {
      await setupAuthenticatedState(createMockUser({ id: 'u9' }), createMockDevice({ platform: 'android' }));
      expect(await SecureStore.getItemAsync('atom_access_token')).toBeTruthy();
      expect(await SecureStore.getItemAsync('atom_refresh_token')).toBe('mock_refresh_token_123');
      expect(await AsyncStorage.getItem('atom_user_data')).toContain('u9');
      expect(await AsyncStorage.getItem('atom_device_id')).toBe('device_token_123');
    });

    it('setupAuthenticatedState uses defaults without args', async () => {
      await setupAuthenticatedState();
      expect(await AsyncStorage.getItem('atom_user_data')).toContain('user_123');
    });

    it('setupUnauthenticatedState and setupFreshInstall clear storage', async () => {
      await setupAuthenticatedState();
      await setupUnauthenticatedState();
      expect(await SecureStore.getItemAsync('atom_access_token')).toBeNull();

      await setupAuthenticatedState();
      await setupFreshInstall();
      expect(await SecureStore.getItemAsync('atom_access_token')).toBeNull();
    });

    it('setupRegisteredDevice stores device metadata', async () => {
      await setupRegisteredDevice('push-token-99');
      expect(await AsyncStorage.getItem('atom_device_id')).toBe('device_id_123');
      expect(await AsyncStorage.getItem('atom_device_token')).toBe('push-token-99');
      expect(await AsyncStorage.getItem('atom_device_registered')).toBe('true');
      expect(await AsyncStorage.getItem('atom_device_capabilities')).toContain('camera');
      expect(await AsyncStorage.getItem('atom_last_sync')).toBeTruthy();
    });

    it.each(['expired', 'expiring-soon', 'missing-refresh', 'user-data-only'] as const)(
      'setupPartialAuthState handles %s',
      async (scenario) => {
        await setupPartialAuthState(scenario);

        if (scenario === 'expired') {
          expect(parseTokenExpiry(await SecureStore.getItemAsync('atom_access_token')!)).toBeLessThan(Date.now());
        } else if (scenario === 'expiring-soon') {
          expect(parseTokenExpiry(await SecureStore.getItemAsync('atom_access_token')!)).toBeGreaterThan(Date.now());
        } else if (scenario === 'missing-refresh') {
          expect(await SecureStore.getItemAsync('atom_access_token')).toBeTruthy();
          expect(await SecureStore.getItemAsync('atom_refresh_token')).toBeNull();
        } else {
          expect(await SecureStore.getItemAsync('atom_access_token')).toBeNull();
          expect(await AsyncStorage.getItem('atom_user_data')).toContain('user_123');
        }
      }
    );

    it('setupWebSocketRooms stores room keys', async () => {
      await setupWebSocketRooms(['agents', 'workflows']);
      expect(await AsyncStorage.getItem('socket_room_agents')).toBe('true');
      expect(await AsyncStorage.getItem('socket_room_workflows')).toBe('true');
    });

    it('setupBiometricState enables and disables', async () => {
      await setupBiometricState(true);
      expect(await SecureStore.getItemAsync('atom_biometric_enabled')).toBe('true');

      await mockSecureStoreState({});
      await setupBiometricState(false);
      expect(await SecureStore.getItemAsync('atom_biometric_enabled')).toBeNull();
    });

    it('setupReturningUser mirrors authenticated state', async () => {
      await setupReturningUser();
      expect(await SecureStore.getItemAsync('atom_access_token')).toBeTruthy();
    });

    it('setupExpiredSession stores expired tokens with user data', async () => {
      await setupExpiredSession();
      expect(parseTokenExpiry(await SecureStore.getItemAsync('atom_access_token')!)).toBeLessThan(Date.now());
      expect(await AsyncStorage.getItem('atom_user_data')).toContain('user_123');
    });

    it.each(['invalid-json', 'malformed-token', 'missing-keys'] as const)(
      'setupCorruptedStorage handles %s',
      async (corruptionType) => {
        await setupCorruptedStorage(corruptionType);

        if (corruptionType === 'invalid-json') {
          expect(await AsyncStorage.getItem('atom_user_data')).toBe('{invalid json}');
        } else if (corruptionType === 'malformed-token') {
          expect(await SecureStore.getItemAsync('atom_access_token')).toBe('invalid_token_format');
          expect(await SecureStore.getItemAsync('atom_token_expiry')).toBe('not_a_number');
        } else {
          expect(await AsyncStorage.getItem('atom_user_data')).toContain('user_123');
          expect(await AsyncStorage.getItem('atom_device_id')).toBeNull();
        }
      }
    );
  });

  describe('verification helpers', () => {
    it('verifyAuthState reports matches for authenticated storage', async () => {
      await setupAuthenticatedState();
      const result = await verifyAuthState({
        hasAccessToken: true,
        hasRefreshToken: true,
        hasUserData: true,
      });
      expect(result.matches).toBe(true);
      expect(result.details).toEqual({
        hasAccessToken: true,
        hasRefreshToken: true,
        hasUserData: true,
      });
    });

    it('verifyAuthState reports misses for empty storage', async () => {
      const result = await verifyAuthState({
        hasAccessToken: true,
        hasRefreshToken: true,
        hasUserData: true,
      });
      expect(result.matches).toBe(false);
      expect(result.details).toEqual({
        hasAccessToken: false,
        hasRefreshToken: false,
        hasUserData: false,
      });
    });

    it('verifyAuthState ignores unspecified checks', async () => {
      const result = await verifyAuthState({ hasAccessToken: true });
      expect(result.details).toEqual({ hasAccessToken: false });
    });

    it('verifyDeviceState reports matches for registered device', async () => {
      await setupRegisteredDevice();
      const result = await verifyDeviceState({
        isRegistered: true,
        hasDeviceId: true,
        hasDeviceToken: true,
        hasCapabilities: true,
      });
      expect(result.matches).toBe(true);
    });

    it('verifyDeviceState reports misses for empty storage', async () => {
      const result = await verifyDeviceState({
        isRegistered: true,
        hasDeviceId: true,
        hasDeviceToken: true,
        hasCapabilities: true,
      });
      expect(result.matches).toBe(false);
      expect(result.details.isRegistered).toBe(false);
    });

    it('verifyDeviceState ignores unspecified checks', async () => {
      const result = await verifyDeviceState({ hasDeviceId: true });
      expect(result.details).toEqual({ hasDeviceId: false });
    });
  });
});
