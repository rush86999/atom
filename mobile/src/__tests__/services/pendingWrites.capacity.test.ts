/** Cache pressure must never silently erase queued user intent. */
const mockCapacityPost = jest.fn();
const mockCapacitySet = jest.fn();
const mockCapacityGet = jest.fn();
const mockCapacityStorage = new Map<string, string>();

const capacities = [
  { resource: 'canvas', capacity: 50, key: 'canvas_cache', rows: 'pendingFormSubmissions' },
  { resource: 'workflow', capacity: 100, key: 'workflow_cache', rows: 'pendingTriggers' },
] as const;

describe('Pending write capacity preserves accepted intent', () => {
  beforeEach(() => {
    jest.resetModules(); jest.useFakeTimers(); mockCapacityStorage.clear();
    mockCapacityPost.mockReset();
    mockCapacityGet.mockReset().mockImplementation(async (key: string) => JSON.parse(mockCapacityStorage.get(key) ?? 'null'));
    mockCapacitySet.mockReset().mockImplementation(async (key: string, value: unknown) => { mockCapacityStorage.set(key, JSON.stringify(value)); return true; });
    jest.doMock('../../services/api', () => ({ apiService: { post: mockCapacityPost, get: jest.fn() } }));
    jest.doMock('../../services/storageService', () => ({ storageService: { getObject: mockCapacityGet, setObject: mockCapacitySet } }));
    jest.doMock('../../storage/secureTokenStorage', () => ({ readAuthSessionSnapshot: async () => ({ token: 'controlled-session', generation: 1, userData: JSON.stringify({ id: 'capacity-owner', workspace_id: 'capacity-workspace' }), deviceId: 'capacity-device' }), isAccessTokenSnapshotCurrent: () => true }));
    jest.doMock('../../services/offlineSyncService', () => ({ offlineSyncService: { getSyncState: () => ({ syncInProgress: true }) } }));
  });
  afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });
  test.each(capacities)('$resource refuses new work at capacity instead of evicting old intent', async family => {
    const rows = Array.from({ length: family.capacity }, (_, i) => ({ id: `intent-${i}`, canvasId: `canvas-${i}`, workflowId: `workflow-${i}`, formData: { observed: i }, input: { observed: i }, submittedAt: '2026-11-09T10:00:00.000Z', createdAt: '2026-11-09T10:00:00.000Z', status: 'pending', deliveryStatus: 'pending', priority: 5, retryCount: 0, userId: 'capacity-owner', workspaceId: 'capacity-workspace', deviceId: 'capacity-device' }));
    mockCapacityStorage.set(family.key, JSON.stringify({ canvases: {}, agents: {}, workflows: {}, executions: {}, htmlCache: {}, cssCache: {}, favorites: [], lastSyncAt: null, [family.rows]: rows }));
    const before = mockCapacityStorage.get(family.key);
    let accepted: boolean;
    if (family.resource === 'canvas') {
      const { canvasSyncService: service }: typeof import('../../services/canvasSyncService') = require('../../services/canvasSyncService');
      await service.initialize();
      accepted = await service.submitForm('new-canvas', { observed: 'new' }, 'capacity-owner', 'capacity-device');
      service.destroy();
    } else {
      const { workflowSyncService: service }: typeof import('../../services/workflowSyncService') = require('../../services/workflowSyncService');
      await service.initialize();
      accepted = await service.triggerWorkflow('new-workflow', { observed: 'new' }, 'capacity-owner', 'capacity-device');
      service.destroy();
    }
    expect(accepted).toBe(false);
    expect(mockCapacityStorage.get(family.key)).toBe(before);
    expect(mockCapacitySet).not.toHaveBeenCalled();
    expect(mockCapacityPost).not.toHaveBeenCalled();
  });
});
