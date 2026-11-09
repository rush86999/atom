/** A lost POST confirmation is not authority for a second dispatch. */
const mockPost = jest.fn();
const mockGet = jest.fn();
const mockReadAuthSessionSnapshot = jest.fn();
let mockGeneration = 1;
const mockGetObject = jest.fn();
const mockSetObject = jest.fn();
const durable = new Map<string, string>();

type PendingClient = { flush: () => Promise<void>; destroy: () => void };
const families = [
  {
    name: 'workflow', key: 'workflow_cache',
    cache: (deliveryStatus: string | null = 'pending') => ({ workflows: {}, executions: {}, lastSyncAt: null, pendingTriggers: [{ id: 'trigger-001', workflowId: 'workflow-001', input: { amount: 0 }, priority: 5, createdAt: '2026-11-09T10:00:00Z', retryCount: 0, status: 'pending', deliveryStatus: deliveryStatus ?? undefined, userId: 'owner-001', deviceId: 'device-001', workspaceId: 'workspace-001' }] }),
    load: async (userId = 'owner-001', deviceId = 'device-001'): Promise<PendingClient> => {
      const { workflowSyncService: service }: typeof import('../../services/workflowSyncService') = require('../../services/workflowSyncService');
      await service.initialize();
      return { flush: () => service.syncExecutions(userId, deviceId), destroy: () => service.destroy() };
    },
  },
  {
    name: 'canvas', key: 'canvas_cache',
    cache: (deliveryStatus: string | null = 'pending') => ({ canvases: {}, htmlCache: {}, cssCache: {}, lastSyncAt: null, favorites: [], pendingFormSubmissions: [{ canvasId: 'canvas-001', formData: { amount: 0 }, submittedAt: '2026-11-09T10:00:00Z', status: 'pending', deliveryStatus: deliveryStatus ?? undefined, userId: 'owner-001', deviceId: 'device-001', workspaceId: 'workspace-001' }] }),
    load: async (userId = 'owner-001', deviceId = 'device-001'): Promise<PendingClient> => {
      const { canvasSyncService: service }: typeof import('../../services/canvasSyncService') = require('../../services/canvasSyncService');
      await service.initialize();
      return { flush: () => service.syncFormSubmissions(userId, deviceId), destroy: () => service.destroy() };
    },
  },
];

