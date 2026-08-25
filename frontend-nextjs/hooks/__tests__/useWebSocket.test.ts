/**
 * useWebSocket Hook Unit Tests
 *
 * Tests for useWebSocket hook handling WebSocket connections, message handling,
 * streaming content, and channel subscriptions. Verifies connection lifecycle,
 * error handling, and proper cleanup.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';

// Mock next-auth useSession
jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

// Import mocked dependency
import { useSession } from 'next-auth/react';

describe('useWebSocket Hook', () => {
  // Helper function to simulate WebSocket events
  const simulateOpen = (ws: any) => {
    act(() => {
      if (ws._onopen) {
        ws._onopen(new Event('open'));
      }
    });
  };

  const simulateMessage = (ws: any, data: string) => {
    act(() => {
      if (ws._onmessage) {
        ws._onmessage(new MessageEvent('message', { data }));
      }
    });
  };

  const simulateClose = (ws: any) => {
    act(() => {
      if (ws._onclose) {
        ws._onclose(new CloseEvent('close'));
      }
    });
  };

  const simulateError = (ws: any) => {
    act(() => {
      if (ws._onerror) {
        ws._onerror(new Event('error'));
      }
    });
  };

  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();

    // Clear WebSocket mock tracking
    ((global as any).WebSocket as any).mock.calls = [];
    ((global as any).WebSocket as any).mock.instances = [];

    // Mock useSession to return a session with backendToken
    (useSession as jest.Mock).mockReturnValue({
      data: { backendToken: 'test-session-token' },
      status: 'authenticated',
    });
  });

  afterEach(() => {
    // Clean up
  });

  describe('1. Connection Lifecycle Tests', () => {
    test('initializes with disconnected state', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      expect(result.current.isConnected).toBe(false);
      expect(result.current.lastMessage).toBeNull();
      expect(result.current.streamingContent).toBeInstanceOf(Map);
      expect(result.current.streamingContent.size).toBe(0);
    });

    test('connects when autoConnect is true', () => {
      renderHook(() => useWebSocket({ autoConnect: true }));

      // WebSocket should be instantiated with correct URL
      // Note: useEffect runs synchronously in renderHook
      expect((global as any).WebSocket.getMockCalls()).toContainEqual(
        ['/ws?token=test-session-token']
      );
    });

    test('does not auto-connect when autoConnect is false', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      expect((global as any).WebSocket.getMockCalls()).toHaveLength(0);
      expect(result.current.isConnected).toBe(false);
    });

    test('sets isConnected to true after successful connection', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];
      simulateOpen(wsInstance);

      expect(result.current.isConnected).toBe(true);
    });

    test('sets isConnected to false after disconnect', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // First connect
      simulateOpen(wsInstance);
      expect(result.current.isConnected).toBe(true);

      // Then disconnect
      simulateClose(wsInstance);
      expect(result.current.isConnected).toBe(false);
    });

    test('schedules a reconnect after an unexpected close (NOT immediate)', () => {
      // Contract: an unexpected close (abnormal, code != 1000/4001/1008)
      // triggers a SCHEDULED reconnect with backoff — not an immediate one.
      // Right after the close, no new socket exists yet; it appears only
      // after the backoff delay elapses (see Reconnection Tests for timing).
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];
      simulateOpen(wsInstance);
      expect(result.current.isConnected).toBe(true);

      // Simulate an unexpected close.
      simulateClose(wsInstance);
      expect(result.current.isConnected).toBe(false);

      // Immediately after the close, no new socket yet (backoff is pending).
      const instances = (global as any).WebSocket.getMockInstances();
      expect(instances).toHaveLength(1);
    });

    test('handles connection errors gracefully', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Simulate error - hook handles silently
      expect(() => {
        simulateError(wsInstance);
      }).not.toThrow();

      // Error is handled silently, no error state exposed
      expect(result.current.error).toBeUndefined();
    });

    test('reconnects after disconnect', () => {
      const { result, rerender } = renderHook(
        ({ autoConnect }) => useWebSocket({ autoConnect }),
        { initialProps: { autoConnect: true } }
      );

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // First connection
      simulateOpen(wsInstance);
      expect(result.current.isConnected).toBe(true);

      // Disconnect
      simulateClose(wsInstance);
      expect(result.current.isConnected).toBe(false);

      // Force reconnect by changing props
      rerender({ autoConnect: false });
      rerender({ autoConnect: true });

      const newWsInstance = (global as any).WebSocket.getMockInstances()[1];
      simulateOpen(newWsInstance);

      expect(result.current.isConnected).toBe(true);
    });

    test('reconnects with the refreshed token when the session updates', () => {
      // When NextAuth refreshes the session (new backendToken), the connect
      // callback gets a new reference, the effect re-runs, and a new WS must
      // be opened using the FRESH token — not the stale one. This is the only
      // path that recovers a connection dropped due to token expiry.
      const { result, rerender } = renderHook(() => useWebSocket({ autoConnect: true }));

      const firstInstance = (global as any).WebSocket.getMockInstances()[0];
      simulateOpen(firstInstance);
      expect(result.current.isConnected).toBe(true);
      expect((global as any).WebSocket.getMockCalls()[0][0]).toContain(
        'token=test-session-token'
      );

      // Simulate a token refresh: NextAuth returns a new session object with a
      // fresh backendToken. The `session` reference changes → connect changes
      // → effect re-runs → new connection.
      (useSession as jest.Mock).mockReturnValue({
        data: { backendToken: 'refreshed-token-456' },
        status: 'authenticated',
      });

      rerender();

      // The old socket is torn down by the effect cleanup and a new one is
      // created with the refreshed token.
      const calls = (global as any).WebSocket.getMockCalls();
      const lastCall = calls[calls.length - 1];
      expect(lastCall[0]).toContain('token=refreshed-token-456');
    });

    test('cleans up WebSocket on unmount', () => {
      const { result, unmount } = renderHook(() =>
        useWebSocket({ autoConnect: true })
      );

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      unmount();

      expect(wsInstance.close).toHaveBeenCalled();
    });

    test('skips connection when no token is available', () => {
      // Mock useSession to return no token
      (useSession as jest.Mock).mockReturnValue({
        data: null,
        status: 'unauthenticated',
      });

      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

      renderHook(() => useWebSocket({ autoConnect: true }));

      // The real hook has NO dev-token fallback: when neither the session nor
      // localStorage provides an auth_token it warns and skips the connection,
      // so no WebSocket is ever constructed.
      expect((global as any).WebSocket.getMockCalls()).toHaveLength(0);

      consoleSpy.mockRestore();
    });

    test('constructs correct WebSocket URL with token parameter', () => {
      (useSession as jest.Mock).mockReturnValue({
        data: { backendToken: 'custom-token-123' },
        status: 'authenticated',
      });

      const { result } = renderHook(() =>
        useWebSocket({
          url: 'ws://localhost:8000/ws',
          autoConnect: true,
        })
      );

      expect((global as any).WebSocket.getMockCalls()).toContainEqual(
        ['ws://localhost:8000/ws?token=custom-token-123']
      );
    });
  });

  describe('2. Message Handling Tests', () => {
    test('receives and parses lastMessage from server', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      const testMessage = {
        type: 'chat',
        data: { text: 'Hello from server' },
        timestamp: '2024-02-28T10:00:00Z',
      };

      simulateMessage(wsInstance, JSON.stringify(testMessage));

      expect(result.current.lastMessage).toEqual(testMessage);
    });

    test('handles malformed JSON messages (catch, no error thrown)', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Should not throw error
      expect(() => {
        simulateMessage(wsInstance, 'invalid json{');
      }).not.toThrow();

      // lastMessage should remain null
      expect(result.current.lastMessage).toBeNull();
    });

    test('handles streaming:update messages', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Send streaming update
      const streamingMessage = {
        type: 'streaming:update',
        id: 'msg-1',
        delta: 'Hello',
      };

      simulateMessage(wsInstance, JSON.stringify(streamingMessage));

      expect(result.current.streamingContent.get('msg-1')).toBe('Hello');
    });

    test('handles streaming:complete messages', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // First send an update
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'msg-1',
          delta: 'Hello',
        })
      );

      expect(result.current.streamingContent.get('msg-1')).toBe('Hello');

      // Then send complete message
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:complete',
          id: 'msg-1',
          content: 'Hello World',
          complete: true,
        })
      );

      // Stream should be removed from streamingContent
      expect(result.current.streamingContent.has('msg-1')).toBe(false);
    });

    test('clears streamingContent on streaming:complete WITHOUT a redundant complete flag', () => {
      // The deletion logic must key off the message TYPE, not a separate
      // `complete: true` field. A streaming:complete message that omits the
      // redundant flag (a perfectly valid backend emission) must still clear
      // the accumulated text — otherwise stale streaming content lingers in
      // the UI forever after the stream finishes.
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Seed a streaming buffer
      simulateMessage(
        wsInstance,
        JSON.stringify({ type: 'streaming:update', id: 'msg-9', delta: 'Partial' })
      );
      expect(result.current.streamingContent.get('msg-9')).toBe('Partial');

      // Complete WITHOUT the redundant `complete: true` field
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:complete',
          id: 'msg-9',
          content: 'Partial',
          // NOTE: no `complete: true` — the type alone signals completion
        })
      );

      expect(result.current.streamingContent.has('msg-9')).toBe(false);
    });

    test('accumulates streaming content in Map by message ID', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Send multiple updates for same stream
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'msg-1',
          delta: 'Hello ',
        })
      );

      expect(result.current.streamingContent.get('msg-1')).toBe('Hello ');

      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'msg-1',
          delta: 'World',
        })
      );

      expect(result.current.streamingContent.get('msg-1')).toBe('Hello World');
    });

    test('removes completed streams from streamingContent Map', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Add stream
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'msg-1',
          delta: 'Content',
        })
      );

      expect(result.current.streamingContent.size).toBe(1);

      // Complete stream
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:complete',
          id: 'msg-1',
          content: 'Content complete',
          complete: true,
        })
      );

      expect(result.current.streamingContent.size).toBe(0);
    });

    test('handles message type field correctly', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      const testMessage = {
        type: 'agent_response',
        data: { agentId: 'agent-1' },
      };

      simulateMessage(wsInstance, JSON.stringify(testMessage));

      expect(result.current.lastMessage?.type).toBe('agent_response');
    });

    test('preserves message timestamp', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      const timestamp = '2024-02-28T12:30:45.123Z';
      const testMessage = {
        type: 'chat',
        data: { text: 'Message with timestamp' },
        timestamp,
      };

      simulateMessage(wsInstance, JSON.stringify(testMessage));

      expect(result.current.lastMessage?.timestamp).toBe(timestamp);
    });
  });

  describe('3. Channel Subscription Tests', () => {
    test('subscribes to channel via sendMessage', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];
      wsInstance.readyState = WebSocket.OPEN;

      act(() => {
        result.current.subscribe('agent:123');
      });

      expect(wsInstance.send).toHaveBeenCalledWith(
        JSON.stringify({ type: 'subscribe', channel: 'agent:123' })
      );
    });

    test('unsubscribes from channel via sendMessage', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];
      wsInstance.readyState = WebSocket.OPEN;

      act(() => {
        result.current.unsubscribe('agent:123');
      });

      expect(wsInstance.send).toHaveBeenCalledWith(
        JSON.stringify({ type: 'unsubscribe', channel: 'agent:123' })
      );
    });

    test('subscribes to initialChannels on connect', () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          initialChannels: ['agent:123', 'agent:456'],
        })
      );

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Trigger open
      simulateOpen(wsInstance);

      // Should subscribe to both channels
      expect(wsInstance.send).toHaveBeenCalledWith(
        JSON.stringify({ type: 'subscribe', channel: 'agent:123' })
      );
      expect(wsInstance.send).toHaveBeenCalledWith(
        JSON.stringify({ type: 'subscribe', channel: 'agent:456' })
      );
    });

    test('handles subscription when not connected (no-op)', () => {
      const wsInstance = {
        readyState: WebSocket.CLOSED,
        send: jest.fn(),
        close: jest.fn(),
      };

      // WebSocket is already mocked globally, no need to mockReturnValue

      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      act(() => {
        result.current.subscribe('agent:123');
      });

      // Should not send when not connected
      expect(wsInstance.send).not.toHaveBeenCalled();
    });

    test('handles unsubscribe when not connected (no-op)', () => {
      const wsInstance = {
        readyState: WebSocket.CLOSED,
        send: jest.fn(),
        close: jest.fn(),
      };

      // WebSocket is already mocked globally, no need to mockReturnValue

      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      act(() => {
        result.current.unsubscribe('agent:123');
      });

      // Should not send when not connected
      expect(wsInstance.send).not.toHaveBeenCalled();
    });

    test('sends correct JSON format for subscribe/unsubscribe', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];
      wsInstance.readyState = WebSocket.OPEN;

      act(() => {
        result.current.subscribe('channel:test');
      });

      const subscribeCall = wsInstance.send.mock.calls[0][0];
      expect(() => JSON.parse(subscribeCall)).not.toThrow();
      expect(JSON.parse(subscribeCall)).toEqual({
        type: 'subscribe',
        channel: 'channel:test',
      });

      act(() => {
        result.current.unsubscribe('channel:test');
      });

      const unsubscribeCall = wsInstance.send.mock.calls[1][0];
      expect(() => JSON.parse(unsubscribeCall)).not.toThrow();
      expect(JSON.parse(unsubscribeCall)).toEqual({
        type: 'unsubscribe',
        channel: 'channel:test',
      });
    });
  });

  describe('4. Streaming Content Tests', () => {
    test('initializes with empty streamingContent Map', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      expect(result.current.streamingContent).toBeInstanceOf(Map);
      expect(result.current.streamingContent.size).toBe(0);
    });

    test('adds delta content to existing stream', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Initial content
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'stream-1',
          delta: 'Hello',
        })
      );

      expect(result.current.streamingContent.get('stream-1')).toBe('Hello');

      // Add delta
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'stream-1',
          delta: ' World',
        })
      );

      expect(result.current.streamingContent.get('stream-1')).toBe(
        'Hello World'
      );
    });

    test('creates new entry for new stream ID', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'stream-1',
          delta: 'Content 1',
        })
      );

      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'stream-2',
          delta: 'Content 2',
        })
      );

      expect(result.current.streamingContent.size).toBe(2);
      expect(result.current.streamingContent.get('stream-1')).toBe('Content 1');
      expect(result.current.streamingContent.get('stream-2')).toBe('Content 2');
    });

    test('deletes stream entry when complete=true', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Add stream
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'stream-1',
          delta: 'Content',
        })
      );

      expect(result.current.streamingContent.has('stream-1')).toBe(true);

      // Complete stream
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:complete',
          id: 'stream-1',
          content: 'Content complete',
          complete: true,
        })
      );

      expect(result.current.streamingContent.has('stream-1')).toBe(false);
    });

    test('returns Map from streamingContent property', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      expect(result.current.streamingContent).toBeInstanceOf(Map);
      // Should support Map methods
      expect(typeof result.current.streamingContent.get).toBe('function');
      expect(typeof result.current.streamingContent.set).toBe('function');
      expect(typeof result.current.streamingContent.has).toBe('function');
      expect(typeof result.current.streamingContent.delete).toBe('function');
    });

    test('handles multiple concurrent streams by ID', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Add multiple streams
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'stream-1',
          delta: 'Agent 1: ',
        })
      );

      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'stream-2',
          delta: 'Agent 2: ',
        })
      );

      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'stream-3',
          delta: 'Agent 3: ',
        })
      );

      expect(result.current.streamingContent.size).toBe(3);

      // Update each stream independently
      simulateMessage(
        wsInstance,
        JSON.stringify({
          type: 'streaming:update',
          id: 'stream-1',
          delta: 'Response 1',
        })
      );

      expect(result.current.streamingContent.get('stream-1')).toBe(
        'Agent 1: Response 1'
      );
      expect(result.current.streamingContent.get('stream-2')).toBe('Agent 2: ');
      expect(result.current.streamingContent.get('stream-3')).toBe('Agent 3: ');
    });
  });

  describe('5. State Management Tests', () => {
    test('returns isConnected boolean', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      expect(typeof result.current.isConnected).toBe('boolean');
      expect(result.current.isConnected).toBe(false);
    });

    test('returns lastMessage or null', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Initially null
      expect(result.current.lastMessage).toBeNull();

      // After message, returns message
      simulateMessage(
        wsInstance,
        JSON.stringify({ type: 'test', data: 'message' })
      );

      expect(result.current.lastMessage).not.toBeNull();
      expect(result.current.lastMessage?.type).toBe('test');
    });

    test('returns streamingContent Map', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      expect(result.current.streamingContent).toBeInstanceOf(Map);
    });

    test('returns subscribe function', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      expect(typeof result.current.subscribe).toBe('function');
    });

    test('returns unsubscribe function', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      expect(typeof result.current.unsubscribe).toBe('function');
    });
  });

  describe('6. Error Handling Tests', () => {
    test('handles WebSocket onerror silently', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Trigger error - should not throw
      expect(() => {
        simulateError(wsInstance);
      }).not.toThrow();

      // No error state exposed by hook
      expect(result.current.error).toBeUndefined();
    });

    test('handles JSON parse errors in onmessage', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Invalid JSON - should not throw
      expect(() => {
        simulateMessage(wsInstance, '{invalid json');
      }).not.toThrow();

      // lastMessage should remain unchanged
      expect(result.current.lastMessage).toBeNull();
    });

    test('handles missing session token gracefully', () => {
      // No session token
      (useSession as jest.Mock).mockReturnValue({
        data: null,
        status: 'unauthenticated',
      });

      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

      expect(() => {
        renderHook(() => useWebSocket({ autoConnect: true }));
      }).not.toThrow();

      // Without any token the hook skips connecting (there is no dev-token
      // fallback), so no WebSocket is constructed.
      expect((global as any).WebSocket.getMockCalls()).toHaveLength(0);

      consoleSpy.mockRestore();
    });

    test('handles connection timeout (via onclose)', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];

      // Simulate connection close (timeout)
      simulateClose(wsInstance);

      expect(result.current.isConnected).toBe(false);
    });

    test('does not throw on sendMessage when disconnected', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      // Should not throw even when disconnected
      expect(() => {
        act(() => {
          result.current.sendMessage({ type: 'test', data: 'message' });
        });
      }).not.toThrow();
    });

    test('does not throw on sendMessage while socket is CONNECTING', () => {
      // A real browser WebSocket.send() throws InvalidStateError when the
      // socket is still in CONNECTING state (readyState 0). subscribe() and
      // unsubscribe() already guard on readyState === OPEN; sendMessage must
      // do the same so a component that sends immediately on mount (before
      // onopen fires) doesn't crash. We simulate real send() behavior here.
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const wsInstance = (global as any).WebSocket.getMockInstances()[0];
      // Socket is CONNECTING (not yet opened): simulate real send() throwing.
      expect(wsInstance.readyState).toBe(0); // CONNECTING
      wsInstance.send = jest.fn(() => {
        throw new DOMException('InvalidStateError', 'InvalidStateError');
      });

      expect(() => {
        act(() => {
          result.current.sendMessage({ type: 'canvas:state_update', data: {} });
        });
      }).not.toThrow();
    });
  });

  // ==========================================================================
  // 7. Reconnection Tests (fake timers, scoped)
  // ==========================================================================
  describe('7. Reconnection Tests', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    // Close helper that accepts a code (the suite-wide simulateClose uses 1000).
    const simulateCloseWithCode = (ws: any, code: number) => {
      act(() => {
        if (ws._onclose) {
          ws._onclose(new CloseEvent('close', { code }));
        }
      });
    };

    const getInstance = (i: number) => (global as any).WebSocket.getMockInstances()[i];
    const callCount = () => (global as any).WebSocket.getMockCalls().length;

    test('reconnects with exponential backoff after an abnormal close (1006)', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      // Initial connection.
      const ws0 = getInstance(0);
      simulateOpen(ws0);
      expect(result.current.isConnected).toBe(true);

      // Abnormal close -> schedules 1st retry (~1s + jitter).
      simulateCloseWithCode(ws0, 1006);
      expect(callCount()).toBe(1); // no immediate reconnect

      act(() => { jest.advanceTimersByTime(2000); }); // past the 1st backoff
      expect(callCount()).toBe(2);

      // 2nd socket also closes -> schedules 2nd retry (~2s).
      const ws1 = getInstance(1);
      simulateCloseWithCode(ws1, 1006);
      act(() => { jest.advanceTimersByTime(4000); });
      expect(callCount()).toBe(3);

      // 3rd socket closes -> schedules 3rd retry (~4s) — last allowed attempt.
      const ws2 = getInstance(2);
      simulateCloseWithCode(ws2, 1006);
      act(() => { jest.advanceTimersByTime(8000); });
      expect(callCount()).toBe(4); // 1 initial + 3 retries

      // 4th socket closes -> maxAttempts (3) reached, NO further retry.
      const ws3 = getInstance(3);
      simulateCloseWithCode(ws3, 1006);
      act(() => { jest.advanceTimersByTime(30000); });
      expect(callCount()).toBe(4);
    });

    test('resets the backoff counter after a successful reconnect', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));

      const ws0 = getInstance(0);
      simulateOpen(ws0);

      // Close -> reconnect -> succeed. The counter resets on open.
      simulateCloseWithCode(ws0, 1006);
      act(() => { jest.advanceTimersByTime(2000); });
      const ws1 = getInstance(1);
      simulateOpen(ws1); // successful reconnect resets attempts to 0
      expect(result.current.reconnectAttempts).toBe(0);

      // A subsequent close should restart the backoff at the ~1s delay, and
      // we should get a full 3 retries again.
      simulateCloseWithCode(ws1, 1006);
      act(() => { jest.advanceTimersByTime(2000); });
      expect(callCount()).toBe(3); // ws0, ws1, + 1 retry
    });

    test('does NOT retry an auth-failure close (4001)', () => {
      renderHook(() => useWebSocket({ autoConnect: true }));
      const ws0 = getInstance(0);
      simulateOpen(ws0);

      simulateCloseWithCode(ws0, 4001);
      // Generously advance — nothing should fire.
      act(() => { jest.advanceTimersByTime(60000); });
      expect(callCount()).toBe(1);
    });

    test('does NOT retry a policy-violation close (1008)', () => {
      renderHook(() => useWebSocket({ autoConnect: true }));
      const ws0 = getInstance(0);
      simulateOpen(ws0);

      simulateCloseWithCode(ws0, 1008);
      act(() => { jest.advanceTimersByTime(60000); });
      expect(callCount()).toBe(1);
    });

    test('does NOT reconnect when reconnect option is false', () => {
      renderHook(() => useWebSocket({ autoConnect: true, reconnect: false }));
      const ws0 = getInstance(0);
      simulateOpen(ws0);

      simulateCloseWithCode(ws0, 1006); // abnormal, but reconnect disabled
      act(() => { jest.advanceTimersByTime(60000); });
      expect(callCount()).toBe(1);
    });

    test('cancels pending reconnect on unmount', () => {
      const { unmount } = renderHook(() => useWebSocket({ autoConnect: true }));
      const ws0 = getInstance(0);
      simulateOpen(ws0);

      simulateCloseWithCode(ws0, 1006); // schedules a retry in ~1s
      // Unmount before the backoff fires — cleanup should clear the timeout.
      unmount();
      act(() => { jest.advanceTimersByTime(60000); });
      expect(callCount()).toBe(1); // no retry after unmount
    });

    test('does NOT reconnect on an intentional disconnect()', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: true }));
      const ws0 = getInstance(0);
      simulateOpen(ws0);
      expect(result.current.isConnected).toBe(true);

      // An explicit disconnect() must not trigger the reconnect loop.
      act(() => { result.current.disconnect(); });
      act(() => { jest.advanceTimersByTime(60000); });
      expect(callCount()).toBe(1);
    });
  });
});
