import React, { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import { io, Socket } from 'socket.io-client';
import { useWebSocketContext } from '../contexts/WebSocketProvider';
import { useAppStore } from '../store';
import { CommunicationsMessage } from '../types';
import { AutonomousCommunicationOrchestrator } from '../autonomous-communication/autonomousCommunicationOrchestrator';
import { AutonomousCommunications } from '../autonomous-communication/types';

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
  userId?: string;
  username?: string;
  enablePresence?: boolean;
  enableCollaborativeEditing?: boolean;
  enableTypingIndicators?: boolean;
  enableReadReceipts?: boolean;
  enableMessageReactions?: boolean;
  enableLiveCursors?: boolean;
  enableOfflineQueue?: boolean;
  enableAnalytics?: boolean;
  enableEncryption?: boolean;
  compressionThreshold?: number;
  batchUpdateInterval?: number;
  maxConcurrentConnections?: number;
  enableAutonomousCommunication?: boolean;
  recentRooms?: string[];
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
    userId,
    username,
    enablePresence = false,
    enableCollaborativeEditing = false,
    enableTypingIndicators = false,
    enableReadReceipts = false,
    enableMessageReactions = false,
    enableLiveCursors = false,
    enableOfflineQueue = true,
    enableAnalytics = false,
    enableEncryption = false,
    compressionThreshold = 1024,
    batchUpdateInterval = 100,
    maxConcurrentConnections = 5,
    enableAutonomousCommunication = false,
    recentRooms = [],
  } = options;

  const socketRef = useRef<Socket | null>(null);
  const messageQueueRef = useRef<any[]>([]);
  const handlersRef = useRef<Map<string, Set<(...args: any[]) => void>>>(new Map());
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const healthCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectCountRef = useRef(0);
  const lastPongRef = useRef<number>(Date.now());
  const [connectionState, setConnectionState] = useState<'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'failed'>('disconnected');
  const { setConnected, addNotification } = useAppStore();

  // Check for a global provider but do not early-return (keep hook call order stable)
  const wsContext = useWebSocketContext();

  // New refs for advanced features
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const batchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const batchBufferRef = useRef<any[]>([]);
  const analyticsRef = useRef<{ [key: string]: number }>({});
  const concurrentConnectionsRef = useRef(0);
  const encryptionKeyRef = useRef<string | null>(null);

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

  // Enhanced reconnection logic with circuit breaker pattern
  const attemptReconnect = useCallback(() => {
    if (reconnectCountRef.current >= reconnectAttempts) {
      setConnectionState('failed');
      addNotification({
        type: 'error',
        title: 'Connection Failed',
        message: 'Unable to establish connection after multiple attempts. Please check your network connection.',
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
      // Compress payload for large data to reduce bandwidth
      const payload = data && typeof data === 'object' && Object.keys(data).length > 10
        ? JSON.stringify(data) // Let the server handle compression
        : data;
      socketRef.current.emit(event, payload);
    } else {
      // Queue message for later sending with priority
      if (messageQueueRef.current.length < messageQueueSize) {
        messageQueueRef.current.push({ event, data, timestamp: Date.now() });
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

  const subscribe = useCallback((event: string, callback: (...args: any[]) => void) => {
    if (!handlersRef.current.has(event)) handlersRef.current.set(event, new Set());
    handlersRef.current.get(event)!.add(callback);
    if (socketRef.current) socketRef.current.on(event, callback);
  }, []);

  const unsubscribe = useCallback((event: string, callback?: (...args: any[]) => void) => {
    const set = handlersRef.current.get(event);
    if (callback) {
      set?.delete(callback);
      if (socketRef.current) socketRef.current.off(event, callback);
    } else {
      set?.forEach((cb) => {
        if (socketRef.current) socketRef.current.off(event, cb as any);
      });
      handlersRef.current.delete(event);
    }
  }, []);

  // Advanced feature utilities
  const encryptData = useCallback((data: any): any => {
    if (!enableEncryption || !encryptionKeyRef.current) return data;
    // Simple XOR encryption for demo - replace with proper encryption in production
    const key = encryptionKeyRef.current;
    const str = JSON.stringify(data);
    let encrypted = '';
    for (let i = 0; i < str.length; i++) {
      encrypted += String.fromCharCode(str.charCodeAt(i) ^ key.charCodeAt(i % key.length));
    }
    return { encrypted: btoa(encrypted), _encrypted: true };
  }, [enableEncryption]);

  const decryptData = useCallback((data: any): any => {
    if (!data._encrypted || !encryptionKeyRef.current) return data;
    try {
      const key = encryptionKeyRef.current;
      const decrypted = atob(data.encrypted);
      let original = '';
      for (let i = 0; i < decrypted.length; i++) {
        original += String.fromCharCode(decrypted.charCodeAt(i) ^ key.charCodeAt(i % key.length));
      }
      return JSON.parse(original);
    } catch (error) {
      console.error('Decryption failed:', error);
      return data;
    }
  }, [enableEncryption]);

  const compressData = useCallback((data: any): any => {
    if (!data || typeof data !== 'object') return data;
    const str = JSON.stringify(data);
    if (str.length < compressionThreshold) return data;
    // Simple compression - in production use proper compression library
    return { compressed: btoa(str), _compressed: true };
  }, [compressionThreshold]);

  const decompressData = useCallback((data: any): any => {
    if (!data._compressed) return data;
    try {
      const decompressed = atob(data.compressed);
      return JSON.parse(decompressed);
    } catch (error) {
      console.error('Decompression failed:', error);
      return data;
    }
  }, []);

  const batchEmit = useCallback((event: string, data: any) => {
    batchBufferRef.current.push({ event, data, timestamp: Date.now() });

    if (batchTimeoutRef.current) {
      clearTimeout(batchTimeoutRef.current);
    }

    batchTimeoutRef.current = setTimeout(() => {
      if (batchBufferRef.current.length > 0) {
        const batchedData = batchBufferRef.current.splice(0);
        emit('batch', { events: batchedData });
      }
    }, batchUpdateInterval);
  }, [emit, batchUpdateInterval]);

  const sendTypingIndicator = useCallback((channelId: string, isTyping: boolean) => {
    if (!enableTypingIndicators) return;

    if (isTyping) {
      emit('typing:start', { channelId, userId, username });
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      typingTimeoutRef.current = setTimeout(() => {
        emit('typing:stop', { channelId, userId, username });
      }, 3000);
    } else {
      emit('typing:stop', { channelId, userId, username });
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
    }
  }, [emit, enableTypingIndicators, userId, username]);

  const sendReadReceipt = useCallback((messageId: string, channelId: string) => {
    if (!enableReadReceipts) return;
    emit('message:read', { messageId, channelId, userId, timestamp: Date.now() });
  }, [emit, enableReadReceipts, userId]);

  const sendMessageReaction = useCallback((messageId: string, reaction: string, action: 'add' | 'remove') => {
    if (!enableMessageReactions) return;
    emit('message:reaction', { messageId, reaction, action, userId });
  }, [emit, enableMessageReactions, userId]);

  const sendCursorPosition = useCallback((documentId: string, position: { x: number; y: number }) => {
    if (!enableLiveCursors) return;
    emit('cursor:move', { documentId, position, userId, username });
  }, [emit, enableLiveCursors, userId, username]);

  const trackAnalytics = useCallback((event: string, data?: any) => {
    if (!enableAnalytics) return;
    analyticsRef.current[event] = (analyticsRef.current[event] || 0) + 1;
    emit('analytics:event', { event, data, timestamp: Date.now() });
  }, [emit, enableAnalytics]);

  const checkConcurrentConnections = useCallback(() => {
    if (concurrentConnectionsRef.current >= maxConcurrentConnections) {
      console.warn('Max concurrent connections reached');
      return false;
    }
    concurrentConnectionsRef.current += 1;
    return true;
  }, [maxConcurrentConnections]);

  const releaseConcurrentConnection = useCallback(() => {
    concurrentConnectionsRef.current = Math.max(0, concurrentConnectionsRef.current - 1);
  }, []);

  // Load persisted queued messages (if any)
  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        const persisted = localStorage.getItem('ws_message_queue');
        if (persisted) {
          messageQueueRef.current = JSON.parse(persisted);
        }
      }
    } catch (e) {
      console.warn('Failed to load persisted WS queue', e);
    }
  }, []);

  // Create socket on mount with autoConnect: false
  useEffect(() => {
    socketRef.current = io(url, {
      transports: ['websocket', 'polling'],
      timeout: 20000,
      forceNew: true,
      autoConnect: false,
      auth: userId ? { userId, username } : undefined,
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

      // Emit presence if enabled
      if (enablePresence && userId) {
        socket.emit('presence:join', { userId, username });
      }

      // Auto-join recent rooms/projects if provided
      if (Array.isArray(recentRooms) && recentRooms.length > 0) {
        recentRooms.forEach((r) => {
          try {
            socket.emit('join_project', r);
          } catch (e) {
            console.warn('Auto-join room failed', r, e);
          }
        });
      }

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

  // Persist queued messages periodically so they survive refreshes
  useEffect(() => {
    const id = setInterval(() => {
      try {
        if (typeof window !== 'undefined') {
          localStorage.setItem('ws_message_queue', JSON.stringify(messageQueueRef.current || []));
        }
      } catch (e) {
        // ignore
      }
    }, 2000);

    return () => clearInterval(id);
  }, []);

  // If a global provider exists, delegate to it (after all hooks called)
  if (wsContext && wsContext.socket) {
    return {
      socket: wsContext.socket,
      isConnected: !!wsContext.socket.connected,
      connectionState: wsContext.socket.connected ? 'connected' : 'disconnected',
      connect: () => wsContext.socket?.connect(),
      disconnect: () => wsContext.socket?.disconnect(),
      emit: wsContext.emit,
      on: wsContext.on,
      off: wsContext.off,
      subscribe: wsContext.subscribe,
      unsubscribe: wsContext.unsubscribe,
      // noop placeholders for advanced features when provider is used
      encryptData: (d: any) => d,
      decryptData: (d: any) => d,
      compressData: (d: any) => d,
      decompressData: (d: any) => d,
      batchEmit: () => {},
      sendTypingIndicator: () => {},
      sendReadReceipt: () => {},
      sendMessageReaction: () => {},
      sendCursorPosition: () => {},
      trackAnalytics: () => {},
      checkConcurrentConnections: () => true,
      releaseConcurrentConnection: () => {},
    } as any;
  }

  return {
    socket: socketRef.current,
    isConnected: socketRef.current?.connected || false,
    connectionState,
    connect,
    disconnect,
    emit,
    on,
    subscribe,
    unsubscribe,
    off,
    // Advanced features
    encryptData,
    decryptData,
    compressData,
    decompressData,
    batchEmit,
    sendTypingIndicator,
    sendReadReceipt,
    sendMessageReaction,
    sendCursorPosition,
    trackAnalytics,
    checkConcurrentConnections,
    releaseConcurrentConnection,
  };
};

// Debounce utility for frequent updates
const useDebounce = (callback: Function, delay: number) => {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  return useCallback((...args: any[]) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => callback(...args), delay);
  }, [callback, delay]);
};

// Batch state updates to reduce re-renders
const useBatchUpdate = () => {
  const batchRef = useRef<Map<string, any>>(new Map());
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const batchUpdate = useCallback((key: string, updateFn: () => void) => {
    batchRef.current.set(key, updateFn);

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      batchRef.current.forEach((fn) => fn());
      batchRef.current.clear();
    }, 16); // Next frame
  }, []);

  return { batchUpdate };
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
  const workflows = useAppStore((state) => state.workflows);

  // Autonomous communication integration
  const autonomousOrchestrator = React.useRef<any>(null);

  // Memoized event handlers to prevent unnecessary re-renders
  // Real-time sync events should be immediate
  const eventHandlers = useMemo(() => ({
    // Task events
    taskCreated: (task: any) => {
      addTask(task);
      addNotification({
        type: 'info',
        title: 'New Task',
        message: `Task "${task.title}" has been created`,
      });
    },

    taskUpdated: (task: any) => {
      updateTask(task.id, task);
    },

    taskDeleted: (taskId: string) => {
      deleteTask(taskId);
      addNotification({
        type: 'info',
        title: 'Task Deleted',
        message: 'A task has been deleted',
      });
    },

    // Message events with optimized payload handling
    messageNew: (message: CommunicationsMessage) => {
      // Limit message history to prevent memory issues
      const maxMessages = 100;
      const currentMessages = messages.slice(0, maxMessages - 1);
      setMessages([message, ...currentMessages]);

      addNotification({
        type: 'info',
        title: 'New Message',
        message: `New message from ${message.from.name}`,
      });
    },

    messageRead: (messageId: string) => {
      markMessageAsRead(messageId);
    },

    // Calendar events
    calendarEventCreated: (event: any) => {
      addCalendarEvent(event);
      addNotification({
        type: 'info',
        title: 'New Event',
        message: `Event "${event.title}" has been added to your calendar`,
      });
    },

    calendarEventUpdated: (event: any) => {
      updateCalendarEvent(event.id, event);
    },

    calendarEventDeleted: (eventId: string) => {
      deleteCalendarEvent(eventId);
      addNotification({
        type: 'info',
        title: 'Event Deleted',
        message: 'A calendar event has been deleted',
      });
    },

    // Integration events with error handling
    integrationConnected: (integration: any) => {
      try {
        updateIntegration(integration.id, integration);
        addNotification({
          type: 'success',
          title: 'Integration Connected',
          message: `${integration.displayName} has been connected`,
        });
      } catch (error) {
        console.error('Error updating integration:', error);
      }
    },

    integrationDisconnected: (integration: any) => {
      try {
        updateIntegration(integration.id, { ...integration, connected: false });
        addNotification({
          type: 'warning',
          title: 'Integration Disconnected',
          message: `${integration.displayName} has been disconnected`,
        });
      } catch (error) {
        console.error('Error updating integration:', error);
      }
    },

    integrationSyncCompleted: (integration: any) => {
      try {
        updateIntegration(integration.id, {
          ...integration,
          lastSync: new Date().toISOString(),
          syncStatus: 'success'
        });
      } catch (error) {
        console.error('Error updating integration sync status:', error);
      }
    },

    integrationSyncFailed: (integration: any) => {
      try {
        updateIntegration(integration.id, {
          ...integration,
          syncStatus: 'failed'
        });
        addNotification({
          type: 'error',
          title: 'Sync Failed',
          message: `Failed to sync ${integration.displayName}`,
        });
      } catch (error) {
        console.error('Error updating integration sync status:', error);
      }
    },

    // Workflow events
    workflowExecuted: (workflow: any) => {
      try {
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
      } catch (error) {
        console.error('Error updating workflow:', error);
      }
    },

    // Real-time workflow execution events
    workflowExecutedRealtime: (data: any) => {
      try {
        const workflow = workflows.find(w => w.id === data.workflowId);
        if (workflow) {
          updateWorkflow(data.workflowId, {
            executionCount: workflow.executionCount + 1,
            lastExecuted: data.timestamp
          });
          addNotification({
            type: 'success',
            title: 'Workflow Executed',
            message: `Workflow "${workflow.name}" completed successfully in ${data.executionTime}ms`,
          });
        }
      } catch (error) {
        console.error('Error handling real-time workflow execution:', error);
      }
    },

    workflowExecutionFailed: (data: any) => {
      try {
        const workflow = workflows.find(w => w.id === data.workflowId);
        if (workflow) {
          addNotification({
            type: 'error',
            title: 'Workflow Execution Failed',
            message: `Workflow "${workflow.name}" failed: ${data.error}`,
          });
        }
      } catch (error) {
        console.error('Error handling workflow execution failure:', error);
      }
    },

    // Agent events
    agentLog: (log: any) => {
      try {
        addAgentLog(log);
      } catch (error) {
        console.error('Error adding agent log:', error);
      }
    },

    agentStatusChanged: (agent: any) => {
      // Placeholder for agent status updates
      console.log('Agent status changed:', agent);
    },

    // Presence events
    presenceJoined: (user: any) => {
      try {
        addNotification({
          type: 'info',
          title: 'User Online',
          message: `${user?.username || user?.userId || 'Someone'} joined`,
        });
      } catch (e) {
        console.log('User joined presence:', user);
      }
    },

    presenceLeft: (user: any) => {
      try {
        addNotification({
          type: 'info',
          title: 'User Offline',
          message: `${user?.username || user?.userId || 'Someone'} left`,
        });
      } catch (e) {
        console.log('User left presence:', user);
      }
    },

    // Collaborative editing events
    documentLocked: (data: any) => {
      console.log('Document locked:', data);
      // Handle document locking for collaborative editing
    },

    documentUnlocked: (data: any) => {
      console.log('Document unlocked:', data);
      // Handle document unlocking
    },

    documentEdited: (data: any) => {
      console.log('Document edited:', data);
      // Handle real-time document changes
    },

    cursorMoved: (data: any) => {
      console.log('Cursor moved:', data);
      // Handle cursor position updates
    },
  }), [
    addTask, updateTask, deleteTask, setMessages, markMessageAsRead,
    addCalendarEvent, updateCalendarEvent, deleteCalendarEvent,
    updateIntegration, updateWorkflow, addAgentLog, addNotification,
    messages
  ]);

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
    // Register all event handlers
    on('task:created', eventHandlers.taskCreated);
    on('task:updated', eventHandlers.taskUpdated);
    on('task:deleted', eventHandlers.taskDeleted);
    on('message:new', eventHandlers.messageNew);
    on('message:read', eventHandlers.messageRead);
    on('calendar:event:created', eventHandlers.calendarEventCreated);
    on('calendar:event:updated', eventHandlers.calendarEventUpdated);
    on('calendar:event:deleted', eventHandlers.calendarEventDeleted);
    on('integration:connected', eventHandlers.integrationConnected);
    on('integration:disconnected', eventHandlers.integrationDisconnected);
    on('integration:sync:completed', eventHandlers.integrationSyncCompleted);
    on('integration:sync:failed', eventHandlers.integrationSyncFailed);
    on('workflow:executed', eventHandlers.workflowExecuted);
    on('workflow:executed:realtime', eventHandlers.workflowExecutedRealtime);
    on('workflow:execution:failed', eventHandlers.workflowExecutionFailed);
    on('agent:log', eventHandlers.agentLog);
    on('agent:status:changed', eventHandlers.agentStatusChanged);
    on('presence:joined', eventHandlers.presenceJoined);
    on('presence:left', eventHandlers.presenceLeft);
    on('document:locked', eventHandlers.documentLocked);
    on('document:unlocked', eventHandlers.documentUnlocked);
    on('document:edited', eventHandlers.documentEdited);
    on('cursor:moved', eventHandlers.cursorMoved);

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
      off('workflow:executed:realtime');
      off('workflow:execution:failed');
      off('agent:log');
      off('agent:status:changed');
      off('presence:joined');
      off('presence:left');
      off('document:locked');
      off('document:unlocked');
      off('document:edited');
      off('cursor:moved');
    };
  }, [on, off, eventHandlers]);

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

// Default export for compatibility with components using default import
export default useWebSocket;
