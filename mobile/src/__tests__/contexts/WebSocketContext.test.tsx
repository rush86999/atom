/**
 * WebSocketContext Tests
 *
 * Tests for WebSocket context provider including:
 * - Connection state management (connecting, connected, disconnected, error)
 * - Reconnection logic with retry attempts and max limits
 * - Connection quality tracking (excellent, good, poor, offline)
 * - Streaming functionality (chunks, complete, errors)
 * - Room management (join, leave, persistence)
 * - Heartbeat mechanism (connection quality tracking)
 * - Agent chat hook (message management)
 * - Typing indicators
 * - Event emission and listeners
 * - Cleanup on unmount
 */

// Set environment variables before any imports
process.env.EXPO_PUBLIC_SOCKET_URL = 'http://localhost:8000';

// Mock expo-constants before importing
jest.mock('expo-constants', () => ({
  expoConfig: {
    name: 'Atom',
    slug: 'atom',
    version: '1.0.0',
    extra: {
      socketUrl: 'http://localhost:8000',
    },
  },
  default: {
    expoConfig: {
      name: 'Atom',
      slug: 'atom',
      version: '1.0.0',
      extra: {
        socketUrl: 'http://localhost:8000',
      },
    },
  },
}));

// Mock socket.io-client to use our mock utilities
jest.mock('socket.io-client', () => {
  const actual = jest.requireActual('../helpers/websocketMocks');
  return {
    io: actual.createMockSocket,
  };
});

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react-native';
import { WebSocketProvider, useWebSocket, useAgentChat } from '../../contexts/WebSocketContext';
import { AuthProvider, useAuth } from '../../contexts/AuthContext';
import { Text, View, Pressable } from 'react-native';

import AsyncStorage from '@react-native-async-storage/async-storage';
import { flushPromises, setupFakeTimers, resetAllMocks } from '../helpers/testUtils';
import {
  createMockSocket,
  getMockSocket,
  simulateConnection,
  simulateDisconnection,
  simulateConnectionError,
  simulateReconnectAttempt,
  simulateReconnect,
  simulateReconnectFailed,
  simulateEvent,
  resetMockSockets,
  getAllEmittedEvents,
} from '../helpers/websocketMocks';

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage');

// Mock AuthContext
jest.mock('../../contexts/AuthContext', () => ({
  ...jest.requireActual('../../contexts/AuthContext'),
  useAuth: jest.fn(),
}));

// ============================================================================
// Test Components
// ============================================================================

interface WebSocketTestComponentProps {
  children?: React.ReactNode;
}

const WebSocketTestComponent: React.FC<WebSocketTestComponentProps> = ({ children }) => {
  const { isConnected, isConnecting, connectionError, connectionQuality, socket } = useWebSocket();
  const { isAuthenticated } = useAuth();

  return (
    <View>
      <Text testID="isConnected">{isConnected.toString()}</Text>
      <Text testID="isConnecting">{isConnecting.toString()}</Text>
      <Text testID="connectionError">{connectionError || 'null'}</Text>
      <Text testID="connectionQuality">{connectionQuality}</Text>
      <Text testID="isAuthenticated">{isAuthenticated.toString()}</Text>
      <Text testID="socketId">{socket?.id || 'no socket'}</Text>
      {children}
    </View>
  );
};

const renderWithWebSocketProvider = (component?: React.ReactNode) => {
  return render(
    <AuthProvider>
      <WebSocketProvider>
        <WebSocketTestComponent />
        {component}
      </WebSocketProvider>
    </AuthProvider>
  );
};

// ============================================================================
// Setup and Teardown
// ============================================================================

