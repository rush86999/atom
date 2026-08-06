/**
 * Canvas State Machine Property Tests
 *
 * Property-based tests for canvas state machine invariants.
 * Tests verify that canvas transitions follow the defined state machine:
 * - idle → presenting, error
 * - presenting → submitted, closed, error
 * - submitted → idle
 * - closed → idle
 * - error → idle, presenting
 *
 * @module property-tests/canvas-invariants
 */

import * as fc from 'fast-check';
import { CanvasState, VALID_CANVAS_TRANSITIONS } from './types';

/**
 * Canvas state machine property.
 *
 * Verifies the transition table matches the documented canvas lifecycle:
 * idle → presenting/error, presenting → submitted/closed/error,
 * submitted/closed → idle, error → idle/presenting.
 *
 * @example
 * ```ts
 * fc.assert(canvasStateMachineProperty);
 * ```
 *
 * Invariant: every state's transition list matches the documented machine
 */
const EXPECTED_CANVAS_TRANSITIONS: Record<CanvasState, CanvasState[]> = {
  idle: ['presenting', 'error'],
  presenting: ['submitted', 'closed', 'error'],
  submitted: ['idle'],
  closed: ['idle'],
  error: ['idle', 'presenting'],
};

export const canvasStateMachineProperty = fc.property(
  fc.constantFrom(...Object.keys(VALID_CANVAS_TRANSITIONS) as CanvasState[]),
  (fromState) => {
    const actual = VALID_CANVAS_TRANSITIONS[fromState];
    const expected = EXPECTED_CANVAS_TRANSITIONS[fromState];

    // Same size and every documented destination present (no typos/drift)
    return (
      actual.length === expected.length &&
      expected.every((state) => actual.includes(state))
    );
  }
);

/**
 * Canvas no direct presenting to idle property.
 *
 * Tests that presenting cannot transition directly to idle.
 * Presenting must go through submitted or closed first.
 *
 * @example
 * ```ts
 * fc.assert(canvasNoDirectPresentingToIdle);
 * ```
 *
 * Invariant: presenting → idle is invalid (must go through submitted or closed)
 */
export const canvasNoDirectPresentingToIdle = fc.property(
  fc.constantFrom(...Object.keys(VALID_CANVAS_TRANSITIONS) as CanvasState[]),
  (fromState) => {
    if (fromState !== 'presenting') {
      return true; // Only test presenting state
    }

    const allowedTransitions = VALID_CANVAS_TRANSITIONS[fromState];

    // Presenting should not transition directly to idle
    return !allowedTransitions.includes('idle');
  }
);

/**
 * Canvas error recovery to idle property.
 *
 * Tests that error state can always recover to idle.
 * Error is non-terminal (unlike submitted/closed which end flow).
 *
 * @example
 * ```ts
 * fc.assert(canvasErrorRecoveryToIdle);
 * ```
 *
 * Invariant: error → idle is always valid (error is recoverable)
 */
export const canvasErrorRecoveryToIdle = fc.property(
  fc.constantFrom('idle' as CanvasState),
  (targetState) => {
    const errorState: CanvasState = 'error';
    const allowedTransitions = VALID_CANVAS_TRANSITIONS[errorState];

    // Error should allow recovery to idle
    return allowedTransitions.includes(targetState);
  }
);

/**
 * Canvas terminal states lead to idle property.
 *
 * Tests that submitted and closed always transition to idle.
 * Terminal states must reset to idle for new canvas.
 *
 * @example
 * ```ts
 * fc.assert(canvasTerminalStatesLeadToIdle);
 * ```
 *
 * Invariant: submitted → idle and closed → idle are always valid
 */
export const canvasTerminalStatesLeadToIdle = fc.property(
  fc.constantFrom('submitted' as CanvasState, 'closed' as CanvasState),
  (terminalState) => {
    const allowedTransitions = VALID_CANVAS_TRANSITIONS[terminalState];

    // Terminal states should lead to idle
    return allowedTransitions.includes('idle') && allowedTransitions.length === 1;
  }
);

/**
 * Canvas idle to presenting property.
 *
 * Tests that idle can transition to presenting.
 * Idle is the starting state for new canvas presentations.
 *
 * @example
 * ```ts
 * fc.assert(canvasIdleToPresenting);
 * ```
 *
 * Invariant: idle → presenting is always valid
 */
