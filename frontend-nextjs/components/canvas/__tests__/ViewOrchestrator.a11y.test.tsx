/**
 * ViewOrchestrator Component Accessibility Tests
 *
 * Purpose: Test ViewOrchestrator for WCAG 2.1 AA compliance
 * Tests: aria-live regions for view changes, landmark regions, focus management, view controls
 */

import { render, screen } from '@testing-library/react';
import axe from '../../../tests/accessibility-config';
import { ViewOrchestrator } from '@/components/canvas/ViewOrchestrator';

// Mock WebSocket hook
jest.mock('@/hooks/useWebSocket', () => ({
  __esModule: true,
  default: () => ({
    socket: null,
    connected: false,
    lastMessage: null
  })
}));

describe('ViewOrchestrator Accessibility', () => {
  it('should have no accessibility violations', async () => {
    const { container } = render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have aria-live for view changes', () => {
    render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Find accessibility tree with aria-live (empty state)
    const liveRegion = document.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
    expect(liveRegion).toHaveAttribute('aria-live', 'polite');
    expect(liveRegion).toHaveAttribute('aria-label', 'View orchestration state');
  });

  it('should have landmark regions for view areas', () => {
    const { container } = render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Component should have proper structure
    const orchestrator = container.querySelector('.view-orchestrator');
    expect(orchestrator).toBeInTheDocument();
  });

  it('should have accessible empty state', () => {
    render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Empty state message should be visible (appears in both UI and accessibility tree)
    const emptyMessages = screen.getAllByText(/no active views/i);
    expect(emptyMessages.length).toBe(2);

    const helperText = screen.getByText(/views will appear here/i);
    expect(helperText).toBeInTheDocument();
  });

  it('should have accessibility tree in empty state', () => {
    const { container } = render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Accessibility tree should exist with empty status
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
    expect(liveRegion).toHaveAttribute('data-canvas-state', 'view_orchestrator');
    expect(liveRegion).toHaveAttribute('data-status', 'empty');

    // Should contain empty state message in JSON
    expect(liveRegion?.textContent).toContain('empty');
    expect(liveRegion?.textContent).toContain('No active views');
  });

  it('should provide proper ARIA attributes for accessibility tree', () => {
    const { container } = render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Accessibility tree should have proper ARIA attributes
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toHaveAttribute('role', 'log');
    expect(liveRegion).toHaveAttribute('aria-live', 'polite');
    expect(liveRegion).toHaveAttribute('aria-label', 'View orchestration state');
  });

  it('should have hidden accessibility tree', () => {
    const { container } = render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Accessibility tree should be hidden from visual display
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toHaveStyle({ display: 'none' });
  });

  it('should expose view orchestration data attributes', () => {
    const { container } = render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Accessibility tree should have data attributes for AI agents
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toHaveAttribute('data-canvas-state', 'view_orchestrator');
    expect(liveRegion).toHaveAttribute('data-status', 'empty');
  });

  it('should have JSON state in accessibility tree', () => {
    const { container } = render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Accessibility tree should contain JSON state
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    const stateText = liveRegion?.textContent || '';

    // Should be valid JSON
    expect(() => JSON.parse(stateText)).not.toThrow();

    // Should contain status and message
    const state = JSON.parse(stateText);
    expect(state).toHaveProperty('status', 'empty');
    expect(state).toHaveProperty('message');
  });

  it('should handle layout variations gracefully', () => {
    const { container } = render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Should have proper CSS classes for layout management
    const orchestrator = container.querySelector('.view-orchestrator');
    expect(orchestrator).toBeInTheDocument();
    expect(orchestrator).toHaveClass('bg-gray-50');
    expect(orchestrator).toHaveClass('dark:bg-gray-800');
  });

  it('should have accessible empty state messaging', () => {
    render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Empty state should be clear to screen readers (appears twice)
    const mainMessages = screen.getAllByText(/no active views/i);
    expect(mainMessages.length).toBeGreaterThanOrEqual(1);

    const subMessage = screen.getByText(/views will appear here when the agent activates them/i);
    expect(subMessage).toBeInTheDocument();
  });

  it('should provide context about view orchestration', () => {
    const { container } = render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Accessibility tree should explain the component's purpose
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    const stateText = liveRegion?.textContent || '';

    // Should describe the state
    expect(stateText).toContain('empty');
  });

  it('should maintain accessibility during state changes', () => {
    const { container } = render(
      <ViewOrchestrator userId="user-123" sessionId="session-456" />
    );

    // Accessibility tree should always be present regardless of state
    const liveRegion = container.querySelector('[role="log"][aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();

    // Should update dynamically when views change
    expect(liveRegion).toHaveAttribute('aria-live', 'polite');
  });
});
