/**
 * Custom Assertion Helpers for Cross-Platform Testing
 *
 * Shared assertion utilities that work across web (React), mobile (React Native),
 * and desktop (Electron/Tauri) testing environments.
 *
 * These helpers provide semantic wrappers around Jest's expect() API with
 * improved readability and consistent error messages across platforms.
 *
 * @module @atom/test-utils/assertions
 */

// ============================================================================
// Error Assertion Helpers
// ============================================================================

/**
 * Assert that a function throws a specific error
 * Semantic wrapper for expect(fn).toThrow() with consistent error messages
 *
 * @param fn - Function to test (should throw when called)
 * @param errorMessage - Expected error message (optional, partial match)
 * @returns void
 *
 * @example
 * assertThrows(() => {
 *   throw new Error('Test error');
 * }, 'Test error');
 *
 * @example
 * assertThrows(() => {
 *   throw new Error('Validation failed: invalid input');
 * }, 'Validation failed');
 *
 * @example
 * // Without error message check
 * assertThrows(() => {
 *   throw new Error('Any error');
 * });
 */
export const assertThrows = (
  fn: () => void,
  errorMessage?: string
): void => {
  expect(fn).toThrow(errorMessage);
};

/**
 * Assert that an async function rejects with a specific error
 * Semantic wrapper for expect(fn).rejects.toThrow() with consistent async patterns
 *
 * @param fn - Async function to test (should reject when called)
 * @param errorMessage - Expected error message (optional, partial match)
 * @returns Promise<void>
 *
 * @example
 * await assertRejects(async () => {
 *   throw new Error('Async error');
 * }, 'Async error');
 *
 * @example
 * // Test API error handling
 * await assertRejects(
 *   () => fetchUser('invalid-id'),
 *   'User not found'
 * );
 *
 * @example
 * // Without error message check
 * await assertRejects(async () => {
 *   throw new Error('Any error');
 * });
 */
export const assertRejects = async (
  fn: () => Promise<unknown>,
  errorMessage?: string
): Promise<void> => {
  await expect(fn).rejects.toThrow(errorMessage);
};

// ============================================================================
// Render Assertion Helpers
// ============================================================================

/**
 * Assert that a component renders without throwing
 * Validates component can mount successfully without errors
 *
 * NOTE: The 'render' function must be imported from the appropriate
 * testing library for your platform:
 * - Web: @testing-library/react
 * - Mobile: @testing-library/react-native
 * - Desktop: @testing-library/react (Electron/Tauri)
 *
 * @param component - React element to render
 * @returns void
 *
 * @example
 * import { render } from '@testing-library/react';
 * import { assertRendersWithoutThrow } from '@atom/test-utils/assertions';
 *
 * assertRendersWithoutThrow(<MyComponent />);
 *
 * @example
 * // With props
 * assertRendersWithoutThrow(
 *   <UserProfile name="John" email="john@example.com" />
 * );
 *
 * @example
 * // Platform-specific render import (React Native)
 * import { render } from '@testing-library/react-native';
 *
 * assertRendersWithoutThrow(<MobileScreen />);
 */
export const assertRendersWithoutThrow = (
  component: React.ReactElement
): void => {
  // NOTE: render must be imported from platform-specific library
  // This assertion validates the component can mount without errors
  expect(() => {
    // TypeScript will error if render is not imported
    // @ts-ignore - Platform-specific render function
    const render = require('@testing-library/react').render ||
                   require('@testing-library/react-native').render;
    render(component);
  }).not.toThrow();
};

/**
 * Assert that a component renders without throwing (explicit render function)
 * Alternative version that accepts render function as parameter for flexibility
 *
 * @param component - React element to render
 * @param renderFn - Render function from appropriate testing library
 * @returns void
 *
 * @example
 * import { render } from '@testing-library/react';
 *
 * assertRendersWithRender(
 *   <MyComponent />,
 *   render
 * );
 *
 * @example
 * // Mobile (React Native)
 * import { render } from '@testing-library/react-native';
 *
 * assertRendersWithRender(<MobileScreen />, render);
 */
export const assertRendersWithRender = (
  component: React.ReactElement,
  renderFn: (component: React.ReactElement) => unknown
): void => {
  expect(() => renderFn(component)).not.toThrow();
};
