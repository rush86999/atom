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
});
