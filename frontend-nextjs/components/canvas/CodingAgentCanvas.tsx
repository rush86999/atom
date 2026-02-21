/**
 * CodingAgentCanvas Component
 *
 * Real-time canvas for autonomous coding agent operations with AI accessibility.
 * Provides code editor UI, operations feed, approval workflow, validation feedback,
 * and history view with full episode integration for WorldModel recall.
 */

import React, { useState, useEffect, useCallback } from 'react';
import useWebSocket from '@/hooks/useWebSocket';

// ============================================================================
// TypeScript Interfaces
// ============================================================================

export interface CodingAgentOperation {
  id: string;
  type: 'code_generation' | 'test_generation' | 'validation' | 'documentation' | 'refactoring';
  status: 'pending' | 'running' | 'complete' | 'failed';
  timestamp: Date;
  codeContent?: string;
  testResults?: TestResult;
  error?: string;
}

export interface TestResult {
  passed: number;
  total: number;
  coverage: number;
  failures: Array<{
    test: string;
    error: string;
  }>;
  duration: number;
}

export interface ValidationFeedback {
  passed: number;
  total: number;
  coverage: number;
  failures: Array<{
    test: string;
    error: string;
  }>;
}

export interface CodeChange {
  operation_id: string;
  file_path: string;
  old_content: string;
  new_content: string;
  timestamp: Date;
}

export interface CodingAgentCanvasProps {
  sessionId: string;
  onApprove?: (actionId: string) => void;
  onRetry?: (actionId: string) => void;
  onReject?: (actionId: string) => void;
  className?: string;
}

// ============================================================================
// Component Implementation
// ============================================================================

/**
 * CodingAgentCanvas - Real-time canvas for autonomous coding agents
 */
