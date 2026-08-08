/**
 * LiveMonitoringPanel Component Tests
 *
 * Verifies the real LiveMonitoringPanel (components/supervision/LiveMonitoringPanel.tsx)
 * against a mocked EventSource SSE stream:
 * - renders header, supervisor identity, progress bar and log viewer
 * - 'connected' stream event adds a log entry
 * - 'action'/'result' supervision events advance steps and reveal OutputPreview
 * - step advancement must NOT be stuck on step 0 by a stale steps closure
 *   (a real bug: the second 'action' re-marked step 0 instead of advancing)
 * - 'done' closes the stream, marks execution complete and fires onComplete
 * - 'error' frames with data surface the server message
 * - a connection-level 'error' event WITHOUT data (real EventSource behavior)
 *   must not crash the component
 * - intervention controls: guidance required, session lookup, terminate flow
 * - autonomous supervisors see no intervention controls
 *
 * APIs: GET /api/supervision/sessions/active,
 *       POST /api/supervision/sessions/:id/intervene
 */
import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import LiveMonitoringPanel from '../LiveMonitoringPanel';

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  closed = false;
  private listeners: Record<string, Array<(e: any) => void>> = {};
  onerror: ((e: any) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, cb: (e: any) => void) {
    (this.listeners[type] = this.listeners[type] || []).push(cb);
  }

  removeEventListener(type: string, cb: (e: any) => void) {
    this.listeners[type] = (this.listeners[type] || []).filter((l) => l !== cb);
  }

  close() {
    this.closed = true;
  }

  emit(type: string, data?: unknown) {
    const payload = { data: data === undefined ? undefined : JSON.stringify(data) };
    (this.listeners[type] || []).forEach((cb) => cb(payload));
  }

  emitNetworkError() {
    // Real EventSource fires an 'error' event with NO data before onerror
    (this.listeners['error'] || []).forEach((cb) => cb({}));
    if (this.onerror) this.onerror(new Event('error'));
  }
}

const defaultProps = {
  executionId: 'exec-1',
  agentId: 'agent-1',
  agentName: 'Sales Researcher',
  supervisorType: 'user' as const,
  supervisorId: 'user-1',
  supervisorName: 'Rushi',
};

const activeSessions = [
  { session_id: 'sess-1', agent_id: 'agent-1' },
  { session_id: 'sess-2', agent_id: 'other-agent' },
];

let interveneBody: any = null;