beforeEach(() => {
  resetAllMocks();
  setupFakeTimers();
  resetMockSockets();

  // Default auth state - authenticated
  (require('../../contexts/AuthContext').useAuth as jest.Mock).mockReturnValue({
    isAuthenticated: true,
    isLoading: false,
    user: { id: 'user_1', email: 'test@example.com' },
    getAccessToken: jest.fn().mockResolvedValue('mock_access_token'),
  });

  // Default AsyncStorage mocks
  (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);
  (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
  (AsyncStorage.removeItem as jest.Mock).mockResolvedValue(undefined);
  (AsyncStorage.getAllKeys as jest.Mock).mockResolvedValue([]);
});

afterEach(() => {
  jest.runOnlyPendingTimers();
  jest.useRealTimers();
  resetMockSockets();
});

// ============================================================================
// Connection Tests (7 tests)
// ============================================================================

describe('WebSocketContext - Connection', () => {
  it('should initialize with disconnected state', async () => {
    // Mock auth as not authenticated
    (require('../../contexts/AuthContext').useAuth as jest.Mock).mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      user: null,
      getAccessToken: jest.fn().mockResolvedValue(null),
    });

    renderWithWebSocketProvider();

    // Initial state should be disconnected
    expect(screen.getByTestId('isConnected').props.children).toBe('false');
    expect(screen.getByTestId('isConnecting').props.children).toBe('false');
    expect(screen.getByTestId('connectionQuality').props.children).toBe('offline');
  });

  it('should connect when authenticated', async () => {
    renderWithWebSocketProvider();

    await act(async () => {
      await flushPromises();
    });

    // Wait for socket to be created
    await waitFor(() => {
      expect(screen.getByTestId('socketId').props.children).not.toBe('no socket');
    });
  });

  it('should set connecting state during connection', async () => {
    renderWithWebSocketProvider();

    // Should show connecting state
    await waitFor(() => {
      expect(screen.getByTestId('isConnecting').props.children).toBe('true');
    });
  });

  it('should update to connected after successful connection', async () => {
    renderWithWebSocketProvider();

    // Wait for socket to be created
    await waitFor(() => {
      expect(screen.getByTestId('socketId').props.children).not.toBe('no socket');
    });

    const socketId = screen.getByTestId('socketId').props.children;

    // Simulate connection
    act(() => {
      simulateConnection(socketId);
    });

    // Should be connected
    await waitFor(() => {
      expect(screen.getByTestId('isConnected').props.children).toBe('true');
    });

    // Should not be connecting anymore
    expect(screen.getByTestId('isConnecting').props.children).toBe('false');
  });

  it('should handle connection errors', async () => {
    renderWithWebSocketProvider();

    // Wait for socket to be created
    await waitFor(() => {
      expect(screen.getByTestId('socketId').props.children).not.toBe('no socket');
    });

    const socketId = screen.getByTestId('socketId').props.children;

    // Simulate connection error
    act(() => {
      simulateConnectionError(socketId, 'Connection refused');
    });

    // Should show error state
    await waitFor(() => {
      expect(screen.getByTestId('connectionError').props.children).not.toBe('null');
    });

    expect(screen.getByTestId('isConnected').props.children).toBe('false');
  });

  it('should disconnect on logout', async () => {
    const ControlComponent = () => {
      const { disconnect } = useWebSocket();

      return (
        <View>
          <WebSocketTestComponent />
          <Pressable testID="disconnectButton" onPress={disconnect} />
        </View>
      );
    };

    render(
      <WebSocketProvider>
        <ControlComponent />
      </WebSocketProvider>
    );

    // Wait for connection
    await waitFor(() => {
      expect(screen.getByTestId('socketId').props.children).not.toBe('no socket');
    });

    const socketId = screen.getByTestId('socketId').props.children;

    // Simulate connection first
    act(() => {
      simulateConnection(socketId);
    });

    await waitFor(() => {
      expect(screen.getByTestId('isConnected').props.children).toBe('true');
    });

    // Clear mocks before disconnect
    jest.clearAllMocks();

    // Trigger disconnect
    act(() => {
      screen.getByTestId('disconnectButton').props.onPress();
    });

    // Should be disconnected
    await waitFor(() => {
      expect(screen.getByTestId('isConnected').props.children).toBe('false');
    });

    expect(screen.getByTestId('connectionQuality').props.children).toBe('offline');
  });

  it('should update connection quality based on latency', async () => {
    renderWithWebSocketProvider();

    // Wait for socket to be created
    await waitFor(() => {
      expect(screen.getByTestId('socketId').props.children).not.toBe('no socket');
    });

    const socketId = screen.getByTestId('socketId').props.children;

    // Simulate connection
    act(() => {
      simulateConnection(socketId);
    });

    await waitFor(() => {
      expect(screen.getByTestId('isConnected').props.children).toBe('true');
    });

    // Initial connection quality should be 'good' after connection
    expect(screen.getByTestId('connectionQuality').props.children).toBe('good');
  });
});

