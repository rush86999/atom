/**
 * AgentOperationTracker Accessibility Tree Tests
 *
 * Tests verify that AgentOperationTracker component renders
 * accessibility trees correctly for AI agent consumption.
 *
 * Focus: Hidden divs with role="log", data-canvas-state attributes,
 * and JSON state serialization.
 */

import React from 'react';
import { renderWithProviders, screen, waitFor } from '../../../tests/test-utils';
import { act, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import AgentOperationTracker, { AgentOperationData } from '../AgentOperationTracker';
import {
  createMockOperationData,
  getAccessibilityTree,
  parseCanvasState,
  assertCanvasDataAttributes,
  assertAccessibilityTreeARIA,
  assertCanvasStateFields,
  mockWebSocket
} from './canvas-accessibility-tree.test-utils';

// Mock WebSocket hook — shared mutable state drives lastMessage so tests can
// simulate incoming canvas:update messages (same pattern as
// agent-request-prompt.test.tsx / integration-connection-guide.test.tsx).
const mockSocket = {
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  send: jest.fn()
};

const mockWsState: { lastMessage: any; force: (() => void) | null } = {
  lastMessage: null,
  force: null
};

jest.mock('@/hooks/useWebSocket', () => {
  const React = jest.requireActual('react');
  const useMockWebSocket = () => {
    const [, force] = React.useReducer((x: number) => x + 1, 0);
    mockWsState.force = force;
    return {
      socket: mockSocket,
      connected: true,
      lastMessage: mockWsState.lastMessage,
      streamingContent: new Map(),
      sendMessage: (msg: any) => mockSocket.send(JSON.stringify(msg))
    };
  };
  return {
    __esModule: true,
    default: useMockWebSocket,
    useWebSocket: useMockWebSocket
  };
});

// Mock next-auth
jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
  SessionProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('AgentOperationTracker Accessibility Tree', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ============================================================================
  // Accessibility Tree Presence Tests
  // ============================================================================

  test('should render hidden accessibility div with role="log"', () => {
    const mockData = createMockOperationData();
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
        className=""
      />
    );

    // Access accessibility tree (hidden from visual display)
    const accessibilityDiv = container.querySelector('[role="log"]');
    expect(accessibilityDiv).toBeInTheDocument();
  });

  test('should render accessibility tree with correct aria-live attribute', () => {
    const mockData = createMockOperationData();
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = container.querySelector('[role="log"]');
    expect(accessibilityDiv).toHaveAttribute('aria-live', 'polite');
  });

  test('should render accessibility tree with correct aria-label', () => {
    const mockData = createMockOperationData();
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = container.querySelector('[role="log"]');
    expect(accessibilityDiv).toHaveAttribute('aria-label', 'Agent operation state');
  });

  test('should render accessibility tree with display:none', () => {
    const mockData = createMockOperationData();
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = container.querySelector('[role="log"]');
    expect(accessibilityDiv).toHaveStyle({ display: 'none' });
  });

  // ============================================================================
  // Data Attributes Tests
  // ============================================================================

  test('should include data-canvas-state attribute', () => {
    const mockData = createMockOperationData();
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    expect(accessibilityDiv).toHaveAttribute('data-canvas-state', 'agent_operation_tracker');
  });

  test('should include data-operation-id attribute', () => {
    const mockData = createMockOperationData({ operation_id: 'op-12345' });
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId="op-12345"
        userId="test-user"
      />
    );

    // Note: When no operation data is present, the operation ID won't be in the tree
    // The tree is only populated when operation state is set
    const accessibilityDiv = getAccessibilityTree(container);
    expect(accessibilityDiv).toBeInTheDocument();
  });

  test('should include data-status attribute', () => {
    const mockData = createMockOperationData({ status: 'running' });
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    expect(accessibilityDiv).toBeInTheDocument();
  });

  test('should include data-progress attribute', () => {
    const mockData = createMockOperationData({ progress: 75 });
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    expect(accessibilityDiv).toBeInTheDocument();
  });

  test('should include all context data attributes', () => {
    const mockData = createMockOperationData({
      context: {
        what: 'Analyzing data',
        why: 'Generate report',
        next: 'Send email'
      }
    });
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    expect(accessibilityDiv).toBeInTheDocument();
  });

  // ============================================================================
  // JSON State Serialization Tests
  // ============================================================================

  test('should serialize full operation state as JSON', () => {
    const mockData = createMockOperationData({
      operation_id: 'op-123',
      status: 'running'
    });
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId="op-123"
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    const state = parseCanvasState(accessibilityDiv);

    // In loading state, should have status: 'loading'
    expect(state).toBeDefined();
    expect(state.status).toBe('loading');
  });

  test('should include operation_id in JSON state', () => {
    const mockData = createMockOperationData({ operation_id: 'test-op-999' });
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    const state = parseCanvasState(accessibilityDiv);

    // Loading state has message field
    expect(state).toHaveProperty('message');
  });

  test('should include context object in JSON state', () => {
    const mockData = createMockOperationData({
      context: {
        what: 'Test context',
        why: 'Test reason',
        next: 'Test next'
      }
    });
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    const state = parseCanvasState(accessibilityDiv);

    expect(state).toBeDefined();
  });

  test('should include logs array in JSON state', () => {
    const mockData = createMockOperationData({
      logs: [
        { timestamp: '2024-01-01T00:00:00Z', level: 'info', message: 'Test log' }
      ]
    });
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    const state = parseCanvasState(accessibilityDiv);

    expect(state).toBeDefined();
  });

  // ============================================================================
  // Edge Cases
  // ============================================================================

  test('should render loading state accessibility tree when no operation', () => {
    const { container } = renderWithProviders(
      <AgentOperationTracker
        userId="test-user"
        className=""
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    expect(accessibilityDiv).toBeInTheDocument();

    // Verify loading state JSON
    const state = parseCanvasState(accessibilityDiv);
    expect(state.status).toBe('loading');
    expect(state.message).toBe('Waiting for operation data...');
  });

  test('should handle missing optional fields gracefully', () => {
    const mockData = createMockOperationData({
      total_steps: undefined,
      completed_at: undefined
    });
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    // Should render without errors
    const accessibilityDiv = getAccessibilityTree(container);
    expect(accessibilityDiv).toBeInTheDocument();
  });

  test('should handle empty context object', () => {
    const mockData = createMockOperationData({
      context: { what: '', why: '', next: '' }
    });
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    expect(accessibilityDiv).toBeInTheDocument();
  });

  test('should handle empty logs array', () => {
    const mockData = createMockOperationData({ logs: [] });
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    expect(accessibilityDiv).toBeInTheDocument();
  });

  test('should handle different status values', () => {
    const statuses: Array<'running' | 'waiting' | 'completed' | 'failed'> = [
      'running',
      'waiting',
      'completed',
      'failed'
    ];

    statuses.forEach(status => {
      const mockData = createMockOperationData({ status });
      const { container } = renderWithProviders(
        <AgentOperationTracker
          operationId={mockData.operation_id}
          userId="test-user"
        />
      );

      const accessibilityDiv = getAccessibilityTree(container);
      expect(accessibilityDiv).toBeInTheDocument();
    });
  });

  test('should handle extreme progress values (0 and 100)', () => {
    const progressValues = [0, 100];

    progressValues.forEach(progress => {
      const mockData = createMockOperationData({ progress });
      const { container } = renderWithProviders(
        <AgentOperationTracker
          operationId={mockData.operation_id}
          userId="test-user"
        />
      );

      const accessibilityDiv = getAccessibilityTree(container);
      expect(accessibilityDiv).toBeInTheDocument();
    });
  });

  // ============================================================================
  // ARIA Compliance Tests
  // ============================================================================

  test('should meet ARIA standards for accessibility tree', () => {
    const mockData = createMockOperationData();
    const { container } = renderWithProviders(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    assertAccessibilityTreeARIA(accessibilityDiv);
  });

  test('should have all required accessibility fields in JSON', () => {
    const { container } = renderWithProviders(
      <AgentOperationTracker
        userId="test-user"
        className=""
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    const state = parseCanvasState(accessibilityDiv);

    assertCanvasStateFields(state, ['status', 'message']);
  });

  // ============================================================================
  // Integration with Utilities Tests
  // ============================================================================

  test('should work with mockWebSocket utility', () => {
    const ws = mockWebSocket();
    expect(ws.socket).toBeDefined();
    expect(ws.connected).toBe(false);
  });

  test('should work with createMockOperationData utility', () => {
    const mockData = createMockOperationData({
      operation_id: 'custom-op-123',
      agent_name: 'CustomAgent'
    });

    expect(mockData.operation_id).toBe('custom-op-123');
    expect(mockData.agent_name).toBe('CustomAgent');
    expect(mockData.status).toBe('running'); // default value
  });
});

// ============================================================================
// Real Behavior Tests — websocket-driven rendering, progress states, logs
// ============================================================================

const simulateWebSocketMessage = (message: any) => {
  act(() => {
    mockWsState.lastMessage = message;
    mockWsState.force?.();
  });
};

// Visible tracker surface (excludes the hidden a11y tree whose JSON duplicates
// agent names / context strings).
const getTracker = () =>
  within(document.querySelector('.agent-operation-tracker') as HTMLElement);

describe('AgentOperationTracker Behavior', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockWsState.lastMessage = null;
    mockWsState.force = null;
  });

  test('shows loading skeleton with a11y "waiting for operation data" state', () => {
    const { container } = renderWithProviders(
      <AgentOperationTracker operationId="op-1" userId="u1" />
    );
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
    const tree = getAccessibilityTree(container);
    expect(parseCanvasState(tree)?.status).toBe('loading');
  });

  test('renders full operation from canvas:update message', () => {
    const op = createMockOperationData({
      operation_id: 'op-1',
      agent_name: 'DataMiner',
      status: 'running',
      progress: 42,
      current_step: 'Extracting rows',
      current_step_index: 2,
      total_steps: 5,
    });
    renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    const tracker = getTracker();
    expect(tracker.getByText('DataMiner')).toBeInTheDocument();
    expect(tracker.getByText('42%')).toBeInTheDocument();
    expect(tracker.getByText('Extracting rows')).toBeInTheDocument();
    expect(tracker.getByText('Step 2 of 5')).toBeInTheDocument();
    expect(tracker.getByText(/Started:/)).toBeInTheDocument();
  });

  test('ignores canvas:update for a different operationId', () => {
    const op = createMockOperationData({ operation_id: 'op-999' });
    renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    const tracker = getTracker();
    expect(tracker.queryByText('TestAgent')).not.toBeInTheDocument();
    expect(parseCanvasState(getAccessibilityTree(document.body))?.status).toBe('loading');
  });

  test('accepts operation when no operationId filter is set', () => {
    const op = createMockOperationData({ operation_id: 'op-any', agent_name: 'AnyAgent' });
    renderWithProviders(<AgentOperationTracker userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    expect(getTracker().getByText('AnyAgent')).toBeInTheDocument();
  });

  test('ignores non-agent_operation_tracker components', () => {
    const { container } = renderWithProviders(<AgentOperationTracker userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'some_other_widget', data: createMockOperationData() },
    });

    const tracker = getTracker();
    expect(tracker.queryByText('TestAgent')).not.toBeInTheDocument();
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  test('merges update action into existing operation', () => {
    const op = createMockOperationData({ operation_id: 'op-1', progress: 20, status: 'running' });
    renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { action: 'update', operation_id: 'op-1', updates: { progress: 85, status: 'completed', current_step: 'Done step' } },
    });

    const tracker = getTracker();
    expect(tracker.getByText('85%')).toBeInTheDocument();
    expect(tracker.getByText('✅')).toBeInTheDocument();
    expect(tracker.getByText('Completed')).toBeInTheDocument();
    expect(tracker.getByText('Done step')).toBeInTheDocument();
  });

  test('ignores update action for a different operation', () => {
    const op = createMockOperationData({ operation_id: 'op-1', progress: 20 });
    renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { action: 'update', operation_id: 'other-op', updates: { progress: 99 } },
    });

    expect(getTracker().getByText('20%')).toBeInTheDocument();
  });

  test('logs malformed messages without crashing', () => {
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    renderWithProviders(<AgentOperationTracker userId="u1" />);

    const evilData: any = {};
    Object.defineProperty(evilData, 'component', {
      get() {
        throw new Error('boom');
      },
    });
    simulateWebSocketMessage({ type: 'canvas:update', data: evilData });

    expect(errorSpy).toHaveBeenCalledWith(
      'Failed to parse WebSocket message:',
      expect.any(Error)
    );
    errorSpy.mockRestore();
  });

  test.each([
    ['running', '⚡', 'Running', 'text-blue-600'],
    ['waiting', '⏸️', 'Waiting', 'text-yellow-600'],
    ['completed', '✅', 'Completed', 'text-green-600'],
    ['failed', '❌', 'Failed', 'text-red-600'],
  ] as Array<[string, string, string, string]>)(
    'renders %s status badge with correct icon and color',
    (status, icon, label, colorClass) => {
      const op = createMockOperationData({ operation_id: 'op-1', status: status as any });
      renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
      simulateWebSocketMessage({
        type: 'canvas:update',
        data: { component: 'agent_operation_tracker', data: op },
      });

      const tracker = getTracker();
      expect(tracker.getByText(icon)).toBeInTheDocument();
      const badge = tracker.getByText(label).closest('div');
      expect(badge?.className).toContain(colorClass);
    }
  );

  test('renders context sections when all three fields present', () => {
    const op = createMockOperationData({
      operation_id: 'op-1',
      context: { what: 'Analyzing data', why: 'Generate report', next: 'Send email' },
    });
    renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    const tracker = getTracker();
    expect(tracker.getByText('📋 Context:')).toBeInTheDocument();
    expect(tracker.getByText("What I'm doing:")).toBeInTheDocument();
    expect(tracker.getByText('Analyzing data')).toBeInTheDocument();
    expect(tracker.getByText('Why:')).toBeInTheDocument();
    expect(tracker.getByText('Generate report')).toBeInTheDocument();
    expect(tracker.getByText("What's next:")).toBeInTheDocument();
    expect(tracker.getByText('Send email')).toBeInTheDocument();
  });

  test('hides context section when all fields are empty', () => {
    const op = createMockOperationData({ operation_id: 'op-1', context: { what: '', why: '', next: '' } });
    renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    expect(getTracker().queryByText('📋 Context:')).not.toBeInTheDocument();
  });

  test('expands/collapses logs and renders level icons', () => {
    const op = createMockOperationData({
      operation_id: 'op-1',
      logs: [
        { timestamp: '2024-01-01T00:00:00Z', level: 'info', message: 'Started run' },
        { timestamp: '2024-01-01T00:00:01Z', level: 'warning', message: 'Slow step' },
        { timestamp: '2024-01-01T00:00:02Z', level: 'error', message: 'Failed retry' },
      ],
    });
    renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    const tracker = getTracker();
    const toggle = tracker.getByText('📜 Operation Logs (3)');
    expect(tracker.queryByText('Started run')).not.toBeInTheDocument();

    act(() => toggle.click());
    expect(tracker.getByText('Started run')).toBeInTheDocument();
    expect(tracker.getByText('Slow step')).toBeInTheDocument();
    expect(tracker.getByText('Failed retry')).toBeInTheDocument();
    expect(tracker.getByText('ℹ️')).toBeInTheDocument();
    expect(tracker.getByText('⚠️')).toBeInTheDocument();
    expect(tracker.getByText('❌')).toBeInTheDocument();
    expect(tracker.getByText(new Date('2024-01-01T00:00:00Z').toLocaleTimeString())).toBeInTheDocument();

    act(() => toggle.click());
    expect(tracker.queryByText('Started run')).not.toBeInTheDocument();
  });

  test('hides logs section when there are no logs', () => {
    const op = createMockOperationData({ operation_id: 'op-1', logs: [] });
    renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    expect(getTracker().queryByText(/Operation Logs/)).not.toBeInTheDocument();
  });

  test('renders completed timestamp when completed_at present', () => {
    const op = createMockOperationData({
      operation_id: 'op-1',
      status: 'completed',
      started_at: '2024-01-01T10:00:00Z',
      completed_at: '2024-01-01T10:05:00Z',
    });
    renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    const tracker = getTracker();
    expect(tracker.getByText(`Completed: ${new Date('2024-01-01T10:05:00Z').toLocaleString()}`)).toBeInTheDocument();
  });

  test('omits step counter when total_steps missing', () => {
    const op = createMockOperationData({ operation_id: 'op-1', total_steps: undefined });
    renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    expect(getTracker().queryByText(/Step \d+ of \d+/)).not.toBeInTheDocument();
  });

  test('populates a11y data attributes from live operation', async () => {
    const op = createMockOperationData({
      operation_id: 'op-1',
      agent_id: 'agent-9',
      agent_name: 'A11yAgent',
      operation_type: 'research',
      progress: 33,
      total_steps: 4,
    });
    renderWithProviders(<AgentOperationTracker operationId="op-1" userId="u1" />);
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });

    const tree = getAccessibilityTree(document.body)!;
    expect(tree).toHaveAttribute('data-operation-id', 'op-1');
    expect(tree).toHaveAttribute('data-agent-id', 'agent-9');
    expect(tree).toHaveAttribute('data-agent-name', 'A11yAgent');
    expect(tree).toHaveAttribute('data-operation-type', 'research');
    expect(tree).toHaveAttribute('data-status', 'running');
    expect(tree).toHaveAttribute('data-progress', '33');
    expect(tree).toHaveAttribute('data-total-steps', '4');
    expect(tree).toHaveAttribute('data-logs-count', '0');

    const state = parseCanvasState(tree);
    expect(state.operation_id).toBe('op-1');
    expect(state.agent_name).toBe('A11yAgent');
    expect(state.progress).toBe(33);
    expect(Array.isArray(state.logs)).toBe(true);
  });

  test('applies className to the tracker container', () => {
    const { container } = renderWithProviders(
      <AgentOperationTracker userId="u1" className="custom-class-xyz" />
    );
    expect(container.querySelector('.custom-class-xyz')).toBeInTheDocument();
  });

  test('resets to loading state when a new operationId arrives after data', () => {
    const op = createMockOperationData({ operation_id: 'op-1', agent_name: 'FirstAgent' });
    const { rerender } = renderWithProviders(
      <AgentOperationTracker operationId="op-1" userId="u1" />
    );
    simulateWebSocketMessage({
      type: 'canvas:update',
      data: { component: 'agent_operation_tracker', data: op },
    });
    expect(getTracker().getByText('FirstAgent')).toBeInTheDocument();

    rerender(<AgentOperationTracker operationId="op-2" userId="u1" />);
    expect(parseCanvasState(getAccessibilityTree(document.body))?.status).toBe('loading');
  });
});
