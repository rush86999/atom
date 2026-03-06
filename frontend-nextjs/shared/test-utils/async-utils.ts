/**
 * Platform-Agnostic Async Utilities for Testing
 *
 * Async utility functions shared across web, mobile, and desktop platforms.
 * These utilities work with both @testing-library/react and @testing-library/react-native.
 *
 * **Platform Compatibility:**
 * - ✅ Web (jsdom, @testing-library/react)
 * - ✅ Mobile (React Native, @testing-library/react-native)
 * - ✅ Desktop (Tauri - JSON fixture testing only)
 *
 * **Key Features:**
 * - waitFor with default timeout for async assertions
 * - flushPromises for Jest fake timer support
 * - waitForCondition for polling-based conditions
 * - Timer advancement utilities (async + sync)
 * - Simple setTimeout wrapper (wait)
 *
 * @module @atom/test-utils/async-utils
 *
 * @example
 * import { waitForAsync, flushPromises, waitForCondition } from '@atom/test-utils';
 *
 * // Wait for async UI update
 * await waitForAsync(() => {
 *   expect(getByText('Loaded')).toBeTruthy();
 * });
 *
 * // Flush pending promises with fake timers
 * jest.useFakeTimers();
 * await flushPromises();
 *
 * // Poll for custom condition
 * await waitForCondition(() => result.current.connected === true);
 */

// ============================================================================
// waitForAsync
// ============================================================================

/**
 * Wrapper around waitFor with default 3000ms timeout
 *
 * Platform-agnostic wrapper that works with both:
 * - @testing-library/react's waitFor (web)
 * - @testing-library/react-native's waitFor (mobile)
 *
 * Uses runtime import to avoid platform-specific dependency issues at build time.
 *
 * @param callback - Async callback function to wait for
 * @param timeout - Timeout in milliseconds (default: 3000ms)
 *
 * @throws Error if timeout is exceeded
 *
 * @example
 * // Web (jsdom) with @testing-library/react
 * await waitForAsync(() => {
 *   expect(screen.getByText('Loaded')).toBeTruthy();
 * });
 *
 * @example
 * // Mobile (React Native) with @testing-library/react-native
 * await waitForAsync(() => {
 *   expect(getByText('Loaded')).toBeTruthy();
 * });
 *
 * @example
 * // Custom timeout for slow operations
 * await waitForAsync(() => {
 *   expect(mockFunction).toHaveBeenCalled();
 * }, 5000); // 5 second timeout
 */
export const waitForAsync = async (
  callback: () => void,
  timeout: number = 3000
): Promise<void> => {
  // Runtime import to avoid platform-specific dependency issues
  // Works with both @testing-library/react and @testing-library/react-native
  const { waitFor } = await import('@testing-library/react');

  await waitFor(callback, { timeout });
};

// ============================================================================
// flushPromises
// ============================================================================

/**
 * Flush all pending promises in the fake timer queue
 *
 * Use with jest.useFakeTimers() for reliable async testing across all platforms.
 * Combines setImmediate (microtask queue) with jest.runAllTimers() (macro task queue).
 *
 * **When to use:**
 * - Testing async state updates (React useState, useEffect)
 * - Testing WebSocket message handling
 * - Testing promise-based API calls
 * - Any async operation that requires fake timers
 *
 * **Note:** Must be used with jest.useFakeTimers() for proper behavior.
 *
 * @returns Promise that resolves after all promises are flushed
 *
 * @example
 * jest.useFakeTimers();
 *
 * // Trigger async operation
 * act(() => {
 *   button.click();
 * });
 *
 * // Flush pending promises
 * await flushPromises();
 *
 * // Assert after promises resolved
 * expect(mockFunction).toHaveBeenCalled();
 *
 * jest.useRealTimers();
 */
export const flushPromises = async (): Promise<void> => {
  return new Promise(resolve => {
    setImmediate(resolve);
    jest.runAllTimers();
  });
};

// ============================================================================
// waitForCondition
// ============================================================================

/**
 * Wait for a condition to be true with polling and fake timer support
 *
 * Alternative to waitFor() when using fake timers. Polls a condition function
 * until it returns true or timeout is exceeded. Uses flushPromises internally
 * for Jest fake timer support.
 *
 * **When to use:**
 * - Testing custom conditions with fake timers
 * - Polling-based assertions (e.g., connection state, loading status)
 * - When waitFor() doesn't work well with fake timers
 *
 * @param condition - Function that returns boolean (true when condition is met)
 * @param timeout - Timeout in milliseconds (default: 5000ms)
 *
 * @throws Error if condition is not met within timeout
 *
 * @example
 * jest.useFakeTimers();
 *
 * // Wait for custom hook state update
 * await waitForCondition(() => result.current.connected === true);
 *
 * // Wait for loading state to clear
 * await waitForCondition(() => !result.current.isLoading);
 *
 * // Custom timeout for slow operations
 * await waitForCondition(
 *   () => mockSocket.readyState === WebSocket.OPEN,
 *   10000 // 10 second timeout
 * );
 *
 * jest.useRealTimers();
 */
