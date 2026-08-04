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
let _setLastMessage: (m: any) => void = () => {};

jest.mock('../useWebSocket', () => ({
  useWebSocket: () => {
    const React = require('react');
    const [lm, setLm] = React.useState(null);
    _setLastMessage = setLm;
    return { lastMessage: lm };
  },
}));

import { useBoardWebSocket } from '../useBoardWebSocket';

describe('useBoardWebSocket dirtyTaskIds accumulation', () => {
  it('unions task IDs across consecutive events (does not replace)', () => {
    const { result } = renderHook(() => useBoardWebSocket('board-1'));

    // First task updated.
    act(() => {
      _setLastMessage({ type: 'board:task:updated', data: { task: { id: 'A' } } });
    });
    expect(result.current.dirtyTaskIds.has('A')).toBe(true);

    // Second task updated before a flush.
    act(() => {
      _setLastMessage({ type: 'board:task:updated', data: { task: { id: 'B' } } });
    });

    // Both must remain dirty — the original code replaced the set, dropping 'A'.
    expect(result.current.dirtyTaskIds.has('A')).toBe(true);
    expect(result.current.dirtyTaskIds.has('B')).toBe(true);
  });

  it('accumulates task_id-style events (deleted/comment)', () => {
    const { result } = renderHook(() => useBoardWebSocket('board-1'));

    act(() => {
      _setLastMessage({ type: 'board:task:updated', data: { task_id: 'T1' } });
    });
    act(() => {
      _setLastMessage({ type: 'board:comment:posted', data: { task_id: 'T2', comment: {} } });
    });

    expect(result.current.dirtyTaskIds.has('T1')).toBe(true);
    expect(result.current.dirtyTaskIds.has('T2')).toBe(true);
  });
});
