/**
 * IntegrationConnectionGuide Component
 *
 * Guides users through integration setup (OAuth flows) with real-time
 * agent feedback and contextual explanations.
 */

import React, { useState, useEffect } from 'react';
import useWebSocket from '@/hooks/useWebSocket';

export interface Permission {
  scope: string;
  why_needed: string;
  risk_level: 'low' | 'medium' | 'high';
}

export interface ConnectionStatus {
  state: string;
  error?: string;
  retry_available: boolean;
}

export interface BrowserSession {
  session_id: string;
  url: string;
  user_can_see: boolean;
}

export interface IntegrationGuideData {
  integration_id: string;
  integration_name: string;
  stage: 'initiating' | 'authorizing' | 'callback' | 'verifying' | 'complete';
  agent_guidance: {
    current_step_title: string;
    explanation: string;
    why_needed: string;
    whats_next: string;
  };
  permissions: Permission[];
  connection_status: ConnectionStatus;
  browser_session?: BrowserSession;
}

export interface IntegrationConnectionGuideProps {
  integrationId?: string;
  userId: string;
  onComplete?: (integrationId: string) => void;
  onError?: (error: string) => void;
  className?: string;
}

/**
 * IntegrationConnectionGuide - Guides users through OAuth/integration setup
 */
export const IntegrationConnectionGuide: React.FC<IntegrationConnectionGuideProps> = ({
  integrationId,
  userId,
  onComplete,
  onError,
  className = ''
}) => {
  const [guideData, setGuideData] = useState<IntegrationGuideData | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [expandedPermission, setExpandedPermission] = useState<number | null>(null);
  const { socket, connected } = useWebSocket();

  const steps = [
    { key: 'initiating', label: 'Initiating', icon: '🚀' },
    { key: 'authorizing', label: 'Authorizing', icon: '🔐' },
    { key: 'callback', label: 'Callback', icon: '📞' },
    { key: 'verifying', label: 'Verifying', icon: '✅' },
    { key: 'complete', label: 'Complete', icon: '🎉' }
  ];

  useEffect(() => {
    if (!socket || !connected) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'canvas:update' && message.data?.component === 'integration_connection_guide') {
          const data = message.data.data;

          // Filter by integrationId if specified
          if (!integrationId || data.integration_id === integrationId) {
            setGuideData(data);

            // Update step index
            const stepIndex = steps.findIndex(s => s.key === data.stage);
            if (stepIndex >= 0) {
              setCurrentStepIndex(stepIndex);
            }
          }
        }

        // Handle updates
        if (message.type === 'canvas:update' && message.data?.action === 'update') {
          setGuideData((prev) => {
            if (!prev) return null;

            const updatedData = { ...prev, ...message.data.updates };
            const stepIndex = steps.findIndex(s => s.key === updatedData.stage);
            if (stepIndex >= 0) {
              setCurrentStepIndex(stepIndex);
            }

            return updatedData;
          });
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    socket.addEventListener('message', handleMessage);

    return () => {
      socket.removeEventListener('message', handleMessage);
    };
  }, [socket, connected, integrationId]);

  // Handle completion
  useEffect(() => {
    if (guideData?.stage === 'complete' && onComplete) {
      onComplete(guideData.integration_id);
    }
  }, [guideData, onComplete]);

  // Handle errors
  useEffect(() => {
    if (guideData?.connection_status.error && onError) {
      onError(guideData.connection_status.error);
    }
  }, [guideData?.connection_status.error, onError]);

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'low':
        return 'bg-green-100 text-green-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'high':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStageStatus = (stageKey: string) => {
    if (!guideData) return 'pending';
    const currentIndex = steps.findIndex(s => s.key === guideData.stage);
    const stepIndex = steps.findIndex(s => s.key === stageKey);

    if (stepIndex < currentIndex) return 'completed';
    if (stepIndex === currentIndex) return 'active';
    return 'pending';
  };

  if (!guideData) {
    return (
      <div className={`integration-connection-guide bg-white rounded-lg shadow-md p-6 ${className}`}>
        <div className="animate-pulse flex items-center space-x-3">
          <div className="w-4 h-4 bg-gray-300 rounded-full"></div>
          <div className="h-4 bg-gray-300 rounded w-48"></div>
        </div>
      </div>
    );
  }

  return (
    <div className={`integration-connection-guide bg-white rounded-lg shadow-md overflow-hidden ${className}`}>
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-4">
        <div className="flex items-center space-x-3">
          <span className="text-3xl">🔗</span>
          <div className="text-white">
            <h3 className="text-lg font-semibold">Connect {guideData.integration_name}</h3>
            <p className="text-sm text-blue-100">Agent-guided integration setup</p>
          </div>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="px-6 py-4 border-b">
        <div className="flex items-center justify-between">
          {steps.map((step, index) => {
            const status = getStageStatus(step.key);
            const isCompleted = status === 'completed';
            const isActive = status === 'active';

            return (
              <React.Fragment key={step.key}>
                <div className="flex flex-col items-center">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg transition-colors ${
                    isCompleted ? 'bg-green-500 text-white' :
                    isActive ? 'bg-blue-600 text-white' :
                    'bg-gray-200 text-gray-500'
                  }`}>
                    {isCompleted ? '✓' : step.icon}
                  </div>
                  <p className={`text-xs mt-1 font-medium ${
                    isCompleted ? 'text-green-600' :
                    isActive ? 'text-blue-600' :
                    'text-gray-500'
                  }`}>
                    {step.label}
                  </p>
                </div>

                {index < steps.length - 1 && (
                  <div className={`flex-1 h-1 mx-2 rounded ${
                    index < currentStepIndex ? 'bg-green-500' : 'bg-gray-200'
                  }`} />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Agent Guidance */}
      <div className="px-6 py-4 bg-blue-50">
        <div className="flex items-start space-x-3">
          <span className="text-2xl">🤖</span>
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-blue-900 mb-1">
              {guideData.agent_guidance.current_step_title}
            </h4>
            <p className="text-sm text-blue-800 mb-3">{guideData.agent_guidance.explanation}</p>

            <div className="bg-blue-100 rounded p-3">
              <div className="mb-2">
                <p className="text-xs font-medium text-blue-900">Why this is needed:</p>
                <p className="text-sm text-blue-800">{guideData.agent_guidance.why_needed}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-blue-900">What's next:</p>
                <p className="text-sm text-blue-800">{guideData.agent_guidance.whats_next}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Permissions */}
      {guideData.permissions.length > 0 && (
        <div className="px-6 py-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">
            🔑 Permissions Requested
          </h4>

          <div className="space-y-2">
            {guideData.permissions.map((permission, index) => (
              <div key={index} className="border rounded-lg overflow-hidden">
                <button
                  onClick={() => setExpandedPermission(expandedPermission === index ? null : index)}
                  className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center space-x-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getRiskColor(permission.risk_level)}`}>
                      {permission.risk_level.toUpperCase()}
                    </span>
                    <span className="font-medium text-gray-900">{permission.scope}</span>
                  </div>
                  <span>{expandedPermission === index ? '▼' : '▶'}</span>
                </button>

                {expandedPermission === index && (
                  <div className="p-3 bg-gray-50 border-t">
                    <p className="text-sm text-gray-700">{permission.why_needed}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Browser Session Preview */}
      {guideData.browser_session && guideData.stage === 'authorizing' && (
        <div className="px-6 py-4">
          <div className="border rounded-lg overflow-hidden">
            <div className="bg-gray-50 px-4 py-2 border-b flex items-center justify-between">
              <span className="text-sm font-medium text-gray-900">Browser Session</span>
              <span className="text-xs text-gray-500">
                {guideData.browser_session.user_can_see ? '👁️ You can see' : '🔒 Agent controlled'}
              </span>
            </div>
            <div className="p-4">
              <p className="text-sm text-gray-700 mb-2">
                I've opened {guideData.integration_name}'s authorization page.
              </p>
              <a
                href={guideData.browser_session.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
              >
                Open Authorization Page
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Connection Status */}
      <div className="px-6 py-4 bg-gray-50">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-gray-700 uppercase tracking-wide">
              Connection Status
            </p>
            <p className={`text-sm font-medium ${
              guideData.connection_status.state === 'error' ? 'text-red-600' :
              guideData.stage === 'complete' ? 'text-green-600' :
              'text-gray-900'
            }`}>
              {guideData.connection_status.state === 'error'
                ? guideData.connection_status.error
                : guideData.connection_status.state}
            </p>
          </div>

          {guideData.connection_status.retry_available && (
            <button
              onClick={() => {
                // Send retry signal
                if (socket && connected) {
                  socket.send(JSON.stringify({
                    type: 'integration:retry',
                    data: {
                      integration_id: guideData.integration_id
                    }
                  }));
                }
              }}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
            >
              Retry Connection
            </button>
          )}
        </div>
      </div>

      {/* Completion Message */}
      {guideData.stage === 'complete' && (
        <div className="px-6 py-4 bg-green-50">
          <div className="flex items-center space-x-3">
            <span className="text-3xl">🎉</span>
            <div>
              <h4 className="text-sm font-semibold text-green-900">Integration Complete!</h4>
              <p className="text-sm text-green-800">
                {guideData.integration_name} has been successfully connected.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IntegrationConnectionGuide;