// ============================================================================
// Reconnection Tests (5 tests)
// ============================================================================

describe('WebSocketContext - Reconnection', () => {
  it('should attempt reconnection after disconnect', async () => {
    renderWithWebSocketProvider();

    // Wait for initial connection
    await waitFor(() => {
      expect(screen.getByTestId('socketId').props.children).not.toBe('no socket');
    });

    const socketId = screen.getByTestId('socketId').props.children;

    // Simulate connection
    act(() => {
      simulateConnection(socketId);
    });

    await waitFor(() => {
      expect(screen.getByTestId('isConnected').props.children).toBe('true');
    });

    // Clear mocks before disconnection
    jest.clearAllMocks();

    // Simulate server disconnect
    act(() => {
      simulateDisconnection(socketId, 'io server disconnect');
    });

    // Should go into connecting state for reconnection
    await waitFor(() => {
      expect(screen.getByTestId('isConnecting').props.children).toBe('true');
    });
  });

  it('should respect MAX_RECONNECT_ATTEMPTS limit', async () => {
    renderWithWebSocketProvider();

    // Wait for socket creation
    await waitFor(() => {
      expect(screen.getByTestId('socketId').props.children).not.toBe('no socket');
    });

    const socketId = screen.getByTestId('socketId').props.children;

    // Simulate multiple failed reconnection attempts
    for (let i = 1; i <= 10; i++) {
      act(() => {
        simulateReconnectAttempt(socketId, i);
      });
    }

    // Simulate final failure
    act(() => {
      simulateReconnectFailed(socketId);
    });

    // Should show error about max attempts
    await waitFor(() => {
      expect(screen.getByTestId('connectionError').props.children).toContain('Unable to connect');
    });
  });

  it('should increment reconnect attempts counter', async () => {
    renderWithWebSocketProvider();

    // Wait for socket creation
    await waitFor(() => {
      expect(screen.getByTestId('socketId').props.children).not.toBe('no socket');
    });

    const socketId = screen.getByTestId('socketId').props.children;

    // Clear mocks
    jest.clearAllMocks();

    // Simulate first reconnection attempt
    act(() => {
      simulateReconnectAttempt(socketId, 1);
    });

    // Should be in connecting state
    await waitFor(() => {
      expect(screen.getByTestId('isConnecting').props.children).toBe('true');
    });

    // Simulate second attempt
    act(() => {
      simulateReconnectAttempt(socketId, 2);
    });

    // Still should be connecting
    expect(screen.getByTestId('isConnecting').props.children).toBe('true');
  });

  it('should stop reconnecting after max attempts', async () => {
    renderWithWebSocketProvider();

    // Wait for socket creation
    await waitFor(() => {
      expect(screen.getByTestId('socketId').props.children).not.toBe('no socket');
    });

    const socketId = screen.getByTestId('socketId').props.children;

    // Clear mocks
    jest.clearAllMocks();

    // Simulate max reconnection attempts (10)
    for (let i = 1; i <= 10; i++) {
      act(() => {
        simulateReconnectAttempt(socketId, i);
      });
    }

    // Simulate reconnect failed event
    act(() => {
      simulateReconnectFailed(socketId);
    });

    // Should stop connecting and show error
    await waitFor(() => {
      expect(screen.getByTestId('isConnecting').props.children).toBe('false');
    });

    expect(screen.getByTestId('connectionError').props.children).toContain('Reconnection failed');
  });

  it('should reconnect after successful reconnection', async () => {
    renderWithWebSocketProvider();

    // Wait for initial connection
    await waitFor(() => {
      expect(screen.getByTestId('socketId').props.children).not.toBe('no socket');
    });

    const socketId = screen.getByTestId('socketId').props.children;

    // Simulate connection
    act(() => {
      simulateConnection(socketId);
    });

    await waitFor(() => {
      expect(screen.getByTestId('isConnected').props.children).toBe('true');
    });

    // Clear mocks before disconnection
    jest.clearAllMocks();

    // Simulate disconnect
    act(() => {
      simulateDisconnection(socketId, 'transport close');
    });

    // Should be disconnected
    expect(screen.getByTestId('isConnected').props.children).toBe('false');

    // Simulate successful reconnection
    act(() => {
      simulateReconnect(socketId, 3);
    });

    // Should be connected again
    await waitFor(() => {
      expect(screen.getByTestId('isConnected').props.children).toBe('true');
    });

    // Should not show error
    expect(screen.getByTestId('connectionError').props.children).toBe('null');
  });

  it('should cleanup on unmount', () => {
    const { unmount } = renderWithWebSocketProvider();

    // Should not throw error on unmount
    expect(() => unmount()).not.toThrow();
  });
});

