/**
 * useBoardWebSocket — supplemental tests for the remaining branches:
 * events without any task id, unknown event types (noop), and the
 * null-boardId path (wsUrl null).
 */
import { renderHook, act } from '@testing-library/react';

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

describe('useBoardWebSocket (branch coverage)', () => {
  it('falls back to no dirty ids when event data has no task id', () => {
    const { result } = renderHook(() => useBoardWebSocket('board-1'));
    act(() => {
      _setLastMessage({ type: 'board:task:created', data: { task: {} } });
    });
    expect(result.current.dirtyTaskIds.size).toBe(0);
    expect(result.current.lastEventAt).toBeGreaterThan(0);
  });

  it('handles an event with no data payload at all', () => {
    const { result } = renderHook(() => useBoardWebSocket('board-1'));
    act(() => {
      _setLastMessage({ type: 'board:task:deleted' });
    });
    expect(result.current.dirtyTaskIds.size).toBe(0);
  });

  it('dispatches noop for unknown event types', () => {
    const { result } = renderHook(() => useBoardWebSocket('board-1'));
    const before = result.current.lastEventAt;
    act(() => {
      _setLastMessage({ type: 'board:unknown:thing' });
    });
    expect(result.current.lastEventAt).toBe(before);
  });

  it('ignores null messages', () => {
    const { result } = renderHook(() => useBoardWebSocket('board-1'));
    const before = result.current.lastEventAt;
    act(() => {
      _setLastMessage(null);
    });
    expect(result.current.lastEventAt).toBe(before);
  });

  it('works with a null boardId (wsUrl undefined)', () => {
    const { result } = renderHook(() => useBoardWebSocket(null));
    act(() => {
      _setLastMessage({ type: 'board:task:updated', data: { task: { id: 'Z' } } });
    });
    expect(result.current.dirtyTaskIds.has('Z')).toBe(true);
  });
});
