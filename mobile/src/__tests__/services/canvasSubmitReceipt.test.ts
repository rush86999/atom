/** Controlled transport, real queued consumer; server receipt is not HTTP success. */
describe('canvas queued submission receipt boundary', () => {
  beforeEach(() => { jest.resetModules(); jest.useFakeTimers(); });
  afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });
  test.each(['verified', 'missing', 'unverified', 'wrong-canvas', 'wrong-operation'] as const)('%s receipt', async mode => {
    let durable = {canvases: {}, htmlCache: {}, cssCache: {}, favorites: [], lastSyncAt: null, pendingFormSubmissions: [{canvasId: 'canvas-001', operationId: 'logical-001', formData: {quantity: 0}, submittedAt: '2026-11-09T10:00:00Z', status: 'pending', deliveryStatus: 'pending', userId: 'owner-001', workspaceId: 'workspace-001', deviceId: 'device-001'}]};
    const receipt = {success: true, canvas_id: mode === 'wrong-canvas' ? 'foreign' : 'canvas-001', operation_id: mode === 'wrong-operation' ? 'foreign' : 'logical-001', audit_id: 'audit-001', verification: {status: mode === 'unverified' ? 'unavailable' : 'verified', effect: 'committed'}, data: {canvas_id: 'canvas-001', submitted: true}};
    const post = jest.fn(async () => ({success: true, data: mode === 'missing' ? {accepted: true} : receipt}));
    jest.doMock('../../services/api', () => ({apiService: {post, get: jest.fn()}}));
    jest.doMock('../../services/storageService', () => ({storageService: {getObject: async () => durable, setObject: async (_key: string, value: typeof durable) => {durable = JSON.parse(JSON.stringify(value)); return true;}}}));
    jest.doMock('../../services/pendingWriteOwner', () => ({authorizePendingWriteOwner: async () => ({token: 'controlled', generation: 0})}));
    jest.doMock('../../storage/secureTokenStorage', () => ({isAccessTokenSnapshotCurrent: () => true}));
    jest.doMock('../../services/offlineSyncService', () => ({offlineSyncService: {}}));
    const {canvasSyncService: service}: typeof import('../../services/canvasSyncService') = require('../../services/canvasSyncService');
    await service.initialize();
    await service.syncFormSubmissions('owner-001', 'device-001');
    expect(durable.pendingFormSubmissions).toHaveLength(mode === 'verified' ? 0 : 1);
    if (mode !== 'verified') {
      expect(durable.pendingFormSubmissions[0].deliveryStatus).toBe('effect_unknown');
      await service.syncFormSubmissions('owner-001', 'device-001');
      expect(post).toHaveBeenCalledTimes(1);
    }
    expect(post).toHaveBeenCalledWith('/api/canvas/submit', {canvas_id: 'canvas-001', operation_id: 'logical-001', form_data: {quantity: 0}}, expect.anything());
    service.destroy();
  });
});
