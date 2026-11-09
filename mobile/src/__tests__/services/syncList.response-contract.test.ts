/** HTTP success is not evidence that a domain list was received. */
import { apiService } from '../../services/api';
import { storageService } from '../../services/storageService';
import { agentSyncService } from '../../services/agentSyncService';
import { workflowSyncService } from '../../services/workflowSyncService';
import { canvasSyncService } from '../../services/canvasSyncService';

jest.mock('../../services/api', () => ({ apiService: { get: jest.fn() } }));
jest.mock('../../services/storageService', () => ({ storageService: { getObject: jest.fn().mockResolvedValue(null), setObject: jest.fn().mockResolvedValue(true) } }));
jest.mock('../../services/offlineSyncService', () => ({ offlineSyncService: { queueAction: jest.fn() } }));

const cases = [
  { resource: 'agents', sync: () => agentSyncService.syncAgents('controlled-user', 'controlled-device') },
  { resource: 'workflows', sync: () => workflowSyncService.syncWorkflows('controlled-user', 'controlled-device') },
  { resource: 'canvases', sync: () => canvasSyncService.syncCanvases('controlled-user', 'controlled-device') },
] as const;

describe('Sync list response evidence', () => {
  beforeAll(async () => {
    jest.useFakeTimers();
    await agentSyncService.initialize();
    await workflowSyncService.initialize();
    await canvasSyncService.initialize();
  });
  beforeEach(() => {
    jest.clearAllMocks();
    jest.mocked(apiService.get).mockReset();
  });
  afterAll(() => {
    agentSyncService.destroy();
    workflowSyncService.destroy();
    canvasSyncService.destroy();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  test.each(cases)('$resource missing list refuses without a cache checkpoint', async ({ sync }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: {} });
    expect((await sync()).success).toBe(false);
    expect(storageService.setObject).not.toHaveBeenCalled();
  });

  test.each(cases)('$resource explicit application failure is not an empty successful sync', async ({ sync }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { success: false, error: 'controlled application refusal' } });
    expect((await sync()).success).toBe(false);
    expect(storageService.setObject).not.toHaveBeenCalled();
  });

  test.each(cases)('$resource malformed records cannot certify a sync or mutate the cache', async ({ resource, sync }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { [resource]: [{}] } });
    expect((await sync()).success).toBe(false);
    expect(storageService.setObject).not.toHaveBeenCalled();
  });

  test.each(cases)('$resource non-array list refuses before cache mutation', async ({ resource, sync }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { [resource]: 'not-a-list' } });
    expect((await sync()).success).toBe(false);
    expect(storageService.setObject).not.toHaveBeenCalled();
  });

  test.each(cases)('$resource genuine empty list remains a valid successful response', async ({ resource, sync }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { [resource]: [] } });
    expect(await sync()).toMatchObject({ success: true, synced: 0, failed: 0 });
  });
});
