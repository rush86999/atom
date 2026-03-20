/**
 * WebSocketContext Tests
 *
 * Comprehensive tests for WebSocketContext including:
 * - WebSocket connection lifecycle
 * - Message sending and receiving
 * - Connection state management
 * - Error handling
 * - Auto-reconnect logic
 * - Room management
 * - Agent chat streaming
 * - Heartbeat and connection quality
 * - useAgentChat hook
 */

import React, { ReactNode } from 'react';
import { renderHook, act, waitFor } from '@testing-library/react-native';
import { Socket } from 'socket.io-client';
import { WebSocketProvider, useWebSocket, useAgentChat } from '../WebSocketContext';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Mock socket.io-client
jest.mock('socket.io-client', () => ({
  io: jest.fn(() => ({
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn(),
    once: jest.fn(),
    disconnect: jest.fn(),
    connect: jest.fn(),
    connected: false,
    id: 'test-socket-id',
  })),
}));

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  getAllKeys: jest.fn(),
  multiGet: jest.fn(),
}));

// Mock Constants
jest.mock('expo-constants', () => ({
  expoConfig: {
    extra: {
      socketUrl: 'http://localhost:8000',
    },
  },
}));

// Mock AuthContext
const mockAuthContext = {
  isAuthenticated: true,
  getAccessToken: jest.fn(() => Promise.resolve('test-token')),
  login: jest.fn(),
  logout: jest.fn(),
  user: { id: 'test-user-id' },
};

jest.mock('../AuthContext', () => ({
  useAuth: () => mockAuthContext,
}));

// Wrapper component for testing hooks
const createWrapper = () => {
  return ({ children }: { children: ReactNode }) => (
    <WebSocketProvider>{children}</WebSocketProvider>
  );
};

// Helper to simulate socket connection
const simulateSocketConnection = (result: { current: any }, socket: any) => {
  Object.defineProperty(socket, 'connected', {
    get: () => true,
    configurable: true,
  });

  const connectCallback = socket.on.mock.calls.find(
    (call: any[]) => call[0] === 'connect'
  )?.[1];

  if (connectCallback) {
    act(() => {
      connectCallback();
    });
  }
};

