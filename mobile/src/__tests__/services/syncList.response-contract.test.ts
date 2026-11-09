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

function completeRecord(id = 'record-1') {
  return { id, name: 'Controlled record', description: 'Observed', maturityLevel: 'INTERN', capabilities: ['chat'], systemPrompt: 'Observed prompt', title: 'Controlled canvas', type: 'chart', data: { observed: true }, definition: { steps: [] }, schema: {}, isActive: false, createdAt: '2026-11-09T10:00:00.000Z', updatedAt: '2026-11-09T11:00:00.000Z', source_revision: 'revision-0001', source_qualifiers: { record: 'opaque-0001', conditions: ['review-required'] } };
}

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

  test.each(cases)('$resource preserves observed source qualifiers on accepted records', async ({ resource, sync }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { [resource]: [completeRecord()] } });
    expect((await sync()).success).toBe(true);
    expect(storageService.setObject).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ [resource]: expect.objectContaining({ 'record-1': expect.objectContaining({ source_revision: 'revision-0001', source_qualifiers: { record: 'opaque-0001', conditions: ['review-required'] } }) }) }));
  });

  test.each(cases)('$resource contradictory response branches refuse instead of choosing one', async ({ resource, sync }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { [resource]: [], success: true, data: { success: false, error: 'controlled contradictory branch' } } });
    expect((await sync()).success).toBe(false);
    expect(storageService.setObject).not.toHaveBeenCalled();
  });

  test.each(cases)('$resource conflicting duplicate identities refuse before cache mutation', async ({ resource, sync }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { [resource]: [completeRecord(), { ...completeRecord(), name: 'Different source material', source_revision: 'revision-0002' }] } });
    expect((await sync()).success).toBe(false);
    expect(storageService.setObject).not.toHaveBeenCalled();
  });

  test.each(cases)('$resource rejects ambiguous or impossible timestamp material', async ({ resource, sync }) => {
    for (const updatedAt of ['01/02/2026', '2026-02-30T00:00:00Z', '2026-11-09T11:00:00']) {
      jest.mocked(storageService.setObject).mockClear();
      jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { [resource]: [{ ...completeRecord(), updatedAt }] } });
      expect((await sync()).success).toBe(false);
      expect(storageService.setObject).not.toHaveBeenCalled();
    }
  });

  test.each(cases)('$resource preserves false and zero qualifiers and an explicit offset instant', async ({ resource, sync }) => {
    const row = { ...completeRecord(), updatedAt: '2026-11-09T13:00:00+02:00', source_qualifiers: { flag: false, quantity: 0 } };
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { success: true, data: [row] } });
    expect((await sync()).success).toBe(true);
    expect(storageService.setObject).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ [resource]: expect.objectContaining({ 'record-1': expect.objectContaining({ updatedAt: new Date('2026-11-09T11:00:00.000Z'), source_qualifiers: { flag: false, quantity: 0 } }) }) }));
  });

  test.each(cases)('$resource genuine wrapped empty list is supported', async ({ sync }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { success: true, data: [] } });
    expect(await sync()).toMatchObject({ success: true, synced: 0, failed: 0 });
  });

  test.each(cases)('$resource genuine empty list remains a valid successful response', async ({ resource, sync }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { [resource]: [] } });
    expect(await sync()).toMatchObject({ success: true, synced: 0, failed: 0 });
  });
});
