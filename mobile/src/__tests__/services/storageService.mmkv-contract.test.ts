/** Installed MMKV4 shape only; no constructor/delete/getSizeInBytes aliases. */

const mockNativeValues = new Map<string, string | number | boolean | ArrayBuffer>();

jest.mock('react-native-mmkv', () => ({
  createMMKV: jest.fn(() => ({
    set: jest.fn((key: string, value: string | number | boolean | ArrayBuffer) => { mockNativeValues.set(key, value); }),
    getString: jest.fn((key: string) => { const v = mockNativeValues.get(key); return typeof v === 'string' ? v : undefined; }),
    getNumber: jest.fn((key: string) => { const v = mockNativeValues.get(key); return typeof v === 'number' ? v : undefined; }),
    getBoolean: jest.fn((key: string) => { const v = mockNativeValues.get(key); return typeof v === 'boolean' ? v : undefined; }),
    contains: jest.fn((key: string) => mockNativeValues.has(key)),
    remove: jest.fn((key: string) => mockNativeValues.delete(key)),
    clearAll: jest.fn(() => { mockNativeValues.clear(); }),
    getAllKeys: jest.fn(() => [...mockNativeValues.keys()]),
    get size() { return 4096; },
  })),
}));

describe('StorageService installed MMKV contract', () => {
  beforeEach(() => {
    mockNativeValues.clear();
    jest.resetModules();
    const AsyncStorage = jest.requireMock<typeof import('@react-native-async-storage/async-storage').default>('@react-native-async-storage/async-storage');
    jest.mocked(AsyncStorage.getAllKeys).mockResolvedValue([]);
    jest.mocked(AsyncStorage.getItem).mockResolvedValue(null);
  });

  test('imports through the actual factory export and preserves the existing store id', async () => {
    const { storageService } = jest.requireActual<typeof import('../../services/storageService')>('../../services/storageService');
    expect(storageService).toBeDefined();
    const { createMMKV } = jest.requireMock<typeof import('react-native-mmkv')>('react-native-mmkv');
    expect(createMMKV).toHaveBeenCalledWith(expect.objectContaining({ id: 'atom-storage' }));
  });

  test('missing native values are null at the existing wrapper boundary', async () => {
    const { storageService } = jest.requireActual<typeof import('../../services/storageService')>('../../services/storageService');
    expect(storageService.getString('auth_token')).toBeNull();
    expect(await storageService.getNumber('user_id')).toBeNull();
    expect(await storageService.getBoolean('biometric_enabled')).toBeNull();
  });

  test('zero and false remain observed values', async () => {
    const { storageService } = jest.requireActual<typeof import('../../services/storageService')>('../../services/storageService');
    await storageService.setNumber('user_id', 0);
    await storageService.setBoolean('biometric_enabled', false);
    expect(await storageService.getNumber('user_id')).toBe(0);
    expect(await storageService.getBoolean('biometric_enabled')).toBe(false);
  });

  test('deletes through remove instead of an invented legacy method', async () => {
    const { storageService } = jest.requireActual<typeof import('../../services/storageService')>('../../services/storageService');
    await storageService.setString('offline_queue', 'controlled-retained-bytes');
    expect(await storageService.delete('offline_queue')).toBe(true);
    expect(storageService.getString('offline_queue')).toBeNull();
    const { createMMKV } = jest.requireMock<typeof import('react-native-mmkv')>('react-native-mmkv');
    const native = jest.mocked(createMMKV).mock.results[0].value;
    expect(native.remove).toHaveBeenCalledWith('offline_queue');
  });

  test('statistics read the native size property', async () => {
    const { storageService } = jest.requireActual<typeof import('../../services/storageService')>('../../services/storageService');
    expect((await storageService.getStats()).mmkvSize).toBe(4096);
  });

  test('clears through the native clearAll method', async () => {
    const { storageService } = jest.requireActual<typeof import('../../services/storageService')>('../../services/storageService');
    await storageService.setString('offline_queue', 'controlled-value');
    expect(await storageService.clear()).toBe(true);
    expect(mockNativeValues.size).toBe(0);
    const { createMMKV } = jest.requireMock<typeof import('react-native-mmkv')>('react-native-mmkv');
    expect(jest.mocked(createMMKV).mock.results[0].value.clearAll).toHaveBeenCalledTimes(1);
    const AsyncStorage = jest.requireMock<typeof import('@react-native-async-storage/async-storage').default>('@react-native-async-storage/async-storage');
    expect(AsyncStorage.clear).toHaveBeenCalledTimes(1);
  });

  test('existing bytes survive a fresh wrapper module load', async () => {
    const first = jest.requireActual<typeof import('../../services/storageService')>('../../services/storageService');
    await first.storageService.setString('offline_queue', 'controlled-original-bytes');
    jest.resetModules();
    const second = jest.requireActual<typeof import('../../services/storageService')>('../../services/storageService');
    expect(second.storageService.getString('offline_queue')).toBe('controlled-original-bytes');
  });
  test('failed replacement keeps existing native bytes and returns false', async () => {
    const { storageService } = jest.requireActual<typeof import('../../services/storageService')>('../../services/storageService');
    const { createMMKV } = jest.requireMock<typeof import('react-native-mmkv')>('react-native-mmkv');
    await storageService.setString('offline_queue', 'controlled-original');
    jest.mocked(jest.mocked(createMMKV).mock.results[0].value.set).mockImplementationOnce(() => { throw new Error('controlled native write refusal'); });
    expect(await storageService.setString('offline_queue', 'controlled-replacement')).toBe(false);
    expect(storageService.getString('offline_queue')).toBe('controlled-original');
  });

  test('failed quota persistence is not cached as a successful initialization', async () => {
    const { storageService } = jest.requireActual<typeof import('../../services/storageService')>('../../services/storageService');
    const AsyncStorage = jest.requireMock<typeof import('@react-native-async-storage/async-storage').default>('@react-native-async-storage/async-storage');
    jest.mocked(AsyncStorage.setItem).mockRejectedValueOnce(new Error('controlled quota write refusal'));
    await expect(storageService.getStorageQuota()).rejects.toThrow('Failed to persist storage quota');
    const calls = jest.mocked(AsyncStorage.setItem).mock.calls.length;
    await expect(storageService.getStorageQuota()).resolves.toEqual(expect.objectContaining({ usedBytes: 4096 }));
    expect(jest.mocked(AsyncStorage.setItem).mock.calls.length).toBe(calls + 1);
  });

});