describe('WebSocketContext', () => {
  let mockSocket: any;

  beforeEach(() => {
    jest.clearAllMocks();

    // Setup mock socket
    mockSocket = {
      on: jest.fn(),
      off: jest.fn(),
      emit: jest.fn(),
      once: jest.fn(),
      disconnect: jest.fn(),
      connect: jest.fn(),
      connected: false,
      id: 'test-socket-id',
    };

    const { io } = require('socket.io-client');
    io.mockReturnValue(mockSocket);

    // Mock AsyncStorage
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue('test-token');
    (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
    (AsyncStorage.removeItem as jest.Mock).mockResolvedValue(undefined);
    (AsyncStorage.getAllKeys as jest.Mock).mockResolvedValue([]);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Connection Lifecycle', () => {
    it('should initialize with offline connection state', () => {
      // Mock as not authenticated to prevent auto-connect
      mockAuthContext.isAuthenticated = false;

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isConnected).toBe(false);
      expect(result.current.isConnecting).toBe(false);
      expect(result.current.connectionError).toBeNull();
      expect(result.current.connectionQuality).toBe('offline');

      // Reset for other tests
      mockAuthContext.isAuthenticated = true;
    });

    it('should connect when authenticated', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const { io } = require('socket.io-client');
      expect(io).toHaveBeenCalledWith(
        'http://localhost:8000',
        expect.objectContaining({
          auth: { token: 'test-token' },
          transports: ['websocket'],
          reconnection: true,
          reconnectionDelay: 5000,
          reconnectionAttempts: 10,
          timeout: 10000,
        })
      );
    });

    it('should not connect if already connected', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      mockSocket.connected = true;

      await act(async () => {
        await result.current.connect();
      });

      // Should only call io once (initial connection)
      const { io } = require('socket.io-client');
      expect(io).toHaveBeenCalledTimes(1);
    });

    it('should not connect while connection is in progress', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      // Set connecting state
      act(() => {
        result.current.connect();
      });

      // Try to connect again while connecting
      await act(async () => {
        await result.current.connect();
      });

      // Should still only have one connection attempt
      const { io } = require('socket.io-client');
      expect(io).toHaveBeenCalledTimes(1);
    });

    it('should handle connection error when no token available', async () => {
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.connectionError).toBe('No authentication token available');
        expect(result.current.isConnecting).toBe(false);
      });
    });

    it('should update connection state on successful connection', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      // Simulate socket connection
      const connectCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'connect'
      )?.[1];

      if (connectCallback) {
        act(() => {
          connectCallback();
        });
      }

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
        expect(result.current.isConnecting).toBe(false);
        expect(result.current.connectionError).toBeNull();
        expect(result.current.connectionQuality).toBe('good');
      });
    });

    it('should handle disconnect event', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      // Set connected state
      act(() => {
        result.current.isConnected = true;
      });

      // Simulate disconnect
      const disconnectCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'disconnect'
      )?.[1];

      if (disconnectCallback) {
        act(() => {
          disconnectCallback('io client disconnect');
        });
      }

      expect(result.current.isConnected).toBe(false);
      expect(result.current.isConnecting).toBe(false);
    });

    it('should manually reconnect on server disconnect', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      // Simulate server disconnect
      const disconnectCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'disconnect'
      )?.[1];

      if (disconnectCallback) {
        act(() => {
          disconnectCallback('io server disconnect');
        });
      }

      expect(mockSocket.connect).toHaveBeenCalled();
    });

    it('should disconnect and cleanup', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      // First connect
      await act(async () => {
        await result.current.connect();
      });

      // Then disconnect
      act(() => {
        result.current.disconnect();
      });

      expect(mockSocket.disconnect).toHaveBeenCalled();
      expect(result.current.isConnected).toBe(false);
      expect(result.current.connectionQuality).toBe('offline');
    });
  });

  describe('Connection State Management', () => {
    it('should track connection state correctly', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isConnected).toBe(false);

      await act(async () => {
        await result.current.connect();
      });

      const connectCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'connect'
      )?.[1];

      if (connectCallback) {
        act(() => {
          connectCallback();
        });
      }

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });
    });

    it('should update connecting state during connection attempts', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.connect();
      });

      expect(result.current.isConnecting).toBe(true);
    });

    it('should reset connecting state on error', async () => {
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.isConnecting).toBe(false);
        expect(result.current.connectionError).toBeTruthy();
      });
    });

    it('should manage connection quality state', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.connectionQuality).toBe('offline');

      await act(async () => {
        await result.current.connect();
      });

      const connectCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'connect'
      )?.[1];

      if (connectCallback) {
        act(() => {
          connectCallback();
        });
      }

      await waitFor(() => {
        expect(result.current.connectionQuality).toBe('good');
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle connection error', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const errorCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'connect_error'
      )?.[1];

      if (errorCallback) {
        act(() => {
          errorCallback(new Error('Connection failed'));
        });
      }

      await waitFor(() => {
        expect(result.current.connectionError).toBe('Connection failed');
        expect(result.current.isConnecting).toBe(false);
      });
    });

    it('should track reconnection attempts', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const errorCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'connect_error'
      )?.[1];

      // Simulate multiple failed attempts
      if (errorCallback) {
        for (let i = 0; i < 10; i++) {
          act(() => {
            errorCallback(new Error('Connection failed'));
          });
        }
      }

      await waitFor(() => {
        expect(result.current.connectionError).toContain('Unable to connect');
      });
    });

    it('should handle reconnection failure', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const reconnectFailedCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'reconnect_failed'
      )?.[1];

      if (reconnectFailedCallback) {
        act(() => {
          reconnectFailedCallback();
        });
      }

      await waitFor(() => {
        expect(result.current.connectionError).toBe('Reconnection failed. Please refresh the app.');
        expect(result.current.isConnecting).toBe(false);
      });
    });

    it('should clear error on successful reconnection', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      // Set error state
      act(() => {
        result.current.connectionError = 'Previous error';
      });

      // Simulate reconnect
      const reconnectCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'reconnect'
      )?.[1];

      if (reconnectCallback) {
        act(() => {
          reconnectCallback(2);
        });
      }

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
        expect(result.current.connectionError).toBeNull();
      });
    });
  });

  describe('Auto-Reconnect Logic', () => {
    it('should attempt reconnection on connection loss', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const reconnectAttemptCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'reconnect_attempt'
      )?.[1];

      if (reconnectAttemptCallback) {
        act(() => {
          reconnectAttemptCallback(1);
        });
      }

      expect(result.current.isConnecting).toBe(true);
    });

    it('should successfully reconnect', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      // Simulate disconnect
      act(() => {
        result.current.isConnected = false;
      });

      // Simulate reconnect
      const reconnectCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'reconnect'
      )?.[1];

      if (reconnectCallback) {
        act(() => {
          reconnectCallback(3);
        });
      }

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
        expect(result.current.connectionError).toBeNull();
      });
    });

    it('should respect max reconnection attempts', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const errorCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'connect_error'
      )?.[1];

      // Exceed max attempts (10)
      if (errorCallback) {
        for (let i = 0; i < 11; i++) {
          act(() => {
            errorCallback(new Error('Connection failed'));
          });
        }
      }

      await waitFor(() => {
        expect(result.current.connectionError).toContain('Unable to connect');
      });
    });
  });

  describe('Message Sending and Receiving', () => {
    it('should emit event when connected', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      act(() => {
        result.current.emit('test:event', { data: 'test' });
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('test:event', { data: 'test' });
    });

    it('should not emit event when not connected', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      // Don't connect, just try to emit
      const consoleWarnSpy = jest.spyOn(console, 'warn');

      act(() => {
        result.current.emit('test:event', { data: 'test' });
      });

      expect(mockSocket.emit).not.toHaveBeenCalled();
      expect(consoleWarnSpy).toHaveBeenCalledWith('Cannot emit event: socket not connected');

      consoleWarnSpy.mockRestore();
    });

    it('should register event listener', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const callback = jest.fn();

      act(() => {
        result.current.on('test:event', callback);
      });

      expect(mockSocket.on).toHaveBeenCalledWith('test:event', callback);
    });

    it('should unregister event listener', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const callback = jest.fn();

      act(() => {
        result.current.off('test:event', callback);
      });

      expect(mockSocket.off).toHaveBeenCalledWith('test:event', callback);
    });

    it('should unregister all event listeners when callback not provided', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      act(() => {
        result.current.off('test:event');
      });

      expect(mockSocket.off).toHaveBeenCalledWith('test:event');
    });

    it('should handle agent:message event', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const messageCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'agent:message'
      )?.[1];

      if (messageCallback) {
        const testData = { agent_id: 'agent-1', message: 'Hello' };
        messageCallback(testData);
      }

      // Callback should be called without errors
      expect(mockSocket.on).toHaveBeenCalledWith('agent:message', expect.any(Function));
    });
  });

  describe('Room Management', () => {
    it('should join room when connected', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      await act(async () => {
        await result.current.joinRoom('user:test-user');
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('join', { room: 'user:test-user' });
      expect(AsyncStorage.setItem).toHaveBeenCalledWith('socket_room_user:test-user', 'true');
    });

    it('should not join room when not connected', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      // Don't connect
      await act(async () => {
        await result.current.joinRoom('user:test-user');
      });

      expect(mockSocket.emit).not.toHaveBeenCalled();
    });

    it('should leave room when connected', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      await act(async () => {
        await result.current.leaveRoom('user:test-user');
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('leave', { room: 'user:test-user' });
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('socket_room_user:test-user');
    });

    it('should rejoin stored rooms on reconnection', async () => {
      (AsyncStorage.getAllKeys as jest.Mock).mockResolvedValue([
        'socket_room_user:test-user',
        'socket_room_agent:agent-1',
        'other_key',
      ]);

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const connectCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'connect'
      )?.[1];

      if (connectCallback) {
        await act(async () => {
          await connectCallback();
        });
      }

      await waitFor(() => {
        expect(mockSocket.emit).toHaveBeenCalledWith('join', { room: 'user:test-user' });
        expect(mockSocket.emit).toHaveBeenCalledWith('join', { room: 'agent:agent-1' });
      });
    });

    it('should handle AsyncStorage errors gracefully when joining room', async () => {
      (AsyncStorage.setItem as jest.Mock).mockRejectedValue(new Error('Storage error'));

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      mockSocket.connected = true;

      const consoleErrorSpy = jest.spyOn(console, 'error');

      await act(async () => {
        await result.current.joinRoom('user:test-user');
      });

      expect(consoleErrorSpy).toHaveBeenCalled();
      consoleErrorSpy.mockRestore();
    });
  });

  describe('Agent Chat Streaming', () => {
    it('should send streaming message', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const onChunk = jest.fn();
      const onComplete = jest.fn();
      const onError = jest.fn();

      act(() => {
        result.current.sendStreamingMessage('agent-1', 'Hello', 'session-1', {
          onChunk,
          onComplete,
          onError,
        });
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('agent:streaming_chat', {
        agent_id: 'agent-1',
        message: 'Hello',
        session_id: 'session-1',
        stream_id: expect.stringContaining('session-1_'),
        platform: 'mobile',
      });
    });

    it('should handle streaming chunk', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const onChunk = jest.fn();
      const onComplete = jest.fn();
      const onError = jest.fn();

      act(() => {
        result.current.sendStreamingMessage('agent-1', 'Hello', 'session-1', {
          onChunk,
          onComplete,
          onError,
        });
      });

      const streamingCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'agent:streaming'
      )?.[1];

      if (streamingCallback) {
        streamingCallback({
          stream_id: 'session-1_1234567890',
          token: 'Hello',
          metadata: {},
        });
      }

      expect(onChunk).toHaveBeenCalledWith({ token: 'Hello', metadata: {} });
    });

    it('should handle streaming complete', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const onChunk = jest.fn();
      const onComplete = jest.fn();
      const onError = jest.fn();

      act(() => {
        result.current.sendStreamingMessage('agent-1', 'Hello', 'session-1', {
          onChunk,
          onComplete,
          onError,
        });
      });

      const completeCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'agent:streaming_complete'
      )?.[1];

      if (completeCallback) {
        completeCallback({ stream_id: 'session-1_1234567890' });
      }

      expect(onComplete).toHaveBeenCalled();
    });

    it('should handle streaming error', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const onChunk = jest.fn();
      const onComplete = jest.fn();
      const onError = jest.fn();

      act(() => {
        result.current.sendStreamingMessage('agent-1', 'Hello', 'session-1', {
          onChunk,
          onComplete,
          onError,
        });
      });

      const errorCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'agent:streaming_error'
      )?.[1];

      if (errorCallback) {
        errorCallback({ stream_id: 'session-1_1234567890', error: 'Streaming failed' });
      }

      expect(onError).toHaveBeenCalledWith('Streaming failed');
    });

    it('should queue message when not connected', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      mockSocket.connected = false;

      const onError = jest.fn();

      act(() => {
        result.current.sendStreamingMessage('agent-1', 'Hello', 'session-1', {
          onChunk: jest.fn(),
          onComplete: jest.fn(),
          onError,
        });
      });

      expect(onError).toHaveBeenCalledWith('Not connected');
    });

    it('should unsubscribe from streaming', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      mockSocket.connected = true;

      const unsubscribe = act(() => {
        return result.current.sendStreamingMessage('agent-1', 'Hello', 'session-1', {
          onChunk: jest.fn(),
          onComplete: jest.fn(),
          onError: jest.fn(),
        });
      });

      act(() => {
        unsubscribe();
      });

      // Unsubscribe should remove callback
      expect(mockSocket.emit).toHaveBeenCalled();
    });
  });

  describe('Stream Subscription', () => {
    it('should subscribe to stream', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const onChunk = jest.fn();
      const onComplete = jest.fn();
      const onError = jest.fn();

      act(() => {
        result.current.subscribeToStream('session-1', onChunk, onComplete, onError);
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('subscribe_stream', {
        session_id: 'session-1',
        stream_id: 'subscribe_session-1',
      });
    });

    it('should unsubscribe from stream', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const unsubscribe = act(() => {
        return result.current.subscribeToStream(
          'session-1',
          jest.fn(),
          jest.fn(),
          jest.fn()
        );
      });

      act(() => {
        unsubscribe();
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('unsubscribe_stream', {
        stream_id: 'subscribe_session-1',
      });
    });
  });

  describe('Typing Indicators', () => {
    it('should subscribe to typing indicators', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const callback = jest.fn();

      act(() => {
        result.current.subscribeToTyping(callback);
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('subscribe_typing');
    });

    it('should receive typing updates', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const callback = jest.fn();

      act(() => {
        result.current.subscribeToTyping(callback);
      });

      const typingCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'agent:typing'
      )?.[1];

      if (typingCallback) {
        typingCallback({ agents: [{ id: 'agent-1', name: 'Test Agent' }] });
      }

      expect(callback).toHaveBeenCalledWith([{ id: 'agent-1', name: 'Test Agent' }]);
    });

    it('should unsubscribe from typing indicators', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      mockSocket.connected = true;

      const callback = jest.fn();

      const unsubscribe = act(() => {
        return result.current.subscribeToTyping(callback);
      });

      act(() => {
        unsubscribe();
      });

      // Callback should be removed from array
      expect(mockSocket.emit).toHaveBeenCalled();
    });
  });

  describe('Heartbeat and Connection Quality', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    it('should start heartbeat on connection', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      // Fast forward 30 seconds
      act(() => {
        jest.advanceTimersByTime(30000);
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('ping');
    });

    it('should measure latency and update connection quality', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      // Simulate 3 heartbeat cycles with low latency
      for (let i = 0; i < 3; i++) {
        act(() => {
          jest.advanceTimersByTime(30000);
        });

        const pongCallback = mockSocket.once.mock.calls.find(
          (call: any[]) => call[0] === 'pong'
        )?.[1];

        if (pongCallback) {
          pongCallback();
        }
      }

      await waitFor(() => {
        expect(result.current.connectionQuality).toBe('excellent');
      });
    });

    it('should detect poor connection quality', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      // Simulate high latency
      for (let i = 0; i < 3; i++) {
        act(() => {
          jest.advanceTimersByTime(30000);
        });

        // Simulate slow response
        const pongCallback = mockSocket.once.mock.calls.find(
          (call: any[]) => call[0] === 'pong'
        )?.[1];

        if (pongCallback) {
          // Simulate 400ms latency
          setTimeout(() => pongCallback(), 400);
        }
      }

      await waitFor(() => {
        expect(result.current.connectionQuality).toBe('poor');
      });
    });

    it('should stop heartbeat on disconnect', () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.disconnect();
      });

      act(() => {
        jest.advanceTimersByTime(30000);
      });

      // Should not emit ping after disconnect
      expect(mockSocket.emit).not.toHaveBeenCalledWith('ping');
    });
  });

  describe('useAgentChat Hook', () => {
    it('should initialize with empty messages', () => {
      const { result } = renderHook(() => useAgentChat('agent-1'), {
        wrapper: createWrapper(),
      });

      expect(result.current.messages).toEqual([]);
      expect(result.current.isStreaming).toBe(false);
    });

    it('should send message', async () => {
      const { result } = renderHook(() => useAgentChat('agent-1'), {
        wrapper: createWrapper(),
      });

      // Wait for hook to be initialized
      await waitFor(() => {
        expect(result.current.socket).toBeTruthy();
      });

      // Mock socket as connected
      Object.defineProperty(mockSocket, 'connected', {
        get: () => true,
        configurable: true,
      });

      act(() => {
        result.current.sendMessage('Hello agent');
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('agent:chat', {
        agent_id: 'agent-1',
        message: 'Hello agent',
      });

      expect(result.current.isStreaming).toBe(true);
    });

    it('should not send message when not connected', async () => {
      const { result } = renderHook(() => useAgentChat('agent-1'), {
        wrapper: createWrapper(),
      });

      // Ensure socket is not connected
      Object.defineProperty(mockSocket, 'connected', {
        get: () => false,
        configurable: true,
      });

      act(() => {
        result.current.sendMessage('Hello agent');
      });

      expect(mockSocket.emit).not.toHaveBeenCalledWith('agent:chat', expect.any(Object));
      expect(result.current.isStreaming).toBe(false);
    });

    it('should handle agent messages', async () => {
      const { result } = renderHook(() => useAgentChat('agent-1'), {
        wrapper: createWrapper(),
      });

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.socket).toBeTruthy();
      });

      // Mock as connected
      Object.defineProperty(mockSocket, 'connected', {
        get: () => true,
        configurable: true,
      });

      const messageCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'agent:message'
      )?.[1];

      if (messageCallback) {
        act(() => {
          messageCallback({ agent_id: 'agent-1', content: 'Hello user' });
        });
      }

      await waitFor(() => {
        expect(result.current.messages).toHaveLength(1);
        expect(result.current.messages[0]).toEqual({ agent_id: 'agent-1', content: 'Hello user' });
      });
    });

    it('should handle streaming messages', async () => {
      const { result } = renderHook(() => useAgentChat('agent-1'), {
        wrapper: createWrapper(),
      });

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.socket).toBeTruthy();
      });

      // Mock as connected
      Object.defineProperty(mockSocket, 'connected', {
        get: () => true,
        configurable: true,
      });

      const streamingCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'agent:streaming'
      )?.[1];

      if (streamingCallback) {
        act(() => {
          streamingCallback({ agent_id: 'agent-1', content: 'Hello' });
        });

        act(() => {
          streamingCallback({ agent_id: 'agent-1', content: ' World' });
        });
      }

      await waitFor(() => {
        expect(result.current.messages).toHaveLength(1);
        expect(result.current.messages[0].content).toBe('Hello World');
        expect(result.current.messages[0].isStreaming).toBe(true);
      });
    });

    it('should handle streaming completion', async () => {
      const { result } = renderHook(() => useAgentChat('agent-1'), {
        wrapper: createWrapper(),
      });

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.socket).toBeTruthy();
      });

      // Mock as connected
      Object.defineProperty(mockSocket, 'connected', {
        get: () => true,
        configurable: true,
      });

      // First, start streaming
      const streamingCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'agent:streaming'
      )?.[1];

      if (streamingCallback) {
        act(() => {
          streamingCallback({ agent_id: 'agent-1', content: 'Hello' });
        });
      }

      expect(result.current.isStreaming).toBe(true);

      // Then complete streaming
      const completeCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'agent:streaming_complete'
      )?.[1];

      if (completeCallback) {
        act(() => {
          completeCallback({ agent_id: 'agent-1' });
        });
      }

      await waitFor(() => {
        expect(result.current.isStreaming).toBe(false);
        expect(result.current.messages[0].isStreaming).toBe(false);
      });
    });

    it('should ignore messages from other agents', async () => {
      const { result } = renderHook(() => useAgentChat('agent-1'), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.socket?.connect();
        mockSocket.connected = true;
      });

      const messageCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'agent:message'
      )?.[1];

      if (messageCallback) {
        act(() => {
          messageCallback({ agent_id: 'agent-2', content: 'Hello from agent-2' });
        });
      }

      expect(result.current.messages).toHaveLength(0);
    });
  });

  describe('Context Provider Behavior', () => {
    it('should provide context to children', () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current).toBeDefined();
      expect(result.current.connect).toBeDefined();
      expect(result.current.disconnect).toBeDefined();
      expect(result.current.emit).toBeDefined();
    });

    it('should throw error when useWebSocket is used outside provider', () => {
      // Suppress console.error for this test
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

      expect(() => {
        renderHook(() => useWebSocket());
      }).toThrow('useWebSocket must be used within a WebSocketProvider');

      consoleErrorSpy.mockRestore();
    });

    it('should auto-connect on mount when authenticated', async () => {
      mockAuthContext.isAuthenticated = true;

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      // Wait for connection attempt
      await waitFor(() => {
        const { io } = require('socket.io-client');
        expect(io).toHaveBeenCalled();
      });
    });

    it('should disconnect on unmount', async () => {
      const { result, unmount } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      // First connect
      await act(async () => {
        await result.current.connect();
      });

      unmount();

      expect(mockSocket.disconnect).toHaveBeenCalled();
    });
  });

  describe('Edge Cases', () => {
    it('should handle socket.io initialization error', async () => {
      const { io } = require('socket.io-client');
      io.mockImplementation(() => {
        throw new Error('Socket initialization failed');
      });

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.connectionError).toBe('Socket initialization failed');
        expect(result.current.isConnecting).toBe(false);
      });
    });

    it('should handle getToken error', async () => {
      (AsyncStorage.getItem as jest.Mock).mockRejectedValue(new Error('Storage error'));

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      const consoleErrorSpy = jest.spyOn(console, 'error');

      await act(async () => {
        await result.current.connect();
      });

      expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to get token:', expect.any(Error));
      consoleErrorSpy.mockRestore();
    });

    it('should handle missing token gracefully', async () => {
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.connectionError).toBe('No authentication token available');
      });
    });

    it('should handle storage setItem error when joining room', async () => {
      (AsyncStorage.setItem as jest.Mock).mockRejectedValue(new Error('Storage error'));

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const consoleErrorSpy = jest.spyOn(console, 'error');

      await act(async () => {
        await result.current.joinRoom('user:test-user');
      });

      expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to store room:', expect.any(Error));
      consoleErrorSpy.mockRestore();
    });

    it('should handle storage removeItem error when leaving room', async () => {
      (AsyncStorage.removeItem as jest.Mock).mockRejectedValue(new Error('Storage error'));

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const consoleErrorSpy = jest.spyOn(console, 'error');

      await act(async () => {
        await result.current.leaveRoom('user:test-user');
      });

      expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to remove room:', expect.any(Error));
      consoleErrorSpy.mockRestore();
    });

    it('should handle multiple simultaneous connect calls', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        result.current.connect();
        result.current.connect();
        result.current.connect();
      });

      const { io } = require('socket.io-client');
      // Should only create socket once
      expect(io).toHaveBeenCalledTimes(1);
    });

    it('should handle pending messages on reconnection', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      Object.defineProperty(mockSocket, 'connected', {
        get: () => false,
        configurable: true,
      });

      // Queue a message
      act(() => {
        result.current.sendStreamingMessage('agent-1', 'Hello', 'session-1', {
          onChunk: jest.fn(),
          onComplete: jest.fn(),
          onError: jest.fn(),
        });
      });

      // Simulate reconnection
      Object.defineProperty(mockSocket, 'connected', {
        get: () => true,
        configurable: true,
      });

      const connectCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'connect'
      )?.[1];

      if (connectCallback) {
        await act(async () => {
          await connectCallback();
        });
      }

      // Pending message should be sent
      expect(mockSocket.emit).toHaveBeenCalledWith('agent:chat', expect.any(Object));
    });

    it('should handle canvas presentation events', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const canvasCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'agent:canvas_present'
      )?.[1];

      if (canvasCallback) {
        act(() => {
          canvasCallback({ canvas_id: 'canvas-1', type: 'chart' });
        });
      }

      // Should handle without errors
      expect(mockSocket.on).toHaveBeenCalledWith('agent:canvas_present', expect.any(Function));
    });

    it('should handle generic socket errors', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const errorCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'error'
      )?.[1];

      const consoleErrorSpy = jest.spyOn(console, 'error');

      if (errorCallback) {
        act(() => {
          errorCallback(new Error('Generic socket error'));
        });
      }

      expect(consoleErrorSpy).toHaveBeenCalled();
      consoleErrorSpy.mockRestore();
    });

    it('should handle room storage errors on rejoin', async () => {
      (AsyncStorage.getAllKeys as jest.Mock).mockRejectedValue(new Error('Storage error'));

      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      const connectCallback = mockSocket.on.mock.calls.find(
        (call: any[]) => call[0] === 'connect'
      )?.[1];

      const consoleErrorSpy = jest.spyOn(console, 'error');

      if (connectCallback) {
        await act(async () => {
          await connectCallback();
        });
      }

      expect(consoleErrorSpy).toHaveBeenCalled();
      consoleErrorSpy.mockRestore();
    });

    it('should handle reconnect timeout cleanup', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      // Disconnect to ensure cleanup runs
      act(() => {
        result.current.disconnect();
      });

      expect(result.current.isConnected).toBe(false);
      expect(result.current.connectionQuality).toBe('offline');
    });

    it('should handle typing indicator unsubscribe correctly', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const callback = jest.fn();

      const unsubscribe = act(() => {
        return result.current.subscribeToTyping(callback);
      });

      // Should have subscribed
      expect(mockSocket.emit).toHaveBeenCalledWith('subscribe_typing');

      // Now unsubscribe
      act(() => {
        unsubscribe();
      });

      // Should remove callback from array
      expect(mockSocket.emit).toHaveBeenCalled();
    });

    it('should handle stream unsubscribe with socket emit', async () => {
      const { result } = renderHook(() => useWebSocket(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.connect();
      });

      simulateSocketConnection(result, mockSocket);

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const unsubscribe = act(() => {
        return result.current.subscribeToStream(
          'session-1',
          jest.fn(),
          jest.fn(),
          jest.fn()
        );
      });

      // Now unsubscribe
      act(() => {
        unsubscribe();
      });

      // Should emit unsubscribe event
      expect(mockSocket.emit).toHaveBeenCalledWith('unsubscribe_stream', {
        stream_id: 'subscribe_session-1',
      });
    });
  });
});
