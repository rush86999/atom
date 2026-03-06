/**
 * Test Cleanup and Mock Reset Utilities
 *
 * Comprehensive test isolation helpers for ensuring clean test state.
 * Works across web, mobile, and desktop testing environments.
 *
 * @module @atom/test-utils/cleanup
 */

/**
 * Reset all mocks and timers to clean state
 * Call in beforeEach for consistent test isolation
 *
 * Resets:
 * - Jest mocks (clearAllMocks)
 * - Jest timers (clearAllTimers)
 * - Fake timers (useRealTimers)
 * - Expo module mocks (MMKV, AsyncStorage, SecureStore)
 *
 * @example
 * beforeEach(() => {
 *   resetAllMocks();
 * });
 *
 * @example
 * // In your test file
 * describe('MyComponent', () => {
 *   beforeEach(() => {
 *     resetAllMocks(); // Ensure clean state for each test
 *   });
 *
 *   it('should work correctly', () => {
 *     // Test with fresh mocks
 *   });
 * });
 */
export const resetAllMocks = (): void => {
  jest.clearAllMocks();
  jest.clearAllTimers();
  jest.useRealTimers();

  // Reset Expo module mocks (mobile-specific but safe to check globally)
  if (typeof global !== 'undefined' && (global as any).__resetMmkvMock) {
    (global as any).__resetMmkvMock();
  }
  if (typeof global !== 'undefined' && (global as any).__resetAsyncStorageMock) {
    (global as any).__resetAsyncStorageMock();
  }
  if (typeof global !== 'undefined' && (global as any).__resetSecureStoreMock) {
    (global as any).__resetSecureStoreMock();
  }
};

/**
 * Setup fake timers for async tests
 * Call in beforeEach for tests using setTimeout/setInterval
 *
 * Configures Jest fake timers with doNotFake option:
 * - requestAnimationFrame: Not faked (performance-critical)
 * - performance: Not faked (performance.now() needs real values)
 *
 * @example
 * beforeEach(() => {
 *   setupFakeTimers();
 * });
 *
 * afterEach(() => {
 *   jest.useRealTimers();
 * });
 *
 * @example
 * // Testing setTimeout/setInterval
 * beforeEach(() => {
 *   setupFakeTimers();
 * });
 *
 * it('should debounce input', () => {
 *   const debouncedFn = jest.fn();
 *   const debounced = debounce(debouncedFn, 300);
 *
 *   debounced();
 *   jest.advanceTimersByTime(300);
 *
 *   expect(debouncedFn).toHaveBeenCalledTimes(1);
 * });
 */
export const setupFakeTimers = (): void => {
  jest.useFakeTimers({
    doNotFake: ['requestAnimationFrame', 'performance'],
  });
};

/**
 * Clean up all mocks and restore platform/device state
 * Call this in afterEach() blocks
 *
 * Performs cleanup in order:
 * 1. Restores platform state (if restorePlatform available)
 * 2. Restores device state (if restoreDevice available)
 * 3. Clears all Jest mocks
 *
 * Note: restorePlatform and restoreDevice are from platform-guards module
 * They will only be available if imported and called explicitly
 *
 * @example
 * afterEach(() => {
 *   cleanupTest();
 * });
 *
 * @example
 * // With platform mocking
 * import { mockPlatform } from '@atom/test-utils/platform-guards';
 *
 * afterEach(() => {
 *   cleanupTest(); // Restores platform state
 * });
 */
export const cleanupTest = (): void => {
  // Restore platform state if available (from platform-guards module)
  // Note: These functions must be imported separately
  if (typeof (restorePlatform as any) === 'function') {
    (restorePlatform as any)();
  }

  // Restore device state if available (from platform-guards module)
  if (typeof (restoreDevice as any) === 'function') {
    (restoreDevice as any)();
  }

  jest.clearAllMocks();
};

/**
 * Clean up all mocks and reset modules
 * More thorough cleanup, use between tests that share modules
 *
 * Performs cleanup in order:
 * 1. Calls cleanupTest() (platform, device, mocks)
 * 2. Resets Jest module cache (resetModules)
 *
 * Use this when:
 * - Tests share module singletons
 * - You need fresh module instances
 * - Testing module initialization logic
 *
 * @example
 * afterEach(() => {
 *   cleanupTestWithReset();
 * });
 *
 * @example
 * // Testing singleton module
 * import { singletonModule } from './singleton';
 *
 * afterEach(() => {
 *   cleanupTestWithReset(); // Ensures fresh singleton instance
 * });
 *
 * it('should initialize correctly', () => {
 *   expect(singletonModule.state).toBe('initial');
 * });
 */
export const cleanupTestWithReset = (): void => {
  cleanupTest();
  jest.resetModules();
};

/**
 * Clear all timers without resetting mocks
 * Use in afterEach when you need to keep mock call history
 *
 * @example
 * afterEach(() => {
 *   clearAllTimers();
 * });
 */
export const clearAllTimers = (): void => {
  jest.clearAllTimers();
  jest.useRealTimers();
};

/**
 * Restore real timers after fake timer setup
 * Use in afterEach to clean up fake timers
 *
 * @example
 * afterEach(() => {
 *   restoreRealTimers();
 * });
 */
export const restoreRealTimers = (): void => {
  jest.useRealTimers();
};

/**
 * Reset all modules in Jest cache
 * Use sparingly - it's expensive but sometimes necessary
 *
 * Use this when:
 * - Testing module-level side effects
 * - Need fresh module instances
 * - Mocking module imports
 *
 * @example
 * afterEach(() => {
 *   resetAllModules();
 * });
 */
export const resetAllModules = (): void => {
  jest.resetModules();
};

/**
 * Comprehensive cleanup for async tests
 * Combines timer cleanup with mock reset
 *
 * @example
 * afterEach(async () => {
 *   await cleanupAsyncTest();
 * });
 */
export const cleanupAsyncTest = async (): Promise<void> => {
  jest.clearAllTimers();
  jest.useRealTimers();
  jest.clearAllMocks();
  await new Promise(resolve => setImmediate(resolve));
};

/**
 * Cleanup for tests using fake timers and promises
 * Ensures all pending promises are flushed
 *
 * @example
 * afterEach(async () => {
 *   await cleanupWithFakeTimers();
 * });
 */
export const cleanupWithFakeTimers = async (): Promise<void> => {
  jest.runAllTimers();
  await new Promise(resolve => setImmediate(resolve));
  jest.clearAllTimers();
  jest.useRealTimers();
  jest.clearAllMocks();
};
