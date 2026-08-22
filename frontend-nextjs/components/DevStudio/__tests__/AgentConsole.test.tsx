/**
 * AgentConsole Component Tests
 *
 * Tests verify the real AgentConsole component
 * (components/DevStudio/AgentConsole.tsx):
 * - renders control panel, status badge and empty log console
 * - requires a goal before starting (error toast)
 * - POSTs {command, timeout} to /api/agent/execute and shows the task id
 * - polls /api/agent-status/agent/status/:taskId until completion, renders
 *   streamed logs, flips the button back to Run and toasts completion
 * - Stop clears local task state and marks the status STOPPED
 * - mode select offers the three agent modes
 *
 * API: POST /api/agent/execute, GET /api/agent-status/agent/status/:taskId
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import AgentConsole from '../AgentConsole';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

describe('AgentConsole', () => {
  let executeBodies: any[];
  let pollCount: number;

  beforeEach(() => {
    jest.clearAllMocks();
    executeBodies = [];
    pollCount = 0;

    server.resetHandlers();
    server.use(
      // AgentConsole builds relative URLs (API base unset in tests); MSW
      // resolves those against the jsdom origin, so handlers must be
      // host-agnostic paths rather than absolute http://localhost:8000 URLs.
      rest.post('/api/agent/execute', async (req, res, ctx) => {
        executeBodies.push(req.body);
        return res(ctx.status(200), ctx.json({ id: 'task-123' }));
      }),
      rest.get('/api/agent-status/agent/status/:taskId', (req, res, ctx) => {
        pollCount += 1;
        return res(
          ctx.status(200),
          ctx.json({ status: 'completed', logs: ['step 1 done', 'step 2 done'] })
        );
      })
    );
  });

  it('renders the control panel, console and idle status', () => {
    render(<AgentConsole />);

    expect(screen.getByText('Control Panel')).toBeInTheDocument();
    expect(screen.getByText('Live Execution Logs')).toBeInTheDocument();
    expect(screen.getByText('No logs available. Ready to start.')).toBeInTheDocument();
    expect(screen.getByText('IDLE')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /run task/i })).toBeInTheDocument();
  });

  it('offers the three agent modes in the mode select', async () => {
    render(<AgentConsole />);

    fireEvent.click(screen.getByRole('combobox'));
    await screen.findByText('Actor (Quick Action)');
    expect(screen.getAllByText('Thinker (Deep Planning)').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Tasker (Sequential)')).toBeInTheDocument();
  });

  it('shows a goal-required toast when running without a goal', () => {
    render(<AgentConsole />);

    fireEvent.click(screen.getByRole('button', { name: /run task/i }));

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Goal Required',
        description: 'Please enter a goal for the agent.',
      })
    );
    expect(executeBodies).toHaveLength(0);
  });

  it('starts the agent with the goal and shows RUNNING + task id toast', async () => {
    render(<AgentConsole />);

    fireEvent.change(screen.getByPlaceholderText(/find the cheapest flight/i), {
      target: { value: 'Summarize Q3 sales' },
    });
    fireEvent.click(screen.getByRole('button', { name: /run task/i }));

    await waitFor(() => {
      expect(executeBodies).toHaveLength(1);
    });
    expect(executeBodies[0]).toEqual({ command: 'Summarize Q3 sales', timeout: 120 });

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Agent Started', description: 'Task ID: task-123' })
      );
    });
    expect(screen.getByText('STARTING')).toBeInTheDocument();
    expect(screen.getByText('Starting agent...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /stop task/i })).toBeInTheDocument();
  });

  it('polls the agent status endpoint and renders completed state', async () => {
    render(<AgentConsole />);

    fireEvent.change(screen.getByPlaceholderText(/find the cheapest flight/i), {
      target: { value: 'Build a report' },
    });
    fireEvent.click(screen.getByRole('button', { name: /run task/i }));

    await screen.findByText('STARTING');
    await waitFor(() => expect(pollCount).toBeGreaterThanOrEqual(1), { timeout: 10000 });

    await screen.findByText('COMPLETED', {}, { timeout: 15000 });
    expect(screen.getByText('step 1 done')).toBeInTheDocument();
    expect(screen.getByText('step 2 done')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /run task/i })).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Task Completed' })
    );
  });

  it('stops the task locally and marks the status STOPPED', async () => {
    render(<AgentConsole />);

    fireEvent.change(screen.getByPlaceholderText(/find the cheapest flight/i), {
      target: { value: 'Stop me' },
    });
    fireEvent.click(screen.getByRole('button', { name: /run task/i }));
    await screen.findByText('STARTING');
    await waitFor(() => {
      expect(executeBodies).toHaveLength(1);
    });

    fireEvent.click(screen.getByRole('button', { name: /stop task/i }));

    expect(screen.getByText('STOPPED')).toBeInTheDocument();
    expect(screen.getByText('[stopped by user]')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /run task/i })).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Task Stopped' }));
  });

  it('shows an error toast when the execute request fails', async () => {
    server.use(
      rest.post('/api/agent/execute', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<AgentConsole />);
    fireEvent.change(screen.getByPlaceholderText(/find the cheapest flight/i), {
      target: { value: 'Doomed run' },
    });
    fireEvent.click(screen.getByRole('button', { name: /run task/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to start the agent service.',
        })
      );
    });
    expect(screen.getByText('ERROR')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /run task/i })).toBeInTheDocument();
  });

  it('disables the goal input while a task is running', async () => {
    render(<AgentConsole />);

    fireEvent.change(screen.getByPlaceholderText(/find the cheapest flight/i), {
      target: { value: 'Long run' },
    });
    fireEvent.click(screen.getByRole('button', { name: /run task/i }));
    await screen.findByText('STARTING');

    const input = screen.getByPlaceholderText(/find the cheapest flight/i) as HTMLInputElement;
    expect(input).toBeDisabled();
  });
});