describe('Pending writes require a durable pre-dispatch boundary', () => {
  beforeEach(() => {
    jest.resetModules();
    jest.useFakeTimers();
    durable.clear();
    mockGeneration = 1;
    mockGet.mockReset().mockResolvedValue({ success: true, data: { id: 'owner-001', workspace_id: 'workspace-001', status: 'active' } });
    mockReadAuthSessionSnapshot.mockReset().mockImplementation(async () => ({ token: 'controlled-session', generation: mockGeneration, userData: JSON.stringify({ id: 'owner-001', workspace_id: 'workspace-001' }), deviceId: 'device-001' }));
    mockPost.mockReset().mockResolvedValue({ success: true, data: { accepted: true } });
    mockGetObject.mockReset().mockImplementation(async (key: string) => JSON.parse(durable.get(key) ?? 'null'));
    mockSetObject.mockReset().mockImplementation(async (key: string, value: unknown) => { durable.set(key, JSON.stringify(value)); return true; });
    jest.doMock('../../services/api', () => ({ apiService: { post: mockPost, get: mockGet } }));
    jest.doMock('../../services/storageService', () => ({ storageService: { getObject: mockGetObject, setObject: mockSetObject } }));
    jest.doMock('../../storage/secureTokenStorage', () => ({ readAuthSessionSnapshot: mockReadAuthSessionSnapshot, isAccessTokenSnapshotCurrent: (snapshot: { generation: number }) => snapshot.generation === mockGeneration }));
    jest.doMock('../../services/offlineSyncService', () => ({ offlineSyncService: { getSyncState: jest.fn() } }));
  });
  afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });

  test.each(families.flatMap(family => ['userId', 'workspaceId', 'deviceId'].map(field => ({ name: family.name, family, field }))))('$name missing queued $field never inherits the current actor', async ({ family, field }) => {
    const cache = family.cache();
    const row = 'pendingTriggers' in cache ? cache.pendingTriggers[0] : cache.pendingFormSubmissions[0];
    Reflect.deleteProperty(row, field);
    durable.set(family.key, JSON.stringify(cache));
    const before = durable.get(family.key);
    const client = await family.load();
    await client.flush();
    expect(mockPost).not.toHaveBeenCalled();
    expect(durable.get(family.key)).toBe(before);
    client.destroy();
  });

  test.each(families)('$name inactive server actor cannot execute pending work', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    mockGet.mockResolvedValue({ success: true, data: { id: 'owner-001', workspace_id: 'workspace-001', status: 'suspended' } });
    const client = await family.load();
    await client.flush();
    expect(mockPost).not.toHaveBeenCalled();
    client.destroy();
  });

  test.each(families)('$name dispatch uses exact bound session without persisting token/profile', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    const client = await family.load();
    await client.flush();
    expect(mockGet).toHaveBeenCalledWith('/api/auth/me', expect.objectContaining({ expectedAccessTokenSnapshot: expect.objectContaining({ generation: 1, token: 'controlled-session' }) }));
    expect(mockPost).toHaveBeenCalledWith(expect.any(String), expect.anything(), expect.objectContaining({ expectedAccessTokenSnapshot: expect.objectContaining({ generation: 1, token: 'controlled-session' }) }));
    expect(Array.from(durable.values()).join('')).not.toContain('controlled-session');
    expect(Array.from(durable.values()).join('')).not.toContain('userData');
    client.destroy();
  });

  test.each(families)('$name replacement during marker persistence cannot dispatch', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    const client = await family.load();
    mockSetObject.mockImplementationOnce(async (key: string, value: unknown) => { durable.set(key, JSON.stringify(value)); mockGeneration += 1; return true; });
    await client.flush();
    expect(mockPost).not.toHaveBeenCalled();
    client.destroy();
  });

  test.each(families)('$name failed restoration after session replacement is reported', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    const client = await family.load();
    mockSetObject.mockImplementationOnce(async (key: string, value: unknown) => { durable.set(key, JSON.stringify(value)); mockGeneration += 1; return true; }).mockResolvedValueOnce(false);
    await expect(client.flush()).rejects.toThrow();
    expect(mockPost).not.toHaveBeenCalled();
    client.destroy();
  });

  test.each(families)('$name a different caller cannot execute stored work', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    const client = await family.load('different-owner', 'device-001');
    await client.flush();
    expect(mockPost).not.toHaveBeenCalled();
    expect(mockSetObject).not.toHaveBeenCalled();
    client.destroy();
  });

  test.each(families)('$name a different device cannot execute stored work', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    const client = await family.load('owner-001', 'different-device');
    await client.flush();
    expect(mockPost).not.toHaveBeenCalled();
    client.destroy();
  });

  test.each(families)('$name authenticated server identity must match the queued owner', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    mockGet.mockResolvedValue({ success: true, data: { id: 'different-owner', workspace_id: 'workspace-001', status: 'active' } });
    const client = await family.load();
    await client.flush();
    expect(mockPost).not.toHaveBeenCalled();
    client.destroy();
  });

  test.each(families)('$name authenticated server workspace must match the queued workspace', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    mockGet.mockResolvedValue({ success: true, data: { id: 'owner-001', workspace_id: 'different-workspace', status: 'active' } });
    const client = await family.load();
    await client.flush();
    expect(mockPost).not.toHaveBeenCalled();
    client.destroy();
  });

  test.each(families)('$name missing canonical session cannot execute stored work', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    mockReadAuthSessionSnapshot.mockResolvedValue({ token: null, generation: 1, userData: null, deviceId: null });
    const client = await family.load();
    await client.flush();
    expect(mockPost).not.toHaveBeenCalled();
    client.destroy();
  });

  test.each(families)('$name replacement during actor lookup cannot authorize old queued work', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    mockGet.mockImplementation(async () => { mockGeneration += 1; return { success: true, data: { id: 'owner-001', workspace_id: 'workspace-001', status: 'active' } }; });
    const client = await family.load();
    await client.flush();
    expect(mockPost).not.toHaveBeenCalled();
    client.destroy();
  });

  test.each(families)('$name known pre-dispatch failure may safely retry once storage recovers', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    const client = await family.load();
    mockSetObject.mockResolvedValueOnce(false);
    await expect(client.flush()).rejects.toThrow();
    expect(mockPost).not.toHaveBeenCalled();
    await client.flush();
    expect(mockPost).toHaveBeenCalledTimes(1);
    client.destroy();
  });

  test.each(families)('$name distinct queued rows remain distinct even with matching target and time', async family => {
    const cache = family.cache();
    const queueKey = 'pendingTriggers' in cache ? 'pendingTriggers' : 'pendingFormSubmissions';
    if ('pendingTriggers' in cache) cache.pendingTriggers.push({ ...cache.pendingTriggers[0], id: 'trigger-002' });
    else cache.pendingFormSubmissions.push({ ...cache.pendingFormSubmissions[0], formData: { amount: 1 } });
    durable.set(family.key, JSON.stringify(cache));
    const client = await family.load();
    await client.flush();
    expect(mockPost).toHaveBeenCalledTimes(2);
    expect(JSON.parse(durable.get(family.key) ?? 'null')).toMatchObject({ [queueKey]: [] });
    client.destroy();
  });

  test.each(families)('$name legacy delivery without an observation is not assumed safe to retry', async family => {
    durable.set(family.key, JSON.stringify(family.cache(null)));
    const client = await family.load();
    const before = durable.get(family.key);
    await client.flush();
    expect(mockPost).not.toHaveBeenCalled();
    expect(durable.get(family.key)).toBe(before);
    client.destroy();
  });

  test.each(families)('$name concurrent flushes cannot dispatch one pending record twice', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    const client = await family.load();
    let release: (() => void) | undefined;
    const response = new Promise<{ success: boolean }>(resolve => { release = () => resolve({ success: true }); });
    const started = new Promise<void>(resolve => { mockPost.mockImplementationOnce(() => { resolve(); return response; }); });
    const first = client.flush();
    await started;
    const second = client.flush();
    if (!release) throw new Error('Controlled transport was not started');
    release();
    await Promise.all([first, second]);
    expect(mockPost).toHaveBeenCalledTimes(1);
    client.destroy();
  });

  test.each(families)('$name refuses dispatch if the durable pre-dispatch write fails', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    const client = await family.load();
    mockSetObject.mockResolvedValueOnce(false);
    await expect(client.flush()).rejects.toThrow();
    expect(mockPost).not.toHaveBeenCalled();
    client.destroy();
  });

  test.each(families)('$name lost confirmation never automatically repeats the POST', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    const client = await family.load();
    mockPost.mockRejectedValueOnce(new Error('Controlled confirmation lost'));
    await client.flush();
    await client.flush();
    expect(mockPost).toHaveBeenCalledTimes(1);
    client.destroy();
    jest.resetModules();
    const restarted = await family.load();
    await restarted.flush();
    expect(mockPost).toHaveBeenCalledTimes(1);
    restarted.destroy();
  });

  test.each(families)('$name accepted POST plus failed completion save cannot repeat after reload', async family => {
    durable.set(family.key, JSON.stringify(family.cache()));
    const client = await family.load();
    mockSetObject.mockImplementationOnce(async (key: string, value: unknown) => { durable.set(key, JSON.stringify(value)); return true; }).mockResolvedValueOnce(false);
    await expect(client.flush()).rejects.toThrow();
    expect(mockPost).toHaveBeenCalledTimes(1);
    client.destroy();
    jest.resetModules();
    const restarted = await family.load();
    await restarted.flush();
    expect(mockPost).toHaveBeenCalledTimes(1);
    restarted.destroy();
  });
});
