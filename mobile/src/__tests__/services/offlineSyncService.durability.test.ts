/** Serialized backing bytes, not UI objects that share mutable references. */
import NetInfo, { NetInfoStateType } from '@react-native-community/netinfo';
import { offlineSyncService, OfflineAction } from '../../services/offlineSyncService';
import { storageService } from '../../services/storageService';

jest.mock('@react-native-community/netinfo', () => ({
  __esModule: true,
  default: { fetch: jest.fn(), addEventListener: jest.fn(() => jest.fn()) },
  NetInfoStateType: { unknown: 'unknown' },
}));
jest.mock('../../services/api', () => ({ apiService: { post: jest.fn().mockResolvedValue({ success: false, error: 'controlled backend refusal' }) } }));

async function start(online = false) {
  jest.mocked(NetInfo.fetch).mockResolvedValueOnce({ type: NetInfoStateType.unknown, isConnected: online, isInternetReachable: online, details: null });
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
});
