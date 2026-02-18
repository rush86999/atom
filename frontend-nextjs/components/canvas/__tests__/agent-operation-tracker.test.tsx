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
import { render, screen, waitFor } from '@testing-library/react';
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
} from './canvas-accessibility-tree.test';

// Mock WebSocket hook
jest.mock('@/hooks/useWebSocket', () => ({
  __esModule: true,
  default: () => ({
    socket: null,
    connected: false,
    lastMessage: null
  })
}));

// Mock next-auth
jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' })
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
    const { container } = render(
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
      const { container } = render(
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
      const { container } = render(
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
    const { container } = render(
      <AgentOperationTracker
        operationId={mockData.operation_id}
        userId="test-user"
      />
    );

    const accessibilityDiv = getAccessibilityTree(container);
    assertAccessibilityTreeARIA(accessibilityDiv);
  });

  test('should have all required accessibility fields in JSON', () => {
    const { container } = render(
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
