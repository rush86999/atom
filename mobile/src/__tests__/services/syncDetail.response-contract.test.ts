/** A typed cache must not manufacture a domain record from transport success. */
import { apiService } from '../../services/api';
import { storageService } from '../../services/storageService';
import { agentSyncService } from '../../services/agentSyncService';
import { workflowSyncService } from '../../services/workflowSyncService';
import { canvasSyncService } from '../../services/canvasSyncService';

jest.mock('../../services/api', () => ({ apiService: { get: jest.fn() } }));
jest.mock('../../services/storageService', () => ({ storageService: { getObject: jest.fn().mockResolvedValue(null), setObject: jest.fn().mockResolvedValue(true) } }));
jest.mock('../../services/offlineSyncService', () => ({ offlineSyncService: { queueAction: jest.fn() } }));

const cases = [
  { resource: 'agent', clear: () => agentSyncService.clearCache(), get: (id: string) => agentSyncService.getAgent(id) },
  { resource: 'canvas', clear: () => canvasSyncService.clearCache(), get: (id: string) => canvasSyncService.getCanvas(id) },
  { resource: 'workflow', clear: () => workflowSyncService.clearCache(), get: (id: string) => workflowSyncService.getWorkflow(id) },
  { resource: 'execution', clear: () => workflowSyncService.clearCache(), get: (id: string) => workflowSyncService.getExecution(id) },
] as const;
let sequence = 0;
function record(id: string) {
  return { id, name: 'Observed', description: 'Observed', maturityLevel: 'INTERN', capabilities: ['chat'], systemPrompt: 'Observed prompt', title: 'Observed canvas', type: 'chart', data: { observed: true }, definition: { steps: [] }, schema: {}, isActive: false, workflowId: 'workflow-opaque-01', status: 'completed', input: { quantity: 0 }, logs: [], createdAt: '2026-11-09T10:00:00.000Z', updatedAt: '2026-11-09T11:00:00.000Z', startedAt: '2026-11-09T10:00:00.000Z', completedAt: '2026-11-09T11:00:00.000Z', source_revision: 'revision-0001', source_qualifiers: { record: 'opaque-0001', review: false } };
}

describe('Sync detail response evidence', () => {
  beforeAll(async () => {
    jest.useFakeTimers();
    await agentSyncService.initialize(); await workflowSyncService.initialize(); await canvasSyncService.initialize();
  });
  beforeEach(() => { jest.clearAllMocks(); jest.mocked(apiService.get).mockReset(); });
  afterAll(() => {
    agentSyncService.destroy(); workflowSyncService.destroy(); canvasSyncService.destroy();
    jest.clearAllTimers(); jest.useRealTimers();
  });
  test.each(cases)('$resource rejects incomplete detail without cache persistence', async ({ get }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: {} });
    expect(await get(`incomplete-${++sequence}`)).toBeNull();
    expect(storageService.setObject).not.toHaveBeenCalled();
  });
  test.each(cases)('$resource refuses a different opaque record id', async ({ get }) => {
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: record('different-opaque-id') });
    expect(await get(`requested-${++sequence}`)).toBeNull();
    expect(storageService.setObject).not.toHaveBeenCalled();
  });
  test.each(cases)('$resource rejects invalid temporal evidence', async ({ get }) => {
    const id = `invalid-time-${++sequence}`;
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: { ...record(id), createdAt: '2026-02-30T00:00:00Z', startedAt: '2026-02-30T00:00:00Z' } });
    expect(await get(id)).toBeNull();
    expect(storageService.setObject).not.toHaveBeenCalled();
  });
  test.each(cases)('$resource decodes dates and retains source qualifiers', async ({ resource, get }) => {
    const id = `valid-${++sequence}`;
    jest.mocked(apiService.get).mockResolvedValue({ success: true, data: record(id) });
    const observed = await get(id);
    expect(observed).toEqual(expect.objectContaining({ id, source_revision: 'revision-0001', source_qualifiers: { record: 'opaque-0001', review: false } }));
    expect(resource === 'execution' ? (observed as { startedAt: Date }).startedAt : (observed as { createdAt: Date }).createdAt).toBeInstanceOf(Date);
    expect(storageService.setObject).toHaveBeenCalledTimes(1);
  });
  test.each(cases)('$resource failed persistence does not seed a successful future cache hit', async ({ get }) => {
    const id = `persistence-failed-${++sequence}`;
    jest.mocked(apiService.get).mockResolvedValueOnce({ success: true, data: record(id) }).mockResolvedValue({ success: false, error: 'Controlled unavailable' });
    jest.mocked(storageService.setObject).mockResolvedValueOnce(false);
    expect(await get(id)).toBeNull();
    expect(await get(id)).toBeNull();
    expect(apiService.get).toHaveBeenCalledTimes(2);
  });

  test.each(cases)('$resource overlapping reads retain both verified records', async ({ get }) => {
    const firstId = `overlap-first-${++sequence}`;
    const secondId = `overlap-second-${++sequence}`;
    jest.mocked(apiService.get).mockImplementation(async (url: string) => ({ success: true, data: record(url.split('/').pop() || '') }));
    const [first, second] = await Promise.all([get(firstId), get(secondId)]);
    expect(first).toEqual(expect.objectContaining({ id: firstId }));
    expect(second).toEqual(expect.objectContaining({ id: secondId }));
    jest.mocked(apiService.get).mockResolvedValue({ success: false, error: 'Controlled offline after both completions' });
    expect(await get(firstId)).toEqual(expect.objectContaining({ id: firstId }));
    expect(await get(secondId)).toEqual(expect.objectContaining({ id: secondId }));
  });

  test.each(cases)('$resource reset refuses a response started before the reset', async ({ get, clear }) => {
    const id = `reset-old-${++sequence}`;
    let deliver: ((value: { success: boolean; data: ReturnType<typeof record> }) => void) | undefined;
    jest.mocked(apiService.get).mockImplementationOnce(() => new Promise(resolve => { deliver = resolve; }));
    const pending = get(id);
    await Promise.resolve();
    await clear();
    if (!deliver) throw new Error('Controlled transport was not dispatched');
    deliver({ success: true, data: record(id) });
    expect(await pending).toBeNull();
    jest.mocked(apiService.get).mockResolvedValue({ success: false, error: 'Controlled offline after reset' });
    expect(await get(id)).toBeNull();
  });

  test('canvas target invalidation retains independent useful detail work', async () => {
    const targetId = `invalidate-target-${++sequence}`;
    const independentId = `retain-independent-${++sequence}`;
    const deliveries = new Map<string, (value: { success: boolean; data: ReturnType<typeof record> }) => void>();
    jest.mocked(apiService.get).mockImplementation((url: string) => new Promise(resolve => { deliveries.set(url.split('/').pop() || '', resolve); }));
    const target = canvasSyncService.getCanvas(targetId);
    const independent = canvasSyncService.getCanvas(independentId);
    await Promise.resolve();
    await canvasSyncService.invalidateCache(targetId);
    for (const id of [targetId, independentId]) {
      const deliver = deliveries.get(id);
      if (!deliver) throw new Error('Controlled detail request was not dispatched');
      deliver({ success: true, data: record(id) });
    }
    expect(await target).toBeNull();
    expect(await independent).toEqual(expect.objectContaining({ id: independentId }));
    jest.mocked(apiService.get).mockResolvedValue({ success: false, error: 'Controlled offline' });
    expect(await canvasSyncService.getCanvas(targetId)).toBeNull();
    expect(await canvasSyncService.getCanvas(independentId)).toEqual(expect.objectContaining({ id: independentId }));
  });

});
