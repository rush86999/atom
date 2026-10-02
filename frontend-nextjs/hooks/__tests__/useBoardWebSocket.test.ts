/**
 * useBoardWebSocket reducer tests.
 *
 * The hook accumulates dirty task IDs across WS events so a consumer can
 * refetch only what changed. The reducer MUST union new task IDs with the
 * existing set — replacing the set (the original behavior) silently drops
 * earlier dirty IDs when multiple task events arrive before a flush.
 */
import { renderHook, act } from '@testing-library/react';

// Mutable lastMessage the test drives into the hook's effect.

// The hook reads board events through the socket's `onMessage` listener — a
// drag emits create → move → transition as a burst, and the `lastMessage`
// state slot coalesces that to one frame, so the cache was invalidated for
// only the last event. The mock delivers to listeners as well as the slot.
import { wsMock } from '../../tests/helpers/wsMock';

jest.mock('../useWebSocket', () => ({
  useWebSocket: require('../../tests/helpers/wsMock').createWebSocketMock(),
}));

import { useBoardWebSocket } from '../useBoardWebSocket';

describe('useBoardWebSocket dirtyTaskIds accumulation', () => {
  it('unions task IDs across consecutive events (does not replace)', () => {
    const { result } = renderHook(() => useBoardWebSocket('board-1'));

    // First task updated.
    act(() => {
      wsMock().emit({ type: 'board:task:updated', data: { task: { id: 'A' } } });
    });
    expect(result.current.dirtyTaskIds.has('A')).toBe(true);

    // Second task updated before a flush.
    act(() => {
      wsMock().emit({ type: 'board:task:updated', data: { task: { id: 'B' } } });
    });

    // Both must remain dirty — the original code replaced the set, dropping 'A'.
    expect(result.current.dirtyTaskIds.has('A')).toBe(true);
    expect(result.current.dirtyTaskIds.has('B')).toBe(true);
  });

  it('accumulates task_id-style events (deleted/comment)', () => {
    const { result } = renderHook(() => useBoardWebSocket('board-1'));

    act(() => {
      wsMock().emit({ type: 'board:task:updated', data: { task_id: 'T1' } });
    });
    act(() => {
      wsMock().emit({ type: 'board:comment:posted', data: { task_id: 'T2', comment: {} } });
    });

    expect(result.current.dirtyTaskIds.has('T1')).toBe(true);
    expect(result.current.dirtyTaskIds.has('T2')).toBe(true);
  });
});
