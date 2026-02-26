/**
 * Canvas Accessibility Tree Test Utilities
 *
 * Shared helper functions for testing canvas accessibility trees.
 * These utilities verify that canvas components render hidden divs
 * with role="log" for AI agent consumption.
 */

import { within } from '@testing-library/react';
import type { AgentOperationData } from '../AgentOperationTracker';

/**
 * Query helper for accessibility tree elements
 * @param container - The DOM container to query
 * @returns The first element with role="log" or null
 */
export const getAccessibilityTree = (container: HTMLElement): HTMLElement | null => {
  return container.querySelector('[role="log"]');
};

/**
 * Parse JSON state from accessibility element textContent
 * @param element - The accessibility element (role="log" div)
 * @returns Parsed JSON object or null if parsing fails
 */
export const parseCanvasState = (element: HTMLElement | null): any | null => {
  if (!element) return null;
  const text = element.textContent || '';
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
};

/**
 * Assert that canvas data attributes are present on an element
 * @param element - The DOM element to check
 * @param expectedAttrs - Object mapping attribute names to expected values
 */
export const assertCanvasDataAttributes = (
  element: HTMLElement,
  expectedAttrs: Record<string, string | number | boolean>
): void => {
  Object.entries(expectedAttrs).forEach(([key, value]) => {
    expect(element).toHaveAttribute(`data-${key}`, String(value));
  });
};

/**
 * Factory for creating mock AgentOperationData
 * @param overrides - Partial data to override defaults
 * @returns Complete AgentOperationData object for testing
 */
export const createMockOperationData = (
  overrides: Partial<AgentOperationData> = {}
): AgentOperationData => ({
  operation_id: 'test-op-123',
  agent_id: 'test-agent-456',
  agent_name: 'TestAgent',
  operation_type: 'test_operation',
  status: 'running',
  current_step: 'Processing test data',
  current_step_index: 1,
  total_steps: 5,
  progress: 20,
  context: {
    what: 'Testing accessibility tree',
    why: 'Verify AI agents can read canvas state',
    next: 'Complete test suite'
  },
  logs: [],
  started_at: new Date().toISOString(),
  ...overrides
});

/**
 * Mock WebSocket for canvas component tests
 * @returns Mock socket object with addEventListener/removeEventListener
 */
export const mockWebSocket = () => ({
  socket: {
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    send: jest.fn()
  },
  connected: false
});

/**
 * Query all accessibility tree elements in a container
 * @param container - The DOM container to query
 * @returns Array of all elements with role="log"
 */
export const getAllAccessibilityTrees = (container: HTMLElement): HTMLElement[] => {
  return Array.from(container.querySelectorAll('[role="log"]'));
};

/**
 * Get canvas state by canvas ID from accessibility tree
 * @param container - The DOM container to query
 * @param canvasId - The canvas ID to filter by
 * @returns Parsed canvas state or null if not found
 */
export const getCanvasStateById = (
  container: HTMLElement,
  canvasId: string
): any | null => {
  const elements = getAllAccessibilityTrees(container);
  for (const element of elements) {
    if (element.getAttribute('data-canvas-id') === canvasId) {
      return parseCanvasState(element);
    }
  }
  return null;
};

/**
 * Assert that accessibility tree has required ARIA attributes
 * @param element - The accessibility element to check
 */
export const assertAccessibilityTreeARIA = (element: HTMLElement | null): void => {
  expect(element).toBeInTheDocument();
  expect(element).toHaveAttribute('role', 'log');
  expect(element).toHaveAttribute('aria-live', 'polite');
  expect(element?.textContent).toBeDefined();
};

/**
 * Assert that JSON state contains required fields
 * @param state - Parsed JSON state object
 * @param requiredFields - Array of required field names
 */
export const assertCanvasStateFields = (
  state: any,
  requiredFields: string[]
): void => {
  requiredFields.forEach(field => {
    expect(state).toHaveProperty(field);
  });
};
