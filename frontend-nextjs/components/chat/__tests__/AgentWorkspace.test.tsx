/**
 * AgentWorkspace Component Tests
 *
 * Covers the REAL AgentWorkspace (components/chat/AgentWorkspace.tsx):
 * - Workspace layout renders Tasks / Artifacts / Browser View tabs
 * - Idle and empty states
 * - agent_step_update: flat + nested payload shapes, step-1 resets the run,
 *   duplicate-step dedup, status -> running, Live badge when connected
 * - agent_status_change: flat + nested status + agent id
 * - canvas:update / canvas:present auto-switch to the Artifacts tab (unless
 *   the action is "close")
 * - Manual tab switching, clear-steps button, maximize/minimize toggle
 *
 * CanvasHost and ArtifactSidebar are mocked (they are covered by their own
 * suites); useWebSocket is mocked with a mutable state object so tests can
 * drive workspace events deterministically.
 */

import React from 'react';
import { renderWithProviders, screen, fireEvent, waitFor } from '../../../tests/test-utils';
import AgentWorkspace from '../AgentWorkspace';

let mockWsState: { lastMessage: any; isConnected: boolean } = {
  lastMessage: null,
  isConnected: false,
};

let mockFetchSessionTrace: jest.Mock;
let mockSubmitStepFeedback: jest.Mock;
jest.mock('@/lib/agent-trace-api', () => ({
  fetchSessionTrace: (...args: any[]) => mockFetchSessionTrace(...args),
  submitStepFeedback: (...args: any[]) => mockSubmitStepFeedback(...args),
}));

jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => mockWsState,
}));

jest.mock('../canvas-host', () => ({
  CanvasHost: ({ lastMessage }: { lastMessage: any }) => (
    <div data-testid="mock-canvas-host">
      {lastMessage ? lastMessage.type : 'no-message'}
    </div>
  ),
}));

jest.mock('../ArtifactSidebar', () => ({
  ArtifactSidebar: ({ onSelectArtifact }: { onSelectArtifact?: (id: string) => void }) => (
    <div data-testid="mock-artifact-sidebar">
      Sidebar
      <button data-testid="pick-artifact" onClick={() => onSelectArtifact?.('art-1')}>
        Pick
      </button>
    </div>
  ),
}));

