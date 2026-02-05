/**
 * WebSocketContext - Real-time WebSocket Communication
 *
 * Provides Socket.IO-based WebSocket functionality for the mobile app:
 * - Automatic connection/reconnection
 * - Event-based messaging
 * - Agent chat streaming
 * - Canvas updates
 * - Real-time notifications
 */

import React, { createContext, useContext, useState, useEffect, ReactNode, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuth } from './AuthContext';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Types
interface WebSocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  isConnecting: boolean;
  connectionError: string | null;

  // Methods
  connect: () => void;
  disconnect: () => void;
  emit: (event: string, data: any) => void;
  on: (event: string, callback: (...args: any[]) => void) => void;
  off: (event: string, callback?: (...args: any[]) => void) => void;
  joinRoom: (room: string) => void;
  leaveRoom: (room: string) => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

// Constants
const SOCKET_URL = process.env.EXPO_PUBLIC_SOCKET_URL || 'http://localhost:8000';
const RECONNECT_INTERVAL = 5000; // 5 seconds
const MAX_RECONNECT_ATTEMPTS = 10;
const ROOM_KEY_PREFIX = 'socket_room_';

/**
 * WebSocketProvider Component
 */
export const WebSocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { isAuthenticated, getAccessToken } = useAuth();
  const socketRef = useRef<Socket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  /**
   * Get current access token
   */
  const getToken = async (): Promise<string | null> => {
    // This would come from AuthContext, but for now we'll use a placeholder
    try {
      return await AsyncStorage.getItem('atom_access_token');
    } catch (error) {
      console.error('Failed to get token:', error);
      return null;
    }
  };

  /**
   * Connect to WebSocket server
   */
  const connect = () => {
    if (socketRef.current?.connected) {
      console.log('Socket already connected');
      return;
    }

    if (isConnecting) {
      console.log('Socket connection already in progress');
      return;
    }

    setIsConnecting(true);
    setConnectionError(null);

    getToken().then((token) => {
      if (!token) {
        setConnectionError('No authentication token available');
        setIsConnecting(false);
        return;
      }

      try {
        const socket = io(SOCKET_URL, {
          auth: { token },
          transports: ['websocket'],
          reconnection: true,
          reconnectionDelay: RECONNECT_INTERVAL,
          reconnectionAttempts: MAX_RECONNECT_ATTEMPTS,
          timeout: 10000,
        });

        socketRef.current = socket;

        // Connection event handlers
        socket.on('connect', async () => {
          console.log('Socket connected:', socket.id);
          setIsConnected(true);
          setIsConnecting(false);
          setConnectionError(null);
          reconnectAttemptsRef.current = 0;

          // Re-join previously joined rooms
          await rejoinRooms();
        });

        socket.on('disconnect', (reason) => {
          console.log('Socket disconnected:', reason);
          setIsConnected(false);
          setIsConnecting(false);

          if (reason === 'io server disconnect') {
            // Server initiated disconnect, need to reconnect manually
            socket.connect();
          }
        });

        socket.on('connect_error', (error) => {
          console.error('Socket connection error:', error);
          setIsConnecting(false);
          setConnectionError(error.message);

          reconnectAttemptsRef.current += 1;
          if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
            console.error('Max reconnection attempts reached');
            setConnectionError('Unable to connect. Please check your internet connection.');
          }
        });

        socket.on('reconnect', (attemptNumber) => {
          console.log('Socket reconnected after', attemptNumber, 'attempts');
          setIsConnected(true);
          setConnectionError(null);
        });

        socket.on('reconnect_attempt', (attemptNumber) => {
          console.log('Socket reconnection attempt:', attemptNumber);
          setIsConnecting(true);
        });

        socket.on('reconnect_failed', () => {
          console.error('Socket reconnection failed');
          setIsConnecting(false);
          setConnectionError('Reconnection failed. Please refresh the app.');
        });

        // Agent event handlers
        socket.on('agent:message', (data) => {
          console.log('Agent message received:', data);
          // This will be handled by components that subscribe
        });

        socket.on('agent:streaming', (data) => {
          console.log('Agent streaming update:', data);
          // Handle streaming updates
        });

        socket.on('agent:canvas_present', (data) => {
          console.log('Canvas presented:', data);
          // Handle canvas presentation
        });

        // Error handler
        socket.on('error', (error) => {
          console.error('Socket error:', error);
        });
      } catch (error: any) {
        console.error('Failed to create socket:', error);
        setIsConnecting(false);
        setConnectionError(error.message || 'Failed to connect');
      }
    });
  };

  /**
   * Disconnect from WebSocket server
   */
  const disconnect = () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }

    setIsConnected(false);
    setIsConnecting(false);
  };

  /**
   * Emit event to server
   */
  const emit = (event: string, data: any) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit(event, data);
    } else {
      console.warn('Cannot emit event: socket not connected');
    }
  };

  /**
   * Register event listener
   */
  const on = (event: string, callback: (...args: any[]) => void) => {
    if (socketRef.current) {
      socketRef.current.on(event, callback);
    }
  };

  /**
   * Unregister event listener
   */
  const off = (event: string, callback?: (...args: any[]) => void) => {
    if (socketRef.current) {
      if (callback) {
        socketRef.current.off(event, callback);
      } else {
        socketRef.current.off(event);
      }
    }
  };

  /**
   * Join a room (e.g., user:{user_id})
   */
  const joinRoom = async (room: string) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('join', { room });

      // Store room for reconnection
      try {
        await AsyncStorage.setItem(ROOM_KEY_PREFIX + room, 'true');
      } catch (error) {
        console.error('Failed to store room:', error);
      }
    }
  };

  /**
   * Leave a room
   */
  const leaveRoom = async (room: string) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('leave', { room });

      // Remove from storage
      try {
        await AsyncStorage.removeItem(ROOM_KEY_PREFIX + room);
      } catch (error) {
        console.error('Failed to remove room:', error);
      }
    }
  };

  /**
   * Re-join all previously joined rooms after reconnection
   */
  const rejoinRooms = async () => {
    try {
      const allKeys = await AsyncStorage.getAllKeys();
      const roomKeys = allKeys.filter(key => key.startsWith(ROOM_KEY_PREFIX));

      for (const key of roomKeys) {
        const room = key.replace(ROOM_KEY_PREFIX, '');
        if (socketRef.current?.connected) {
          socketRef.current.emit('join', { room });
        }
      }
    } catch (error) {
      console.error('Failed to rejoin rooms:', error);
    }
  };

  /**
   * Auto-connect when authenticated
   */
  useEffect(() => {
    if (isAuthenticated && !socketRef.current) {
      connect();
    } else if (!isAuthenticated && socketRef.current) {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [isAuthenticated]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  const value: WebSocketContextType = {
    socket: socketRef.current,
    isConnected,
    isConnecting,
    connectionError,
    connect,
    disconnect,
    emit,
    on,
    off,
    joinRoom,
    leaveRoom,
  };

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
};

/**
 * useWebSocket Hook
 */
export const useWebSocket = (): WebSocketContextType => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

/**
 * Helper hook for agent chat streaming
 */
export const useAgentChat = (agentId: string) => {
  const { socket, isConnected } = useWebSocket();
  const [messages, setMessages] = useState<any[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    if (!socket || !isConnected) return;

    const handleMessage = (data: any) => {
      setMessages((prev) => [...prev, data]);
    };

    const handleStreaming = (data: any) => {
      if (data.agent_id === agentId) {
        setMessages((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.isStreaming) {
            // Append to last message
            const updated = [...prev];
            updated[prev.length - 1] = {
              ...lastMessage,
              content: lastMessage.content + data.content,
            };
            return updated;
          } else {
            // New streaming message
            return [...prev, { ...data, isStreaming: true }];
          }
        });
      }
    });

    const handleStreamingComplete = (data: any) => {
      if (data.agent_id === agentId) {
        setIsStreaming(false);
        setMessages((prev) => {
          const updated = [...prev];
          const lastMessage = updated[updated.length - 1];
          if (lastMessage && lastMessage.isStreaming) {
            updated[updated.length - 1] = {
              ...lastMessage,
              isStreaming: false,
            };
          }
          return updated;
        });
      }
    };

    socket.on('agent:message', handleMessage);
    socket.on('agent:streaming', handleStreaming);
    socket.on('agent:streaming_complete', handleStreamingComplete);

    return () => {
      socket.off('agent:message', handleMessage);
      socket.off('agent:streaming', handleStreaming);
      socket.off('agent:streaming_complete', handleStreamingComplete);
    };
  }, [socket, isConnected, agentId]);

  const sendMessage = (content: string) => {
    if (socket && isConnected) {
      setIsStreaming(true);
      socket.emit('agent:chat', {
        agent_id: agentId,
        message: content,
      });
    }
  };

  return {
    messages,
    isStreaming,
    sendMessage,
  };
};
