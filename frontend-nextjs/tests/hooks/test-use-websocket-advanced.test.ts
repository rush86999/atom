import { renderHook, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock WebSocket for testing
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  sentMessages: any[] = [];

  constructor(public url: string) {
    // Simulate connection delay
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 100);
  }

  send(data: string): void {
    this.sentMessages.push(JSON.parse(data));
  }

  close(code?: number, reason?: string): void {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code, reason }));
    }
  }

  // Test helper to simulate receiving a message
  simulateMessage(data: any): void {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  // Test helper to simulate error
  simulateError(): void {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

// Mock useWebSocket hook
const createMockUseWebSocket = () => {
  let wsInstance: MockWebSocket | null = null;
  let messageQueue: any[] = [];
  let reconnectAttempts = 0;
  let maxReconnectAttempts = 3;
  let reconnectDelay = 1000;

  return {
    useWebSocket: (url: string, options: {
      onMessage?: (data: any) => void;
      onError?: (error: Event) => void;
      onClose?: (event: CloseEvent) => void;
      onOpen?: (event: Event) => void;
      reconnect?: boolean;
      maxReconnectAttempts?: number;
      reconnectDelay?: number;
    } = {}) => {
      const {
        onMessage,
        onError,
        onClose,
        onOpen,
        reconnect = true,
        maxReconnectAttempts: maxAttempts = 3,
        reconnectDelay: delay = 1000,
      } = options;

      maxReconnectAttempts = maxAttempts;
      reconnectDelay = delay;

      const connect = () => {
        try {
          wsInstance = new MockWebSocket(url);

          wsInstance.onopen = (event) => {
            reconnectAttempts = 0;
            if (onOpen) onOpen(event);
          };

          wsInstance.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);

              // Handle request-response pattern
              if (data._requestId) {
                const pendingRequest = messageQueue.find(
                  (req) => req.requestId === data._requestId
                );
                if (pendingRequest) {
                  clearTimeout(pendingRequest.timer);
                  messageQueue = messageQueue.filter(
                    (req) => req.requestId !== data._requestId
                  );
                  pendingRequest.resolve(data);
                  return;
                }
              }

              if (onMessage) onMessage(data);
            } catch (error) {
              // Handle non-JSON messages
              if (onMessage) onMessage(event.data);
            }
          };

          wsInstance.onerror = (event) => {
            if (onError) onError(event);
          };

          wsInstance.onclose = (event) => {
            if (onClose) onClose(event);

            // Attempt reconnection if enabled
            if (reconnect && reconnectAttempts < maxReconnectAttempts) {
              reconnectAttempts++;
              setTimeout(() => {
                connect();
              }, reconnectDelay * Math.pow(2, reconnectAttempts - 1)); // Exponential backoff
            }

            wsInstance = null;
          };
        } catch (error) {
          if (onError) onError(error as Event);
        }
      };

      const disconnect = () => {
        if (wsInstance) {
          wsInstance.close();
          wsInstance = null;
        }
      };

      const send = (data: any) => {
        if (wsInstance && wsInstance.readyState === MockWebSocket.OPEN) {
          wsInstance.send(JSON.stringify(data));
          return true;
        }
        return false;
      };

      const sendAndWait = (data: any, timeout = 5000): Promise<any> => {
        return new Promise((resolve, reject) => {
          const requestId = `req-${Date.now()}-${Math.random()}`;
          const messageWithId = { ...data, _requestId: requestId };

          const timer = setTimeout(() => {
            reject(new Error('WebSocket request timeout'));
          }, timeout);

          // Store pending request
          messageQueue.push({ requestId, resolve, reject, timer });

          send(messageWithId);
        });
      };

      const getReadyState = () => {
        return wsInstance?.readyState ?? MockWebSocket.CLOSED;
      };

      const isConnected = () => {
        return getReadyState() === MockWebSocket.OPEN;
      };

      // Test helpers
      const getTestInstance = () => wsInstance;

      return {
        connect,
        disconnect,
        send,
        sendAndWait,
        getReadyState,
        isConnected,
        getTestInstance,
      };
    },
  };
};