// ============================================================================
// Streaming Tests (4 tests)
// ============================================================================

describe('WebSocketContext - Streaming', () => {
  it('should send streaming message', async () => {
    const onChunk = jest.fn();
    const TestComponent = () => {
      const { sendStreamingMessage } = useWebSocket();

      return (
        <View>
          <Text
            testID="sendMessage"
            onPress={() => {
              sendStreamingMessage('agent_123', 'test message', 'session_456', {
                onChunk,
                onComplete: jest.fn(),
                onError: jest.fn(),
              });
            }}
          >
            Send Message
          </Text>
        </View>
      );
    };

    const { getByTestId } = renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    // Send message
    await act(async () => {
      getByTestId('sendMessage').props.onPress();
    });

    expect(mockSocket.emit).toHaveBeenCalledWith('agent:streaming_chat', expect.objectContaining({
      agent_id: 'agent_123',
      message: 'test message',
      session_id: 'session_456',
      platform: 'mobile',
    }));
  });

  it('should handle streaming chunks', async () => {
    const onChunk = jest.fn();
    const streamCallbacks = new Map();

    // Store callbacks for testing
    (useWebSocket as jest.MockedFunction<typeof useWebSocket>).mockImplementation(() => {
      React.useState(() => streamCallbacks);
      return React.useContext(React.createContext<any>(undefined));
    });

    const TestComponent = () => {
      const { sendStreamingMessage } = useWebSocket();

      React.useEffect(() => {
        const unsubscribe = sendStreamingMessage('agent_123', 'test', 'session_456', {
          onChunk,
          onComplete: jest.fn(),
          onError: jest.fn(),
        });

        return () => unsubscribe();
      }, []);

      return <View testID="test" />;
    };

    renderWithWebSocketProvider(<TestComponent />);

    // Simulate streaming chunk
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    // Get the stream_id from the emit call
    const emitCall = (mockSocket.emit as jest.Mock).mock.calls.find(call => call[0] === 'agent:streaming_chat');
    if (emitCall && emitCall[1]) {
      const streamId = emitCall[1].stream_id;

      // Simulate streaming chunk
      if (mockSocketListeners['agent:streaming']) {
        mockSocketListeners['agent:streaming']({
          stream_id: streamId,
          token: 'Hello',
          metadata: {},
        });
      }

      expect(onChunk).toHaveBeenCalledWith({ token: 'Hello', metadata: {} });
    }
  });

  it('should handle streaming complete', async () => {
    const onComplete = jest.fn();

    const TestComponent = () => {
      const { sendStreamingMessage } = useWebSocket();

      React.useEffect(() => {
        sendStreamingMessage('agent_123', 'test', 'session_456', {
          onChunk: jest.fn(),
          onComplete,
          onError: jest.fn(),
        });
      }, []);

      return <View testID="test" />;
    };

    renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection and get stream_id
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    const emitCall = (mockSocket.emit as jest.Mock).mock.calls.find(call => call[0] === 'agent:streaming_chat');
    if (emitCall && emitCall[1]) {
      const streamId = emitCall[1].stream_id;

      // Simulate streaming complete
      await act(async () => {
        if (mockSocketListeners['agent:streaming_complete']) {
          mockSocketListeners['agent:streaming_complete']({ stream_id });
        }
      });

      expect(onComplete).toHaveBeenCalled();
    }
  });

  it('should handle streaming error', async () => {
    const onError = jest.fn();

    const TestComponent = () => {
      const { sendStreamingMessage } = useWebSocket();

      React.useEffect(() => {
        sendStreamingMessage('agent_123', 'test', 'session_456', {
          onChunk: jest.fn(),
          onComplete: jest.fn(),
          onError,
        });
      }, []);

      return <View testID="test" />;
    };

    renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection and get stream_id
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    const emitCall = (mockSocket.emit as jest.Mock).mock.calls.find(call => call[0] === 'agent:streaming_chat');
    if (emitCall && emitCall[1]) {
      const streamId = emitCall[1].stream_id;

      // Simulate streaming error
      await act(async () => {
        if (mockSocketListeners['agent:streaming_error']) {
          mockSocketListeners['agent:streaming_error']({ stream_id, error: 'Stream failed' });
        }
      });

      expect(onError).toHaveBeenCalledWith('Stream failed');
    }
  });
});