export const CodingAgentCanvas: React.FC<CodingAgentCanvasProps> = ({
  sessionId,
  onApprove,
  onRetry,
  onReject,
  className = ''
}) => {
  // State management
  const [operations, setOperations] = useState<CodingAgentOperation[]>([]);
  const [codeContent, setCodeContent] = useState('');
  const [language, setLanguage] = useState<'python' | 'typescript' | 'javascript' | 'sql' | 'yaml'>('python');
  const [approvalRequired, setApprovalRequired] = useState<string | null>(null);
  const [validationFeedback, setValidationFeedback] = useState<ValidationFeedback | null>(null);
  const [historyView, setHistoryView] = useState(false);
  const [codeChanges, setCodeChanges] = useState<CodeChange[]>([]);
  const [currentAction, setCurrentAction] = useState<string | null>(null);

  const { socket, connected } = useWebSocket();

  // ============================================================================
  // WebSocket Integration
  // ============================================================================

  useEffect(() => {
    if (!socket || !connected) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);

        // Handle coding agent canvas updates
        if (message.type === 'canvas:update' && message.data?.component === 'coding_agent_canvas') {
          const data = message.data.data;

          // Filter by sessionId
          if (data.sessionId === sessionId) {
            if (data.operations) {
              setOperations(data.operations.map((op: any) => ({
                ...op,
                timestamp: new Date(op.timestamp)
              })));
            }
            if (data.codeContent !== undefined) {
              setCodeContent(data.codeContent);
            }
            if (data.language) {
              setLanguage(data.language);
            }
            if (data.approvalRequired !== undefined) {
              setApprovalRequired(data.approvalRequired);
            }
            if (data.validationFeedback) {
              setValidationFeedback(data.validationFeedback);
            }
            if (data.currentAction) {
              setCurrentAction(data.currentAction);
            }
          }
        }

        // Handle operation updates
        if (message.type === 'coding:operation_update') {
          if (message.data.sessionId === sessionId) {
            setOperations((prev) => {
              const existing = prev.findIndex(op => op.id === message.data.operation.id);
              if (existing >= 0) {
                const updated = [...prev];
                updated[existing] = {
                  ...message.data.operation,
                  timestamp: new Date(message.data.operation.timestamp)
                };
                return updated;
              }
              return [
                ...prev,
                {
                  ...message.data.operation,
                  timestamp: new Date(message.data.operation.timestamp)
                }
              ];
            });
          }
        }

        // Handle code changes
        if (message.type === 'coding:code_change') {
          if (message.data.sessionId === sessionId) {
            setCodeChanges((prev) => [
              ...prev,
              {
                ...message.data.change,
                timestamp: new Date(message.data.change.timestamp)
              }
            ]);
          }
        }

        // Handle approval requests
        if (message.type === 'coding:approval_required') {
          if (message.data.sessionId === sessionId) {
            setApprovalRequired(message.data.actionId);
            setCodeContent(message.data.codeContent);
          }
        }

        // Handle validation results
        if (message.type === 'coding:validation_result') {
          if (message.data.sessionId === sessionId) {
            setValidationFeedback(message.data.feedback);
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
  }, [socket, connected, sessionId]);

  // ============================================================================
  // Action Handlers
  // ============================================================================

  const handleApprove = useCallback(() => {
    if (approvalRequired) {
      onApprove?.(approvalRequired);
      setApprovalRequired(null);
    }
  }, [approvalRequired, onApprove]);

  const handleRetry = useCallback(() => {
    if (approvalRequired) {
      onRetry?.(approvalRequired);
    }
  }, [approvalRequired, onRetry]);

  const handleReject = useCallback(() => {
    if (approvalRequired) {
      onReject?.(approvalRequired);
      setApprovalRequired(null);
    }
  }, [approvalRequired, onReject]);

  const toggleHistoryView = useCallback(() => {
    setHistoryView((prev) => !prev);
  }, []);

  // ============================================================================
  // Rendering Helpers
  // ============================================================================

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'pending':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'complete':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'failed':
        return 'text-red-600 bg-red-50 border-red-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return '⚡';
      case 'pending':
        return '⏳';
      case 'complete':
        return '✅';
      case 'failed':
        return '❌';
      default:
        return '🔄';
    }
  };

  const getOperationTypeLabel = (type: string) => {
    switch (type) {
      case 'code_generation':
        return 'Code Generation';
      case 'test_generation':
        return 'Test Generation';
      case 'validation':
        return 'Validation';
      case 'documentation':
        return 'Documentation';
      case 'refactoring':
        return 'Refactoring';
      default:
        return type;
    }
  };

  const isAgentActive = operations.some(op => op.status === 'running');

  // ============================================================================
  // Render Functions
  // ============================================================================

  const renderApprovalWorkflow = () => {
    if (!approvalRequired) return null;

    return (
      <div className="approval-workspace mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
        <h3 className="text-lg font-semibold text-yellow-900 mb-3">Agent Suggestion Requires Approval</h3>
        <div className="suggestion-preview mb-4">
          <pre className="bg-white p-3 rounded border border-yellow-300 overflow-x-auto text-sm">
            <code>{codeContent}</code>
          </pre>
        </div>
        <div className="approval-actions flex space-x-3">
          <button
            onClick={handleApprove}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition"
          >
            Approve
          </button>
          <button
            onClick={handleRetry}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
          >
            Retry
          </button>
          <button
            onClick={handleReject}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition"
          >
            Reject
          </button>
        </div>
      </div>
    );
  };

  const renderValidationFeedback = () => {
    if (!validationFeedback) return null;

    const passRate = (validationFeedback.passed / validationFeedback.total) * 100;

    return (
      <div className="validation-feedback mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <h4 className="text-md font-semibold text-blue-900 mb-2">Test Results</h4>
        <div className="mb-2">
          <span className="text-lg font-bold">
            {validationFeedback.passed} / {validationFeedback.total}
          </span>
          <span className="text-gray-600 ml-2">tests passing ({passRate.toFixed(1)}%)</span>
        </div>
        <div className="coverage-metrics mb-3">
          <span className="font-medium">Coverage: </span>
          <span className={`font-bold ${validationFeedback.coverage >= 80 ? 'text-green-600' : 'text-orange-600'}`}>
            {validationFeedback.coverage.toFixed(1)}%
          </span>
        </div>
        {validationFeedback.failures.length > 0 && (
          <div className="failures mt-3">
            <h5 className="text-sm font-semibold text-red-700 mb-2">Failures:</h5>
            <div className="max-h-40 overflow-y-auto">
              {validationFeedback.failures.map((failure, idx) => (
                <div key={idx} className="text-sm text-red-600 mb-1">
                  <span className="font-medium">{failure.test}:</span> {failure.error}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderHistoryView = () => {
    if (!historyView) return null;

    return (
      <div className="history-view mt-4 p-4 bg-gray-50 border border-gray-200 rounded-lg">
        <h4 className="text-md font-semibold text-gray-900 mb-3">Code Changes History</h4>
        <div className="space-y-2 max-h-60 overflow-y-auto">
          {codeChanges.map((change) => (
            <div key={change.operation_id} className="operation-log p-2 bg-white rounded border">
              <div className="flex justify-between items-center mb-1">
                <span className="font-medium text-sm">{change.file_path}</span>
                <span className="text-xs text-gray-500">
                  {change.timestamp.toLocaleString()}
                </span>
              </div>
              <pre className="text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                <code>{change.new_content.substring(0, 200)}...</code>
              </pre>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // ============================================================================
  // Main Render
  // ============================================================================

  return (
    <div className={`coding-agent-canvas bg-white rounded-lg shadow-md p-6 ${className}`}>
      {/* Header */}
      <div className="canvas-header flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <span className="text-2xl">🤖</span>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Autonomous Coding Agent</h2>
            <p className="text-sm text-gray-500">Session: {sessionId}</p>
          </div>
        </div>
        <div className="agent-status flex items-center space-x-2">
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${isAgentActive ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
            <span className="mr-1">{isAgentActive ? '⚡' : '💤'}</span>
            {isAgentActive ? 'Active' : 'Idle'}
          </span>
          {currentAction && (
            <span className="text-sm text-gray-600 max-w-xs truncate">{currentAction}</span>
          )}
        </div>
      </div>

      {/* Code Editor UI */}
      <div className="code-editor mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-700">Generated Code</h3>
          <span className="text-xs text-gray-500 uppercase">{language}</span>
        </div>
        <textarea
          value={codeContent}
          onChange={(e) => setCodeContent(e.target.value)}
          placeholder="Generated code will appear here..."
          className="code-textarea w-full h-64 p-3 font-mono text-sm bg-gray-50 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Real-time Operations Feed */}
      <div className="operations-feed mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-700">Agent Operations</h3>
          <button
            onClick={toggleHistoryView}
            className="text-xs text-blue-600 hover:text-blue-800"
          >
            {historyView ? 'Hide' : 'Show'} History
          </button>
        </div>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {operations.length === 0 ? (
            <div className="text-sm text-gray-500 italic">No operations yet...</div>
          ) : (
            operations.map((op) => (
              <div
                key={op.id}
                className={`operation flex items-center justify-between p-2 rounded border ${getStatusColor(op.status)}`}
              >
                <div className="flex items-center space-x-2">
                  <span>{getStatusIcon(op.status)}</span>
                  <span className="text-sm font-medium">{getOperationTypeLabel(op.type)}</span>
                </div>
                <span className="text-xs text-gray-500">{op.timestamp.toLocaleTimeString()}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Conditional Sections */}
      {renderApprovalWorkflow()}
      {renderValidationFeedback()}
      {renderHistoryView()}

      {/* Hidden Accessibility Mirror for AI Agents */}
      <div
        role="log"
        aria-live="polite"
        aria-label="Coding agent canvas state"
        style={{ display: 'none' }}
        data-canvas-type="coding"
        data-canvas-component="coding_agent_canvas"
        data-session-id={sessionId}
        data-operations-count={operations.length}
        data-code-content-length={codeContent.length}
        data-language={language}
        data-approval-required={approvalRequired || 'false'}
        data-validation-feedback={validationFeedback ? JSON.stringify(validationFeedback) : ''}
        data-current-action={currentAction || ''}
        data-agent-active={isAgentActive}
      >
        {JSON.stringify({
          sessionId,
          canvas_type: 'coding',
          component: 'coding_agent_canvas',
          operations: operations.map(op => ({
            id: op.id,
            type: op.type,
            status: op.status,
            timestamp: op.timestamp.toISOString(),
            codeContent: op.codeContent,
            error: op.error
          })),
          codeContent,
          language,
          validationFeedback,
          approvalRequired,
          currentAction,
          agentActive: isAgentActive,
          codeChangesCount: codeChanges.length
        }, null, 2)}
      </div>
    </div>
  );
};

export default CodingAgentCanvas;
