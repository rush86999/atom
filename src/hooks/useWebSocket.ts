import { useEffect, useRef, useCallback, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAppStore } from '../store';
import { CommunicationsMessage } from '../types';

interface UseWebSocketOptions {
  url?: string;
  enabled?: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: any) => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
  messageQueueSize?: number;
  enableHeartbeat?: boolean;
  enableHealthMonitoring?: boolean;
  healthCheckInterval?: number;
  exponentialBackoff?: boolean;
  maxReconnectDelay?: number;
}

export const useWebSocket = (options: UseWebSocketOptions = {}) => {
  const {
    url = process.env.REACT_APP_WS_URL || 'ws://localhost:3001',
    enabled = false,
    onConnect,
    onDisconnect,
    onError,
    reconnectAttempts = 5,
    reconnectInterval = 1000,
    messageQueueSize = 100,
    enableHeartbeat = true,
    enableHealthMonitoring = true,
    healthCheckInterval = 30000,
    exponentialBackoff = true,
    maxReconnectDelay = 30000,
  } = options;

  const socketRef = useRef<Socket | null>(null);
  const messageQueueRef = useRef<any[]>([]);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const healthCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectCountRef = useRef(0);
  const lastPongRef = useRef<number>(Date.now());
  const [connectionState, setConnectionState] = useState<'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'failed'>('disconnected');
  const { setConnected, addNotification } = useAppStore();

  // Calculate exponential backoff delay
  const getReconnectDelay = useCallback((attempt: number): number => {
    if (!exponentialBackoff) return reconnectInterval;
    const delay = Math.min(reconnectInterval * Math.pow(2, attempt), maxReconnectDelay);
    return delay + Math.random() * 1000; // Add jitter
  }, [exponentialBackoff, reconnectInterval, maxReconnectDelay]);

  // Health monitoring function
  const startHealthMonitoring = useCallback(() => {
    if (!enableHealthMonitoring) return;

    healthCheckIntervalRef.current = setInterval(() => {
      const now = Date.now();
      const timeSinceLastPong = now - lastPongRef.current;

      if (timeSinceLastPong > healthCheckInterval * 2) {
        console.warn('Connection health check failed - no pong received');
        // Force reconnection if health check fails
        if (socketRef.current) {
          socketRef.current.disconnect();
        }
      }
    }, healthCheckInterval);
  }, [enableHealthMonitoring, healthCheckInterval]);

  // Advanced reconnection logic
  const attemptReconnect = useCallback(() => {
    if (reconnectCountRef.current >= reconnectAttempts) {
      setConnectionState('failed');
      addNotification({
        type: 'error',
        title: 'Connection Failed',
        message: 'Unable to establish connection after multiple attempts',
      });
      return;
    }

    const delay = getReconnectDelay(reconnectCountRef.current);
    console.log(`Attempting reconnection in ${delay}ms (attempt ${reconnectCountRef.current + 1}/${reconnectAttempts})`);

    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectCountRef.current += 1;
      setConnectionState('reconnecting');
      connect();
    }, delay);
  }, [reconnectAttempts, getReconnectDelay, addNotification]);

  const connect = useCallback(() => {
    if (!enabled || socketRef.current?.connected) return;

    setConnectionState('connecting');
    socketRef.current?.connect();
  }, [enabled]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      setConnected(false);
    }
  }, [setConnected]);

  const emit = useCallback((event: string, data?: any) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit(event, data);
    } else {
      // Queue message for later sending
      if (messageQueueRef.current.length < messageQueueSize) {
        messageQueueRef.current.push({ event, data });
        console.log('Message queued:', event);
      } else {
        console.warn('Message queue full, dropping message:', event);
      }
    }
  }, [messageQueueSize]);

  const on = useCallback((event: string, callback: (...args: any[]) => void) => {
    if (socketRef.current) {
      socketRef.current.on(event, callback);
    }
  }, []);

  const off = useCallback((event: string, callback?: (...args: any[]) => void) => {
    if (socketRef.current) {
      if (callback) {
        socketRef.current.off(event, callback);
      } else {
        socketRef.current.off(event);
      }
    }
  }, []);

  // Create socket on mount with autoConnect: false
  useEffect(() => {
    socketRef.current = io(url, {
      transports: ['websocket', 'polling'],
      timeout: 20000,
      forceNew: true,
      autoConnect: false,
    });

    const socket = socketRef.current;

    socket.on('connect', () => {
      console.log('WebSocket connected');
      setConnected(true);
      setConnectionState('connected');
      reconnectCountRef.current = 0; // Reset reconnection count on successful connection
      onConnect?.();

      // Send queued messages
      while (messageQueueRef.current.length > 0) {
        const queuedMessage = messageQueueRef.current.shift();
        if (queuedMessage) {
          socket.emit(queuedMessage.event, queuedMessage.data);
          console.log('Sent queued message:', queuedMessage.event);
        }
      }

      // Start heartbeat and health monitoring
      if (enableHeartbeat) {
        heartbeatIntervalRef.current = setInterval(() => {
          socket.emit('ping');
        }, 30000); // Send ping every 30 seconds
      }

      startHealthMonitoring();

      addNotification({
        type: 'success',
        title: 'Connected',
        message: 'Real-time updates enabled',
      });
    });

    socket.on('pong', () => {
      lastPongRef.current = Date.now();
    });

    socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      setConnected(false);
      setConnectionState('disconnected');
      onDisconnect?.();

      // Clear intervals
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = null;
      }
      if (healthCheckIntervalRef.current) {
        clearInterval(healthCheckIntervalRef.current);
        healthCheckIntervalRef.current = null;
      }

      // Always show notification on disconnect
      addNotification({
        type: 'warning',
        title: 'Disconnected',
        message: 'Real-time updates disabled',
      });

      if (reason === 'io server disconnect' || reason === 'io client disconnect') {
        // Attempt reconnection for server disconnects or client-initiated disconnects that should reconnect
        attemptReconnect();
      }
    });

    socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      setConnected(false);
      setConnectionState('disconnected');
      onError?.(error);

      // Attempt reconnection on connection errors
      attemptReconnect();

      addNotification({
        type: 'error',
        title: 'Connection Error',
        message: 'Failed to connect to real-time updates',
      });
    });

    socket.on('reconnect', (attemptNumber) => {
      console.log('WebSocket reconnected after', attemptNumber, 'attempts');
      setConnected(true);
      setConnectionState('connected');
      addNotification({
        type: 'success',
        title: 'Reconnected',
        message: 'Real-time updates restored',
      });
    });

    socket.on('reconnect_error', (error) => {
      console.error('WebSocket reconnection error:', error);
      setConnectionState('disconnected');
      attemptReconnect();
    });

    socket.on('reconnect_failed', () => {
      console.error('WebSocket reconnection failed');
      setConnectionState('failed');
      addNotification({
        type: 'error',
        title: 'Reconnection Failed',
        message: 'Unable to restore real-time updates',
      });
    });

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [url, setConnected, onConnect, onDisconnect, onError, addNotification, enableHeartbeat, startHealthMonitoring, attemptReconnect]);

  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  return {
    socket: socketRef.current,
    isConnected: socketRef.current?.connected || false,
    connectionState,
    connect,
    disconnect,
    emit,
    on,
    off,
  };
};