// ============================================================================
// Room Management Tests (3 tests)
// ============================================================================

describe('WebSocketContext - Rooms', () => {
  it('should join room and persist to storage', async () => {
    const TestComponent = () => {
      const { joinRoom } = useWebSocket();

      return (
        <View>
          <Text testID="joinRoom" onPress={() => joinRoom('agent_123')}>
            Join Room
          </Text>
        </View>
      );
    };

    const { getByTestId } = renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    // Join room
    await act(async () => {
      getByTestId('joinRoom').props.onPress();
    });

    expect(mockSocket.emit).toHaveBeenCalledWith('join', { room: 'agent_123' });
    expect(AsyncStorage.setItem).toHaveBeenCalledWith('socket_room_agent_123', 'true');
  });

  it('should leave room and remove from storage', async () => {
    const TestComponent = () => {
      const { leaveRoom } = useWebSocket();

      return (
        <View>
          <Text testID="leaveRoom" onPress={() => leaveRoom('agent_123')}>
            Leave Room
          </Text>
        </View>
      );
    };

    const { getByTestId } = renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    // Leave room
    await act(async () => {
      getByTestId('leaveRoom').props.onPress();
    });

    expect(mockSocket.emit).toHaveBeenCalledWith('leave', { room: 'agent_123' });
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('socket_room_agent_123');
  });

  it('should rejoin rooms after reconnection', async () => {
    // Mock AsyncStorage to return saved rooms
    (AsyncStorage.getAllKeys as jest.Mock).mockResolvedValue([
      'socket_room_user_1',
      'socket_room_agent_123',
    ]);

    renderWithWebSocketProvider();

    // Simulate connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    // Verify rooms were rejoined
    expect(mockSocket.emit).toHaveBeenCalledWith('join', { room: 'user_1' });
    expect(mockSocket.emit).toHaveBeenCalledWith('join', { room: 'agent_123' });
  });
});

// ============================================================================
// Heartbeat Tests (2 tests)
// ============================================================================

