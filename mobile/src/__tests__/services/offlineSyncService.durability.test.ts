/** Serialized backing bytes, not UI objects that share mutable references. */
import NetInfo, { NetInfoStateType } from '@react-native-community/netinfo';
import { offlineSyncService, OfflineAction } from '../../services/offlineSyncService';
import { storageService } from '../../services/storageService';
import { apiService } from '../../services/api';
import type { ApiResponse } from '../../types/common';

jest.mock('@react-native-community/netinfo', () => ({
  __esModule: true,
  default: { fetch: jest.fn(), addEventListener: jest.fn(() => jest.fn()) },
  NetInfoStateType: { unknown: 'unknown' },
}));
jest.mock('../../services/api', () => ({ apiService: { post: jest.fn().mockResolvedValue({ success: false, error: 'controlled backend refusal' }) } }));

async function start(online = false) {
  jest.mocked(NetInfo.fetch).mockResolvedValueOnce({ type: NetInfoStateType.unknown, isConnected: online, isInternetReachable: null, details: null });
  await offlineSyncService.initialize();
}
function readQueue(): OfflineAction[] {
  const raw = storageService.getString('offline_queue');
  return raw ? JSON.parse(raw) : [];
}
function add(message: string) {
  return offlineSyncService.queueAction('agent_message', { agentId: 'controlled-agent', message }, 'low', 'controlled-user', 'controlled-device');
}

