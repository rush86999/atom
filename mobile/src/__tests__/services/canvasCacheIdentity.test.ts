import AsyncStorage from '@react-native-async-storage/async-storage';
import { CanvasService } from '../../services/canvasService';

// Retained caches are observations, never authority. Corrupt envelopes must not
// supply a different canvas or evade expiry by omitting their timestamps.
describe('canvas cache identity and lifetime boundary', () => {
  beforeEach(async () => { await AsyncStorage.clear(); });
  const record = () => ({canvasId: 'requested', data: {id: 'requested'}, metadata: {id: 'requested'}, cachedAt: Date.now(), expiresAt: Date.now() + 60000, size: 20});
  test('matching current envelope remains readable', async () => {
    await AsyncStorage.setItem('@atom_canvas_cache_requested', JSON.stringify(record()));
    expect((await new CanvasService().getCachedCanvas('requested'))?.data.id).toBe('requested');
  });
  test('wrong envelope identity refuses', async () => {
    await AsyncStorage.setItem('@atom_canvas_cache_requested', JSON.stringify({...record(), canvasId: 'foreign'}));
    expect(await new CanvasService().getCachedCanvas('requested')).toBeNull();
  });
  test('wrong payload identity refuses', async () => {
    await AsyncStorage.setItem('@atom_canvas_cache_requested', JSON.stringify({...record(), data: {id: 'foreign'}}));
    expect(await new CanvasService().getCachedCanvas('requested')).toBeNull();
  });
  test('missing expiry refuses rather than living forever', async () => {
    const {expiresAt, ...missing} = record();
    await AsyncStorage.setItem('@atom_canvas_cache_requested', JSON.stringify(missing));
    expect(await new CanvasService().getCachedCanvas('requested')).toBeNull();
  });
});