export const canvasIdleToPresenting = fc.property(
  fc.constantFrom('presenting' as CanvasState),
  (targetState) => {
    const idleState: CanvasState = 'idle';
    const allowedTransitions = VALID_CANVAS_TRANSITIONS[idleState];

    // Idle should allow presenting
    return allowedTransitions.includes(targetState);
  }
);

/**
 * Canvas presenting transitions property.
 *
 * Tests that presenting has exactly three valid transitions.
 * Presenting can go to submitted, closed, or error.
 *
 * @example
 * ```ts
 * fc.assert(canvasPresentingTransitions);
 * ```
 *
 * Invariant: presenting has exactly 3 transitions (submitted, closed, error)
 */
export const canvasPresentingTransitions = fc.property(
  fc.constantFrom('presenting' as CanvasState),
  (state) => {
    const allowedTransitions = VALID_CANVAS_TRANSITIONS[state];

    // Presenting should have exactly 3 transitions
    return allowedTransitions.length === 3 &&
           allowedTransitions.includes('submitted') &&
           allowedTransitions.includes('closed') &&
           allowedTransitions.includes('error');
  }
);

/**
 * Canvas error state recoverability property.
 *
 * Tests that error state is recoverable (non-terminal).
 * Error can transition to both idle and presenting.
 *
 * @example
 * ```ts
 * fc.assert(canvasErrorStateRecoverability);
 * ```
 *
 * Invariant: error state has 2 recovery paths (idle, presenting)
 */
export const canvasErrorStateRecoverability = fc.property(
  fc.constantFrom('error' as CanvasState),
  (state) => {
    const allowedTransitions = VALID_CANVAS_TRANSITIONS[state];

    // Error should have 2 recovery paths
    return allowedTransitions.length === 2 &&
           allowedTransitions.includes('idle') &&
           allowedTransitions.includes('presenting');
  }
);

/**
 * Canvas no terminal state loops property.
 *
 * Tests that terminal states (submitted, closed) cannot loop back.
 * Once terminal, canvas must go through idle to restart.
 *
 * @example
 * ```ts
 * fc.assert(canvasNoTerminalStateLoops);
 * ```
 *
 * Invariant: submitted/closed cannot transition to each other or themselves
 */
const TERMINAL_STATES: CanvasState[] = ['submitted', 'closed'];

export const canvasNoTerminalStateLoops = fc.property(
  fc.constantFrom(...TERMINAL_STATES),
  fc.constantFrom(...TERMINAL_STATES),
  (fromState, toState) => {
    const allowedTransitions = VALID_CANVAS_TRANSITIONS[fromState];

    // Terminal states never transition to themselves or to each other:
    // the only legal destination is idle.
    const loopsToTerminal = allowedTransitions.some((state) =>
      TERMINAL_STATES.includes(state)
    );
    if (loopsToTerminal) return false;

    // The sampled terminal-state destination must be rejected, and the
    // state must still have the idle escape hatch to restart the flow.
    return (
      !allowedTransitions.includes(toState) &&
      allowedTransitions.includes('idle')
    );
  }
);

/**
 * Canvas state sequence validity property.
 *
 * Tests that sequences of state transitions are valid.
 * No invalid transitions in multi-step sequences.
 *
 * @example
 * ```ts
 * fc.assert(canvasStateSequenceValidity);
 * ```
 *
 * Invariant: All transitions in sequence are valid.
 * Note: a random sequence of states is not expected to be a valid walk, so
 * the walk is built step-by-step along the transition table — every step
 * verifies the destination is a real, defined state (no typos/deletions).
 */
export const canvasStateSequenceValidity = fc.property(
  fc.array(fc.integer({ min: 0, max: 9 }), { minLength: 2, maxLength: 10 }),
  (stepIndices) => {
    const definedStates = Object.keys(VALID_CANVAS_TRANSITIONS) as CanvasState[];
    const sequence: CanvasState[] = ['idle'];

    for (const index of stepIndices) {
      const fromState = sequence[sequence.length - 1];
      const destinations = VALID_CANVAS_TRANSITIONS[fromState];

      if (destinations.length === 0) {
        // Terminal state — the walk legitimately ends here
        return true;
      }

      const toState = destinations[index % destinations.length];
      if (!definedStates.includes(toState)) {
        // Table references an undefined state
        return false;
      }
      sequence.push(toState);
    }

    // Every consecutive pair must be a transition listed in the table
    for (let i = 0; i < sequence.length - 1; i++) {
      if (!VALID_CANVAS_TRANSITIONS[sequence[i]].includes(sequence[i + 1])) {
        return false;
      }
    }

    return true;
  }
);
