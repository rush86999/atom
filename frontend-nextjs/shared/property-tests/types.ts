/**
 * Shared Type Definitions for Property Tests
 *
 * Centralized types for property-based testing across all platforms.
 * These types ensure consistency when testing invariants in canvas state,
 * agent maturity, and serialization behaviors.
 *
 * @module property-tests/types
 */

/**
 * Canvas state machine states.
 *
 * Canvas lifecycle: idle → presenting → submitted/closed/error → idle
 *
 * @example
 * ```ts
 * const state: CanvasState = 'idle';
 * const transitions = VALID_CANVAS_TRANSITIONS[state];
 * ```
 */
export type CanvasState = 'idle' | 'presenting' | 'submitted' | 'closed' | 'error';

/**
 * Agent maturity levels following governance framework.
 *
 * Progression: STUDENT → INTERN → SUPERVISED → AUTONOMOUS
 *
 * @example
 * ```ts
 * const level: AgentMaturityLevel = 'INTERN';
 * const index = MATURITY_ORDER.indexOf(level);
 * ```
 */
export type AgentMaturityLevel = 'STUDENT' | 'INTERN' | 'SUPERVISED' | 'AUTONOMOUS';

/**
 * Property test configuration.
 *
 * Controls test execution parameters for reproducible runs.
 *
 * @example
 * ```ts
 * const config: PropertyTestConfig = {
 *   numRuns: 100,
 *   timeout: 10000,
 *   seed: 12345
 * };
 * ```
 */
export interface PropertyTestConfig {
  /** Number of test cases to generate (default: 100) */
  numRuns: number;
  /** Timeout per test case in milliseconds (default: 10000) */
  timeout: number;
  /** Random seed for reproducible runs (undefined = random) */
  seed?: number;
}

/**
 * Valid canvas state transitions.
 *
 * Defines the state machine for canvas lifecycle:
 * - idle: Starting state, can present or error
 * - presenting: Active presentation, can submit, close, or error
 * - submitted: Terminal state, must reset to idle
 * - closed: Terminal state, must reset to idle
 * - error: Recoverable, can retry or reset
 *
 * @example
 * ```ts
 * const allowed = VALID_CANVAS_TRANSITIONS['idle']; // ['presenting', 'error']
 * const isValid = allowed.includes('presenting'); // true
 * ```
 */
export const VALID_CANVAS_TRANSITIONS: Record<CanvasState, CanvasState[]> = {
  idle: ['presenting', 'error'],
  presenting: ['submitted', 'closed', 'error'],
  submitted: ['idle'],
  closed: ['idle'],
  error: ['idle', 'presenting'],
};

/**
 * Agent maturity progression order.
 *
 * Defines the linear progression from STUDENT to AUTONOMOUS.
 * Used for monotonic progression validation.
 *
 * @example
 * ```ts
 * const currentIndex = MATURITY_ORDER.indexOf('INTERN'); // 1
 * const nextIndex = currentIndex + 1;
 * const nextLevel = MATURITY_ORDER[nextIndex]; // 'SUPERVISED'
 * ```
 */
export const MATURITY_ORDER: AgentMaturityLevel[] = [
  'STUDENT',
  'INTERN',
  'SUPERVISED',
  'AUTONOMOUS',
];

/**
 * Agent maturity state transitions.
 *
 * Defines valid maturity level transitions following governance rules:
 * - STUDENT: Can progress to INTERN only
 * - INTERN: Can progress to SUPERVISED only
 * - SUPERVISED: Can progress to AUTONOMOUS only
 * - AUTONOMOUS: Terminal state (no higher level)
 *
 * Invariant: Maturity levels only increase (never decrease).
 *
 * @example
 * ```ts
 * const allowed = MATURITY_TRANSITIONS['STUDENT']; // ['INTERN']
 * const canSkip = allowed.includes('AUTONOMOUS'); // false
 * ```
 */
export const MATURITY_TRANSITIONS: Record<AgentMaturityLevel, AgentMaturityLevel[]> = {
  STUDENT: ['INTERN'],
  INTERN: ['SUPERVISED'],
  SUPERVISED: ['AUTONOMOUS'],
  AUTONOMOUS: [], // Terminal state
};

/**
 * Canvas state metadata for testing.
 *
 * Additional information about canvas states for invariant validation.
 */
export interface CanvasStateMetadata {
  /** State identifier */
  state: CanvasState;
  /** Whether state is terminal (no outgoing transitions except to idle) */
  isTerminal: boolean;
  /** Whether state allows user interaction */
  isInteractive: boolean;
  /** Whether state is recoverable (can transition without full reset) */
  isRecoverable: boolean;
}

/**
 * Agent maturity metadata for testing.
 *
 * Additional information about maturity levels for governance validation.
 */
export interface AgentMaturityMetadata {
  /** Maturity level */
  level: AgentMaturityLevel;
  /** Numerical rank (higher = more autonomy) */
  rank: number;
  /** Whether level is terminal (AUTONOMOUS) */
  isTerminal: boolean;
  /** Whether automated triggers are allowed */
  allowsAutomation: boolean;
}

/**
 * Canvas state metadata lookup table.
 *
 * Provides metadata for each canvas state.
 */
export const CANVAS_STATE_METADATA: Record<CanvasState, CanvasStateMetadata> = {
  idle: {
    state: 'idle',
    isTerminal: false,
    isInteractive: false,
    isRecoverable: true,
  },
  presenting: {
    state: 'presenting',
    isTerminal: false,
    isInteractive: true,
    isRecoverable: true,
  },
  submitted: {
    state: 'submitted',
    isTerminal: true,
    isInteractive: false,
    isRecoverable: false,
  },
  closed: {
    state: 'closed',
    isTerminal: true,
    isInteractive: false,
    isRecoverable: false,
  },
  error: {
    state: 'error',
    isTerminal: false,
    isInteractive: false,
    isRecoverable: true,
  },
};

/**
 * Agent maturity metadata lookup table.
 *
 * Provides metadata for each maturity level.
 */
export const MATURITY_METADATA: Record<AgentMaturityLevel, AgentMaturityMetadata> = {
  STUDENT: {
    level: 'STUDENT',
    rank: 0,
    isTerminal: false,
    allowsAutomation: false,
  },
  INTERN: {
    level: 'INTERN',
    rank: 1,
    isTerminal: false,
    allowsAutomation: false, // Proposal-only
  },
  SUPERVISED: {
    level: 'SUPERVISED',
    rank: 2,
    isTerminal: false,
    allowsAutomation: true, // Under supervision
  },
  AUTONOMOUS: {
    level: 'AUTONOMOUS',
    rank: 3,
    isTerminal: true,
    allowsAutomation: true, // Full execution
  },
};
