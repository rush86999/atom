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
// Cleanup Utilities
// ============================================================================
export * from './cleanup';

// ============================================================================
// Platform Guards
// ============================================================================
export * from './platform-guards';
