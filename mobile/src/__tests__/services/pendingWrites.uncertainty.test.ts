/** A lost POST confirmation is not authority for a second dispatch. */
const mockPost = jest.fn();
const mockGetObject = jest.fn();
const mockSetObject = jest.fn();
const durable = new Map<string, string>();

type PendingClient = { flush: () => Promise<void>; destroy: () => void };
const families = [
  {
    name: 'workflow', key: 'workflow_cache',
    cache: (deliveryStatus: string | null = 'pending') => ({ workflows: {}, executions: {}, lastSyncAt: null, pendingTriggers: [{ id: 'trigger-001', workflowId: 'workflow-001', input: { amount: 0 }, priority: 5, createdAt: '2026-11-09T10:00:00Z', retryCount: 0, status: 'pending', deliveryStatus: deliveryStatus ?? undefined, userId: 'owner-001', deviceId: 'device-001' }] }),
    load: async (): Promise<PendingClient> => {
      const { workflowSyncService: service }: typeof import('../../services/workflowSyncService') = require('../../services/workflowSyncService');
      await service.initialize();
      return { flush: () => service.syncExecutions('owner-001', 'device-001'), destroy: () => service.destroy() };
    },
  },
  {
    name: 'canvas', key: 'canvas_cache',
    cache: (deliveryStatus: string | null = 'pending') => ({ canvases: {}, htmlCache: {}, cssCache: {}, lastSyncAt: null, favorites: [], pendingFormSubmissions: [{ canvasId: 'canvas-001', formData: { amount: 0 }, submittedAt: '2026-11-09T10:00:00Z', status: 'pending', deliveryStatus: deliveryStatus ?? undefined, userId: 'owner-001', deviceId: 'device-001' }] }),
    load: async (): Promise<PendingClient> => {
      const { canvasSyncService: service }: typeof import('../../services/canvasSyncService') = require('../../services/canvasSyncService');
      await service.initialize();
      return { flush: () => service.syncFormSubmissions('owner-001', 'device-001'), destroy: () => service.destroy() };
    },
  },
];

describe('Pending writes require a durable pre-dispatch boundary', () => {
  beforeEach(() => {
    jest.resetModules();
    jest.useFakeTimers();
    durable.clear();
    mockPost.mockReset().mockResolvedValue({ success: true, data: { accepted: true } });
    mockGetObject.mockReset().mockImplementation(async (key: string) => JSON.parse(durable.get(key) ?? 'null'));
    mockSetObject.mockReset().mockImplementation(async (key: string, value: unknown) => { durable.set(key, JSON.stringify(value)); return true; });
    jest.doMock('../../services/api', () => ({ apiService: { post: mockPost } }));
    jest.doMock('../../services/storageService', () => ({ storageService: { getObject: mockGetObject, setObject: mockSetObject } }));
    jest.doMock('../../services/offlineSyncService', () => ({ offlineSyncService: { getSyncState: jest.fn() } }));
  });
  afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });

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