describe('LiveMonitoringPanel', () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    interveneBody = null;
    (global as any).EventSource = MockEventSource;
    server.resetHandlers();
    server.use(
      rest.get('/api/supervision/sessions/active', (req, res, ctx) =>
        res(ctx.status(200), ctx.json(activeSessions))
      ),
      rest.post('/api/supervision/sessions/:sessionId/intervene', (req, res, ctx) => {
        interveneBody = req.body;
        return res(ctx.status(200), ctx.json({ message: 'Pause requested' }));
      })
    );
  });

  afterEach(() => {
    delete (global as any).EventSource;
  });

  it('renders header, supervisor identity, steps and empty log viewer', () => {
    render(<LiveMonitoringPanel {...defaultProps} />);

    expect(screen.getByText('Live Monitoring: Sales Researcher')).toBeInTheDocument();
    expect(screen.getByText('Supervisor:')).toBeInTheDocument();
    expect(screen.getByText('👤 User')).toBeInTheDocument();
    expect(screen.getByText('Rushi')).toBeInTheDocument();
    expect(screen.getByText('user-1')).toBeInTheDocument();

    expect(screen.getByText('Execution Progress')).toBeInTheDocument();
    expect(screen.getByText('20%')).toBeInTheDocument();
    expect(screen.getByText('Initialize execution')).toBeInTheDocument();
    expect(screen.getByText('Finalize')).toBeInTheDocument();

    expect(screen.getByText('Execution Logs')).toBeInTheDocument();
    expect(screen.getByText('Waiting for logs...')).toBeInTheDocument();

    // user supervisor + executing → intervention controls visible
    expect(screen.getByText('Intervention Controls')).toBeInTheDocument();
  });

  it('adds a log entry on the connected stream event', async () => {
    render(<LiveMonitoringPanel {...defaultProps} />);

    act(() => {
      MockEventSource.instances[0].emit('connected', { timestamp: '2026-08-01T10:00:00Z' });
    });

    expect(await screen.findByText('Connected to execution exec-1')).toBeInTheDocument();
  });

  it('advances steps and shows the output preview from supervision events', async () => {
    const { container } = render(<LiveMonitoringPanel {...defaultProps} />);
    const es = MockEventSource.instances[0];

    act(() => {
      es.emit('supervision_event', {
        timestamp: '2026-08-01T10:00:01Z',
        event_type: 'action',
        data: { step: 'load context' },
      });
    });
    expect(container.querySelectorAll('.step-in_progress').length).toBe(1);
    expect(container.querySelectorAll('.step-completed').length).toBe(0);

    act(() => {
      es.emit('supervision_event', {
        timestamp: '2026-08-01T10:00:02Z',
        event_type: 'result',
        data: { output: { answer: 42 } },
      });
    });
    expect(container.querySelectorAll('.step-completed').length).toBe(1);

    // OutputPreview appears with the streamed output
    expect(await screen.findByText('Output')).toBeInTheDocument();
    expect(container.querySelector('.output-preview')).toBeInTheDocument();

    // log entries were added for each event
    expect(screen.getByText(/action: /)).toBeInTheDocument();
    expect(screen.getByText(/result: /)).toBeInTheDocument();
  });

  it('advances past step 0 on subsequent action events (stale-closure bug guard)', async () => {
    const { container } = render(<LiveMonitoringPanel {...defaultProps} />);
    const es = MockEventSource.instances[0];

    act(() => {
      es.emit('supervision_event', { timestamp: 't0', event_type: 'action', data: {} });
    });
    act(() => {
      es.emit('supervision_event', { timestamp: 't1', event_type: 'result', data: {} });
    });
    act(() => {
      es.emit('supervision_event', { timestamp: 't2', event_type: 'action', data: {} });
    });

    // currentStep must advance to step index 1 → 2/5 = 40%
    expect(screen.getByText('40%')).toBeInTheDocument();
    expect(container.querySelectorAll('.step-completed').length).toBe(1);
    expect(container.querySelectorAll('.step-in_progress').length).toBe(1);
  });

  it('marks the running step failed on an error supervision event', async () => {
    const { container } = render(<LiveMonitoringPanel {...defaultProps} />);
    const es = MockEventSource.instances[0];

    act(() => {
      es.emit('supervision_event', { timestamp: 't0', event_type: 'action', data: {} });
    });
    act(() => {
      es.emit('supervision_event', {
        timestamp: 't1',
        event_type: 'error',
        data: { error_message: 'Agent crashed' },
      });
    });

    expect(container.querySelectorAll('.step-failed').length).toBe(1);
    expect(screen.getByText('Agent crashed')).toBeInTheDocument();
  });

  it('stops execution and fires onComplete on the done event', async () => {
    const onComplete = jest.fn();
    render(<LiveMonitoringPanel {...defaultProps} onComplete={onComplete} />);
    const es = MockEventSource.instances[0];

    act(() => {
      es.emit('done');
    });

    expect(await screen.findByText('Execution terminated')).toBeInTheDocument();
    expect(es.closed).toBe(true);
    expect(onComplete).toHaveBeenCalledWith({ executionId: 'exec-1', success: true });
  });

  it('surfaces the server message from an error frame with data', async () => {
    render(<LiveMonitoringPanel {...defaultProps} />);
    const es = MockEventSource.instances[0];

    act(() => {
      es.emit('error', { message: 'Execution failed: timeout' });
    });

    expect(await screen.findByText('Execution failed: timeout')).toBeInTheDocument();
    expect(screen.getByText('Execution terminated')).toBeInTheDocument();
    expect(es.closed).toBe(true);
  });

  it('does not crash when the connection error event carries no data', async () => {
    render(<LiveMonitoringPanel {...defaultProps} />);
    const es = MockEventSource.instances[0];

    act(() => {
      es.emitNetworkError();
    });

    expect(await screen.findByText('Connection error')).toBeInTheDocument();
    expect(screen.getByText('Execution terminated')).toBeInTheDocument();
    expect(es.closed).toBe(true);
  });

  it('requires guidance before submitting an intervention', async () => {
    render(<LiveMonitoringPanel {...defaultProps} />);

    fireEvent.click(screen.getByRole('button', { name: 'Submit Intervention' }));

    expect(screen.getByText('Please provide guidance for the intervention')).toBeInTheDocument();
  });

  it('submits an intervention with the selected type and guidance', async () => {
    render(<LiveMonitoringPanel {...defaultProps} />);

    fireEvent.change(screen.getByPlaceholderText('Provide guidance...'), {
      target: { value: 'Slow down and verify the numbers' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Intervention' }));

    expect(await screen.findByText(/Intervention: pause - Pause requested/)).toBeInTheDocument();
    expect(interveneBody).toEqual({
      intervention_type: 'pause',
      guidance: 'Slow down and verify the numbers',
    });
    // guidance cleared after a successful intervention
    expect((screen.getByPlaceholderText('Provide guidance...') as HTMLInputElement).value).toBe('');
  });

  it('reports when no active supervision session exists for the agent', async () => {
    server.use(
      rest.get('/api/supervision/sessions/active', (req, res, ctx) =>
        res(ctx.status(200), ctx.json([]))
      )
    );
    render(<LiveMonitoringPanel {...defaultProps} />);

    fireEvent.change(screen.getByPlaceholderText('Provide guidance...'), {
      target: { value: 'stop' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Intervention' }));

    expect(await screen.findByText('No active supervision session found')).toBeInTheDocument();
  });

  it('shows an error when the intervene API call fails', async () => {
    server.use(
      rest.post('/api/supervision/sessions/:sessionId/intervene', (req, res, ctx) =>
        res(ctx.status(500), ctx.json({ message: 'boom' }))
      )
    );
    render(<LiveMonitoringPanel {...defaultProps} />);

    fireEvent.change(screen.getByPlaceholderText('Provide guidance...'), {
      target: { value: 'stop now' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Intervention' }));

    expect(await screen.findByText('Failed to intervene')).toBeInTheDocument();
  });

  it('terminates execution and hides controls after a terminate intervention', async () => {
    render(<LiveMonitoringPanel {...defaultProps} />);

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'terminate' } });
    expect(screen.getByRole('button', { name: 'Terminate Execution' })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Provide guidance...'), {
      target: { value: 'kill it' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Terminate Execution' }));

    await waitFor(() => {
      expect(screen.queryByText('Intervention Controls')).not.toBeInTheDocument();
    });
    expect(screen.getByText('Execution terminated')).toBeInTheDocument();
  });

  it('hides intervention controls for autonomous agent supervisors', async () => {
    render(
      <LiveMonitoringPanel
        {...defaultProps}
        supervisorType="autonomous_agent"
        supervisorId="agent-reviewer"
        supervisorName="Queen Agent"
      />
    );

    expect(screen.getByText('🤖 Autonomous Agent')).toBeInTheDocument();
    expect(screen.queryByText('Intervention Controls')).not.toBeInTheDocument();
  });
});
