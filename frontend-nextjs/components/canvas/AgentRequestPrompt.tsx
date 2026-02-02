/**
 * AgentRequestPrompt Component
 *
 * Displays agent requests for user input, decisions, or permissions.
 * Shows options with consequences and allows user to respond.
 */

import React, { useState, useEffect } from 'react';
import useWebSocket from '@/hooks/useWebSocket';

export interface RequestOption {
  label: string;
  description: string;
  consequences: string;
  action: string;
}

export interface RequestData {
  request_id: string;
  agent_id: string;
  agent_name: string;
  request_type: 'permission' | 'input' | 'decision' | 'confirmation';
  urgency: 'low' | 'medium' | 'high' | 'blocking';
  title: string;
  explanation: string;
  context: {
    operation: string;
    impact: string;
    alternatives?: string[];
  };
  options: RequestOption[];
  suggested_option: number;
  expires_at?: string;
  governance: {
    requires_signature: boolean;
    audit_log_required: boolean;
    revocable: boolean;
  };
}

export interface AgentRequestPromptProps {
  requestId?: string;
  userId: string;
  onResponse?: (requestId: string, response: any) => void;
  className?: string;
}

/**
 * AgentRequestPrompt - Displays agent requests for user input
 */
export const AgentRequestPrompt: React.FC<AgentRequestPromptProps> = ({
  requestId,
  userId,
  onResponse,
  className = ''
}) => {
  const [requestData, setRequestData] = useState<RequestData | null>(null);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [responding, setResponding] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);
  const { socket, connected } = useWebSocket();

  useEffect(() => {
    if (!socket || !connected) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'agent:request') {
          const data = message.data;

          // Filter by requestId if specified
          if (!requestId || data.request_id === requestId) {
            setRequestData(data);
            // Pre-select suggested option
            setSelectedOption(data.suggested_option);

            // Set up expiration timer
            if (data.expires_at) {
              const expiresAt = new Date(data.expires_at);
              const now = new Date();
              const remaining = Math.max(0, Math.floor((expiresAt.getTime() - now.getTime()) / 1000));
              setTimeRemaining(remaining);
            }
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
  }, [socket, connected, requestId]);

  // Countdown timer
  useEffect(() => {
    if (timeRemaining === null || timeRemaining <= 0) return;

    const timer = setInterval(() => {
      setTimeRemaining((prev) => (prev !== null ? Math.max(0, prev - 1) : null));
    }, 1000);

    return () => clearInterval(timer);
  }, [timeRemaining]);

  const handleResponse = async (optionIndex: number) => {
    if (!requestData || !socket) return;

    setResponding(true);

    const option = requestData.options[optionIndex];
    const response = {
      action: option.action,
      label: option.label,
      timestamp: new Date().toISOString()
    };

    // Send response via WebSocket
    socket.send(JSON.stringify({
      type: 'agent:request_response',
      data: {
        request_id: requestData.request_id,
        response: response
      }
    }));

    // Also call REST API for persistence
    try {
      const apiResponse = await fetch('/api/agent-guidance/request/' + requestData.request_id + '/respond', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          request_id: requestData.request_id,
          response: response
        })
      });

      if (!apiResponse.ok) {
        console.error('Failed to record response:', await apiResponse.text());
      }
    } catch (error) {
      console.error('Error sending response:', error);
    }

    // Call callback
    if (onResponse) {
      onResponse(requestData.request_id, response);
    }

    setResponding(false);
  };

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'low':
        return 'bg-blue-100 text-blue-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'high':
        return 'bg-orange-100 text-orange-800';
      case 'blocking':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getUrgencyIcon = (urgency: string) => {
    switch (urgency) {
      case 'low':
        return 'ℹ️';
      case 'medium':
        return '⚠️';
      case 'high':
        return '🔶';
      case 'blocking':
        return '🚨';
      default:
        return '•';
    }
  };

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  if (!requestData) {
    return null;
  }

  const expired = timeRemaining === 0;

  return (
    <div className={`agent-request-prompt bg-white rounded-lg shadow-lg p-6 border-2 ${
      requestData.urgency === 'blocking' ? 'border-red-500' :
      requestData.urgency === 'high' ? 'border-orange-500' :
      'border-gray-200'
    } ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center space-x-3">
          <span className="text-3xl">🤖</span>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {requestData.title}
            </h3>
            <p className="text-sm text-gray-500">
              From: {requestData.agent_name}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Urgency Badge */}
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${getUrgencyColor(requestData.urgency)}`}>
            <span className="mr-1">{getUrgencyIcon(requestData.urgency)}</span>
            {requestData.urgency.charAt(0).toUpperCase() + requestData.urgency.slice(1)}
          </span>

          {/* Expiration Timer */}
          {timeRemaining !== null && (
            <span className={`text-xs font-mono ${timeRemaining < 60 ? 'text-red-600' : 'text-gray-600'}`}>
              {expired ? 'Expired' : formatTime(timeRemaining)}
            </span>
          )}
        </div>
      </div>

      {/* Explanation */}
      <div className="mb-4 p-4 bg-blue-50 rounded-lg">
        <p className="text-sm text-blue-900">{requestData.explanation}</p>
      </div>

      {/* Context */}
      <div className="mb-4 p-4 bg-gray-50 rounded-lg">
        <h4 className="text-sm font-semibold text-gray-900 mb-2">Context</h4>

        <div className="space-y-2 text-sm">
          <div>
            <span className="font-medium text-gray-700">Operation: </span>
            <span className="text-gray-900">{requestData.context.operation}</span>
          </div>
          <div>
            <span className="font-medium text-gray-700">Impact: </span>
            <span className="text-gray-900">{requestData.context.impact}</span>
          </div>

          {requestData.context.alternatives && requestData.context.alternatives.length > 0 && (
            <div>
              <span className="font-medium text-gray-700">Alternatives: </span>
              <ul className="list-disc list-inside text-gray-900 ml-2">
                {requestData.context.alternatives.map((alt, index) => (
                  <li key={index}>{alt}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Options */}
      <div>
        <h4 className="text-sm font-semibold text-gray-900 mb-3">Choose an option:</h4>

        <div className="space-y-3">
          {requestData.options.map((option, index) => {
            const isSuggested = index === requestData.suggested_option;
            const isSelected = selectedOption === index;

            return (
              <button
                key={index}
                onClick={() => !expired && !responding && setSelectedOption(index)}
                disabled={expired || responding}
                className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50'
                    : isSuggested
                    ? 'border-blue-300 bg-blue-50/50 hover:bg-blue-50'
                    : 'border-gray-200 hover:bg-gray-50'
                } ${expired || responding ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="font-medium text-gray-900">{option.label}</span>
                      {isSuggested && (
                        <span className="px-2 py-0.5 bg-blue-500 text-white text-xs rounded">
                          Suggested
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700 mb-2">{option.description}</p>
                    <p className="text-xs text-gray-600">
                      <span className="font-medium">Consequence:</span> {option.consequences}
                    </p>
                  </div>

                  {isSelected && (
                    <span className="text-2xl text-blue-600">✓</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Submit Button */}
      {selectedOption !== null && (
        <div className="mt-4 flex items-center justify-between">
          <p className="text-xs text-gray-500">
            {requestData.governance.audit_log_required && '📋 This decision will be logged for audit purposes.'}
            {requestData.governance.requires_signature && ' ✍️ Your signature will be required.'}
          </p>

          <button
            onClick={() => selectedOption !== null && handleResponse(selectedOption)}
            disabled={expired || responding || selectedOption === null}
            className={`px-6 py-2 rounded-lg font-medium text-white transition-colors ${
              expired || responding
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {responding ? 'Responding...' : expired ? 'Expired' : 'Submit Response'}
          </button>
        </div>
      )}

      {/* Revocation Notice */}
      {requestData.governance.revocable && (
        <p className="mt-4 text-xs text-gray-500 text-center">
          You can revoke this decision at any time before the operation completes.
        </p>
      )}
    </div>
  );
};

export default AgentRequestPrompt;
