/**
 * CollaborativeCursor Component Tests
 *
 * Tests verify the real CollaborativeCursor component
 * (components/Collaboration/CollaborativeCursor.tsx):
 * - WebSocket connection lifecycle (URL derivation, close on unmount)
 * - cursor_update messages render remote cursors (name label, position,
 *   selection indicator) and ignore the current user's own cursor
 * - user_left removes a cursor; inactivity timeout removes stale cursors
 * - malformed messages are swallowed (fail-soft, no crash)
 * - renders nothing when there are no remote cursors
 *
 * Uses the MockWebSocket installed by tests/setup.ts; messages are driven by
 * invoking the instance's `_onmessage` handler directly. The mock's tracking
 * arrays accumulate across tests, so each test snapshots the instance list
 * length before rendering and resolves its own instance afterwards.
 */
import React from 'react';
import { render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import CollaborativeCursor, { CollaborativeCursorHandle } from '../CollaborativeCursor';

const MockWebSocket = (global as any).WebSocket as any;
const wsInstances = () => MockWebSocket.getMockInstances();

const renderCursor = (props: {
  workflowId?: string;
  sessionId?: string;
  currentUserId?: string;
  ref?: React.Ref<CollaborativeCursorHandle>;
}) => {
  const before = wsInstances().length;
  const result = render(
    <CollaborativeCursor
      ref={props.ref}
      workflowId={props.workflowId || 'wf-1'}
      sessionId={props.sessionId}
      currentUserId={props.currentUserId}
    />
  );
  const instance = wsInstances()[before];
  return { ...result, instance, wsCreated: wsInstances().length - before };
};

const sendMessage = (instance: any, message: unknown) => {
  act(() => {
    instance._onmessage({ data: JSON.stringify(message) });
  });
};

describe('CollaborativeCursor', () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  it('renders nothing when no sessionId is provided', () => {
    const { container, wsCreated } = renderCursor({});
    expect(container.firstChild).toBeNull();
    expect(wsCreated).toBe(0);
  });

  it('opens a WebSocket with the workflow session URL derived from the API base', () => {
    const { instance, wsCreated } = renderCursor({ sessionId: 'sess-1', currentUserId: 'user-1' });
    expect(wsCreated).toBe(1);
    expect(instance._url).toBe('/ws/sess-1/user-1');
  });

  it('renders a remote cursor with name, position and selection indicator', () => {
    const { instance } = renderCursor({ sessionId: 'sess-1', currentUserId: 'me' });

    sendMessage(instance, {
      type: 'cursor_update',
      user_id: 'user-2',
      user_name: 'Alice',
      user_color: '#ff0000',
      cursor_position: { x: 120, y: 240 },
      selected_node: 'node-42',
      timestamp: '2024-01-01T00:00:00Z',
    });

    const container = document.querySelector('.collaborative-cursors-container');
    expect(container).not.toBeNull();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText(/node-42/)).toBeInTheDocument();
    const cursor = container?.querySelector('.collaborative-cursor');
    expect(cursor).toHaveStyle({ left: '120px', top: '240px' });
    expect(cursor?.querySelector('svg path')).toHaveAttribute('fill', '#ff0000');
  });

  it("does not render the current user's own cursor", () => {
    const { instance } = renderCursor({ sessionId: 'sess-1', currentUserId: 'me' });

    sendMessage(instance, {
      type: 'cursor_update',
      user_id: 'me',
      user_name: 'Myself',
      cursor_position: { x: 10, y: 10 },
    });

    expect(document.querySelector('.collaborative-cursors-container')).toBeNull();
    expect(screen.queryByText('Myself')).not.toBeInTheDocument();
  });

  it('defaults the user color and name when the message omits them', () => {
    const { instance } = renderCursor({ sessionId: 'sess-1', currentUserId: 'me' });

    sendMessage(instance, {
      type: 'cursor_update',
      user_id: 'anon-1',
      cursor_position: { x: 1, y: 2 },
    });

    expect(screen.getByText('anon-1')).toBeInTheDocument();
    const cursor = document.querySelector('.collaborative-cursor');
    expect(cursor?.querySelector('svg path')).toHaveAttribute('fill', '#2196F3');
  });

  it('removes a cursor when the user leaves', () => {
    const { instance } = renderCursor({ sessionId: 'sess-1', currentUserId: 'me' });

    sendMessage(instance, {
      type: 'cursor_update',
      user_id: 'user-2',
      user_name: 'Alice',
      cursor_position: { x: 1, y: 2 },
    });
    expect(screen.getByText('Alice')).toBeInTheDocument();

    sendMessage(instance, { type: 'user_left', user_id: 'user-2' });
    expect(screen.queryByText('Alice')).not.toBeInTheDocument();
    expect(document.querySelector('.collaborative-cursors-container')).toBeNull();
  });

  it('removes a cursor after 10 seconds of inactivity', () => {
    jest.useFakeTimers();
    const { instance } = renderCursor({ sessionId: 'sess-1', currentUserId: 'me' });

    sendMessage(instance, {
      type: 'cursor_update',
      user_id: 'user-2',
      user_name: 'Alice',
      cursor_position: { x: 1, y: 2 },
    });
    expect(screen.getByText('Alice')).toBeInTheDocument();

    act(() => {
      jest.advanceTimersByTime(10000);
    });
    expect(screen.queryByText('Alice')).not.toBeInTheDocument();
  });

  it('swallows malformed WebSocket messages without crashing', () => {
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    const { instance } = renderCursor({ sessionId: 'sess-1', currentUserId: 'me' });

    act(() => {
      instance._onmessage({ data: '{not valid json' });
    });
    expect(errorSpy).toHaveBeenCalled();
    expect(document.querySelector('.collaborative-cursors-container')).toBeNull();
    errorSpy.mockRestore();
  });

  it('sends heartbeats while the socket is open', () => {
    jest.useFakeTimers();
    const { instance } = renderCursor({ sessionId: 'sess-1', currentUserId: 'me' });
    instance.readyState = WebSocket.OPEN;

    act(() => {
      jest.advanceTimersByTime(30000);
    });

    expect(instance.send).toHaveBeenCalledWith(JSON.stringify({ type: 'heartbeat' }));
  });

  it('closes the WebSocket and clears the heartbeat on unmount', () => {
    const { unmount, instance } = renderCursor({ sessionId: 'sess-1', currentUserId: 'me' });
    unmount();
    expect(instance.close).toHaveBeenCalled();
  });

  it('renders multiple remote cursors from different users', () => {
    const { instance } = renderCursor({ sessionId: 'sess-1', currentUserId: 'me' });

    sendMessage(instance, {
      type: 'cursor_update',
      user_id: 'user-2',
      user_name: 'Alice',
      cursor_position: { x: 1, y: 2 },
    });
    sendMessage(instance, {
      type: 'cursor_update',
      user_id: 'user-3',
      user_name: 'Bob',
      cursor_position: { x: 3, y: 4 },
    });

    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(document.querySelectorAll('.collaborative-cursor')).toHaveLength(2);
  });

  it('exposes sendCursorPosition via ref so parents can send updates', () => {
    const ref = React.createRef<CollaborativeCursorHandle>();
    const { instance } = renderCursor({ sessionId: 'sess-1', currentUserId: 'me', ref });
    instance.readyState = WebSocket.OPEN;

    act(() => {
      ref.current?.sendCursorPosition({ x: 50, y: 60 }, 'node-9');
    });

    expect(instance.send).toHaveBeenCalledWith(
      JSON.stringify({
        type: 'cursor_update',
        cursor_position: { x: 50, y: 60 },
        selected_node: 'node-9',
      })
    );
  });

  it('does not send cursor updates when the socket is not open', () => {
    const ref = React.createRef<CollaborativeCursorHandle>();
    const { instance } = renderCursor({ sessionId: 'sess-1', currentUserId: 'me', ref });
    instance.readyState = WebSocket.CONNECTING;

    act(() => {
      ref.current?.sendCursorPosition({ x: 1, y: 2 });
    });

    expect(instance.send).not.toHaveBeenCalled();
  });
});
