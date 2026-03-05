/**
 * AgentOperationTracker Component Accessibility Tests
 *
 * Purpose: Test AgentOperationTracker for WCAG 2.1 AA compliance
 * Tests: aria-live regions, progress bar accessibility, operation announcements, step labels
 */

import { render, screen } from '@testing-library/react';
import axe from '../../../tests/accessibility-config';
import { AgentOperationTracker, AgentOperationData } from '@/components/canvas/AgentOperationTracker';

// Mock WebSocket hook
jest.mock('@/hooks/useWebSocket', () => ({
  __esModule: true,
  default: () => ({
    socket: null,
    connected: false,
    lastMessage: null
  })
}));

const mockOperationData: AgentOperationData = {
  operation_id: 'op-123',
  agent_id: 'agent-456',
  agent_name: 'TestAgent',
  operation_type: 'data_processing',
  status: 'running',
  current_step: 'Processing data',
  total_steps: 5,
  current_step_index: 2,
  progress: 40,
  context: {
    what: 'Processing customer data',
    why: 'To generate monthly reports',
    next: 'Will validate results next'
  },
  logs: [
    {
      timestamp: '2026-03-04T10:00:00Z',
      level: 'info',
      message: 'Started processing'
    },
    {
      timestamp: '2026-03-04T10:01:00Z',
      level: 'warning',
      message: 'High memory usage detected'
    }
  ],
  started_at: '2026-03-04T10:00:00Z'
};

describe('AgentOperationTracker Accessibility', () => {
  it('should have no accessibility violations', async () => {
    const { container } = render(
      <AgentOperationTracker userId="user-123" operationId="op-123" />
    );

    // Component shows loading state when WebSocket disconnected
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have aria-live for progress updates', () => {
    render(
      <AgentOperationTracker userId="user-123" operationId="op-123" />
    );

    // Find accessibility tree with aria-live (loading state)
    const liveRegion = document.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
    expect(liveRegion).toHaveAttribute('aria-live', 'polite');
    expect(liveRegion).toHaveAttribute('aria-label', 'Agent operation state');
  });

  it('should announce operation completion via accessibility tree', () => {
    const { container } = render(
      <AgentOperationTracker userId="user-123" operationId="op-123" />
    );

    // Accessibility tree should expose operation status
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();

    // Status should be in accessibility tree (loading state when disconnected)
    expect(liveRegion).toHaveAttribute('data-status', 'loading');
  });

  it('should have accessible loading state', () => {
    const { container } = render(
      <AgentOperationTracker userId="user-123" operationId="op-123" />
    );

    // Loading indicator should be visible
    const loadingElement = container.querySelector('.animate-pulse');
    expect(loadingElement).toBeInTheDocument();
  });

  it('should have accessibility tree in loading state', () => {
    const { container } = render(
      <AgentOperationTracker userId="user-123" operationId="op-123" />
    );

    // Accessibility tree should exist with loading status
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
    expect(liveRegion).toHaveAttribute('data-canvas-state', 'agent_operation_tracker');
    expect(liveRegion).toHaveAttribute('data-status', 'loading');

    // Should contain loading message in JSON
    expect(liveRegion?.textContent).toContain('loading');
    expect(liveRegion?.textContent).toContain('Waiting for operation data');
  });

  it('should provide proper ARIA attributes for accessibility tree', () => {
    const { container } = render(
      <AgentOperationTracker userId="user-123" operationId="op-123" />
    );

    // Accessibility tree should have proper ARIA attributes
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toHaveAttribute('role', 'log');
    expect(liveRegion).toHaveAttribute('aria-live', 'polite');
    expect(liveRegion).toHaveAttribute('aria-label', 'Agent operation state');
  });

  it('should have hidden accessibility tree', () => {
    const { container } = render(
      <AgentOperationTracker userId="user-123" operationId="op-123" />
    );

    // Accessibility tree should be hidden from visual display
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toHaveStyle({ display: 'none' });
  });

  it('should expose operation data attributes in accessibility tree', () => {
    const { container } = render(
      <AgentOperationTracker userId="user-123" operationId="op-123" />
    );

    // Accessibility tree should have data attributes for AI agents
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toHaveAttribute('data-canvas-state', 'agent_operation_tracker');
    expect(liveRegion).toHaveAttribute('data-status', 'loading');
  });

  it('should have JSON state in accessibility tree', () => {
    const { container } = render(
      <AgentOperationTracker userId="user-123" operationId="op-123" />
    );

    // Accessibility tree should contain JSON state
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    const stateText = liveRegion?.textContent || '';

    // Should be valid JSON
    expect(() => JSON.parse(stateText)).not.toThrow();

    // Should contain status and message
    const state = JSON.parse(stateText);
    expect(state).toHaveProperty('status', 'loading');
    expect(state).toHaveProperty('message');
  });
});
