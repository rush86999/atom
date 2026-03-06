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

// Re-export all utility modules
export * from './types';
export * from './async-utils';
export * from './mock-factories';
export * from './assertions';
export * from './cleanup';
export * from './platform-guards';