// Specialized hook for real-time data synchronization
export const useRealtimeSync = () => {
  const {
    setTasks,
    addTask,
    updateTask,
    deleteTask,
    setMessages,
    markMessageAsRead,
    setCalendarEvents,
    addCalendarEvent,
    updateCalendarEvent,
    deleteCalendarEvent,
    setIntegrations,
    updateIntegration,
    setWorkflows,
    addWorkflow,
    updateWorkflow,
    deleteWorkflow,
    addAgentLog,
    addNotification,
  } = useAppStore();

  const messages = useAppStore((state) => state.messages);

  const { on, off, isConnected } = useWebSocket({
    enabled: true,
    onConnect: () => {
      console.log('Real-time sync enabled');
    },
    onDisconnect: () => {
      console.log('Real-time sync disabled');
    },
  });

  useEffect(() => {
    // Task events
    on('task:created', (task) => {
      addTask(task);
      addNotification({
        type: 'info',
        title: 'New Task',
        message: `Task "${task.title}" has been created`,
      });
    });

    on('task:updated', (task) => {
      updateTask(task.id, task);
    });

    on('task:deleted', (taskId) => {
      deleteTask(taskId);
      addNotification({
        type: 'info',
        title: 'Task Deleted',
        message: 'A task has been deleted',
      });
    });

    // Message events
    on('message:new', (message: CommunicationsMessage) => {
      setMessages([message, ...messages]);
      addNotification({
        type: 'info',
        title: 'New Message',
        message: `New message from ${message.from.name}`,
      });
    });

    on('message:read', (messageId) => {
      markMessageAsRead(messageId);
    });

    // Calendar events
    on('calendar:event:created', (event) => {
      addCalendarEvent(event);
      addNotification({
        type: 'info',
        title: 'New Event',
        message: `Event "${event.title}" has been added to your calendar`,
      });
    });

    on('calendar:event:updated', (event) => {
      updateCalendarEvent(event.id, event);
    });

    on('calendar:event:deleted', (eventId) => {
      deleteCalendarEvent(eventId);
      addNotification({
        type: 'info',
        title: 'Event Deleted',
        message: 'A calendar event has been deleted',
      });
    });

    // Integration events
    on('integration:connected', (integration) => {
      updateIntegration(integration.id, integration);
      addNotification({
        type: 'success',
        title: 'Integration Connected',
        message: `${integration.displayName} has been connected`,
      });
    });

    on('integration:disconnected', (integration) => {
      updateIntegration(integration.id, { ...integration, connected: false });
      addNotification({
        type: 'warning',
        title: 'Integration Disconnected',
        message: `${integration.displayName} has been disconnected`,
      });
    });

    on('integration:sync:completed', (integration) => {
      updateIntegration(integration.id, {
        ...integration,
        lastSync: new Date().toISOString(),
        syncStatus: 'success'
      });
    });

    on('integration:sync:failed', (integration) => {
      updateIntegration(integration.id, {
        ...integration,
        syncStatus: 'failed'
      });
      addNotification({
        type: 'error',
        title: 'Sync Failed',
        message: `Failed to sync ${integration.displayName}`,
      });
    });

    // Workflow events
    on('workflow:executed', (workflow) => {
      updateWorkflow(workflow.id, {
        ...workflow,
        lastExecuted: new Date().toISOString(),
        executionCount: workflow.executionCount + 1
      });
      addNotification({
        type: 'success',
        title: 'Workflow Executed',
        message: `Workflow "${workflow.name}" has been executed`,
      });
    });

    // Agent events
    on('agent:log', (log) => {
      addAgentLog(log);
    });

    on('agent:status:changed', (agent) => {
      // Update agent status in the store
      // This would require an updateAgent method that can handle status updates
    });

    return () => {
      // Clean up all event listeners
      off('task:created');
      off('task:updated');
      off('task:deleted');
      off('message:new');
      off('message:read');
      off('calendar:event:created');
      off('calendar:event:updated');
      off('calendar:event:deleted');
      off('integration:connected');
      off('integration:disconnected');
      off('integration:sync:completed');
      off('integration:sync:failed');
      off('workflow:executed');
      off('agent:log');
      off('agent:status:changed');
    };
  }, [
    on,
    off,
    addTask,
    updateTask,
    deleteTask,
    setMessages,
    markMessageAsRead,
    addCalendarEvent,
    updateCalendarEvent,
    deleteCalendarEvent,
    updateIntegration,
    updateWorkflow,
    addAgentLog,
    addNotification,
    messages,
  ]);

  return { isConnected };
};

// Hook for optimistic updates
export const useOptimisticUpdate = () => {
  const { addNotification } = useAppStore();

  const optimisticUpdate = useCallback(
    async <T>(
      updateFn: () => Promise<T>,
      rollbackFn: () => void,
      options: {
        successMessage?: string;
        errorMessage?: string;
        onSuccess?: (result: T) => void;
        onError?: (error: any) => void;
      } = {}
    ): Promise<T | null> => {
      try {
        const result = await updateFn();
        if (options.successMessage) {
          addNotification({
            type: 'success',
            title: 'Success',
            message: options.successMessage,
          });
        }
        options.onSuccess?.(result);
        return result;
      } catch (error) {
        rollbackFn();
        if (options.errorMessage) {
          addNotification({
            type: 'error',
            title: 'Error',
            message: options.errorMessage,
          });
        }
        options.onError?.(error);
        return null;
      }
    },
    [addNotification]
  );

  return { optimisticUpdate };
};
