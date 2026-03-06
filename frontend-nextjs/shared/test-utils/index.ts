/**
 * Shared Test Utilities for Atom
 *
 * Platform-agnostic test helpers shared across:
 * - Frontend (Next.js with @testing-library/react)
 * - Mobile (React Native with @testing-library/react-native)
 * - Desktop (Tauri with cargo test - JSON fixtures only)
 *
 * Import via: @atom/test-utils
 *
 * @example
 * import { waitForAsync, createMockWebSocket } from '@atom/test-utils';
 *
 * @module @atom/test-utils
 */

// ============================================================================
// Type Definitions
// ============================================================================
export * from './types';

// ============================================================================
// Async Utilities (Plan 02)
// ============================================================================
export {
  waitForAsync,
  flushPromises,
  waitForCondition,
  wait,
  advanceTimersByTime,
  advanceTimersByTimeSync,
} from './async-utils';
export * from './async-utils';

// ============================================================================
// Mock Factory Functions (Plan 03)
// ============================================================================
export {
  createMockWebSocket,
  createMockFn,
  createMockAsyncFn,
} from './mock-factories';
export * from './mock-factories';

// ============================================================================
// Assertion Helpers (Plan 03)
// ============================================================================
export {
  assertThrows,
  assertRejects,
  assertRendersWithoutThrow,
  assertRendersWithRender,
} from './assertions';
export * from './assertions';

// ============================================================================
// Cleanup Utilities (Plan 04)
// ============================================================================
export {
  resetAllMocks,
  setupFakeTimers,
  cleanupTest,
  cleanupTestWithReset,
  clearAllTimers,
  restoreRealTimers,
  resetAllModules,
  cleanupAsyncTest,
  cleanupWithFakeTimers,
} from './cleanup';
export * from './cleanup';

// ============================================================================
// Platform Guards (Plan 04)
// ============================================================================
export {
  isWeb,
  isReactNative,
  isTauri,
  isIOS,
  isAndroid,
  skipIfNotWeb,
  skipIfNotReactNative,
  skipIfNotTauri,
  testEachPlatform,
  skipOnPlatform,
  onlyOnPlatform,
} from './platform-guards';
export * from './platform-guards';

// ============================================================================
// Test Data Fixtures (Plan 05a)
// ============================================================================
export {
  mockAgents,
  mockWorkflows,
  mockUser,
  testDataFixture,
} from './test-data';
export * from './test-data';