describe('AgentWorkspace', () => {
  beforeEach(() => {
    mockWsState = { lastMessage: null, isConnected: false };
  });

  // Test 1: renders workspace layout with expected sections
  test('renders workspace layout with expected sections', () => {
    const { container } = renderWithProviders(<AgentWorkspace sessionId={null} />);

    expect(container.textContent).toContain('Agent Workspace');
    expect(container.textContent).toContain('Tasks');
    expect(container.textContent).toContain('Artifacts');
    expect(container.textContent).toContain('Browser View');
  });

  // Test 2: handles loading state initially
  test('shows idle status initially', () => {
    const { container } = renderWithProviders(<AgentWorkspace sessionId={null} />);

    expect(container.textContent).toContain('Agent Status:');
  });

  // Test 3: handles empty state with no steps
  test('handles empty state with no execution steps', () => {
    const { container } = renderWithProviders(<AgentWorkspace sessionId={null} />);

    expect(container.textContent).toContain('No execution steps yet');
  });

  // Test 4: renders without errors
  test('renders without errors', () => {
    expect(() => renderWithProviders(<AgentWorkspace sessionId={null} />)).not.toThrow();
  });

  // Test 5: renders maximize/minimize button
  test('renders maximize/minimize button', () => {
    const { container } = renderWithProviders(<AgentWorkspace sessionId={null} />);

    const buttons = container.querySelectorAll('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  // Test 6: displays proper layout structure
  test('displays proper layout structure', () => {
    const { container } = renderWithProviders(<AgentWorkspace sessionId={null} />);

    expect(container.querySelector('.h-full.flex.flex-col')).toBeInTheDocument();
  });

  test('shows the Live badge when the websocket is connected', () => {
    mockWsState = { lastMessage: null, isConnected: true };
    renderWithProviders(<AgentWorkspace sessionId={null} />);

    expect(screen.getByText('Live')).toBeInTheDocument();
  });
});

describe('AgentWorkspace event handling', () => {
  beforeEach(() => {
    mockWsState = { lastMessage: null, isConnected: false };
  });

  test('renders a step update and sets status to running', () => {
    mockWsState = {
      isConnected: false,
      lastMessage: {
        type: 'agent_step_update',
        step: { step: 1, thought: 'Searching docs', action: 'search', observation: 'Found 3 results' },
      },
    };

    renderWithProviders(<AgentWorkspace sessionId={null} />);

    expect(screen.getByText('Step 1')).toBeInTheDocument();
    expect(screen.getByText('search')).toBeInTheDocument();
    expect(screen.getByText('Searching docs')).toBeInTheDocument();
    expect(screen.getByText('Found 3 results')).toBeInTheDocument();
    expect(screen.getByText('Execution Steps (1)')).toBeInTheDocument();
    expect(screen.getByText(/Agent Status: running/)).toBeInTheDocument();
    expect(screen.getByText(/Processing step 1/)).toBeInTheDocument();
  });

  test('handles nested data.step payloads', () => {
    mockWsState = {
      isConnected: false,
      lastMessage: {
        type: 'agent_step_update',
        data: { step: { step: 1, thought: 'Nested thought' } },
      },
    };

    renderWithProviders(<AgentWorkspace sessionId={null} />);

    expect(screen.getByText('Nested thought')).toBeInTheDocument();
    expect(screen.getByText('Execution Steps (1)')).toBeInTheDocument();
  });

  test('uses the raw data object as the step when step is not nested', () => {
    mockWsState = {
      isConnected: false,
      lastMessage: {
        type: 'agent_step_update',
        data: { step: 1, thought: 'Flat data step' },
      },
    };

    renderWithProviders(<AgentWorkspace sessionId={null} />);

    expect(screen.getByText('Flat data step')).toBeInTheDocument();
    expect(screen.getByText('Step 1')).toBeInTheDocument();
  });

  test('appends sequential steps and deduplicates repeat step numbers', () => {
    mockWsState = {
      isConnected: false,
      lastMessage: { type: 'agent_step_update', step: { step: 1, thought: 'One' } },
    };
    const { rerender } = renderWithProviders(<AgentWorkspace sessionId={null} />);
    expect(screen.getByText('Execution Steps (1)')).toBeInTheDocument();

    mockWsState.lastMessage = { type: 'agent_step_update', step: { step: 2, thought: 'Two' } };
    rerender(<AgentWorkspace sessionId={null} />);
    expect(screen.getByText('Execution Steps (2)')).toBeInTheDocument();
    expect(screen.getByText('Two')).toBeInTheDocument();

    // Duplicate step 2 must NOT be appended again
    mockWsState.lastMessage = { type: 'agent_step_update', step: { step: 2, thought: 'Two' } };
    rerender(<AgentWorkspace sessionId={null} />);
    expect(screen.getByText('Execution Steps (2)')).toBeInTheDocument();
  });

  test('a step 1 message starts a fresh run and clears previous steps', () => {
    mockWsState = {
      isConnected: false,
      lastMessage: { type: 'agent_step_update', step: { step: 1, thought: 'One' } },
    };
    const { rerender } = renderWithProviders(<AgentWorkspace sessionId={null} />);
    mockWsState.lastMessage = { type: 'agent_step_update', step: { step: 2, thought: 'Two' } };
    rerender(<AgentWorkspace sessionId={null} />);
    expect(screen.getByText('Execution Steps (2)')).toBeInTheDocument();

    mockWsState.lastMessage = { type: 'agent_step_update', step: { step: 1, thought: 'Fresh start' } };
    rerender(<AgentWorkspace sessionId={null} />);
    expect(screen.getByText('Execution Steps (1)')).toBeInTheDocument();
    expect(screen.getByText('Fresh start')).toBeInTheDocument();
    expect(screen.queryByText('Two')).not.toBeInTheDocument();
  });

  test('agent_status_change updates the status (flat and nested)', () => {
    const { rerender } = renderWithProviders(<AgentWorkspace sessionId={null} />);

    mockWsState.lastMessage = { type: 'agent_status_change', status: 'completed' };
    rerender(<AgentWorkspace sessionId={null} />);
    expect(screen.getByText(/Agent Status: completed/)).toBeInTheDocument();

    mockWsState.lastMessage = { type: 'agent_status_change', data: { status: 'failed' } };
    rerender(<AgentWorkspace sessionId={null} />);
    expect(screen.getByText(/Agent Status: failed/)).toBeInTheDocument();
  });

  test('canvas:update auto-switches to the artifacts tab', () => {
    mockWsState = {
      isConnected: false,
      lastMessage: { type: 'canvas:update', data: { action: 'present', component: 'markdown' } },
    };

    renderWithProviders(<AgentWorkspace sessionId={null} />);

    expect(screen.getByTestId('mock-canvas-host')).toBeInTheDocument();
    expect(screen.getByTestId('mock-artifact-sidebar')).toBeInTheDocument();
    expect(screen.queryByText('Execution Steps (0)')).not.toBeInTheDocument();
  });

  test('canvas:present also auto-switches to the artifacts tab', () => {
    mockWsState = {
      isConnected: false,
      lastMessage: { type: 'canvas:present', data: { action: 'show' } },
    };

    renderWithProviders(<AgentWorkspace sessionId={null} />);

    expect(screen.getByTestId('mock-canvas-host')).toBeInTheDocument();
  });

  test('artifact selection flows through the sidebar callback', () => {
    mockWsState = {
      isConnected: false,
      lastMessage: { type: 'canvas:present', data: { action: 'show' } },
    };
    const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    renderWithProviders(<AgentWorkspace sessionId={null} />);

    fireEvent.click(screen.getByTestId('pick-artifact'));
    expect(consoleSpy).toHaveBeenCalledWith('Selected artifact:', 'art-1');
    consoleSpy.mockRestore();
  });

  test('canvas:update with action close does not switch tabs', () => {
    mockWsState = {
      isConnected: false,
      lastMessage: { type: 'canvas:update', data: { action: 'close' } },
    };

    renderWithProviders(<AgentWorkspace sessionId={null} />);

    expect(screen.getByText('Execution Steps (0)')).toBeInTheDocument();
    expect(screen.queryByTestId('mock-canvas-host')).not.toBeInTheDocument();
  });
});

describe('AgentWorkspace interactions', () => {
  beforeEach(() => {
    mockWsState = { lastMessage: null, isConnected: false };
  });

  test('switches tabs manually', () => {
    renderWithProviders(<AgentWorkspace sessionId={null} />);

    fireEvent.click(screen.getByText('Browser View'));
    expect(screen.getByText(/Browser view will appear here/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Artifacts'));
    expect(screen.getByTestId('mock-canvas-host')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Tasks'));
    expect(screen.getByText('Execution Steps (0)')).toBeInTheDocument();
  });

  test('clears steps and resets status via the trash button', () => {
    mockWsState = {
      isConnected: false,
      lastMessage: { type: 'agent_step_update', step: { step: 1, thought: 'One' } },
    };
    renderWithProviders(<AgentWorkspace sessionId={null} />);
    expect(screen.getByText('Execution Steps (1)')).toBeInTheDocument();

    const trashButton = screen.getAllByRole('button').find(b => b.querySelector('.lucide-trash-2'))!;
    fireEvent.click(trashButton);

    expect(screen.getByText('Execution Steps (0)')).toBeInTheDocument();
    expect(screen.getByText(/No execution steps yet/)).toBeInTheDocument();
    expect(screen.getByText(/Agent Status: idle/)).toBeInTheDocument();
  });

  test('maximizes and restores the workspace layout', () => {
    const { container } = renderWithProviders(<AgentWorkspace sessionId={null} />);
    expect(container.querySelector('.fixed.inset-0')).toBeNull();

    fireEvent.click(screen.getAllByRole('button').find(b => b.querySelector('.lucide-maximize-2'))!);
    expect(container.querySelector('.fixed.inset-0')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button').find(b => b.querySelector('.lucide-minimize-2'))!);
    expect(container.querySelector('.fixed.inset-0')).toBeNull();
  });

  test('no trash button when there are no steps', () => {
    renderWithProviders(<AgentWorkspace sessionId={null} />);
    expect(screen.queryAllByRole('button').some(b => b.querySelector('.lucide-trash-2'))).toBe(false);
  });
});

describe('AgentWorkspace trace pipeline', () => {
  beforeEach(() => {
    mockWsState = { lastMessage: null, isConnected: false };
    mockFetchSessionTrace = jest.fn().mockResolvedValue({ runs: [], session_id: null });
    mockSubmitStepFeedback = jest.fn().mockResolvedValue(undefined);
  });

  test('normalizes the backend `output` key to observation', () => {
    mockWsState.lastMessage = {
      type: 'agent_step_update',
      data: {
        execution_id: 'exec-a', session_id: 's1', agent_id: 'atom_main',
        step: { step: 1, thought: 'Think', action: 'search', output: 'Found it' },
      },
    };
    renderWithProviders(<AgentWorkspace sessionId="s1" />);
    expect(screen.getByText('Found it')).toBeInTheDocument();
    expect(screen.getByText('search')).toBeInTheDocument();
  });

  test('drops events that belong to a different chat session', async () => {
    mockWsState.lastMessage = {
      type: 'agent_step_update',
      data: { execution_id: 'exec-b', session_id: 'other-session', step: { step: 1, thought: 'Not mine' } },
    };
    renderWithProviders(<AgentWorkspace sessionId="s1" />);
    await waitFor(() => expect(screen.getByText(/No execution steps yet/)).toBeInTheDocument());
    expect(screen.queryByText('Not mine')).not.toBeInTheDocument();
  });

  test('groups steps by execution id and archives the earlier run', () => {
    const { rerender } = renderWithProviders(<AgentWorkspace sessionId={null} />);

    mockWsState.lastMessage = {
      type: 'agent_step_update',
      data: { execution_id: 'exec-1', step: { step: 1, thought: 'First run step' } },
    };
    rerender(<AgentWorkspace sessionId={null} />);
    expect(screen.getByText('First run step')).toBeInTheDocument();

    // a new execution id starts a fresh current run; the old one is archived
    mockWsState.lastMessage = {
      type: 'agent_step_update',
      data: { execution_id: 'exec-2', step: { step: 1, thought: 'Second run step' } },
    };
    rerender(<AgentWorkspace sessionId={null} />);
    expect(screen.getByText('Second run step')).toBeInTheDocument();
    expect(screen.queryByText('First run step')).not.toBeInTheDocument(); // collapsed
    expect(screen.getByText('Previous runs (1)')).toBeInTheDocument();
    expect(screen.getByText(/exec-1/)).toBeInTheDocument();
  });

  test('run lifecycle status events fire activity and settled callbacks', () => {
    const onAgentActivity = jest.fn();
    const onRunSettled = jest.fn();
    const { rerender } = renderWithProviders(
      <AgentWorkspace sessionId={null} onAgentActivity={onAgentActivity} onRunSettled={onRunSettled} />
    );

    mockWsState.lastMessage = {
      type: 'agent_status_change',
      data: { status: 'running', execution_id: 'exec-7', agent_id: 'atom_main' },
    };
    rerender(
      <AgentWorkspace sessionId={null} onAgentActivity={onAgentActivity} onRunSettled={onRunSettled} />
    );
    expect(onAgentActivity).toHaveBeenCalledWith('run_start');

    mockWsState.lastMessage = {
      type: 'agent_status_change',
      data: { status: 'success', execution_id: 'exec-7' },
    };
    rerender(
      <AgentWorkspace sessionId={null} onAgentActivity={onAgentActivity} onRunSettled={onRunSettled} />
    );
    expect(onRunSettled).toHaveBeenCalledTimes(1);
  });

  test('history restore merges persisted runs into the timeline', async () => {
    mockFetchSessionTrace.mockResolvedValue({
      runs: [
        {
          execution_id: 'hist-1',
          agent_id: 'atom_main',
          status: 'completed',
          input_summary: 'older task',
          started_at: '2026-08-28T09:00:00Z',
          steps: [
            { step_number: 1, thought: 'older thought', observation: 'older result' },
          ],
        },
        {
          execution_id: 'hist-2',
          agent_id: 'atom_main',
          status: 'completed',
          input_summary: 'past task',
          started_at: '2026-08-28T10:00:00Z',
          steps: [
            { step_number: 1, thought: 'old thought', observation: 'old result', feedback_score: -1 },
          ],
        },
      ],
      session_id: 's1',
    });
    renderWithProviders(<AgentWorkspace sessionId="s1" />);

    // newest persisted run is the current run
    await waitFor(() => expect(screen.getByText('old thought')).toBeInTheDocument());
    expect(screen.getByText(/hist-2/)).toBeInTheDocument();
    expect(screen.getByText('Previous runs (1)')).toBeInTheDocument();
    // persisted thumbs-down feedback is restored on the step
    expect(screen.getByLabelText('Thumbs down').className).toContain('text-red-400');
    expect(mockFetchSessionTrace).toHaveBeenCalledWith('s1');

    // expand the archived run to inspect its trace
    fireEvent.click(screen.getByText(/hist-1/));
    expect(screen.getByText('older thought')).toBeInTheDocument();
  });

  test('step feedback posts through the trace API with run linkage', async () => {
    mockWsState.lastMessage = {
      type: 'agent_step_update',
      data: {
        execution_id: 'exec-fb', agent_id: 'atom_main', session_id: 's1',
        step: { step: 2, thought: 'Plan', action: 'query', observation: 'rows' },
      },
    };
    renderWithProviders(<AgentWorkspace sessionId="s1" />);

    fireEvent.click(screen.getByLabelText('Thumbs up'));
    await waitFor(() =>
      expect(mockSubmitStepFeedback).toHaveBeenCalledWith(
        expect.objectContaining({
          agentId: 'atom_main',
          runId: 'exec-fb',
          executionId: 'exec-fb',
          stepNumber: 2,
          feedbackType: 'thumbs_up',
        })
      )
    );
  });

  test('collapsed rail renders, badges unread steps, and expands on click', () => {
    const onToggleCollapsed = jest.fn();
    // collapse first, then a step arrives while collapsed
    mockWsState.lastMessage = {
      type: 'agent_step_update',
      data: { execution_id: 'exec-r', step: { step: 1, thought: 'rail step' } },
    };
    const { rerender } = renderWithProviders(
      <AgentWorkspace sessionId={null} collapsed onToggleCollapsed={onToggleCollapsed} />
    );

    expect(screen.getByTestId('workspace-rail')).toBeInTheDocument();
    expect(screen.getByLabelText('1 unread steps')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Expand agent workspace'));
    expect(onToggleCollapsed).toHaveBeenCalledTimes(1);

    // expanded → rail disappears, unread resets
    rerender(<AgentWorkspace sessionId={null} collapsed={false} onToggleCollapsed={onToggleCollapsed} />);
    expect(screen.queryByTestId('workspace-rail')).not.toBeInTheDocument();
  });

  test('auto-hide preference toggle renders and calls back', () => {
    const onAutoHideToggle = jest.fn();
    const { rerender } = renderWithProviders(
      <AgentWorkspace sessionId={null} autoHide onAutoHideToggle={onAutoHideToggle} />
    );
    expect(screen.getByLabelText('Toggle auto-hide')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Toggle auto-hide'));
    expect(onAutoHideToggle).toHaveBeenCalledWith(false);

    rerender(<AgentWorkspace sessionId={null} autoHide={false} onAutoHideToggle={onAutoHideToggle} />);
    expect(screen.getByLabelText('Toggle auto-hide').className).not.toContain('text-indigo-400');
  });

  test('manual collapse button in the header collapses the panel', () => {
    const onToggleCollapsed = jest.fn();
    renderWithProviders(
      <AgentWorkspace sessionId={null} onToggleCollapsed={onToggleCollapsed} />
    );
    fireEvent.click(screen.getByLabelText('Collapse workspace'));
    expect(onToggleCollapsed).toHaveBeenCalledTimes(1);
  });
});

describe('AgentWorkspace structured action payloads', () => {
  beforeEach(() => {
    mockWsState = { lastMessage: null, isConnected: false };
  });

  test('renders a structured {tool, params} action without crashing', () => {
    // Regression: the backend emits action as a structured object
    // ({tool, params}); rendering it as a React child threw
    // "Objects are not valid as a React child" on every chat turn.
    mockWsState = {
      isConnected: false,
      lastMessage: {
        type: 'agent_step_update',
        step: {
          step: 1,
          thought: 'Planning the send',
          action: { tool: 'canvas_action_planner', params: { action: 'send_email' } },
          action_input: { action: 'send_email', to: ['a@b.com'] },
          observation: 'Planned send_email to a@b.com',
        },
      },
    };

    expect(() => renderWithProviders(<AgentWorkspace sessionId={null} />)).not.toThrow();

    expect(screen.getByText('Step 1')).toBeInTheDocument();
    // The badge shows the tool NAME, not [object Object]
    expect(screen.getByText('canvas_action_planner')).toBeInTheDocument();
    // The params object is stringified into the input line (not [object Object])
    expect(screen.getByText(/\{"action":"send_email","to":\["a@b.com"\]\}/)).toBeInTheDocument();
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });
});
