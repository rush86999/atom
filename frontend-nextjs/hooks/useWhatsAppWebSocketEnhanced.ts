"""
WhatsApp Business - Enhanced React WebSocket Hook
Improved WebSocket client with error handling and reconnection
"""

import { useState, useEffect, useRef, useCallback } from 'react';
import { useToast } from '@chakra-ui/react';

interface WebSocketState {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  lastMessage: any;
  connectionAttempts: number;
  reconnectCount: number;
}

interface UseWhatsAppWebSocketOptions {
  url?: string;
  autoConnect?: boolean;
  reconnectAttempts?: number;
  reconnectDelay?: number;
  pingInterval?: number;
  debugMode?: boolean;
}

export const useWhatsAppWebSocketEnhanced = (options: UseWhatsAppWebSocketOptions = {}) => {
  const {
    url = 'ws://localhost:5058/ws/whatsapp',
    autoConnect = true,
    reconnectAttempts = 5,
    reconnectDelay = 3000,
    pingInterval = 30000,
    debugMode = false,
  } = options;

  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    isConnecting: false,
    error: null,
    lastMessage: null,
    connectionAttempts: 0,
    reconnectCount: 0,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const toast = useToast();

  // Debug logging
  const debugLog = useCallback((message: string, data?: any) => {
    if (debugMode) {
      console.log(`[WhatsAppWebSocket] ${message}`, data || '');
    }
  }, [debugMode]);

  // Clear timeouts
  const clearTimeouts = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  // Set WebSocket state
  const setWebSocketState = useCallback((updates: Partial<WebSocketState>) => {
    setState(prev => ({ ...prev, ...updates }));
  }, []);

  // Send ping message
  const sendPing = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        const pingMessage = {
          type: 'ping',
          timestamp: new Date().toISOString(),
        };
        wsRef.current.send(JSON.stringify(pingMessage));
        debugLog('Ping sent', pingMessage);
      } catch (error) {
        debugLog('Error sending ping', error);
        setWebSocketState({ error: 'Failed to send ping message' });
      }
    }
  }, [debugLog, setWebSocketState]);

  // Handle WebSocket open
  const handleOpen = useCallback(() => {
    debugLog('WebSocket connection opened');
    clearTimeouts();
    setWebSocketState({
      isConnected: true,
      isConnecting: false,
      error: null,
    });

    // Start ping interval
    pingIntervalRef.current = setInterval(sendPing, pingInterval);

    // Show success toast
    toast({
      title: 'Connected to WhatsApp',
      description: 'Real-time updates are now active',
      status: 'success',
      duration: 3000,
      isClosable: true,
    });
  }, [clearTimeouts, debugLog, setWebSocketState, sendPing, pingInterval, toast]);

  // Handle WebSocket message
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data);
      debugLog('Message received', message);
      
      setWebSocketState({ lastMessage: message });

      // Handle specific message types
      switch (message.type) {
        case 'pong':
          debugLog('Pong received');
          break;
        case 'connection_established':
          debugLog('Connection confirmed', message);
          break;
        case 'subscription_confirmed':
          debugLog('Subscription confirmed', message);
          break;
        case 'test_notification_response':
          debugLog('Test notification response', message);
          break;
        case 'error':
          debugLog('WebSocket error message', message);
          setWebSocketState({ error: message.error });
          toast({
            title: 'WebSocket Error',
            description: message.error || 'Unknown error occurred',
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
          break;
        default:
          debugLog('Unknown message type', message.type);
      }
    } catch (error) {
      debugLog('Error parsing message', error);
      setWebSocketState({ error: 'Error parsing WebSocket message' });
    }
  }, [debugLog, setWebSocketState, toast]);

  // Handle WebSocket error
  const handleError = useCallback((error: Event) => {
    debugLog('WebSocket error', error);
    clearTimeouts();
    setWebSocketState({
      isConnected: false,
      isConnecting: false,
      error: 'WebSocket connection error',
    });

    toast({
      title: 'Connection Error',
      description: 'Failed to connect to WhatsApp WebSocket',
      status: 'error',
      duration: 5000,
      isClosable: true,
    });
  }, [clearTimeouts, debugLog, setWebSocketState, toast]);

  // Handle WebSocket close
  const handleClose = useCallback((event: CloseEvent) => {
    debugLog('WebSocket closed', { code: event.code, reason: event.reason });
    clearTimeouts();
    
    setWebSocketState(prev => ({
      isConnected: false,
      isConnecting: false,
      error: `WebSocket closed: ${event.code}`,
      connectionAttempts: prev.connectionAttempts + 1,
    }));

    // Auto-reconnect logic
    if (event.code !== 1000 && state.reconnectCount < reconnectAttempts) {
      debugLog('Attempting to reconnect', { 
        attempt: state.reconnectCount + 1, 
        maxAttempts: reconnectAttempts 
      });
      
      reconnectTimeoutRef.current = setTimeout(() => {
        setWebSocketState(prev => ({
          reconnectCount: prev.reconnectCount + 1,
        }));
        connect();
      }, reconnectDelay);
    } else {
      toast({
        title: 'Connection Lost',
        description: 'WhatsApp WebSocket connection lost',
        status: 'warning',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [clearTimeouts, debugLog, reconnectAttempts, reconnectDelay, state.reconnectCount, setWebSocketState, toast]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      debugLog('WebSocket already connected');
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) {
      debugLog('WebSocket already connecting');
      return;
    }

    debugLog('Connecting to WebSocket', { url });
    setWebSocketState({
      isConnecting: true,
      error: null,
    });

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = handleOpen;
      ws.onmessage = handleMessage;
      ws.onerror = handleError;
      ws.onclose = handleClose;

    } catch (error) {
      debugLog('Error creating WebSocket', error);
      setWebSocketState({
        isConnecting: false,
        error: 'Failed to create WebSocket connection',
      });
    }
  }, [url, handleOpen, handleMessage, handleError, handleClose, debugLog, setWebSocketState]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    debugLog('Manually disconnecting');
    clearTimeouts();
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }
    
    setWebSocketState({
      isConnected: false,
      isConnecting: false,
      error: null,
      reconnectCount: 0,
    });
  }, [clearTimeouts, debugLog, setWebSocketState]);

  // Send message through WebSocket
  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        const messageString = typeof message === 'string' ? message : JSON.stringify(message);
        wsRef.current.send(messageString);
        debugLog('Message sent', message);
        return true;
      } catch (error) {
        debugLog('Error sending message', error);
        setWebSocketState({ error: 'Failed to send WebSocket message' });
        return false;
      }
    } else {
      debugLog('WebSocket not connected, cannot send message');
      setWebSocketState({ error: 'WebSocket not connected' });
      return false;
    }
  }, [debugLog, setWebSocketState]);

  // Subscribe to events
  const subscribeToEvents = useCallback((events: string[]) => {
    const subscribeMessage = {
      type: 'subscribe',
      subscriptions: events,
    };
    return sendMessage(subscribeMessage);
  }, [sendMessage]);

  // Send test notification
  const sendTestNotification = useCallback(() => {
    const testMessage = {
      type: 'test_notification',
      message: 'Test notification from enhanced hook',
      timestamp: new Date().toISOString(),
    };
    return sendMessage(testMessage);
  }, [sendMessage]);

  // Test WebSocket connection
  const testConnection = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      sendTestNotification();
      return true;
    } else {
      connect();
      return false;
    }
  }, [wsRef, connect, sendTestNotification]);

  // Auto-connect when component mounts
  useEffect(() => {
    if (autoConnect) {
      debugLog('Auto-connecting on mount');
      connect();
    }

    // Cleanup on unmount
    return () => {
      debugLog('Cleaning up on unmount');
      clearTimeouts();
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmount');
      }
    };
  }, [autoConnect]); // Only run once on mount

  return {
    // Connection state
    isConnected: state.isConnected,
    isConnecting: state.isConnecting,
    error: state.error,
    lastMessage: state.lastMessage,
    connectionAttempts: state.connectionAttempts,
    reconnectCount: state.reconnectCount,

    // Connection methods
    connect,
    disconnect,
    reconnect: connect,
    testConnection,

    // Message methods
    sendMessage,
    sendPing,
    sendTestNotification,

    // Subscription methods
    subscribeToEvents,

    // Raw WebSocket reference
    websocket: wsRef.current,

    // Debug info
    debugMode,
  };
};

export default useWhatsAppWebSocketEnhanced;