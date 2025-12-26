// WhatsApp WebSocket Hook
// React hook for real-time WebSocket connection to WhatsApp Business

import { useState, useEffect, useRef, useCallback } from "react";

interface WebSocketMessage {
  type: string;
  data?: any;
  timestamp?: string;
  error?: string;
}

interface WebSocketState {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  lastMessage: WebSocketMessage | null;
  connectionAttempts: number;
  reconnectCount: number;
}

interface UseWhatsAppWebSocketOptions {
  url?: string;
  autoConnect?: boolean;
  reconnectAttempts?: number;
  reconnectDelay?: number;
  pingInterval?: number;
}

export const useWhatsAppWebSocket = (
  options: UseWhatsAppWebSocketOptions = {},
) => {
  const {
    url = "ws://localhost:5058/ws",
    autoConnect = true,
    reconnectAttempts = 5,
    reconnectDelay = 3000,
    pingInterval = 30000,
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

  // Clear any existing timeouts
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

  // Set WebSocket state - accepts both partial object and function updater
  const setWebSocketState = useCallback(
    (updates: Partial<WebSocketState> | ((prev: WebSocketState) => Partial<WebSocketState>)) => {
      setState((prev) => {
        const newUpdates = typeof updates === 'function' ? updates(prev) : updates;
        return { ...prev, ...newUpdates };
      });
    },
    [],
  );

  // Send ping message to keep connection alive
  const sendPing = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(
          JSON.stringify({
            type: "ping",
            timestamp: new Date().toISOString(),
          }),
        );
      } catch (error) {
        console.error("Error sending ping:", error);
      }
    }
  }, []);

  // Handle WebSocket open
  const handleOpen = useCallback(() => {
    console.log("WhatsApp WebSocket connected");
    clearTimeouts();
    setWebSocketState({
      isConnected: true,
      isConnecting: false,
      error: null,
    });

    // Start ping interval
    pingIntervalRef.current = setInterval(sendPing, pingInterval);
  }, [clearTimeouts, pingInterval, sendPing]);

  // Handle WebSocket message
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data);
      setWebSocketState({
        lastMessage: message,
      });

      // Handle specific message types
      switch (message.type) {
        case "pong":
          // Ping response received
          break;
        case "connection_status":
          console.log("Connection status update:", message.status);
          break;
        case "message_status_update":
          console.log("Message status update:", message);
          break;
        case "new_message":
          console.log("New message received:", message);
          break;
        default:
          console.log("Unknown message type:", message.type);
      }
    } catch (error) {
      console.error("Error parsing WebSocket message:", error);
      setWebSocketState({
        error: "Error parsing WebSocket message",
      });
    }
  }, []);

  // Handle WebSocket error
  const handleError = useCallback(
    (error: Event) => {
      console.error("WhatsApp WebSocket error:", error);
      clearTimeouts();
      setWebSocketState({
        isConnected: false,
        isConnecting: false,
        error: "WebSocket connection error",
      });
    },
    [clearTimeouts],
  );

  // Handle WebSocket close
  const handleClose = useCallback(
    (event: CloseEvent) => {
      console.log("WhatsApp WebSocket closed:", event.code, event.reason);
      clearTimeouts();
      setWebSocketState((prev) => ({
        isConnected: false,
        isConnecting: false,
        error: `WebSocket closed: ${event.code}`,
        connectionAttempts: prev.connectionAttempts + 1,
      }));

      // Auto-reconnect if not manually closed
      if (event.code !== 1000 && state.reconnectCount < reconnectAttempts) {
        console.log(
          `Attempting to reconnect in ${reconnectDelay}ms (attempt ${state.reconnectCount + 1}/${reconnectAttempts})`,
        );
        reconnectTimeoutRef.current = setTimeout(() => {
          setWebSocketState((prev) => ({
            reconnectCount: prev.reconnectCount + 1,
          }));
          connect();
        }, reconnectDelay);
      }
    },
    [clearTimeouts, reconnectAttempts, reconnectDelay, state.reconnectCount],
  );

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log("WebSocket already connected");
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) {
      console.log("WebSocket already connecting");
      return;
    }

    console.log("Connecting to WhatsApp WebSocket:", url);
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
      console.error("Error creating WebSocket:", error);
      setWebSocketState({
        isConnecting: false,
        error: "Failed to create WebSocket connection",
      });
    }
  }, [url, handleOpen, handleMessage, handleError, handleClose]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    console.log("Disconnecting from WebSocket");
    clearTimeouts();

    if (wsRef.current) {
      wsRef.current.close(1000, "Manual disconnect");
      wsRef.current = null;
    }

    setWebSocketState({
      isConnected: false,
      isConnecting: false,
      error: null,
      reconnectCount: 0,
    });
  }, [clearTimeouts]);

  // Send message through WebSocket
  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        const messageString =
          typeof message === "string" ? message : JSON.stringify(message);
        wsRef.current.send(messageString);
        return true;
      } catch (error) {
        console.error("Error sending WebSocket message:", error);
        setWebSocketState({
          error: "Failed to send WebSocket message",
        });
        return false;
      }
    } else {
      console.error("WebSocket not connected");
      setWebSocketState({
        error: "WebSocket not connected",
      });
      return false;
    }
  }, []);

  // Subscribe to specific events
  const subscribeToEvents = useCallback(
    (events: string[]) => {
      const subscribeMessage = {
        type: "subscribe",
        subscriptions: events,
      };
      return sendMessage(subscribeMessage);
    },
    [sendMessage],
  );

  // Unsubscribe from events
  const unsubscribeFromEvents = useCallback(
    (events: string[]) => {
      const unsubscribeMessage = {
        type: "unsubscribe",
        subscriptions: events,
      };
      return sendMessage(unsubscribeMessage);
    },
    [sendMessage],
  );

  // Auto-connect when component mounts
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, [autoConnect]); // Only run once on mount

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearTimeouts();
      if (wsRef.current) {
        wsRef.current.close(1000, "Component unmount");
      }
    };
  }, []);

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
    reconnect: connect, // Alias for connect

    // Message methods
    sendMessage,
    sendPing,

    // Subscription methods
    subscribeToEvents,
    unsubscribeFromEvents,

    // Raw WebSocket reference
    websocket: wsRef.current,
  };
};

export default useWhatsAppWebSocket;
