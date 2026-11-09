import AsyncStorage from '@react-native-async-storage/async-storage';
import { CanvasService } from '../../services/canvasService';
import { clearAuthSession, commitAuthSession, readAccessTokenSnapshot } from '../../storage/secureTokenStorage';

async function signIn(id: string, workspace = 'workspace-one') {
  expect(await commitAuthSession(await readAccessTokenSnapshot(), {
    token: `controlled-cache-session-${id}`,
    expiresAt: '2099-01-01T00:00:00Z',
    userData: JSON.stringify({ id, workspace_id: workspace }),
  })).toBe(true);
}
const data = { id: 'shared-canvas-id', metadata: { id: 'shared-canvas-id' }, private_note: 'owner A observation' };

describe('canvas cache account/session boundary', () => {
  beforeEach(async () => { await clearAuthSession(); await AsyncStorage.clear(); });
  test('same owner can reopen the actual durable cache in a fresh service', async () => {
    await signIn('owner-A');
    await new CanvasService().cacheCanvas(data.id, data);
    expect((await new CanvasService().getCachedCanvas(data.id))?.data).toEqual(data);
  });
  test('a different account cannot read the same canvas cache key', async () => {
    await signIn('owner-A');
    await new CanvasService().cacheCanvas(data.id, data);
    await signIn('owner-B');
    expect(await new CanvasService().getCachedCanvas(data.id)).toBeNull();
  });
  test('a workspace change cannot reuse the previous workspace observation', async () => {
    await signIn('owner-A');
    await new CanvasService().cacheCanvas(data.id, data);
    await signIn('owner-A', 'workspace-two');
    expect(await new CanvasService().getCachedCanvas(data.id)).toBeNull();
  });
  test('logout makes the previous cached observation unavailable', async () => {
    await signIn('owner-A');
    await new CanvasService().cacheCanvas(data.id, data);
    await clearAuthSession();
    expect(await new CanvasService().getCachedCanvas(data.id)).toBeNull();
  });
  test('a network load started by the old account cannot return into a new session', async () => {
    await signIn('owner-A');
    let resolveFetch: (value: typeof data) => void = () => { throw new Error('fetch not started'); };
    let started: () => void = () => {};
    const ready = new Promise<void>(resolve => { started = resolve; });
    const fetched = new Promise<typeof data>(resolve => { resolveFetch = resolve; });
    const load = new CanvasService().loadCanvas(data.id, () => { started(); return fetched; });
    // Attach rejection observation before changing sessions.
    const result = load.then(value => ({ value }), () => ({ refused: true }));
    await ready;
    await signIn('owner-B');
    resolveFetch(data);
    expect(await result).toEqual({ refused: true });
    expect(await new CanvasService().getCachedCanvas(data.id)).toBeNull();
  });
  test('an old account background refresh cannot populate the next account cache', async () => {
    await signIn('owner-A');
    let resolveFetch: (value: typeof data) => void = () => { throw new Error('fetch not started'); };
    let started: () => void = () => {};
    const ready = new Promise<void>(resolve => { started = resolve; });
    const fetched = new Promise<typeof data>(resolve => { resolveFetch = resolve; });
    const refresh = new CanvasService().refreshCanvas(data.id, () => { started(); return fetched; }).catch(() => undefined);
    await ready;
    await signIn('owner-B');
    resolveFetch(data);
    await refresh;
    expect(await new CanvasService().getCachedCanvas(data.id)).toBeNull();
  });
  test('an anonymous caller cannot create a reusable canvas record', async () => {
    await new CanvasService().cacheCanvas(data.id, data);
    expect((await AsyncStorage.getAllKeys()).filter(key => key.startsWith('@atom_canvas_cache_'))).toEqual([]);
  });

});
