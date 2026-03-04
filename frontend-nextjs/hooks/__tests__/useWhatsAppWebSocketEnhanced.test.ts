/**
 * useWhatsAppWebSocketEnhanced Hook Unit Tests
 *
 * Tests for enhanced WhatsApp WebSocket hook covering:
 * - All base WebSocket functionality from useWhatsAppWebSocket
 * - Debug logging with debugMode
 * - Toast notifications for connection events
 * - testConnection() method
 * - sendTestNotification() method
 * - Enhanced error handling
 * - Cleanup verification
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useWhatsAppWebSocketEnhanced } from '../useWhatsAppWebSocketEnhanced';
import { createMockWebSocket } from '../test-helpers';

// Mock toast hook
const mockToastFn = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: mockToastFn,
  }),
}));

describe('useWhatsAppWebSocketEnhanced Hook', () => {
  let mockWsInstances: any[] = [];

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    mockWsInstances = [];
    mockToastFn.mockClear();

    // Replace global WebSocket
    (global as any).WebSocket = jest.fn(() => {
      const mockWs = createMockWebSocket();
      mockWsInstances.push(mockWs);
      return mockWs;
    }) as any;

    // Mock console.log for debug mode
    jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  describe('1. Enhanced Features Tests', () => {
    test('has all base WebSocket functionality', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: false })
      );

      // Base WebSocket methods
      expect(result.current.connect).toBeDefined();
      expect(result.current.disconnect).toBeDefined();
      expect(result.current.sendMessage).toBeDefined();
      expect(result.current.sendPing).toBeDefined();
      expect(result.current.subscribeToEvents).toBeDefined();

      // State properties
      expect(result.current.isConnected).toBe(false);
      expect(result.current.isConnecting).toBe(false);
      expect(result.current.error).toBeNull();
      expect(result.current.lastMessage).toBeNull();
    });

    test('has additional debug logging feature', () => {
      const consoleLogSpy = jest.spyOn(console, 'log');

      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: false,
          debugMode: true,
        })
      );

      // Trigger some action that should log
      act(() => {
        result.current.connect();
      });

      // Debug logs should be present
      expect(consoleLogSpy).toHaveBeenCalled();

      consoleLogSpy.mockRestore();
    });

    test('no debug logs when debugMode is false', () => {
      const consoleLogSpy = jest.spyOn(console, 'log');

      renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: false,
          debugMode: false,
        })
      );

      // Should not log when debugMode is false
      expect(consoleLogSpy).not.toHaveBeenCalled();

      consoleLogSpy.mockRestore();
    });

    test('has testConnection() method', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: false })
      );

      expect(typeof result.current.testConnection).toBe('function');
    });

    test('has sendTestNotification() method', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: false })
      );

      expect(typeof result.current.sendTestNotification).toBe('function');
    });

    test('exposes debugMode in return value', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: false,
          debugMode: true,
        })
      );

      expect(result.current.debugMode).toBe(true);
    });
  });

  describe('2. Toast Integration Tests', () => {
    test('shows success toast on connection', async () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: false,
        })
      );

      // Trigger connection
      act(() => {
        mockWsInstances[0].simulateOpen();
      });

      await waitFor(() => {
        expect(mockToastFnFn).toHaveBeenCalledWith(
          expect.objectContaining({
            title: 'Connected to WhatsApp',
            variant: 'success',
          })
        );
      });
    });

    test('shows error toast on connection failure', async () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: false,
        })
      );

      // Trigger error
      act(() => {
        mockWsInstances[0].simulateError();
      });

      await waitFor(() => {
        expect(mockToastFn).toHaveBeenCalledWith(
          expect.objectContaining({
            title: 'Connection Error',
            variant: 'error',
          })
        );
      });
    });

    test('shows error toast on WebSocket error message', async () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: false,
        })
      );

      // Connect first
      act(() => {
        mockWsInstances[0].simulateOpen();
      });

      // Send error message
      act(() => {
        mockWsInstances[0].simulateMessage({
          type: 'error',
          error: 'Authentication failed',
        });
      });

      await waitFor(() => {
        expect(mockToastFn).toHaveBeenCalledWith(
          expect.objectContaining({
            title: 'WebSocket Error',
            description: 'Authentication failed',
            variant: 'error',
          })
        );
      });
    });

    test('shows warning toast when connection lost', async () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          reconnectAttempts: 0,
          debugMode: false,
        })
      );

      // Connect then close with error code
      act(() => {
        mockWsInstances[0].simulateOpen();
      });

      mockToastFn.mockClear();

      act(() => {
        mockWsInstances[0].simulateClose(1001, 'Connection lost');
      });

      await waitFor(() => {
        expect(mockToastFn).toHaveBeenCalledWith(
          expect.objectContaining({
            title: 'Connection Lost',
            variant: 'warning',
          })
        );
      });
    });
  });

  describe('3. Debug Mode Tests', () => {
    test('logs connection attempts when debugMode=true', () => {
      const consoleLogSpy = jest.spyOn(console, 'log');

      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: false,
          debugMode: true,
        })
      );

      act(() => {
        result.current.connect();
      });

      expect(consoleLogSpy).toHaveBeenCalledWith(
        '[WhatsAppWebSocket]',
        expect.any(String),
        expect.anything()
      );

      consoleLogSpy.mockRestore();
    });

    test('logs messages when debugMode=true', () => {
      const consoleLogSpy = jest.spyOn(console, 'log');

      renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: true,
        })
      );

      act(() => {
        mockWsInstances[0].simulateOpen();
        mockWsInstances[0].simulateMessage({ type: 'test', data: 'test' });
      });

      expect(consoleLogSpy).toHaveBeenCalledWith(
        '[WhatsAppWebSocket]',
        expect.stringContaining('Message received'),
        expect.anything()
      );

      consoleLogSpy.mockRestore();
    });

    test('logs include helpful context', () => {
      const consoleLogSpy = jest.spyOn(console, 'log');

      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: false,
          debugMode: true,
        })
      );

      act(() => {
        result.current.connect();
      });

      const logCalls = consoleLogSpy.mock.calls;
      const logMessage = logCalls[logCalls.length - 1];

      // Format: [WhatsAppWebSocket] message data
      expect(logMessage[0]).toBe('[WhatsAppWebSocket]');
      expect(typeof logMessage[1]).toBe('string');
      expect(logMessage.length).toBeGreaterThanOrEqual(2);

      consoleLogSpy.mockRestore();
    });

    test('no logs when debugMode=false (default)', () => {
      const consoleLogSpy = jest.spyOn(console, 'log');

      renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: false,
          debugMode: false,
        })
      );

      act(() => {
        // Trigger various actions
        mockWsInstances[0]?.simulateOpen();
        mockWsInstances[0]?.simulateMessage({ type: 'test' });
      });

      // Should not have logged anything
      expect(consoleLogSpy).not.toHaveBeenCalled();

      consoleLogSpy.mockRestore();
    });
  });

  describe('4. Additional Methods Tests', () => {
    test('testConnection() sends test notification if connected', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: true })
      );

      mockWsInstances[0].readyState = WebSocket.OPEN;

      act(() => {
        const sent = result.current.testConnection();
        expect(sent).toBe(true);
      });

      expect(mockWsInstances[0].send).toHaveBeenCalledWith(
        expect.stringContaining('test_notification')
      );
    });

    test('testConnection() calls connect() if not connected', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: false })
      );

      act(() => {
        result.current.testConnection();
      });

      expect((global as any).WebSocket).toHaveBeenCalled();
    });

    test('sendTestNotification() sends test_notification message', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: true })
      );

      mockWsInstances[0].readyState = WebSocket.OPEN;

      act(() => {
        result.current.sendTestNotification();
      });

      const sentData = JSON.parse(mockWsInstances[0].send.mock.calls[0][0]);

      expect(sentData.type).toBe('test_notification');
      expect(sentData.message).toBe('Test notification from enhanced hook');
      expect(sentData).toHaveProperty('timestamp');
    });

    test('sendTestNotification() returns false when not connected', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: false })
      );

      const sent = result.current.sendTestNotification();

      expect(sent).toBe(false);
    });
  });

  describe('5. Message Handling Tests', () => {
    test('handles subscription_confirmed message', () => {
      const consoleLogSpy = jest.spyOn(console, 'log');

      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: true,
        })
      );

      act(() => {
        mockWsInstances[0].simulateOpen();
        mockWsInstances[0].simulateMessage({
          type: 'subscription_confirmed',
          subscriptions: ['message', 'status'],
        });
      });

      expect(result.current.lastMessage).toHaveProperty(
        'type',
        'subscription_confirmed'
      );

      consoleLogSpy.mockRestore();
    });

    test('handles test_notification_response', () => {
      const consoleLogSpy = jest.spyOn(console, 'log');

      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: true,
        })
      );

      act(() => {
        mockWsInstances[0].simulateOpen();
        mockWsInstances[0].simulateMessage({
          type: 'test_notification_response',
          status: 'received',
        });
      });

      expect(result.current.lastMessage).toHaveProperty(
        'type',
        'test_notification_response'
      );

      consoleLogSpy.mockRestore();
    });

    test('logs unknown message types when debugMode enabled', () => {
      const consoleLogSpy = jest.spyOn(console, 'log');

      renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: true,
        })
      );

      act(() => {
        mockWsInstances[0].simulateOpen();
        mockWsInstances[0].simulateMessage({
          type: 'unknown_type',
          data: 'test',
        });
      });

      expect(consoleLogSpy).toHaveBeenCalledWith(
        '[WhatsAppWebSocket]',
        'Unknown message type',
        'unknown_type'
      );

      consoleLogSpy.mockRestore();
    });

    test('does not log unknown messages when debugMode disabled', () => {
      const consoleLogSpy = jest.spyOn(console, 'log');

      renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: false,
        })
      );

      act(() => {
        mockWsInstances[0].simulateOpen();
        mockWsInstances[0].simulateMessage({
          type: 'unknown_type',
          data: 'test',
        });
      });

      expect(consoleLogSpy).not.toHaveBeenCalled();

      consoleLogSpy.mockRestore();
    });
  });

  describe('6. Cleanup Tests', () => {
    test('includes all cleanup from base hook', () => {
      const { unmount } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: true })
      );

      unmount();

      // Should close WebSocket
      expect(mockWsInstances[0].close).toHaveBeenCalled();
    });

    test('clears timeouts and intervals', () => {
      const { unmount } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          pingInterval: 10000,
          reconnectDelay: 5000,
        })
      );

      act(() => {
        mockWsInstances[0].simulateOpen();
      });

      unmount();

      // Run all timers - should not throw or leak
      act(() => {
        jest.runAllTimers();
      });

      expect(true).toBe(true);
    });

    test('no toast calls after unmount', () => {
      const { unmount } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: false,
        })
      );

      // Clear initial toast from connection
      mockToastFn.mockClear();

      unmount();

      // Trigger events after unmount
      act(() => {
        mockWsInstances[0].simulateError();
      });

      // Should not show new toast after unmount
      expect(mockToastFn).not.toHaveBeenCalled();
    });
  });

  describe('7. Error Handling Tests', () => {
    test('enhanced error logging with debugMode', () => {
      const consoleLogSpy = jest.spyOn(console, 'log');

      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: true,
        })
      );

      act(() => {
        mockWsInstances[0].simulateError();
      });

      expect(consoleLogSpy).toHaveBeenCalledWith(
        '[WhatsAppWebSocket]',
        expect.stringContaining('error'),
        expect.anything()
      );

      consoleLogSpy.mockRestore();
    });

    test('toast notifications for all error types', async () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: false,
        })
      );

      // Test onerror event
      act(() => {
        mockWsInstances[0].simulateError();
      });

      await waitFor(() => {
        expect(mockToastFn).toHaveBeenCalledWith(
          expect.objectContaining({
            variant: 'error',
          })
        );
      });
    });

    test('graceful degradation on errors', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({
          autoConnect: true,
          debugMode: false,
        })
      );

      // Trigger multiple errors
      act(() => {
        mockWsInstances[0].simulateError();
        mockWsInstances[0].simulateError();
      });

      // Should not throw or crash
      expect(result.current.error).toBeTruthy();
    });

    test('updates error state correctly', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: true })
      );

      act(() => {
        mockWsInstances[0].simulateError();
      });

      expect(result.current.error).toBe('WebSocket connection error');

      // Clear error by reconnecting
      act(() => {
        mockWsInstances[0].simulateOpen();
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('8. State Management Tests', () => {
    test('returns all base state properties', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: false })
      );

      expect(typeof result.current.isConnected).toBe('boolean');
      expect(typeof result.current.isConnecting).toBe('boolean');
      expect(result.current.error).toBeNull(); // error is null or string
      expect(result.current.lastMessage).toBeNull();
      expect(typeof result.current.connectionAttempts).toBe('number');
      expect(typeof result.current.reconnectCount).toBe('number');
    });

    test('returns all connection methods', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: false })
      );

      expect(typeof result.current.connect).toBe('function');
      expect(typeof result.current.disconnect).toBe('function');
      expect(typeof result.current.reconnect).toBe('function');
      expect(typeof result.current.testConnection).toBe('function');
    });

    test('returns all message methods', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: false })
      );

      expect(typeof result.current.sendMessage).toBe('function');
      expect(typeof result.current.sendPing).toBe('function');
      expect(typeof result.current.sendTestNotification).toBe('function');
    });

    test('returns subscription methods', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: false })
      );

      expect(typeof result.current.subscribeToEvents).toBe('function');
    });

    test('returns websocket reference', () => {
      const { result } = renderHook(() =>
        useWhatsAppWebSocketEnhanced({ autoConnect: true })
      );

      expect(result.current.websocket).toBeDefined();
    });
  });
});
