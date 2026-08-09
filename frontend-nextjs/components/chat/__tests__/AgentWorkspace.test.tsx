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
