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

import fc from 'fast-check';
import { CanvasState, VALID_CANVAS_TRANSITIONS } from './types';

/**
 * Canvas state machine property.
 *
 * Tests that all state transitions follow VALID_CANVAS_TRANSITIONS.
 * Generates random (fromState, toState) pairs and validates transition.
 *
 * @example
 * ```ts
 * fc.assert(canvasStateMachineProperty);
 * ```
 *
 * Invariant: For all (fromState, toState) pairs, transition must be valid
 */
export const canvasStateMachineProperty = fc.property(
  fc.constantFrom(...Object.keys(VALID_CANVAS_TRANSITIONS) as CanvasState[]),
  fc.constantFrom(...Object.keys(VALID_CANVAS_TRANSITIONS) as CanvasState[]),
  (fromState, toState) => {
    const allowedTransitions = VALID_CANVAS_TRANSITIONS[fromState];
    return allowedTransitions.includes(toState);
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
export const canvasNoTerminalStateLoops = fc.property(
  fc.constantFrom('submitted' as CanvasState, 'closed' as CanvasState),
  fc.constantFrom('submitted' as CanvasState, 'closed' as CanvasState),
  (fromState, toState) => {
    const allowedTransitions = VALID_CANVAS_TRANSITIONS[fromState];

    // Terminal states should only transition to idle
    if (fromState === toState) {
      // No self-loops
      return !allowedTransitions.includes(toState);
    }

    // No transitions between terminal states
    return toState === 'idle' && allowedTransitions.includes(toState);
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
 * Invariant: All transitions in sequence are valid
 */
export const canvasStateSequenceValidity = fc.property(
  fc.array(
    fc.constantFrom(...Object.keys(VALID_CANVAS_TRANSITIONS) as CanvasState[]),
    { minLength: 2, maxLength: 10 }
  ),
  (stateSequence) => {
    // Check that each consecutive transition is valid
    for (let i = 0; i < stateSequence.length - 1; i++) {
      const fromState = stateSequence[i];
      const toState = stateSequence[i + 1];
      const allowedTransitions = VALID_CANVAS_TRANSITIONS[fromState];

      if (!allowedTransitions.includes(toState)) {
        return false; // Invalid transition found
      }
    }

    return true;
  }
);