describe('OfflineSync durable pending intent contract', () => {
  beforeEach(async () => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    await storageService.clear();
  });
  afterEach(() => {
    offlineSyncService.destroy();
    jest.clearAllTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  test('concurrent additions retain both exact action identities in fresh bytes', async () => {
    await start();
    jest.spyOn(Math, 'random').mockReturnValueOnce(0.1).mockReturnValueOnce(0.2);
    const ids = await Promise.all([add('first'), add('second')]);
    expect(new Set(readQueue().map((a) => a.id))).toEqual(new Set(ids));
    expect(readQueue()).toHaveLength(2);
  });

  test('a refused storage write cannot return a queued action identity', async () => {
    await start();
    jest.spyOn(storageService, 'setString').mockResolvedValueOnce(false);
    await expect(add('must not be acknowledged')).rejects.toThrow();
    expect(readQueue()).toHaveLength(0);
  });

  test('corrupt retained queue bytes refuse without erasing recovery material', async () => {
    await start();
    const original = '{controlled-corrupt-queue';
    await storageService.setString('offline_queue', original);
    await expect(add('must not overwrite corrupt history')).rejects.toThrow();
    expect(storageService.getString('offline_queue')).toBe(original);
  });

  test('hourly maintenance cannot silently drop unsent low-priority work', async () => {
    await start();
    const id = await add('still waiting offline');
    await jest.advanceTimersByTimeAsync(60 * 60 * 1000);
    expect(readQueue().map((a) => a.id)).toContain(id);
    expect(readQueue()[0].status).toBe('pending');
  });

  test('exhausted retries remain durable failed work for an explicit owner action', async () => {
    await start(true);
    const id = await add('failed business work must remain visible');
    for (let i = 0; i < 5; i++) {
      const sync = offlineSyncService.triggerSync();
      await jest.advanceTimersByTimeAsync(32000);
      await sync;
    }
    const item = readQueue().find((a) => a.id === id);
    expect(item).toEqual(expect.objectContaining({ id, status: 'failed', syncAttempts: 5 }));
  });
  test('fourteen simulated offline days retain the same unsent intent', async () => {
    await start();
    const id = await add('long wait still belongs to its owner');
    await jest.advanceTimersByTimeAsync(14 * 24 * 60 * 60 * 1000);
    expect(readQueue()).toEqual([expect.objectContaining({ id, status: 'pending', syncAttempts: 0 })]);
  });

  test('clearing disposable cache preserves unsent queue data', async () => {
    await start();
    const id = await add('intent is not disposable cache');
    await storageService.clearCachedData();
    expect(readQueue().map((a) => a.id)).toContain(id);
  });

  test('explicit removal during backoff prevents a stale transport dispatch', async () => {
    await start(true);
    const id = await add('remove before admission');
    const queue = readQueue(); queue[0].syncAttempts = 1;
    await storageService.setString('offline_queue', JSON.stringify(queue));
    const syncing = offlineSyncService.triggerSync();
    await jest.advanceTimersByTimeAsync(0);
    expect(await offlineSyncService.removeActions([id])).toBe(1);
    await jest.advanceTimersByTimeAsync(3000);
    await syncing;
    expect(apiService.post).not.toHaveBeenCalled();
    expect(readQueue()).toHaveLength(0);
  });

  test('in-flight work cannot be deleted, retried or represented as stopped', async () => {
    await start(true);
    const id = await add('already admitted');
    let finish: ((response: ApiResponse<unknown>) => void) | undefined;
    const transport = new Promise<ApiResponse<unknown>>((resolve) => { finish = resolve; });
    jest.mocked(apiService.post).mockReturnValueOnce(transport);
    const syncing = offlineSyncService.triggerSync();
    await jest.advanceTimersByTimeAsync(0);
    expect(apiService.post).toHaveBeenCalledTimes(1);
    await expect(offlineSyncService.removeActions([id])).rejects.toThrow('in-flight');
    await expect(offlineSyncService.retryActions([id])).rejects.toThrow();
    await expect(offlineSyncService.clearQueue()).rejects.toThrow();
    expect(readQueue()[0]).toEqual(expect.objectContaining({ id, status: 'syncing' }));
    if (!finish) throw new Error('missing controlled transport resolver');
    finish({ success: false, error: 'controlled refusal after admission' });
    await syncing;
    expect(readQueue()[0].id).toBe(id);
  });

  test('a refused claim dispatches no transport and earns no successful sync', async () => {
    await start(true);
    const id = await add('claim must be durable before effect');
    const write = storageService.setString.bind(storageService);
    let refusedQueueWrite = false;
    jest.spyOn(storageService, 'setString').mockImplementation(async (key, value) => {
      if (key === 'offline_queue' && !refusedQueueWrite) { refusedQueueWrite = true; return false; }
      return write(key, value);
    });
    const result = await offlineSyncService.triggerSync();
    expect(refusedQueueWrite).toBe(true);
    expect(apiService.post).not.toHaveBeenCalled();
    expect(result.success).toBe(false);
    expect(readQueue()[0]).toEqual(expect.objectContaining({ id, status: 'pending', syncAttempts: 0 }));
  });

  test('metadata failure cannot turn a confirmed queue write into a failed enqueue', async () => {
    await start();
    jest.spyOn(storageService, 'setObject').mockRejectedValueOnce(new Error('controlled metadata unavailable'));
    const result = await add('one confirmed queue operation').catch(() => null);
    expect(result).not.toBeNull();
    expect(readQueue().map((a) => a.id)).toEqual([result]);
  });

  test('removal reconciles quota from the remaining queue instead of leaking usage', async () => {
    await start();
    const id = await add('remove this reservation');
    expect((await offlineSyncService.getStorageQuota()).usedBytes).toBeGreaterThan(0);
    await offlineSyncService.removeActions([id]);
    expect((await offlineSyncService.getStorageQuota()).usedBytes).toBe(0);
  });

  test('explicit clear does not leave a full quota for an empty queue', async () => {
    await start();
    await add('clear only when not in flight');
    await offlineSyncService.clearQueue();
    expect((await offlineSyncService.getStorageQuota()).usedBytes).toBe(0);
  });

  test('quota can be rebuilt after projection writes failed and the service reinitializes', async () => {
    await start();
    const metadata = jest.spyOn(storageService, 'setObject').mockResolvedValue(false);
    const id = await add('canonical queue survives missing projections');
    metadata.mockRestore();
    offlineSyncService.destroy();
    await start();
    expect(readQueue().map((a) => a.id)).toEqual([id]);
    expect((await offlineSyncService.getStorageQuota()).usedBytes).toBeGreaterThan(0);
  });

  test('sync state cannot hide retained pending work behind a stale zero projection', async () => {
    await start();
    await add('retained work is authoritative');
    const state = await offlineSyncService.getSyncState();
    await storageService.setObject('sync_state', { ...state, pendingCount: 0 });
    expect((await offlineSyncService.getSyncState()).pendingCount).toBe(1);
  });

  test('sync state refuses unreadable queue authority rather than reporting all synced', async () => {
    await start();
    await storageService.setString('offline_queue', '{controlled-unreadable');
    await expect(offlineSyncService.getSyncState()).rejects.toThrow();
  });

  test('sync state keeps exhausted failed work visible in the unresolved count', async () => {
    await start();
    await add('failed work is still unresolved');
    const queue = readQueue().map(action => ({ ...action, status: 'failed', syncAttempts: 5 }));
    await storageService.setString('offline_queue', JSON.stringify(queue));
    const state = await offlineSyncService.getSyncState();
    await storageService.setObject('sync_state', { ...state, pendingCount: 0 });
    expect((await offlineSyncService.getSyncState()).pendingCount).toBe(1);
  });

});
