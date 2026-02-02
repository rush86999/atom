/**
 * OperationErrorGuide Component
 *
 * Displays error information with actionable resolution suggestions.
 * Shows what happened, why, and provides multiple resolution options.
 */

import React, { useState, useEffect } from 'react';
import useWebSocket from '@/hooks/useWebSocket';

export interface ErrorDetail {
  type: string;
  code: string;
  message: string;
  technical_details: string;
}

export interface AgentAnalysis {
  what_happened: string;
  why_it_happened: string;
  impact: string;
}

export interface Resolution {
  title: string;
  description: string;
  agent_can_fix: boolean;
  steps: string[];
}

export interface ErrorData {
  operation_id: string;
  error: ErrorDetail;
  agent_analysis: AgentAnalysis;
  resolutions: Resolution[];
  suggested_resolution: number;
}

export interface OperationErrorGuideProps {
  operationId?: string;
  userId: string;
  onResolutionSelect?: (resolution: Resolution) => void;
  className?: string;
}

/**
 * OperationErrorGuide - Displays error with resolution options
 */
export const OperationErrorGuide: React.FC<OperationErrorGuideProps> = ({
  operationId,
  userId,
  onResolutionSelect,
  className = ''
}) => {
  const [errorData, setErrorData] = useState<ErrorData | null>(null);
  const [selectedResolution, setSelectedResolution] = useState<number | null>(null);
  const [expandedResolution, setExpandedResolution] = useState<number | null>(null);
  const { socket, connected } = useWebSocket();

  useEffect(() => {
    if (!socket || !connected) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'operation:error') {
          const data = message.data;

          // Filter by operationId if specified
          if (!operationId || data.operation_id === operationId) {
            setErrorData(data);
            // Auto-expand suggested resolution
            setExpandedResolution(data.suggested_resolution);
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
  }, [socket, connected, operationId]);

  const handleResolutionClick = (index: number, resolution: Resolution) => {
    setSelectedResolution(index);
    if (onResolutionSelect) {
      onResolutionSelect(resolution);
    }

    // Send resolution to backend
    if (socket && connected) {
      socket.send(JSON.stringify({
        type: 'error:resolution_selected',
        data: {
          operation_id: errorData?.operation_id,
          resolution_index: index,
          resolution: resolution
        }
      }));
    }
  };

  if (!errorData) {
    return null;
  }

  const getErrorIcon = (type: string) => {
    switch (type) {
      case 'permission_denied':
        return '🔒';
      case 'auth_expired':
        return '🔑';
      case 'network_error':
        return '🌐';
      case 'rate_limit':
        return '⏱️';
      case 'invalid_input':
        return '⚠️';
      case 'resource_not_found':
        return '🔍';
      default:
        return '❌';
    }
  };

  return (
    <div className={`operation-error-guide bg-white rounded-lg shadow-md p-6 border-l-4 border-red-500 ${className}`}>
      {/* Error Header */}
      <div className="flex items-start space-x-3 mb-4">
        <span className="text-3xl">{getErrorIcon(errorData.error.type)}</span>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">
            Operation Failed
          </h3>
          <p className="text-sm text-gray-600">{errorData.error.message}</p>
          {errorData.error.code && (
            <span className="inline-block mt-2 px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded">
              Error Code: {errorData.error.code}
            </span>
          )}
        </div>
      </div>

      {/* Agent Analysis */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg">
        <h4 className="text-sm font-semibold text-gray-900 mb-3">📊 Agent Analysis</h4>

        <div className="space-y-3">
          <div>
            <p className="text-xs font-medium text-gray-700 uppercase tracking-wide">
              What Happened
            </p>
            <p className="text-sm text-gray-900">{errorData.agent_analysis.what_happened}</p>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-700 uppercase tracking-wide">
              Why It Happened
            </p>
            <p className="text-sm text-gray-900">{errorData.agent_analysis.why_it_happened}</p>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-700 uppercase tracking-wide">
              Impact
            </p>
            <p className="text-sm text-gray-900">{errorData.agent_analysis.impact}</p>
          </div>
        </div>
      </div>

      {/* Resolutions */}
      <div>
        <h4 className="text-sm font-semibold text-gray-900 mb-3">🔧 Suggested Resolutions</h4>

        <div className="space-y-3">
          {errorData.resolutions.map((resolution, index) => {
            const isSuggested = index === errorData.suggested_resolution;
            const isSelected = selectedResolution === index;
            const isExpanded = expandedResolution === index;

            return (
              <div
                key={index}
                className={`border rounded-lg overflow-hidden transition-all ${
                  isSuggested ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                } ${isSelected ? 'ring-2 ring-blue-500' : ''}`}
              >
                {/* Resolution Header */}
                <button
                  onClick={() => setExpandedResolution(isExpanded ? null : index)}
                  className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center space-x-3">
                    {isSuggested && (
                      <span className="px-2 py-1 bg-blue-500 text-white text-xs font-medium rounded">
                        Suggested
                      </span>
                    )}
                    <span className="font-medium text-gray-900">{resolution.title}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    {resolution.agent_can_fix && (
                      <span className="text-xs text-green-600">🤖 Agent can fix</span>
                    )}
                    <span>{isExpanded ? '▼' : '▶'}</span>
                  </div>
                </button>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="p-4 pt-0 border-t">
                    <p className="text-sm text-gray-700 mb-3">{resolution.description}</p>

                    {/* Steps */}
                    <div className="mb-4">
                      <p className="text-xs font-medium text-gray-700 uppercase tracking-wide mb-2">
                        Steps:
                      </p>
                      <ol className="text-sm text-gray-900 space-y-1">
                        {resolution.steps.map((step, stepIndex) => (
                          <li key={stepIndex} className="flex items-start">
                            <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center bg-gray-200 text-gray-700 text-xs rounded-full mr-2 mt-0.5">
                              {stepIndex + 1}
                            </span>
                            <span>{step}</span>
                          </li>
                        ))}
                      </ol>
                    </div>

                    {/* Select Button */}
                    <button
                      onClick={() => handleResolutionClick(index, resolution)}
                      className={`w-full py-2 px-4 rounded-lg font-medium transition-colors ${
                        isSelected
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      {isSelected ? '✓ Selected' : resolution.agent_can_fix ? 'Let Agent Fix' : 'Fix Manually'}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Technical Details (Collapsible) */}
      <details className="mt-6">
        <summary className="cursor-pointer text-sm text-gray-600 hover:text-gray-900">
          Show Technical Details
        </summary>
        <pre className="mt-2 p-3 bg-gray-900 text-gray-100 text-xs rounded overflow-x-auto">
          {errorData.error.technical_details}
        </pre>
      </details>
    </div>
  );
};

export default OperationErrorGuide;