describe('WebSocketContext - Heartbeat', () => {
  it('should send heartbeat every 30 seconds', async () => {
    renderWithWebSocketProvider();

    // Simulate connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
      await flushPromises();
    });

    // Clear previous calls
    const initialEmitCalls = (mockSocket.emit as jest.Mock).mock.calls.length;

    // Advance time by 30 seconds
    act(() => {
      jest.advanceTimersByTime(30000);
    });

    // Should have at least one more emit call (the ping)
    expect((mockSocket.emit as jest.Mock).mock.calls.length).toBeGreaterThan(initialEmitCalls);
    expect(mockSocket.emit).toHaveBeenCalledWith('ping');
  });

  it('should update connection quality based on latency', async () => {
    const { getByTestId } = renderWithWebSocketProvider();

    // Simulate connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
      await flushPromises();
    });

    // Simulate excellent latency (< 100ms)
    act(() => {
      jest.advanceTimersByTime(30000);
      if (mockSocketOnceListeners.pong) {
        setTimeout(() => mockSocketOnceListeners.pong(), 50);
        jest.advanceTimersByTime(50);
      }
    });

    await waitFor(() => {
      expect(getByTestId('connectionQuality')).toHaveTextContent('excellent');
    });

    // Simulate good latency (100-300ms)
    await act(async () => {
      jest.advanceTimersByTime(30000);
      jest.advanceTimersByTime(30000);
      jest.advanceTimersByTime(30000);
      if (mockSocketOnceListeners.pong) {
        setTimeout(() => mockSocketOnceListeners.pong(), 200);
        jest.advanceTimersByTime(200);
      }
    });

    await waitFor(() => {
      expect(getByTestId('connectionQuality')).toHaveTextContent('good');
    });
  });
});

// ============================================================================
// Agent Chat Hook Tests (2 tests)
// ============================================================================

describe('useAgentChat', () => {
  it('should manage chat messages', async () => {
    const TestComponent = () => {
      const { messages } = useAgentChat('agent_123');

      return (
        <View>
          <Text testID="messageCount">{messages.length}</Text>
        </View>
      );
    };

    const { getByTestId } = renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    // Simulate message received
    await act(async () => {
      if (mockSocketListeners['agent:message']) {
        mockSocketListeners['agent:message']({
          agent_id: 'agent_123',
          content: 'Hello from agent',
        });
      }
    });

    expect(getByTestId('messageCount')).toHaveTextContent('1');
  });

  it('should send message via socket', async () => {
    const TestComponent = () => {
      const { sendMessage } = useAgentChat('agent_123');

      return (
        <View>
          <Text
            testID="sendMessage"
            onPress={() => sendMessage('Hello agent')}
          >
            Send
          </Text>
        </View>
      );
    };

    const { getByTestId } = renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    // Clear previous emit calls
    (mockSocket.emit as jest.Mock).mockClear();

    // Send message
    await act(async () => {
      getByTestId('sendMessage').props.onPress();
    });

    expect(mockSocket.emit).toHaveBeenCalledWith('agent:chat', {
      agent_id: 'agent_123',
      message: 'Hello agent',
    });
  });
});

// ============================================================================
// Typing Indicator Tests (2 tests)
// ============================================================================

describe('WebSocketContext - Typing Indicators', () => {
  it('should subscribe to typing indicators', async () => {
    const callback = jest.fn();
    const TestComponent = () => {
      const { subscribeToTyping } = useWebSocket();

      React.useEffect(() => {
        const unsubscribe = subscribeToTyping(callback);
        return () => unsubscribe();
      }, []);

      return <View testID="test" />;
    };

    renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    expect(mockSocket.emit).toHaveBeenCalledWith('subscribe_typing');
  });

  it('should receive typing indicator updates', async () => {
    const callback = jest.fn();
    const agents = [{ id: 'agent_123', name: 'Test Agent' }];

    const TestComponent = () => {
      const { subscribeToTyping } = useWebSocket();

      React.useEffect(() => {
        subscribeToTyping(callback);
      }, []);

      return <View testID="test" />;
    };

    renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    // Simulate typing indicator
    await act(async () => {
      if (mockSocketListeners['agent:typing']) {
        mockSocketListeners['agent:typing']({ agents });
      }
    });

    expect(callback).toHaveBeenCalledWith(agents);
  });
});

// ============================================================================
// Stream Subscription Tests (2 tests)
// ============================================================================

