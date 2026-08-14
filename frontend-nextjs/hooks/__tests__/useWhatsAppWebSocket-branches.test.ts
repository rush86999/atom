/**
 * useWhatsAppWebSocket Branch Coverage Tests (wave 119)
 *
 * Closes the remaining gaps in useWhatsAppWebSocket.ts:
 * - sendPing send-throw catch (line 88)
 * - handleMessage JSON.parse failure (lines 133-134)
 * - connect() when already CONNECTING (lines 190-191)
 * - WebSocket constructor throw (lines 209-210)
 * - sendMessage send-throw path (lines 244-248)
 * - unmount cleanup closing the socket (line 300)
 */

import { renderHook, act } from '@testing-library/react';
import { useWhatsAppWebSocket } from '../useWhatsAppWebSocket';
import { createMockWebSocket } from '../test-helpers';

describe('useWhatsAppWebSocket - Branch Coverage', () => {
  let mockWsInstances: any[] = [];

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockWsInstances = [];

    const MockWebSocket = jest.fn(() => {
      const mockWs = createMockWebSocket();
      mockWsInstances.push(mockWs);
      return mockWs;
    }) as any;
    // Real WebSocket exposes these static constants; without them the hook's
    // readyState guards compare against undefined (test-env gap).
    MockWebSocket.CONNECTING = 0;
    MockWebSocket.OPEN = 1;
    MockWebSocket.CLOSING = 2;
    MockWebSocket.CLOSED = 3;
    (global as any).WebSocket = MockWebSocket;
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('sendPing logs and survives a throwing socket send', () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() =>
      useWhatsAppWebSocket({ autoConnect: true })
    );

    act(() => {
      mockWsInstances[0].simulateOpen();
      mockWsInstances[0].send.mockImplementation(() => {
        throw new Error('socket closed under us');
      });
    });

    act(() => {
      jest.advanceTimersByTime(30000);
    });

    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'Error sending ping:',
      expect.any(Error)
    );

    consoleErrorSpy.mockRestore();
  });

  test('invalid message payload sets a parse-error state', () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() =>
      useWhatsAppWebSocket({ autoConnect: true })
    );

    act(() => {
      mockWsInstances[0].simulateOpen();
      mockWsInstances[0].simulateMessage('this-is-not-json{{{');
    });

    expect(result.current.error).toBe('Error parsing WebSocket message');
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'Error parsing WebSocket message:',
      expect.any(Error)
    );

    consoleErrorSpy.mockRestore();
  });

  test('connect() is a no-op while the socket is already CONNECTING', () => {
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation();

    const { result } = renderHook(() =>
      useWhatsAppWebSocket({ autoConnect: true })
    );

    // wsRef.current.readyState is still CONNECTING (0)
    expect(mockWsInstances).toHaveLength(1);

    act(() => {
      result.current.connect();
    });

    // No second socket was created
    expect(mockWsInstances).toHaveLength(1);
    expect(consoleLogSpy).toHaveBeenCalledWith(
      'WebSocket already connecting'
    );

    consoleLogSpy.mockRestore();
  });

  test('connect() is a no-op while the socket is already OPEN', () => {
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation();

    const { result } = renderHook(() =>
      useWhatsAppWebSocket({ autoConnect: true })
    );

    act(() => {
      mockWsInstances[0].simulateOpen();
    });

    act(() => {
      result.current.connect();
    });

    expect(mockWsInstances).toHaveLength(1);
    expect(consoleLogSpy).toHaveBeenCalledWith('WebSocket already connected');

    consoleLogSpy.mockRestore();
  });

  test('WebSocket constructor failure sets a connection error', () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

    (global as any).WebSocket = jest.fn(() => {
      throw new Error('WebSocket is not available');
    });

    const { result } = renderHook(() =>
      useWhatsAppWebSocket({ autoConnect: true })
    );

    expect(result.current.isConnecting).toBe(false);
    expect(result.current.error).toBe('Failed to create WebSocket connection');
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'Error creating WebSocket:',
      expect.any(Error)
    );

    consoleErrorSpy.mockRestore();
  });

  test('sendMessage returns false and sets error when the socket send throws', () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() =>
      useWhatsAppWebSocket({ autoConnect: true })
    );

    act(() => {
      mockWsInstances[0].simulateOpen();
      mockWsInstances[0].send.mockImplementation(() => {
        throw new Error('send failed');
      });
    });

    let sent: boolean | undefined;
    act(() => {
      sent = result.current.sendMessage({ type: 'test' });
    });

    expect(sent).toBe(false);
    expect(result.current.error).toBe('Failed to send WebSocket message');
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'Error sending WebSocket message:',
      expect.any(Error)
    );

    consoleErrorSpy.mockRestore();
  });

  test('sendMessage returns false when the socket is not connected', () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() =>
      useWhatsAppWebSocket({ autoConnect: false })
    );

    let sent: boolean | undefined;
    act(() => {
      sent = result.current.sendMessage({ type: 'test' });
    });

    expect(sent).toBe(false);
    expect(result.current.error).toBe('WebSocket not connected');
    expect(consoleErrorSpy).toHaveBeenCalledWith('WebSocket not connected');

    consoleErrorSpy.mockRestore();
  });

  test('unmount closes the underlying socket cleanly', () => {
    const { unmount } = renderHook(() =>
      useWhatsAppWebSocket({ autoConnect: true })
    );

    act(() => {
      mockWsInstances[0].simulateOpen();
    });

    expect(() => unmount()).not.toThrow();
    // The manual-disconnect cleanup closes with code 1000
    expect(mockWsInstances[0].close).toHaveBeenCalledWith(
      1000,
      'Manual disconnect'
    );
  });

  test('sendMessage sends raw strings without re-stringifying', () => {
    const { result } = renderHook(() =>
      useWhatsAppWebSocket({ autoConnect: true })
    );

    act(() => {
      mockWsInstances[0].simulateOpen();
    });

    let sent: boolean | undefined;
    act(() => {
      sent = result.current.sendMessage('{"type":"raw"}');
    });

    expect(sent).toBe(true);
    expect(mockWsInstances[0].send).toHaveBeenCalledWith('{"type":"raw"}');
  });
});
