/**
 * Live Monitoring Panel
 *
 * Main monitoring panel for real-time agent execution supervision.
 * Displays execution progress, logs, supervisor info, and intervention controls.
 */

import React, { useState, useEffect, useCallback } from 'react';
import LogStreamViewer from './LogStreamViewer';
import ExecutionProgressBar from './ExecutionProgressBar';
import SupervisorIdentity from './SupervisorIdentity';
import OutputPreview from './OutputPreview';

interface Props {
  executionId: string;
  agentId: string;
  agentName: string;
  supervisorType: 'user' | 'autonomous_agent';
  supervisorId: string;
  supervisorName?: string;
  onComplete?: (result: any) => void;
}

interface ExecutionStep {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  startedAt?: string;
  completedAt?: string;
}

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error';
  message: string;
  data?: any;
}

interface State {
  isExecuting: boolean;
  currentStep: number;
  logs: LogEntry[];
  output: any;
  canIntervene: boolean;
}

const LiveMonitoringPanel: React.FC<Props> = ({
  executionId,
  agentId,
  agentName,
  supervisorType,
  supervisorId,
  supervisorName,
  onComplete
}) => {
  const [state, setState] = useState<State>({
    isExecuting: true,
    currentStep: 0,
    logs: [],
    output: null,
    canIntervene: supervisorType === 'user'
  });

  const [steps, setSteps] = useState<ExecutionStep[]>([
    { id: '1', name: 'Initialize execution', status: 'pending' },
    { id: '2', name: 'Load context', status: 'pending' },
    { id: '3', name: 'Execute agent logic', status: 'pending' },
    { id: '4', name: 'Generate output', status: 'pending' },
    { id: '5', name: 'Finalize', status: 'pending' }
  ]);

  const [error, setError] = useState<string | null>(null);
  const [interventionType, setInterventionType] = useState<string>('pause');
  const [guidance, setGuidance] = useState<string>('');

  // Connect to SSE stream
  useEffect(() => {
    const eventSource = new EventSource(
      `/api/supervision/${executionId}/stream`
    );

    eventSource.addEventListener('connected', (event: MessageEvent) => {
      const data = JSON.parse(event.data);
      addLog({
        timestamp: data.timestamp,
        level: 'info',
        message: `Connected to execution ${executionId}`,
        data
      });
    });

    eventSource.addEventListener('supervision_event', (event: MessageEvent) => {
      const eventData = JSON.parse(event.data);

      // Add log entry
      addLog({
        timestamp: eventData.timestamp,
        level: 'info',
        message: `${eventData.event_type}: ${JSON.stringify(eventData.data)}`,
        data: eventData.data
      });

      // Update steps based on event type
      updateStepsFromEvent(eventData);
    });

    eventSource.addEventListener('done', (event: MessageEvent) => {
      setState(prev => ({ ...prev, isExecuting: false }));
      eventSource.close();

      if (onComplete) {
        onComplete({ executionId, success: true });
      }
    });

    eventSource.addEventListener('error', (event: MessageEvent) => {
      const data = JSON.parse(event.data);
      setError(data.message);
      setState(prev => ({ ...prev, isExecuting: false }));
      eventSource.close();
    });

    eventSource.onerror = (err) => {
      console.error('SSE error:', err);
      setError('Connection error');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [executionId, onComplete]);

  const addLog = useCallback((log: LogEntry) => {
    setState(prev => ({
      ...prev,
      logs: [...prev.logs, log]
    }));
  }, []);

  const updateStepsFromEvent = useCallback((eventData: any) => {
    if (eventData.event_type === 'action') {
      const stepIndex = steps.findIndex(s => s.status === 'pending' || s.status === 'in_progress');
      if (stepIndex >= 0) {
        setSteps(prev => {
          const updated = [...prev];
          updated[stepIndex] = {
            ...updated[stepIndex],
            status: 'in_progress',
            startedAt: eventData.timestamp
          };
          return updated;
        });
        setState(prev => ({ ...prev, currentStep: stepIndex }));
      }
    } else if (eventData.event_type === 'result') {
      // Mark current step as completed
      setSteps(prev => {
        const updated = [...prev];
        const currentIdx = updated.findIndex(s => s.status === 'in_progress');
        if (currentIdx >= 0) {
          updated[currentIdx] = {
            ...updated[currentIdx],
            status: 'completed',
            completedAt: eventData.timestamp
          };
        }
        return updated;
      });

      // Store output if available
      if (eventData.data?.output) {
        setState(prev => ({ ...prev, output: eventData.data.output }));
      }
    } else if (eventData.event_type === 'error') {
      // Mark current step as failed
      setSteps(prev => {
        const updated = [...prev];
        const currentIdx = updated.findIndex(s => s.status === 'in_progress');
        if (currentIdx >= 0) {
          updated[currentIdx] = {
            ...updated[currentIdx],
            status: 'failed',
            completedAt: eventData.timestamp
          };
        }
        return updated;
      });

      addLog({
        timestamp: eventData.timestamp,
        level: 'error',
        message: eventData.data.error_message || 'Unknown error',
        data: eventData.data
      });
    }
  }, [steps, addLog]);

  const handleIntervene = async () => {
    if (!guidance.trim()) {
      setError('Please provide guidance for the intervention');
      return;
    }

    try {
      // Find the active supervision session
      const sessionsResponse = await fetch('/api/supervision/sessions/active');
      const sessions = await sessionsResponse.json();
      const session = sessions.find((s: any) => s.agent_id === agentId);

      if (!session) {
        setError('No active supervision session found');
        return;
      }

      const response = await fetch(
        `/api/supervision/sessions/${session.session_id}/intervene`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            intervention_type: interventionType,
            guidance
          })
        }
      );

      if (!response.ok) {
        throw new Error('Failed to intervene');
      }

      const result = await response.json();

      addLog({
        timestamp: new Date().toISOString(),
        level: 'info',
        message: `Intervention: ${interventionType} - ${result.message}`
      });

      setGuidance('');

      if (interventionType === 'terminate') {
        setState(prev => ({ ...prev, isExecuting: false, canIntervene: false }));
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="live-monitoring-panel">
      <div className="panel-header">
        <h3>Live Monitoring: {agentName}</h3>
        <SupervisorIdentity
          supervisorType={supervisorType}
          supervisorId={supervisorId}
          supervisorName={supervisorName}
        />
      </div>

      <ExecutionProgressBar
        steps={steps}
        currentStep={state.currentStep}
      />

      <div className="monitoring-content">
        <LogStreamViewer
          executionId={executionId}
          logs={state.logs}
          autoScroll={true}
        />

        {state.output && (
          <OutputPreview
            executionId={executionId}
            output={state.output}
            outputType="json"
          />
        )}
      </div>

      {state.canIntervene && state.isExecuting && (
        <div className="intervention-controls">
          <h4>Intervention Controls</h4>
          <select
            value={interventionType}
            onChange={(e) => setInterventionType(e.target.value)}
          >
            <option value="pause">Pause</option>
            <option value="correct">Correct</option>
            <option value="terminate">Terminate</option>
          </select>

          <input
            type="text"
            placeholder="Provide guidance..."
            value={guidance}
            onChange={(e) => setGuidance(e.target.value)}
          />

          <button onClick={handleIntervene}>
            {interventionType === 'terminate' ? 'Terminate Execution' : 'Submit Intervention'}
          </button>
        </div>
      )}

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {!state.isExecuting && (
        <div className="execution-complete">
          Execution {state.output ? 'completed' : 'terminated'}
        </div>
      )}
    </div>
  );
};

export default LiveMonitoringPanel;
