/**
 * AgentOperationTracker Component
 *
 * Displays real-time agent operations with progress tracking,
 * context explanations, and live operation logs.
 */

import React, { useState, useEffect } from 'react';
import useWebSocket from '@/hooks/useWebSocket';

export interface OperationLog {
  timestamp: string;
  level: 'info' | 'warning' | 'error';
  message: string;
}

export interface OperationContext {
  what: string;
  why: string;
  next: string;
}

export interface AgentOperationData {
  operation_id: string;
  agent_id: string;
  agent_name: string;
  operation_type: string;
  status: 'running' | 'waiting' | 'completed' | 'failed';
  current_step: string;
  total_steps?: number;
  current_step_index: number;
  progress: number; // 0-100
  context: OperationContext;
  metadata?: Record<string, any>;
  logs: OperationLog[];
  started_at: string;
  completed_at?: string;
}

export interface AgentOperationTrackerProps {
  operationId?: string;
  userId: string;
  className?: string;
}

/**
 * AgentOperationTracker - Displays live agent operation progress
 */
export const AgentOperationTracker: React.FC<AgentOperationTrackerProps> = ({
  operationId,
  userId,
  className = ''
}) => {
  const [operation, setOperation] = useState<AgentOperationData | null>(null);
  const [logsExpanded, setLogsExpanded] = useState(false);
  const { socket, connected } = useWebSocket();

  useEffect(() => {
    if (!socket || !connected) return;

    // Subscribe to canvas updates
    const handleMessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);

        // Handle operation present
        if (message.type === 'canvas:update' && message.data?.component === 'agent_operation_tracker') {
          const data = message.data.data;

          // Filter by operationId if specified
          if (!operationId || data.operation_id === operationId) {
            setOperation(data);
          }
        }

        // Handle operation updates
        if (message.type === 'canvas:update' && message.data?.action === 'update') {
          if (message.data.operation_id === operation?.operation_id) {
            setOperation((prev) => ({
              ...prev!,
              ...message.data.updates
            }));
          }
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    socket.addEventListener('message', handleMessage);

    return () => {
      socket.removeEventListener('message', handleMessage);
    };
  }, [socket, connected, operationId, operation]);

  if (!operation) {
    return (
      <div className={`agent-operation-tracker loading ${className}`}>
        <div className="animate-pulse flex items-center space-x-3">
          <div className="w-4 h-4 bg-gray-300 rounded-full"></div>
          <div className="h-4 bg-gray-300 rounded w-48"></div>
        </div>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'text-blue-600 bg-blue-50';
      case 'waiting':
        return 'text-yellow-600 bg-yellow-50';
      case 'completed':
        return 'text-green-600 bg-green-50';
      case 'failed':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return '⚡';
      case 'waiting':
        return '⏸️';
      case 'completed':
        return '✅';
      case 'failed':
        return '❌';
      default:
        return '🔄';
    }
  };

  const getLogIcon = (level: string) => {
    switch (level) {
      case 'info':
        return 'ℹ️';
      case 'warning':
        return '⚠️';
      case 'error':
        return '❌';
      default:
        return '•';
    }
  };

  return (
    <div className={`agent-operation-tracker bg-white rounded-lg shadow-md p-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <span className="text-2xl">🤖</span>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{operation.agent_name}</h3>
            <p className="text-sm text-gray-500">Agent Operation</p>
          </div>
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(operation.status)}`}>
          <span className="mr-1">{getStatusIcon(operation.status)}</span>
          {operation.status.charAt(0).toUpperCase() + operation.status.slice(1)}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="flex justify-between text-sm text-gray-600 mb-2">
          <span>Progress</span>
          <span>{operation.progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-300 ease-out"
            style={{ width: `${operation.progress}%` }}
          ></div>
        </div>
        {operation.total_steps && (
          <p className="text-xs text-gray-500 mt-1">
            Step {operation.current_step_index} of {operation.total_steps}
          </p>
        )}
      </div>

      {/* Current Step */}
      <div className="mb-4 p-4 bg-gray-50 rounded-lg">
        <p className="text-sm font-medium text-gray-700 mb-1">Current Step:</p>
        <p className="text-gray-900">{operation.current_step}</p>
      </div>

      {/* Context */}
      {(operation.context.what || operation.context.why || operation.context.next) && (
        <div className="mb-4 p-4 bg-blue-50 rounded-lg">
          <p className="text-sm font-medium text-blue-900 mb-2">📋 Context:</p>

          {operation.context.what && (
            <div className="mb-2">
              <p className="text-sm font-medium text-blue-800">What I'm doing:</p>
              <p className="text-sm text-blue-700">{operation.context.what}</p>
            </div>
          )}

          {operation.context.why && (
            <div className="mb-2">
              <p className="text-sm font-medium text-blue-800">Why:</p>
              <p className="text-sm text-blue-700">{operation.context.why}</p>
            </div>
          )}

          {operation.context.next && (
            <div>
              <p className="text-sm font-medium text-blue-800">What's next:</p>
              <p className="text-sm text-blue-700">{operation.context.next}</p>
            </div>
          )}
        </div>
      )}

      {/* Logs */}
      {operation.logs.length > 0 && (
        <div className="border-t pt-4">
          <button
            onClick={() => setLogsExpanded(!logsExpanded)}
            className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            <span>📜 Operation Logs ({operation.logs.length})</span>
            <span>{logsExpanded ? '▼' : '▶'}</span>
          </button>

          {logsExpanded && (
            <div className="mt-3 max-h-60 overflow-y-auto bg-gray-50 rounded p-3 space-y-2">
              {operation.logs.map((log, index) => (
                <div key={index} className="flex items-start space-x-2 text-sm">
                  <span className="flex-shrink-0">{getLogIcon(log.level)}</span>
                  <div className="flex-1 min-w-0">
                    <p className={`font-medium ${
                      log.level === 'error' ? 'text-red-700' :
                      log.level === 'warning' ? 'text-yellow-700' :
                      'text-gray-700'
                    }`}>
                      {log.message}
                    </p>
                    <p className="text-xs text-gray-500">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="mt-4 pt-4 border-t text-xs text-gray-500">
        Started: {new Date(operation.started_at).toLocaleString()}
        {operation.completed_at && (
          <span className="ml-4">
            Completed: {new Date(operation.completed_at).toLocaleString()}
          </span>
        )}
      </div>
    </div>
  );
};

export default AgentOperationTracker;
