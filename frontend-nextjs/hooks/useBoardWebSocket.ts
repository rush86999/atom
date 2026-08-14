'use client';

import { useEffect, useReducer } from 'react';
import { useWebSocket } from './useWebSocket';
import { type BoardTask } from '../lib/boards-api';

export type BoardEvent =
  | { type: 'board:task:created'; data: { task: Partial<BoardTask> } }
  | { type: 'board:task:moved'; data: { task: Partial<BoardTask> } }
  | { type: 'board:task:transitioned'; data: { task: Partial<BoardTask> } }
  | { type: 'board:task:updated'; data: { task: Partial<BoardTask> } }
  | { type: 'board:task:deleted'; data: { task_id: string } }
  | { type: 'board:comment:posted'; data: { task_id: string; comment: unknown } }
  | { type: string; data?: unknown };

type State = {
  lastEventAt: number;
  dirtyTaskIds: Set<string>;
};

type Action =
  | { kind: 'invalidate'; taskIds?: string[] }
  | { kind: 'noop' };

function reducer(_state: State, action: Action): State {
  switch (action.kind) {
    case 'invalidate': {
      // UNION with existing dirty IDs. Replacing the set (the original
      // behavior) silently dropped earlier dirty task IDs when multiple task
      // events arrived before the consumer flushed — those updates were never
      // refetched.
      const next = new Set(_state.dirtyTaskIds);
      for (const id of action.taskIds || []) {
        next.add(id);
      }
      return {
        lastEventAt: Date.now(),
        dirtyTaskIds: next,
      };
    }
    case 'noop':
    default:
      return _state;
  }
}

export function useBoardWebSocket(
  boardId: string | null,
  options: { linkedCanvasId?: string | null } = {},
) {
  const wsUrl = boardId ? buildBoardWsUrl(boardId) : null;

  const { lastMessage } = useWebSocket({
    url: wsUrl || undefined,
    autoConnect: Boolean(wsUrl),
  });

  const [state, dispatch] = useReducer(reducer, {
    lastEventAt: 0,
    dirtyTaskIds: new Set<string>(),
  });

  useEffect(() => {
    if (!lastMessage) return;
    const msg = lastMessage as BoardEvent;
    switch (msg.type) {
      case 'board:task:created':
      case 'board:task:moved':
      case 'board:task:transitioned':
      case 'board:task:updated':
      case 'board:task:deleted':
      case 'board:comment:posted':
        dispatch({
          kind: 'invalidate',
          taskIds: msg.data && (msg.data as any).task_id
            ? [(msg.data as any).task_id]
            : msg.data && (msg.data as any).task && (msg.data as any).task.id
            ? [(msg.data as any).task.id]
            : undefined,
        });
        break;
      default:
        dispatch({ kind: 'noop' });
    }
  }, [lastMessage]);

  return state;
}

function buildBoardWsUrl(boardId: string): string {
  return `/ws/boards/${boardId}`;
}
