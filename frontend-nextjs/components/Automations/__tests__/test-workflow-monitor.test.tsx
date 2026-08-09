/**
 * WorkflowMonitor Component Tests
 *
 * Tests verify the REAL WorkflowMonitor component
 * (components/Automations/WorkflowMonitor.tsx):
 *
 * - Empty state + initial executions rendering (all 4 statuses, error text)
 * - WebSocket lifecycle: connect success/failure, subscribe with workflowId
 * - Live event handling: workflow.started/progress/completed/failed/paused/resumed
 * - Non-started events for unknown executions are ignored
 * - Resume action (success + failure)
 *
 * lib/websocket-client is mocked with a controllable client exposing an
 * `emit` helper so tests can drive the registered message handlers.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import WorkflowMonitor from '../WorkflowMonitor';

jest.mock('sonner', () => {
  const api: any = {
    success: jest.fn(),
    error: jest.fn(),
    warning: jest.fn(),
  };
  return { toast: api, __testApi: api };
});

jest.mock('@/lib/websocket-client', () => {
  const api: any = { instances: [], createClient: null };

  const createClient = () => {
    const listeners: Record<string, Function[]> = {};
    const client: any = {
      connect: jest.fn(() =>
        api.connectError
          ? Promise.reject(api.connectError)
          : Promise.resolve()
      ),
      subscribe: jest.fn(),
      disconnect: jest.fn(),
      on: jest.fn((event: string, cb: Function) => {
        if (!listeners[event]) listeners[event] = [];
        listeners[event].push(cb);
        return jest.fn();
      }),
      emit: (event: string, message: any) => {
        (listeners[event] || []).forEach((cb: Function) => cb(message));
      },
    };
    api.instances.push(client);
    return client;
  };
  api.createClient = createClient;

  return {
    __esModule: true,
    getWebSocketClient: jest.fn(createClient),
    WebSocketClient: class {},
    __testApi: api,
  };
});

const wsApi = () => (jest.requireMock('@/lib/websocket-client') as any).__testApi;
const lastClient = () => wsApi().instances[wsApi().instances.length - 1];
const sonnerApi = () => (jest.requireMock('sonner') as any).__testApi;

const jsonResponse = (body: any, ok = true) => ({
  ok,
  status: ok ? 200 : 500,
  json: async () => body,
});

const startedMsg = (executionId: string, workflowId = 'wf-1') => ({
  type: 'workflow.started',
  timestamp: '2026-08-09T10:00:00Z',
  execution_id: executionId,
  data: { workflow_id: workflowId },
});

describe('WorkflowMonitor', () => {
  let fetchSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    // resetMocks wipes factory implementations before each test; re-install
    (jest.requireMock('@/lib/websocket-client') as any).getWebSocketClient.mockImplementation(
      wsApi().createClient
    );
    wsApi().instances.length = 0;
    wsApi().connectError = null;
    sonnerApi().success.mockClear();
    sonnerApi().error.mockClear();
    sonnerApi().warning.mockClear();
    fetchSpy = jest
      .spyOn(global as any, 'fetch')
      .mockResolvedValue(jsonResponse({}));
  });

  it('shows the empty state with a Disconnected badge before WS connects', () => {
    render(<WorkflowMonitor />);
    expect(screen.getByText('No active executions')).toBeInTheDocument();
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
  });

  it('renders initial executions with statuses, icons and errors', () => {
    render(
      <WorkflowMonitor
        initialExecutions={[
          {
            execution_id: 'exec-running',
            workflow_id: 'wf-1',
            status: 'running',
            started_at: '2026-08-09T10:00:00Z',
            steps_executed: 3,
            current_step: 'Send Slack',
          },
          {
            execution_id: 'exec-done',
            workflow_id: 'wf-2',
            status: 'completed',
            started_at: '2026-08-09T09:00:00Z',
            completed_at: '2026-08-09T09:00:05Z',
            steps_executed: 5,
          },
          {
            execution_id: 'exec-failed',
            workflow_id: 'wf-3',
            status: 'failed',
            started_at: '2026-08-09T08:00:00Z',
            steps_executed: 1,
            error: 'API timeout',
          },
          {
            execution_id: 'exec-paused',
            workflow_id: 'wf-4',
            status: 'paused',
            started_at: '2026-08-09T07:00:00Z',
            steps_executed: 2,
          },
        ]}
      />
    );

    // workflow_id is rendered in full; execution_id only as an 8-char slice
    expect(screen.getByText('wf-1')).toBeInTheDocument();
    expect(screen.getByText('wf-2')).toBeInTheDocument();
    expect(screen.getByText('wf-3')).toBeInTheDocument();
    expect(screen.getByText('wf-4')).toBeInTheDocument();
    expect(screen.getByText(/ID: exec-run/)).toBeInTheDocument();
    expect(screen.getByText(/ID: exec-don/)).toBeInTheDocument();
    expect(screen.getByText(/ID: exec-fai/)).toBeInTheDocument();
    expect(screen.getByText(/ID: exec-pau/)).toBeInTheDocument();
    // error text rendered for the failed execution
    expect(screen.getByText('API timeout')).toBeInTheDocument();
    // status badges (4 executions + Connected header badge)
    expect(screen.getAllByText('completed')).toHaveLength(1);
    expect(screen.getAllByText('failed')).toHaveLength(1);
    expect(screen.getAllByText('paused')).toHaveLength(1);
    expect(screen.getAllByText('running')).toHaveLength(1);
    // paused executions expose a Resume button
    expect(screen.getByRole('button', { name: /resume/i })).toBeInTheDocument();
  });

  it('connects, subscribes to the workflow channel and shows Connected', async () => {
    render(<WorkflowMonitor workflowId="wf-42" />);

    await waitFor(() => {
      expect(lastClient().connect).toHaveBeenCalled();
    });
    expect(lastClient().subscribe).toHaveBeenCalledWith('workflow:wf-42');
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  it('connects without subscribing when no workflowId is provided', async () => {
    render(<WorkflowMonitor />);
    await waitFor(() => {
      expect(lastClient().connect).toHaveBeenCalled();
    });
    expect(lastClient().subscribe).not.toHaveBeenCalled();
  });

  it('shows an error toast when the WebSocket connection fails', async () => {
    wsApi().connectError = new Error('ws down');
    render(<WorkflowMonitor workflowId="wf-1" />);

    await waitFor(() => {
      expect(sonnerApi().error).toHaveBeenCalledWith(
        'Failed to connect to real-time updates'
      );
    });
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
  });

  it('adds a new execution on workflow.started', async () => {
    render(<WorkflowMonitor />);
    await waitFor(() => expect(lastClient().connect).toHaveBeenCalled());

    actEmit('workflow.started', startedMsg('exec-1', 'wf-9'));

    expect(screen.getByText(/ID: exec-1/)).toBeInTheDocument();
    expect(screen.getByText('wf-9')).toBeInTheDocument();
    expect(screen.getByText(/Steps: 0/)).toBeInTheDocument();
    expect(screen.getByText('running')).toBeInTheDocument();
  });

  it('updates steps and current step on workflow.progress', async () => {
    render(<WorkflowMonitor initialExecutions={[execFixture('exec-1', 'running')]} />);
    await waitFor(() => expect(lastClient().connect).toHaveBeenCalled());

    actEmit('workflow.progress', {
      type: 'workflow.progress',
      timestamp: '2026-08-09T10:01:00Z',
      execution_id: 'exec-1',
      data: { steps_executed: 4, current_step: 'Send Email' },
    });

    expect(screen.getByText(/Steps: 4/)).toBeInTheDocument();
  });

  it('marks an execution completed on workflow.completed', async () => {
    render(<WorkflowMonitor initialExecutions={[execFixture('exec-1', 'running')]} />);
    await waitFor(() => expect(lastClient().connect).toHaveBeenCalled());

    actEmit('workflow.completed', {
      type: 'workflow.completed',
      timestamp: '2026-08-09T10:02:00Z',
      execution_id: 'exec-1',
      data: { steps_executed: 6 },
    });

    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.queryByText('running')).not.toBeInTheDocument();
  });

  it('marks an execution failed with the error from the event', async () => {
    render(<WorkflowMonitor initialExecutions={[execFixture('exec-1', 'running')]} />);
    await waitFor(() => expect(lastClient().connect).toHaveBeenCalled());

    actEmit('workflow.failed', {
      type: 'workflow.failed',
      timestamp: '2026-08-09T10:03:00Z',
      execution_id: 'exec-1',
      data: { error: 'Provider rate limited' },
    });

    expect(screen.getByText('failed')).toBeInTheDocument();
    expect(screen.getByText('Provider rate limited')).toBeInTheDocument();
  });

  it('pauses an execution, warns via toast and resumes on button click', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ ok: true }));
    render(<WorkflowMonitor initialExecutions={[execFixture('exec-1', 'running')]} />);
    await waitFor(() => expect(lastClient().connect).toHaveBeenCalled());

    actEmit('workflow.paused', {
      type: 'workflow.paused',
      timestamp: '2026-08-09T10:04:00Z',
      execution_id: 'exec-1',
      data: { current_step: 'Wait for approval', reason: 'Needs human input' },
    });

    expect(screen.getByText('paused')).toBeInTheDocument();
    expect(sonnerApi().warning).toHaveBeenCalledWith(
      'Workflow execution paused: Needs human input'
    );
    expect(screen.getByRole('button', { name: /resume/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /resume/i }));
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/workflows/exec-1/resume',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ action: 'resume' }),
        })
      );
    });
    expect(sonnerApi().success).toHaveBeenCalledWith('Workflow resumed successfully');
  });

  it('falls back to the default reason and toasts resume failure', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, false));
    render(<WorkflowMonitor initialExecutions={[execFixture('exec-1', 'paused')]} />);
    await waitFor(() => expect(lastClient().connect).toHaveBeenCalled());

    actEmit('workflow.paused', {
      type: 'workflow.paused',
      timestamp: '2026-08-09T10:04:00Z',
      execution_id: 'exec-1',
      data: {},
    });
    expect(sonnerApi().warning).toHaveBeenCalledWith(
      'Workflow execution paused: Waiting for input'
    );

    fireEvent.click(screen.getByRole('button', { name: /resume/i }));
    await waitFor(() => {
      expect(sonnerApi().error).toHaveBeenCalledWith('Failed to resume workflow');
    });
  });

  it('resumes an execution after a thrown fetch error', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('net'));
    render(<WorkflowMonitor initialExecutions={[execFixture('exec-1', 'paused')]} />);
    await waitFor(() => expect(lastClient().connect).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /resume/i }));
    await waitFor(() => {
      expect(sonnerApi().error).toHaveBeenCalledWith('Failed to resume workflow');
    });
  });

  it('sets an execution back to running on workflow.resumed', async () => {
    render(<WorkflowMonitor initialExecutions={[execFixture('exec-1', 'paused')]} />);
    await waitFor(() => expect(lastClient().connect).toHaveBeenCalled());

    actEmit('workflow.resumed', {
      type: 'workflow.resumed',
      timestamp: '2026-08-09T10:05:00Z',
      execution_id: 'exec-1',
      data: {},
    });

    expect(screen.getByText('running')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /resume/i })).not.toBeInTheDocument();
  });

  it('ignores events for unknown executions unless they are workflow.started', async () => {
    render(<WorkflowMonitor />);
    await waitFor(() => expect(lastClient().connect).toHaveBeenCalled());

    // non-started event for an unknown execution must not add anything
    actEmit('workflow.completed', {
      type: 'workflow.completed',
      timestamp: '2026-08-09T10:06:00Z',
      execution_id: 'ghost-exec',
      data: { steps_executed: 2 },
    });
    expect(screen.queryByText('ID: ghost-ex')).not.toBeInTheDocument();

    // non-workflow message types are ignored by the event handler
    actEmit('system.alert', {
      type: 'system.alert',
      timestamp: '2026-08-09T10:07:00Z',
      execution_id: 'ghost-exec',
      data: {},
    });
    expect(screen.queryByText('ID: ghost-ex')).not.toBeInTheDocument();
  });

  it('unsubscribes and disconnects on unmount', async () => {
    const { unmount } = render(<WorkflowMonitor workflowId="wf-1" />);
    await waitFor(() => expect(lastClient().connect).toHaveBeenCalled());

    const client = lastClient();
    unmount();
    expect(client.disconnect).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const execFixture = (executionId: string, status: string) => ({
  execution_id: executionId,
  workflow_id: 'wf-1',
  status: status as any,
  started_at: '2026-08-09T10:00:00Z',
  steps_executed: 0,
});

const actEmit = (event: string, message: any) => {
  const ReactAct = (jest.requireActual('react') as any).act;
  ReactAct(() => {
    lastClient().emit(event, message);
  });
};