export const waitForCondition = async (
  condition: () => boolean,
  timeout = 5000,
): Promise<void> => {
  const startTime = Date.now();

  while (!condition()) {
    if (Date.now() - startTime > timeout) {
      throw new Error(`Condition not met within ${timeout}ms`);
    }

    await flushPromises();
  }
};

// ============================================================================
// wait
// ============================================================================

/**
 * Simple setTimeout wrapper for waiting a specific amount of time
 *
 * Use for intentional delays in tests (e.g., testing debouncing, loading states).
 * Prefer waitForAsync or waitForCondition for most async operations.
 *
 * **When to use:**
 * - Testing debounce/throttle behavior
 * - Adding intentional delays for timing-related tests
 * - Testing loading states with minimum duration
 *
 * @param ms - Milliseconds to wait
 *
 * @returns Promise that resolves after specified delay
 *
 * @example
 * // Test debounce behavior
 * input.onChange('hello');
 * await wait(300); // Wait debounce period
 * expect(mockFunction).toHaveBeenCalledTimes(1);
 *
 * @example
 * // Test minimum loading duration
 * startLoading();
 * await wait(500); // Ensure loading shows for at least 500ms
 * stopLoading();
 */
export const wait = async (ms: number): Promise<void> => {
  return new Promise((resolve) => setTimeout(resolve, ms));
};

// ============================================================================
// advanceTimersByTime (async)
// ============================================================================

/**
 * Advance timers by a specific amount (async version with promise flushing)
 *
 * Combines jest.advanceTimersByTime() with flushPromises() for complete timer
 * advancement including pending promises. Use when tests need to advance time
 * AND resolve promises triggered by timer callbacks.
 *
 * **When to use:**
 * - Testing setTimeout/setInterval with async callbacks
 * - Advancing time while resolving timer-triggered promises
 * - Most async timer scenarios
 *
 * @param ms - Milliseconds to advance timers
 *
 * @returns Promise that resolves after timers advance and promises flush
 *
 * @example
 * jest.useFakeTimers();
 *
 * // Start a timer-based operation
 * startHeartbeat();
 *
 * // Advance time by 30 seconds and flush promises
 * await advanceTimersByTime(30000);
 *
 * // Assert after timer advanced and promises resolved
 * expect(heartbeatCallback).toHaveBeenCalledTimes(30);
 *
 * jest.useRealTimers();
 */
export const advanceTimersByTime = async (ms: number): Promise<void> => {
  jest.advanceTimersByTime(ms);
  await flushPromises();
};

// ============================================================================
// advanceTimersByTimeSync
// ============================================================================

/**
 * Advance timers by a specific amount (synchronous version)
 *
 * Synchronous timer advancement without promise flushing. Use when you need to
 * advance timers quickly without waiting for promise resolution.
 *
 * **When to use:**
 * - Fast-forwarding through large time periods (e.g., 30s heartbeat intervals)
 * - Testing timer-based logic without async callbacks
 * - Performance-critical tests where promise flushing isn't needed
 *
 * @param ms - Milliseconds to advance timers
 *
 * @example
 * jest.useFakeTimers();
 *
 * // Start heartbeat with 30s interval
 * startHeartbeat();
 *
 * // Fast-forward 30 seconds (no promise flushing needed)
 * advanceTimersByTimeSync(30000);
 *
 * // Assert timer callback was called
 * expect(heartbeatCallback).toHaveBeenCalledTimes(1);
 *
 * jest.useRealTimers();
 *
 * @example
 * // Multiple large advances (faster than async version)
 * advanceTimersByTimeSync(30000); // 30 seconds
 * advanceTimersByTimeSync(30000); // 60 seconds total
 * advanceTimersByTimeSync(30000); // 90 seconds total
 */
export const advanceTimersByTimeSync = (ms: number): void => {
  jest.advanceTimersByTime(ms);
};

// ============================================================================
// Platform-Agnostic Design Notes
// ============================================================================

/**
 * **Platform Compatibility Strategy:**
 *
 * 1. **No Platform-Specific APIs:**
 *    - ❌ No Platform.OS (React Native specific)
 *    - ❌ No window.document (DOM specific)
 *    - ❌ No Alert, Dimensions, etc. (React Native specific)
 *
 * 2. **Testing Library Agnostic:**
 *    - Uses runtime import for waitFor (works with both web and mobile)
 *    - Jest fake timers work across all platforms
 *    - setTimeout/setImmediate are standard JavaScript APIs
 *
 * 3. **Jest Fake Timer Support:**
 *    - flushPromises uses setImmediate + jest.runAllTimers()
 *    - Works consistently across jsdom (web) and React Native (mobile)
 *    - Enables deterministic async testing without real delays
 *
 * 4. **Pattern Matching:**
 *    - Extracted from mobile/src/__tests__/helpers/testUtils.ts (lines 203-315)
 *    - Same function signatures and behavior for consistency
 *    - JSDoc examples updated for platform-agnostic usage
 *
 * **Migration Notes:**
 * - Mobile tests can import from @atom/test-utils instead of ../../helpers/testUtils
 * - Function signatures match existing mobile utilities (drop-in replacement)
 * - Web tests can now use waitForAsync instead of creating custom wrappers
 */