describe('WebSocketContext - Stream Subscription', () => {
  it('should subscribe to stream updates', async () => {
    const onChunk = jest.fn();
    const onComplete = jest.fn();
    const onError = jest.fn();

    const TestComponent = () => {
      const { subscribeToStream } = useWebSocket();

      React.useEffect(() => {
        const unsubscribe = subscribeToStream('session_456', onChunk, onComplete, onError);
        return () => unsubscribe();
      }, []);

      return <View testID="test" />;
    };

    renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    expect(mockSocket.emit).toHaveBeenCalledWith('subscribe_stream', {
      session_id: 'session_456',
      stream_id: 'subscribe_session_456',
    });
  });

  it('should unsubscribe from stream on cleanup', async () => {
    const onChunk = jest.fn();
    const onComplete = jest.fn();
    const onError = jest.fn();

    const TestComponent = () => {
      const { subscribeToStream } = useWebSocket();

      React.useEffect(() => {
        const unsubscribe = subscribeToStream('session_456', onChunk, onComplete, onError);
        return () => {
          unsubscribe();
          expect(mockSocket.emit).toHaveBeenCalledWith('unsubscribe_stream', {
            stream_id: 'subscribe_session_456',
          });
        };
      }, []);

      return <View testID="test" />;
    };

    const { unmount } = renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    unmount();
  });
});

// ============================================================================
// Event Emission Tests (2 tests)
// ============================================================================

describe('WebSocketContext - Event Emission', () => {
  it('should emit events when connected', async () => {
    const TestComponent = () => {
      const { emit } = useWebSocket();

      return (
        <View>
          <Text
            testID="emitEvent"
            onPress={() => emit('test:event', { data: 'test' })}
          >
            Emit
          </Text>
        </View>
      );
    };

    const { getByTestId } = renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    // Clear previous emit calls
    (mockSocket.emit as jest.Mock).mockClear();

    // Emit event
    await act(async () => {
      getByTestId('emitEvent').props.onPress();
    });

    expect(mockSocket.emit).toHaveBeenCalledWith('test:event', { data: 'test' });
  });

  it('should not emit events when disconnected', async () => {
    const consoleWarn = jest.spyOn(console, 'warn').mockImplementation();

    const TestComponent = () => {
      const { emit } = useWebSocket();

      return (
        <View>
          <Text
            testID="emitEvent"
            onPress={() => emit('test:event', { data: 'test' })}
          >
            Emit
          </Text>
        </View>
      );
    };

    const { getByTestId } = renderWithWebSocketProvider(<TestComponent />);

    // Emit event while not connected
    await act(async () => {
      getByTestId('emitEvent').props.onPress();
    });

    expect(mockSocket.emit).not.toHaveBeenCalled();
    expect(consoleWarn).toHaveBeenCalledWith('Cannot emit event: socket not connected');

    consoleWarn.mockRestore();
  });
});

// ============================================================================
// Event Listener Tests (2 tests)
// ============================================================================

describe('WebSocketContext - Event Listeners', () => {
  it('should register event listeners', async () => {
    const callback = jest.fn();

    const TestComponent = () => {
      const { on } = useWebSocket();

      React.useEffect(() => {
        on('test:event', callback);
      }, []);

      return <View testID="test" />;
    };

    renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    expect(mockSocket.on).toHaveBeenCalledWith('test:event', callback);
  });

  it('should unregister event listeners', async () => {
    const callback = jest.fn();

    const TestComponent = () => {
      const { off } = useWebSocket();

      return (
        <View>
          <Text
            testID="offEvent"
            onPress={() => off('test:event', callback)}
          >
            Off
          </Text>
        </View>
      );
    };

    const { getByTestId } = renderWithWebSocketProvider(<TestComponent />);

    // Wait for connection
    await act(async () => {
      mockSocketConnected = true;
      if (mockSocketListeners.connect) {
        mockSocketListeners.connect();
      }
    });

    // Unregister event
    await act(async () => {
      getByTestId('offEvent').props.onPress();
    });

    expect(mockSocket.off).toHaveBeenCalledWith('test:event', callback);
  });
});
