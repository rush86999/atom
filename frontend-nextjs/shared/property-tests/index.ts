/**
 * Cross-Platform Property Tests
 *
 * Shared property-based tests using FastCheck for invariant validation
 * across frontend (Next.js), mobile (React Native), and desktop (Tauri).
 *
 * Property tests verify invariants (always-true properties) rather than
 * specific examples, catching edge cases that example-based tests miss.
 *
 * Usage:
 *   import { canvasStateMachineProperty } from '@atom/property-tests';
 *   fc.assert(canvasStateMachineProperty);
 *
 * @see https://github.com/dubzzz/fast-check
 */

// Canvas state machine invariants
export * from './canvas-invariants';

// Agent maturity state machine invariants
export * from './agent-maturity-invariants';

// Serialization roundtrip invariants
export * from './serialization-invariants';

// Shared types
export * from './types';

// Shared configuration
export * from './config';
