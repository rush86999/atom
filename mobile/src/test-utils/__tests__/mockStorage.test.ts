/**
 * mockStorage Utilities Unit Tests
 *
 * Exercises the storage seeding/reading helpers against the jest.setup
 * in-memory AsyncStorage/SecureStore/MMKV mocks, including the JSON-parse
 * fallback and default-export bundle.
 */

import mockStorageModule, {
  resetAsyncStorage,
  seedAsyncStorage,
  getAllAsyncStorageItems,
  clearAsyncStorage,
  resetMmkvStorage,
  seedMmkvStorage,
  resetSecureStore,
  seedSecureStore,
  getSecureStoreItem,
  resetAllStorage,
  seedAllStorage,
  clearAllStorage,
  setMockAuthToken,
  getMockAuthToken,
  clearMockAuthToken,
} from '../mockStorage';

describe('mockStorage', () => {
  beforeAll(() => {
    // Trigger the jest.setup react-native-mmkv mock factory, which installs
    // global.__mmkvGlobalInstance on first require.
    jest.requireMock('react-native-mmkv');
  });

  beforeEach(() => {
    resetAllStorage();
  });

  afterEach(() => {
    resetAllStorage();
  });

  it('default export bundles every named helper', () => {
    expect(mockStorageModule.resetAsyncStorage).toBe(resetAsyncStorage);
    expect(mockStorageModule.seedAsyncStorage).toBe(seedAsyncStorage);
    expect(mockStorageModule.getAllAsyncStorageItems).toBe(getAllAsyncStorageItems);
    expect(mockStorageModule.clearAsyncStorage).toBe(clearAsyncStorage);
    expect(mockStorageModule.resetMmkvStorage).toBe(resetMmkvStorage);
    expect(mockStorageModule.seedMmkvStorage).toBe(seedMmkvStorage);
    expect(mockStorageModule.resetSecureStore).toBe(resetSecureStore);
    expect(mockStorageModule.seedSecureStore).toBe(seedSecureStore);
    expect(mockStorageModule.getSecureStoreItem).toBe(getSecureStoreItem);
    expect(mockStorageModule.resetAllStorage).toBe(resetAllStorage);
    expect(mockStorageModule.seedAllStorage).toBe(seedAllStorage);
    expect(mockStorageModule.clearAllStorage).toBe(clearAllStorage);
    expect(mockStorageModule.setMockAuthToken).toBe(setMockAuthToken);
    expect(mockStorageModule.getMockAuthToken).toBe(getMockAuthToken);
    expect(mockStorageModule.clearMockAuthToken).toBe(clearMockAuthToken);
  });

  describe('AsyncStorage', () => {
    it('seeds and reads back items with JSON round-trip', async () => {
      seedAsyncStorage({ user: { id: 'u1' }, count: 3, flag: true });
      const all = await getAllAsyncStorageItems();
      expect(all.user).toEqual({ id: 'u1' });
      expect(all.count).toBe(3);
      expect(all.flag).toBe(true);
    });

    it('returns raw strings when JSON.parse fails', async () => {
      // Write invalid JSON directly (bypassing seedAsyncStorage's
      // JSON.stringify) to force the parse fallback.
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      await AsyncStorage.setItem('raw', '{not json}');
      const all = await getAllAsyncStorageItems();
      expect(all.raw).toBe('{not json}');
    });

    it('returns an empty object after clearing', async () => {
      seedAsyncStorage({ a: 1 });
      await clearAsyncStorage();
      expect(await getAllAsyncStorageItems()).toEqual({});
    });

    it('resetAsyncStorage invokes the global reset helper', async () => {
      seedAsyncStorage({ a: 1 });
      resetAsyncStorage();
      expect(await getAllAsyncStorageItems()).toEqual({});
    });

    it('reset helpers tolerate missing global hooks', async () => {
      const saved = {
        asyncStorage: (global as any).__resetAsyncStorageMock,
        mmkv: (global as any).__resetMmkvMock,
        secureStore: (global as any).__resetSecureStoreMock,
      };
      (global as any).__resetAsyncStorageMock = undefined;
      (global as any).__resetMmkvMock = undefined;
      (global as any).__resetSecureStoreMock = undefined;
      try {
        seedAsyncStorage({ a: 1 });
        seedMmkvStorage({ b: 2 });
        await seedSecureStore({ c: '3' });

        expect(() => resetAsyncStorage()).not.toThrow();
        expect(() => resetMmkvStorage()).not.toThrow();
        expect(() => resetSecureStore()).not.toThrow();
        expect(() => resetAllStorage()).not.toThrow();

        // Data survives because no reset hook exists to clear it
        expect(await getAllAsyncStorageItems()).toEqual({ a: 1 });
        expect(await getSecureStoreItem('c')).toBe('3');
      } finally {
        (global as any).__resetAsyncStorageMock = saved.asyncStorage;
        (global as any).__resetMmkvMock = saved.mmkv;
        (global as any).__resetSecureStoreMock = saved.secureStore;
      }
    });
  });

  describe('MMKV', () => {
    it('seeds into the global mmkv storage', () => {
      seedMmkvStorage({ theme: 'dark', version: 2 });
      const instance = (global as any).__mmkvGlobalInstance;
      expect(instance.getString('theme')).toBe('dark');
      expect(instance.getNumber('version')).toBe(2);
    });

    it('resetMmkvStorage clears seeded values', () => {
      seedMmkvStorage({ theme: 'dark' });
      resetMmkvStorage();
      const instance = (global as any).__mmkvGlobalInstance;
      expect(instance.getString('theme')).toBeNull();
    });

    it('falls back to __mmkvStorage map when the global instance is absent', () => {
      const instance = (global as any).__mmkvGlobalInstance;
      const fallback = new Map();
      (global as any).__mmkvStorage = fallback;
      (global as any).__mmkvGlobalInstance = undefined;
      try {
        seedMmkvStorage({ theme: 'dark' });
        expect(fallback.get('theme')).toBe('dark');
      } finally {
        (global as any).__mmkvGlobalInstance = instance;
        delete (global as any).__mmkvStorage;
      }
    });
  });

  describe('SecureStore', () => {
    it('seeds and reads items', async () => {
      await seedSecureStore({ token: 'abc' });
      expect(await getSecureStoreItem('token')).toBe('abc');
    });

    it('resetSecureStore clears seeded items', async () => {
      await seedSecureStore({ token: 'abc' });
      resetSecureStore();
      expect(await getSecureStoreItem('token')).toBeNull();
    });

    it('set/get/clear mock auth token round-trip', async () => {
      expect(await getMockAuthToken()).toBeNull();

      await setMockAuthToken();
      expect(await getMockAuthToken()).toBe('test-auth-token');

      await setMockAuthToken('custom-token');
      expect(await getMockAuthToken()).toBe('custom-token');

      await clearMockAuthToken();
      expect(await getMockAuthToken()).toBeNull();
    });
  });

  describe('combined helpers', () => {
    it('seedAllStorage seeds each present section only', async () => {
      await seedAllStorage({
        asyncStorage: { user: { id: 'u1' } },
        mmkv: { theme: 'light' },
        secureStore: { token: 't1' },
      });

      expect((await getAllAsyncStorageItems()).user).toEqual({ id: 'u1' });
      expect((global as any).__mmkvGlobalInstance.getString('theme')).toBe('light');
      expect(await getSecureStoreItem('token')).toBe('t1');
    });

    it('seedAllStorage tolerates missing sections', async () => {
      await expect(seedAllStorage({})).resolves.toBeUndefined();
      await expect(seedAllStorage({ asyncStorage: { a: 1 } })).resolves.toBeUndefined();
    });

    it('clearAllStorage clears every storage system', async () => {
      await seedAllStorage({
        asyncStorage: { a: 1 },
        mmkv: { b: 2 },
        secureStore: { c: '3' },
      });
      await clearAllStorage();

      expect(await getAllAsyncStorageItems()).toEqual({});
      expect((global as any).__mmkvGlobalInstance.getAllKeys()).toEqual([]);
      expect(await getSecureStoreItem('c')).toBeNull();
    });
  });
});
