/**
 * ViewOrchestrator Component
 *
 * Manages multi-view layout (browser, terminal, canvas) with agent guidance.
 * Coordinates view switching and provides contextual guidance for each view.
 */

import React, { useState, useEffect } from 'react';
import useWebSocket from '@/hooks/useWebSocket';

export interface View {
  view_id: string;
  view_type: 'canvas' | 'browser' | 'terminal' | 'app';
  title: string;
  status: 'active' | 'background' | 'closed';
  position: { x: number; y: number };
  size: { width: string; height: string };
  url?: string;
  command?: string;
}

export interface CanvasGuidance {
  agent_id: string;
  message: string;
  what_youre_seeing: string;
  controls: Array<{
    label: string;
    action: string;
  }>;
}

export interface ViewOrchestrationData {
  layout: 'split_horizontal' | 'split_vertical' | 'grid' | 'tabs';
  active_views: View[];
  canvas_guidance?: CanvasGuidance;
  current_view: string;
}

export interface ViewOrchestratorProps {
  userId: string;
  sessionId?: string;
  onViewTakeover?: (viewId: string) => void;
  className?: string;
}

/**
 * ViewOrchestrator - Manages multi-view layout with agent coordination
 */
export const ViewOrchestrator: React.FC<ViewOrchestratorProps> = ({
  userId,
  sessionId,
  onViewTakeover,
  className = ''
}) => {
  const [orchestration, setOrchestration] = useState<ViewOrchestrationData | null>(null);
  const [activeTab, setActiveTab] = useState<string>('');
  const [canvasExpanded, setCanvasExpanded] = useState(true);
  const { socket, connected } = useWebSocket();

  useEffect(() => {
    if (!socket || !connected) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);

        // Handle view switch
        if (message.type === 'view:switch') {
          const data = message.data;

          setOrchestration((prev) => ({
            layout: data.layout || prev?.layout || 'split_vertical',
            active_views: data.views || prev?.active_views || [],
            canvas_guidance: data.canvas_guidance,
            current_view: data.view_id
          }));

          // Set first view as active if tabs
          if (data.layout === 'tabs' && data.views && data.views.length > 0) {
            setActiveTab(data.views[0].view_id);
          }
        }

        // Handle view activation
        if (message.type === 'view:activated') {
          const view = message.data.view;

          setOrchestration((prev) => {
            const activeViews = prev?.active_views || [];
            const existingIndex = activeViews.findIndex(v => v.view_id === view.view_id);

            if (existingIndex >= 0) {
              activeViews[existingIndex] = view;
            } else {
              activeViews.push(view);
            }

            return {
              ...prev!,
              active_views: activeViews
            };
          });
        }

        // Handle view close
        if (message.type === 'view:closed') {
          const viewId = message.data.view_id;

          setOrchestration((prev) => ({
            ...prev!,
            active_views: prev?.active_views.filter(v => v.view_id !== viewId) || []
          }));
        }

        // Handle guidance update
        if (message.type === 'view:guidance_update') {
          setOrchestration((prev) => ({
            ...prev!,
            canvas_guidance: message.data.guidance
          }));
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

  const handleTakeControl = (viewId: string) => {
    if (onViewTakeover) {
      onViewTakeover(viewId);
    }

    // Send takeover signal via WebSocket
    if (socket && connected) {
      socket.send(JSON.stringify({
        type: 'view:takeover',
        data: {
          view_id: viewId,
          user_controlled: true
        }
      }));
    }
  };

  const handleControlAction = (action: string) => {
    if (socket && connected) {
      socket.send(JSON.stringify({
        type: 'view:control_action',
        data: {
          action: action
        }
      }));
    }
  };

  const getViewIcon = (viewType: string) => {
    switch (viewType) {
      case 'canvas':
        return '🎨';
      case 'browser':
        return '🌐';
      case 'terminal':
        return '⌨️';
      case 'app':
        return '📱';
      default:
        return '📄';
    }
  };

  const getLayoutClasses = () => {
    switch (orchestration?.layout) {
      case 'split_horizontal':
        return 'flex-row space-x-4';
      case 'split_vertical':
        return 'flex-col space-y-4';
      case 'grid':
        return 'grid grid-cols-2 gap-4';
      case 'tabs':
        return 'flex-col';
      default:
        return 'flex-row space-x-4';
    }
  };

  if (!orchestration || orchestration.active_views.length === 0) {
    return (
      <div className={`view-orchestrator bg-gray-50 rounded-lg p-8 ${className}`}>
        <div className="text-center text-gray-500">
          <p className="text-lg mb-2">No active views</p>
          <p className="text-sm">Views will appear here when the agent activates them.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`view-orchestrator bg-gray-100 rounded-lg overflow-hidden ${className}`}>
      {/* Canvas Guidance Panel */}
      {orchestration.canvas_guidance && canvasExpanded && (
        <div className="bg-white border-b p-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center space-x-2">
              <span className="text-xl">🤖</span>
              <div>
                <h4 className="text-sm font-semibold text-gray-900">Agent Guidance</h4>
                <p className="text-xs text-gray-500">
                  Agent ID: {orchestration.canvas_guidance.agent_id}
                </p>
              </div>
            </div>
            <button
              onClick={() => setCanvasExpanded(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              ▼
            </button>
          </div>

          <div className="bg-blue-50 rounded p-3 mb-3">
            <p className="text-sm text-blue-900">{orchestration.canvas_guidance.message}</p>
          </div>

          <div className="bg-gray-50 rounded p-3">
            <p className="text-xs font-medium text-gray-700 mb-1">What you're seeing:</p>
            <p className="text-sm text-gray-900">{orchestration.canvas_guidance.what_youre_seeing}</p>
          </div>

          {/* Control Buttons */}
          {orchestration.canvas_guidance.controls.length > 0 && (
            <div className="mt-3 flex space-x-2">
              {orchestration.canvas_guidance.controls.map((control, index) => (
                <button
                  key={index}
                  onClick={() => handleControlAction(control.action)}
                  className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                >
                  {control.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Collapse button when panel is hidden */}
      {orchestration.canvas_guidance && !canvasExpanded && (
        <button
          onClick={() => setCanvasExpanded(true)}
          className="w-full bg-white border-b p-2 text-center text-sm text-gray-600 hover:bg-gray-50"
        >
          ▶ Show Agent Guidance
        </button>
      )}

      {/* Layout Header (Tabs mode) */}
      {orchestration.layout === 'tabs' && (
        <div className="bg-white border-b flex">
          {orchestration.active_views.map((view) => (
            <button
              key={view.view_id}
              onClick={() => setActiveTab(view.view_id)}
              className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
                activeTab === view.view_id
                  ? 'bg-blue-50 text-blue-700 border-b-2 border-blue-600'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <span className="mr-2">{getViewIcon(view.view_type)}</span>
              {view.title}
            </button>
          ))}
        </div>
      )}

      {/* Views Container */}
      <div className={`p-4 flex ${getLayoutClasses()}`}>
        {orchestration.active_views.map((view) => {
          const isActive = orchestration.layout === 'tabs' ? activeTab === view.view_id : view.status === 'active';

          return (
            <div
              key={view.view_id}
              className={`${orchestration.layout === 'tabs' && !isActive ? 'hidden' : ''} ${
                orchestration.layout === 'split_horizontal' ? 'flex-1' :
                orchestration.layout === 'split_vertical' ? 'w-full' :
                orchestration.layout === 'grid' ? '' :
                'w-full'
              }`}
            >
              <ViewPanel
                view={view}
                isActive={isActive}
                onTakeControl={() => handleTakeControl(view.view_id)}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};

interface ViewPanelProps {
  view: View;
  isActive: boolean;
  onTakeControl: () => void;
}

const ViewPanel: React.FC<ViewPanelProps> = ({ view, isActive, onTakeControl }) => {
  const [takingControl, setTakingControl] = useState(false);

  const handleTakeControl = () => {
    setTakingControl(true);
    onTakeControl();
  };

  return (
    <div className={`bg-white rounded-lg shadow overflow-hidden ${isActive ? 'ring-2 ring-blue-500' : ''}`}>
      {/* View Header */}
      <div className="bg-gray-50 border-b px-4 py-2 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-lg">{getViewIcon(view.view_type)}</span>
          <span className="text-sm font-medium text-gray-900">{view.title}</span>
        </div>

        <div className="flex items-center space-x-2">
          <span className={`px-2 py-1 rounded text-xs font-medium ${
            view.status === 'active' ? 'bg-green-100 text-green-800' :
            view.status === 'background' ? 'bg-yellow-100 text-yellow-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {view.status}
          </span>

          {!takingControl && (
            <button
              onClick={handleTakeControl}
              className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors"
            >
              Take Control
            </button>
          )}

          {takingControl && (
            <span className="text-xs text-green-600">✓ You're in control</span>
          )}
        </div>
      </div>

      {/* View Content */}
      <div className="bg-white" style={{ height: '400px' }}>
        {view.view_type === 'browser' && view.url && (
          <iframe
            src={view.url}
            className="w-full h-full"
            title={view.title}
            sandbox="allow-same-origin allow-scripts allow-forms"
          />
        )}

        {view.view_type === 'terminal' && view.command && (
          <div className="p-4 bg-gray-900 text-gray-100 font-mono text-sm h-full overflow-auto">
            <p className="text-green-400">$ {view.command}</p>
            <p className="text-gray-400">Executing...</p>
          </div>
        )}

        {view.view_type === 'canvas' && (
          <div className="p-4">
            <p className="text-sm text-gray-600">Canvas view content would appear here.</p>
          </div>
        )}

        {view.view_type === 'app' && (
          <div className="p-4">
            <p className="text-sm text-gray-600">App view content would appear here.</p>
          </div>
        )}
      </div>
    </div>
  );
};

function getViewIcon(viewType: string): string {
  switch (viewType) {
    case 'canvas':
      return '🎨';
    case 'browser':
      return '🌐';
    case 'terminal':
      return '⌨️';
    case 'app':
      return '📱';
    default:
      return '📄';
  }
}

export default ViewOrchestrator;