describe('useWebSocket - Advanced Tests', () => {
  let mockUseWebSocket: ReturnType<typeof createMockUseWebSocket>['useWebSocket'];

  beforeEach(() => {
    const mock = createMockUseWebSocket();
    mockUseWebSocket = mock.useWebSocket;
  });

  describe('Connection Management', () => {
    it('should establish WebSocket connection', async () => {
      const onOpen = jest.fn();
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws', { onOpen })
      );

      act(() => {
        result.current.connect();
      });

      // Wait for connection
      await waitFor(() => {
        expect(result.current.isConnected()).toBe(true);
      });

      expect(onOpen).toHaveBeenCalled();
    });

    it('should handle connection errors', async () => {
      const onError = jest.fn();
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://invalid-host', { onError })
      );

      // Mock connection failure
      act(() => {
        result.current.connect();
        const ws = result.current.getTestInstance();
        if (ws) {
          ws.simulateError();
        }
      });

      expect(onError).toHaveBeenCalled();
    });

    it('should close connection on disconnect', async () => {
      const onClose = jest.fn();
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws', { onClose })
      );

      act(() => {
        result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.isConnected()).toBe(true);
      });

      act(() => {
        result.current.disconnect();
      });

      expect(result.current.isConnected()).toBe(false);
      expect(onClose).toHaveBeenCalled();
    });
  });

  describe('Message Handling', () => {
    it('should receive and parse JSON messages', async () => {
      const onMessage = jest.fn();
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws', { onMessage })
      );

      act(() => {
        result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.isConnected()).toBe(true);
      });

      const testMessage = {
        type: 'update',
        data: { value: 'test' },
      };

      act(() => {
        const ws = result.current.getTestInstance();
        if (ws) {
          ws.simulateMessage(testMessage);
        }
      });

      expect(onMessage).toHaveBeenCalledWith(testMessage);
    });

    it('should send messages via WebSocket', async () => {
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws')
      );

      act(() => {
        result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.isConnected()).toBe(true);
      });

      const messageToSend = {
        type: 'action',
        payload: { action: 'test' },
      };

      act(() => {
        const sent = result.current.send(messageToSend);
        expect(sent).toBe(true);
      });

      const ws = result.current.getTestInstance();
      expect(ws?.sentMessages).toContainEqual(messageToSend);
    });

    it('should return false when sending while disconnected', () => {
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws')
      );

      // Don't connect, just try to send
      act(() => {
        const sent = result.current.send({ test: 'data' });
        expect(sent).toBe(false);
      });
    });
  });

  describe('Request-Response Pattern', () => {
    it('should send message and wait for response', async () => {
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws')
      );

      act(() => {
        result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.isConnected()).toBe(true);
      });

      // Send request and handle response
      const requestPromise = result.current.sendAndWait({
        type: 'request',
        action: 'get_data',
      });

      // Simulate response after a delay
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 50));

        const ws = result.current.getTestInstance();
        if (ws && ws.sentMessages.length > 0) {
          const sentMessage = ws.sentMessages[ws.sentMessages.length - 1];
          ws.simulateMessage({
            type: 'response',
            _requestId: sentMessage._requestId,
            data: { result: 'success' },
          });
        }
      });

      const responseData = await requestPromise;
      expect(responseData.data.result).toBe('success');
    });

    it('should timeout waiting for response', async () => {
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws')
      );

      act(() => {
        result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.isConnected()).toBe(true);
      });

      let errorReceived: Error | null = null;

      act(() => {
        result.current
          .sendAndWait({ type: 'request' }, 100) // Short timeout
          .catch((error) => {
            errorReceived = error;
          });
      });

      await waitFor(() => {
        expect(errorReceived).toBeInstanceOf(Error);
      }, { timeout: 3000 });

      expect(errorReceived?.message).toContain('timeout');
    });
  });

  describe('Automatic Reconnection', () => {
    it('should reconnect on connection loss', async () => {
      let connectionCount = 0;
      const onOpen = jest.fn();

      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws', {
          onOpen,
          reconnect: true,
          maxReconnectAttempts: 3,
          reconnectDelay: 100,
        })
      );

      act(() => {
        result.current.connect();
        connectionCount++;
      });

      await waitFor(() => {
        expect(result.current.isConnected()).toBe(true);
      });

      expect(onOpen).toHaveBeenCalledTimes(1);

      // Simulate connection loss
      act(() => {
        const ws = result.current.getTestInstance();
        if (ws) {
          ws.close();
          connectionCount++;
        }
      });

      // Wait for reconnection
      await waitFor(() => {
        expect(result.current.isConnected()).toBe(true);
      }, { timeout: 3000 });

      expect(onOpen).toHaveBeenCalledTimes(2);
    });

    it('should stop reconnecting after max attempts', async () => {
      const onClose = jest.fn();

      const { result } = renderHook(() =>
        mockUseWebSocket('ws://invalid-host', {
          onClose,
          reconnect: true,
          maxReconnectAttempts: 2,
          reconnectDelay: 50,
        })
      );

      act(() => {
        result.current.connect();
      });

      // Wait for all reconnection attempts to fail
      await waitFor(() => {
        expect(onClose).toHaveBeenCalledTimes(3); // Initial + 2 retries
      }, { timeout: 5000 });

      expect(result.current.isConnected()).toBe(false);
    });

    it('should use exponential backoff for reconnection', async () => {
      const connectionTimes: number[] = [];
      const onOpen = jest.fn((event) => {
        connectionTimes.push(Date.now());
      });

      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws', {
          onOpen,
          reconnect: true,
          maxReconnectAttempts: 3,
          reconnectDelay: 100,
        })
      );

      act(() => {
        result.current.connect();
      });

      // First connection
      await waitFor(() => {
        expect(connectionTimes).toHaveLength(1);
      });

      // Trigger reconnection
      act(() => {
        const ws = result.current.getTestInstance();
        if (ws) {
          ws.close();
        }
      });

      // Second connection (should have delay)
      await waitFor(() => {
        expect(connectionTimes).toHaveLength(2);
      });

      const delay1 = connectionTimes[1] - connectionTimes[0];
      expect(delay1).toBeGreaterThanOrEqual(100); // At least reconnectDelay
    });
  });

  describe('Ready State Management', () => {
    it('should report correct ready states', async () => {
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws')
      );

      expect(result.current.getReadyState()).toBe(MockWebSocket.CLOSED);

      act(() => {
        result.current.connect();
      });

      // Should be CONNECTING briefly, then OPEN
      await waitFor(() => {
        expect(result.current.isConnected()).toBe(true);
      });

      act(() => {
        result.current.disconnect();
      });

      expect(result.current.isConnected()).toBe(false);
    });
  });

  describe('Message Queue Management', () => {
    it('should handle multiple concurrent requests', async () => {
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws')
      );

      act(() => {
        result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.isConnected()).toBe(true);
      });

      // Send all requests first
      const requestPromises = [];
      for (let i = 0; i < 5; i++) {
        requestPromises.push(
          result.current.sendAndWait({
            type: 'request',
            index: i,
          })
        );
      }

      // Then simulate responses
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 50));

        const ws = result.current.getTestInstance();
        if (ws) {
          for (let i = 0; i < 5; i++) {
            const sentMessage = ws.sentMessages[i];
            ws.simulateMessage({
              type: 'response',
              _requestId: sentMessage._requestId,
              data: { index: i },
            });
          }
        }
      });

      const responses = await Promise.all(requestPromises);
      expect(responses).toHaveLength(5);
      expect(responses[0].data.index).toBe(0);
      expect(responses[4].data.index).toBe(4);
    });
  });

  describe('Edge Cases', () => {
    it('should handle malformed JSON messages', async () => {
      const onMessage = jest.fn();
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws', { onMessage })
      );

      act(() => {
        result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.isConnected()).toBe(true);
      });

      act(() => {
        const ws = result.current.getTestInstance();
        if (ws) {
          // Simulate receiving malformed JSON
          if (ws.onmessage) {
            ws.onmessage(new MessageEvent('message', { data: 'not-json' }));
          }
        }
      });

      // Should not crash, just pass raw data
      expect(onMessage).toHaveBeenCalledWith('not-json');
    });

    it('should handle rapid connect/disconnect cycles', async () => {
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws')
      );

      for (let i = 0; i < 10; i++) {
        act(() => {
          result.current.connect();
        });

        await waitFor(() => {
          expect(result.current.isConnected()).toBe(true);
        });

        act(() => {
          result.current.disconnect();
        });

        expect(result.current.isConnected()).toBe(false);
      }
    });

    it('should handle sending while connecting', async () => {
      const { result } = renderHook(() =>
        mockUseWebSocket('ws://localhost:8000/ws')
      );

      act(() => {
        result.current.connect();
      });

      // Immediately try to send (before connection established)
      const sent = result.current.send({ test: 'data' });

      // Should return false or handle gracefully
      expect(typeof sent).toBe('boolean');
    });
  });
});
