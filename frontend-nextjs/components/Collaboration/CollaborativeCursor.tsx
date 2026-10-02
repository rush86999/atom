/**
 * Collaborative Cursor Component
 * Shows other users' cursors on the workflow canvas
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { createSocketGuard, redactSocketUrl } from '@/lib/guardedSocket';
import { motion } from 'framer-motion';

interface CursorPosition {
  x: number;
  y: number;
  viewport?: {
    width: number;
    height: number;
  };
}

interface RemoteCursor {
  user_id: string;
  user_name: string;
  user_color: string;
  cursor_position: CursorPosition;
  selected_node?: string;
  last_updated: string;
}

interface CollaborativeCursorProps {
  sessionId?: string;
  workflowId: string;
  currentUserId?: string;
  canvasRef?: React.RefObject<HTMLDivElement>;
}

export interface CollaborativeCursorHandle {
  sendCursorPosition: (position: CursorPosition, selectedNode?: string) => void;
}

export const CollaborativeCursor = React.forwardRef<CollaborativeCursorHandle, CollaborativeCursorProps>(
  ({ sessionId, workflowId, currentUserId, canvasRef }, ref) => {
  const [remoteCursors, setRemoteCursors] = useState<Map<string, RemoteCursor>>(new Map());
  // Generation-guarded socket (lib/guardedSocket). Changing session or user
  // re-runs the effect: the old socket is closed and a new one opened, but the
  // close is asynchronous, so the OLD socket's onmessage could still deliver
  // another document's cursors into the one now on screen.
  const socketGuardRef = useRef(createSocketGuard());
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize WebSocket connection
  useEffect(() => {
    if (!sessionId) return;

    // Derive WS base from NEXT_PUBLIC_API_URL (env-configurable), matching
    // the useWebSocket hook pattern. Was hardcoded ws://localhost:8000.
    const apiBase = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, '');
    const wsBase = apiBase.replace(/^http/, 'ws');
    const wsUrl = `${wsBase}/ws/${sessionId}/${currentUserId}`;

    const closeSocket = socketGuardRef.current.open(wsUrl, {
      onMessage: (message) => {
        if (message.type === 'cursor_update') {
          setRemoteCursors((prev) => {
            const newMap = new Map(prev);

            if (message.user_id === currentUserId) {
              // Don't show our own cursor
              newMap.delete(message.user_id);
            } else {
              newMap.set(message.user_id, {
                user_id: message.user_id,
                user_name: message.user_name || message.user_id,
                user_color: message.user_color || '#2196F3',
                cursor_position: message.cursor_position,
                selected_node: message.selected_node,
                last_updated: message.timestamp || new Date().toISOString(),
              });

              // Remove cursor after 10 seconds of inactivity
              setTimeout(() => {
                setRemoteCursors((prev2) => {
                  const newMap2 = new Map(prev2);
                  newMap2.delete(message.user_id);
                  return newMap2;
                });
              }, 10000);
            }

            return newMap;
          });
        } else if (message.type === 'user_joined') {
          console.log('User joined:', message.user_id);
        } else if (message.type === 'user_left') {
          setRemoteCursors((prev) => {
            const newMap = new Map(prev);
            newMap.delete(message.user_id);
            return newMap;
          });
        } else if (message.type === 'lock_acquired') {
          // Handle lock events
          console.log('Lock acquired:', message.resource_id);
        } else if (message.type === 'lock_released') {
          console.log('Lock released:', message.resource_id);
        }
      },
      onParseError: () => {
        // A non-JSON frame (keepalive, proxy noise, partial) is swallowed so it
        // cannot kill the handler — but it is reported rather than silent.
        console.error('[CollaborativeCursor] unparseable WebSocket frame');
      },
      onError: () => {
        console.error(`[CollaborativeCursor] WebSocket error on ${redactSocketUrl(wsUrl)}`);
      },
    });

    // Send heartbeat every 30 seconds
    heartbeatIntervalRef.current = setInterval(() => {
      const ws = socketGuardRef.current.current();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'heartbeat' }));
      }
    }, 30000);

    return () => {
      closeSocket();
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = null;
      }
    };
  }, [sessionId, currentUserId]);

  // Send cursor position updates
  const sendCursorPosition = useCallback((position: CursorPosition, selectedNode?: string) => {
    const ws = socketGuardRef.current.current();
    if (!sessionId || !ws || ws.readyState !== WebSocket.OPEN) {
      return;
    }

    ws.send(JSON.stringify({
      type: 'cursor_update',
      cursor_position: position,
      selected_node: selectedNode,
    }));
  }, [sessionId]);

  // Expose function to send cursor updates (can be used by parent)
  React.useImperativeHandle(ref, () => ({ sendCursorPosition }));

  if (remoteCursors.size === 0) {
    return null; // Don't render anything if no remote cursors
  }

  return (
    <div className="collaborative-cursors-container">
      {Array.from(remoteCursors.values()).map((cursor) => (
        <motion.div
          key={cursor.user_id}
          className="collaborative-cursor"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          transition={{ duration: 0.2 }}
          style={{
            position: 'absolute',
            left: cursor.cursor_position.x,
            top: cursor.cursor_position.y,
            pointerEvents: 'none', // Don't block interactions
            zIndex: 1000,
          }}
        >
          {/* Cursor Icon */}
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            style={{
              transform: 'rotate(-15deg)',
              filter: `drop-shadow(1px 1px 2px rgba(0,0,0,0.3))`,
            }}
          >
            <path
              d="M5.65376 12.3673H5.46026L5.31739 12.7309C5.30195 12.7631 5.28636 12.7951 5.27061 12.8271L2.4958 18.6582C2.40455 18.8501 2.31349 19.0422 2.22258 19.2344L1.42089 19.2344C1.26421 19.2344 1.10795 19.1895 0.951854 19.0996C0.795756 19.0098 0.639898 18.9649 0.483836 18.875L2.71134 12.6821C2.62043 12.5922 2.52946 12.5025 2.43855 12.4127C2.34764 12.323 2.25674 12.2335 2.16583 12.1439L2.02447 12.0024L5.65376 12.3673ZM5.65376 12.3673L9.32491 7.99969L9.32491 7.99969L5.65376 12.3673Z"
              fill={cursor.user_color}
            />
          </svg>

          {/* User Name Label */}
          <div
            className="cursor-label"
            style={{
              position: 'absolute',
              left: 16,
              top: 16,
              backgroundColor: cursor.user_color,
              color: '#fff',
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: '600',
              whiteSpace: 'nowrap',
              boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
            }}
          >
            {cursor.user_name}
          </div>

          {/* Selection Indicator */}
          {cursor.selected_node && (
            <div
              className="selection-indicator"
              style={{
                position: 'absolute',
                left: 8,
                top: 32,
                backgroundColor: `${cursor.user_color}20`,
                border: `1px dashed ${cursor.user_color}`,
                padding: '2px 6px',
                borderRadius: '4px',
                fontSize: '10px',
                color: cursor.user_color,
              }}
            >
            🔍 {cursor.selected_node}
            </div>
          )}
        </motion.div>
      ))}
    </div>
  );
});

CollaborativeCursor.displayName = 'CollaborativeCursor';

export default CollaborativeCursor;
