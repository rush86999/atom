/** Real session + owner helper + Axios + cache consumer; controlled transports only. */
import type { AxiosAdapter } from 'axios';

const families = [
  { name: 'workflow', key: 'workflow_cache', cache: () => ({ workflows: {}, executions: {}, lastSyncAt: null, pendingTriggers: [{ id: 'operation-001', workflowId: 'workflow-001', input: { observed: 0 }, priority: 5, createdAt: '2026-11-09T10:00:00Z', retryCount: 0, deliveryStatus: 'pending', userId: 'owner-001', workspaceId: 'workspace-001', deviceId: 'device-001' }] }),
    load: async () => { const { workflowSyncService: service }: typeof import('../../services/workflowSyncService') = require('../../services/workflowSyncService'); await service.initialize(); return { flush: () => service.syncExecutions('owner-001', 'device-001'), destroy: () => service.destroy() }; } },
  { name: 'canvas', key: 'canvas_cache', cache: () => ({ canvases: {}, htmlCache: {}, cssCache: {}, favorites: [], lastSyncAt: null, pendingFormSubmissions: [{ canvasId: 'canvas-001', formData: { observed: 0 }, submittedAt: '2026-11-09T10:00:00Z', status: 'pending', deliveryStatus: 'pending', userId: 'owner-001', workspaceId: 'workspace-001', deviceId: 'device-001' }] }),
    load: async () => { const { canvasSyncService: service }: typeof import('../../services/canvasSyncService') = require('../../services/canvasSyncService'); await service.initialize(); return { flush: () => service.syncFormSubmissions('owner-001', 'device-001'), destroy: () => service.destroy() }; } },
];
const modes: Array<'current' | 'lookup-change' | 'marker-change'> = ['current', 'lookup-change', 'marker-change'];

describe('Pending owner end-to-end in the controlled service stack', () => {
  beforeEach(() => { jest.resetModules(); jest.useFakeTimers(); });
  afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });

  test.each(families.flatMap(family => modes.map(mode => ({ family, mode, name: family.name }))))('$name / $mode binds the exact authenticated request', async ({ family, mode }) => {
    const secure = new Map([['atom_access_token', 'controlled-owner-A'], ['atom_device_id', 'device-001']]);
    const ordinary = new Map([['atom_user_data', JSON.stringify({ id: 'owner-001', workspace_id: 'workspace-001' })]]);
    const durable = new Map([[family.key, JSON.stringify(family.cache())]]);
    const effects: string[] = [];
    const observations: Array<{ method: string | undefined; url: string | undefined; authorization: unknown; hasConstraint: boolean }> = [];
    let markerChanged = false;
    jest.doMock('expo-secure-store', () => ({ WHEN_UNLOCKED: 'WHEN_UNLOCKED', getItemAsync: jest.fn(async (key: string) => secure.get(key) ?? null), setItemAsync: jest.fn(async (key: string, value: string) => { secure.set(key, value); }), deleteItemAsync: jest.fn(async (key: string) => { secure.delete(key); }) }));
    jest.doMock('@react-native-async-storage/async-storage', () => ({ getItem: jest.fn(async (key: string) => ordinary.get(key) ?? null), setItem: jest.fn(async (key: string, value: string) => { ordinary.set(key, value); }), removeItem: jest.fn(async (key: string) => { ordinary.delete(key); }) }));
    jest.dontMock('../../storage/secureTokenStorage');
    jest.dontMock('../../services/pendingWriteOwner');
    jest.dontMock('../../services/api');
    const auth: typeof import('../../storage/secureTokenStorage') = require('../../storage/secureTokenStorage');
    jest.doMock('../../services/storageService', () => ({ storageService: {
      getObject: async (key: string) => JSON.parse(durable.get(key) ?? 'null'),
      setObject: async (key: string, value: unknown) => {
        durable.set(key, JSON.stringify(value));
        if (mode === 'marker-change' && !markerChanged) { markerChanged = true; await auth.secureSet('atom_access_token', 'controlled-owner-B'); }
        return true;
      },
    } }));
    jest.doMock('../../services/offlineSyncService', () => ({ offlineSyncService: {} }));
    const adapter: AxiosAdapter = async config => {
      observations.push({ method: config.method, url: config.url, authorization: config.headers.Authorization, hasConstraint: 'expectedAccessTokenSnapshot' in config });
      if (config.method === 'get' && config.url === '/api/auth/me') {
        if (mode === 'lookup-change') await auth.secureSet('atom_access_token', 'controlled-owner-B');
        return { config, status: 200, statusText: 'OK', headers: {}, data: { id: 'owner-001', workspace_id: 'workspace-001', status: 'active' } };
      }
      if (config.method !== 'post') throw new Error('Unexpected controlled transport');
      effects.push(config.url ?? 'missing');
      return { config, status: 200, statusText: 'OK', headers: {}, data: { accepted: true } };
    };
    const axiosModule: typeof import('axios') = require('axios');
    axiosModule.default.defaults.adapter = adapter;
    const client = await family.load();
    await client.flush();
    expect(effects).toHaveLength(mode === 'current' ? 1 : 0);
    expect(observations).toHaveLength(mode === 'current' ? 2 : 1);
    for (const observation of observations) {
      expect(observation.authorization).toBe('Bearer controlled-owner-A');
      expect(observation.hasConstraint).toBe(false);
    }
    expect(Array.from(durable.values()).join('')).not.toContain('controlled-owner-A');
    expect(Array.from(durable.values()).join('')).not.toContain('controlled-owner-B');
    client.destroy();
  });
});
