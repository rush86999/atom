import React, { createContext, useContext, useEffect, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';

type WSContextValue = {
  socket: Socket | null;
  emit: (event: string, data?: any) => void;
  on: (event: string, cb: (...args: any[]) => void) => void;
  off: (event: string, cb?: (...args: any[]) => void) => void;
  subscribe: (event: string, cb: (...args: any[]) => void) => void;
  unsubscribe: (event: string, cb?: (...args: any[]) => void) => void;
};

const WebSocketContext = createContext<WSContextValue | null>(null);

export const useWebSocketContext = (): WSContextValue | null => useContext(WebSocketContext);

export const WebSocketProvider: React.FC<{ url?: string; children: React.ReactNode }> = ({ url, children }) => {
  const socketRef = useRef<Socket | null>(null);
  const handlersRef = useRef<Map<string, Set<(...args: any[]) => void>>>(new Map());

  const WS_URL = url || process.env.REACT_APP_WS_URL || 'ws://localhost:3001';

  useEffect(() => {
    // Create and connect socket
    try {
      socketRef.current = io(WS_URL, { transports: ['websocket', 'polling'], autoConnect: true });
    } catch (e) {
      console.warn('Failed to init socket.io client', e);
      socketRef.current = null;
    }

    const socket = socketRef.current;

    const wrapOn = (event: string, cb: (...args: any[]) => void) => {
      if (!handlersRef.current.has(event)) handlersRef.current.set(event, new Set());
      handlersRef.current.get(event)!.add(cb);
      socket?.on(event, cb);
    };

    const wrapOff = (event: string, cb?: (...args: any[]) => void) => {
      const set = handlersRef.current.get(event);
      if (cb) {
        set?.delete(cb);
        socket?.off(event, cb);
      } else {
        set?.forEach((c) => socket?.off(event, c));
        handlersRef.current.delete(event);
      }
    };

    const onAny = (event: string, ...args: any[]) => {
      // no-op
    };

    socket?.on('connect_error', (err: any) => console.warn('WS connect_error', err));

    return () => {
      // cleanup
      try {
        handlersRef.current.forEach((set, event) => {
          set.forEach((cb) => socket?.off(event, cb));
        });
        handlersRef.current.clear();
        socket?.disconnect();
      } catch (e) {
        // ignore
      }
    };
  }, [WS_URL]);

  const emit = useCallback((event: string, data?: any) => {
    if (socketRef.current && socketRef.current.connected) {
      socketRef.current.emit(event, data);
    }
  }, []);

  const on = useCallback((event: string, cb: (...args: any[]) => void) => {
    const socket = socketRef.current;
    if (!handlersRef.current.has(event)) handlersRef.current.set(event, new Set());
    handlersRef.current.get(event)!.add(cb);
    socket?.on(event, cb);
  }, []);

  const off = useCallback((event: string, cb?: (...args: any[]) => void) => {
    const socket = socketRef.current;
    const set = handlersRef.current.get(event);
    if (cb) {
      set?.delete(cb);
      socket?.off(event, cb);
    } else {
      set?.forEach((c) => socket?.off(event, c));
      handlersRef.current.delete(event);
    }
  }, []);

  const subscribe = on;
  const unsubscribe = off;

  const value: WSContextValue = {
    socket: socketRef.current,
    emit,
    on,
    off,
    subscribe,
    unsubscribe,
  };

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
};
