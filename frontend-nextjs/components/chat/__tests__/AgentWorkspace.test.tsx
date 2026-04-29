/**
 * AgentWorkspace Component Tests
 *
 * Tests verify AgentWorkspace renders workspace layout with sections,
 * handles loading/empty states, and displays agent steps.
 *
 * Source: components/chat/AgentWorkspace.tsx (51 lines, 0% coverage)
 */

import React from 'react';
import { renderWithProviders, screen } from '../../../tests/test-utils';
import AgentWorkspace from '../AgentWorkspace';

describe('AgentWorkspace', () => {
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
});
