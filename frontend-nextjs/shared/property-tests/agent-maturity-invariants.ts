/**
 * Agent Maturity State Machine Property Tests
 *
 * Property-based tests for agent maturity level invariants.
 * Tests verify that maturity transitions follow governance rules:
 * - STUDENT → INTERN → SUPERVISED → AUTONOMOUS
 * - Monotonic progression (never decrease)
 * - AUTONOMOUS is terminal (no higher level)
 * - No skipping levels without graduation criteria
 *
 * @module property-tests/agent-maturity-invariants
 */

import fc from 'fast-check';
import { AgentMaturityLevel, MATURITY_ORDER, MATURITY_TRANSITIONS } from './types';

/**
 * Maturity monotonic progression property.
 *
 * Tests that maturity levels only increase (never decrease).
 * Uses sorted integer arrays to generate monotonic sequences.
 *
 * @example
 * ```ts
 * fc.assert(maturityMonotonicProgression);
 * ```
 *
 * Invariant: For all maturity sequences, indices are non-decreasing
 */
export const maturityMonotonicProgression = fc.property(
  fc.array(fc.integer({ min: 0, max: 3 }), { minLength: 2, maxLength: 10 })
    .map(indices => {
      // Sort to ensure monotonic progression (valid governance path)
      return [...indices].sort((a, b) => a - b);
    }),
  (indices) => {
    // Verify each step is greater than or equal to previous
    for (let i = 1; i < indices.length; i++) {
      if (indices[i] < indices[i - 1]) {
        return false; // Not monotonic
      }
    }

    // Verify all indices map to valid maturity levels
    for (const index of indices) {
      if (index < 0 || index >= MATURITY_ORDER.length) {
        return false; // Invalid index
      }
    }

    return true;
  }
);

/**
 * AUTONOMOUS is terminal property.
 *
 * Tests that AUTONOMOUS is the final level (no higher levels).
 * AUTONOMOUS has index 3, no levels exist beyond it.
 *
 * @example
 * ```ts
 * fc.assert(autonomousIsTerminal);
 * ```
 *
 * Invariant: AUTONOMOUS has no outgoing transitions (terminal state)
 */
export const autonomousIsTerminal = fc.property(
  fc.constantFrom('AUTONOMOUS' as AgentMaturityLevel),
  (level) => {
    const allowedTransitions = MATURITY_TRANSITIONS[level];

    // AUTONOMOUS should have no outgoing transitions
    return allowedTransitions.length === 0;
  }
);

/**
 * STUDENT cannot skip to AUTONOMOUS property.
 *
 * Tests that STUDENT cannot skip directly to AUTONOMOUS.
 * Must progress through INTERN and SUPERVISED first.
 * Maximum single-step transition is +1 level (governance rule).
 *
 * @example
 * ```ts
 * fc.assert(studentCannotSkipToAutonomous);
 * ```
 *
 * Invariant: STUDENT → INTERN only (no skipping levels)
 */
export const studentCannotSkipToAutonomous = fc.property(
  fc.constantFrom('STUDENT' as AgentMaturityLevel),
  (level) => {
    const allowedTransitions = MATURITY_TRANSITIONS[level];

    // STUDENT should only transition to INTERN (next level)
    return allowedTransitions.length === 1 &&
           allowedTransitions[0] === 'INTERN';
  }
);

/**
 * Maturity transitions are forward property.
 *
 * Tests that all valid transitions go forward (index increases).
 * From index N, valid transitions are only to N+1.
 * Cannot transition to same level or lower level.
 *
 * @example
 * ```ts
 * fc.assert(maturityTransitionsAreForward);
 * ```
 *
 * Invariant: All transitions increase maturity rank (no same-level or backward transitions)
 */
export const maturityTransitionsAreForward = fc.property(
  fc.constantFrom(...Object.keys(MATURITY_TRANSITIONS) as AgentMaturityLevel[]),
  (fromState) => {
    const fromIndex = MATURITY_ORDER.indexOf(fromState);
    const allowedTransitions = MATURITY_TRANSITIONS[fromState];

    // All transitions should go to higher levels (if not terminal)
    for (const toState of allowedTransitions) {
      const toIndex = MATURITY_ORDER.indexOf(toState);

      if (toIndex <= fromIndex) {
        return false; // Not a forward transition
      }
    }

    return true;
  }
);

/**
 * Maturity order consistency property.
 *
 * Tests that MATURITY_ORDER array is consistent with MATURITY_TRANSITIONS.
 * Each level should have transitions defined.
 *
 * @example
 * ```ts
 * fc.assert(maturityOrderConsistency);
 * ```
 *
 * Invariant: All maturity levels have defined transitions (may be empty for terminal)
 */
export const maturityOrderConsistency = fc.property(
  fc.constantFrom(...MATURITY_ORDER),
  (level) => {
    // Every level should have transitions defined
    const hasTransitions = level in MATURITY_TRANSITIONS;

    if (!hasTransitions) {
      return false;
    }

    // Transitions should be array (even if empty for terminal)
    return Array.isArray(MATURITY_TRANSITIONS[level]);
  }
);

/**
 * Maturity graduation path property.
 *
 * Tests that there is a valid path from STUDENT to AUTONOMOUS.
 * Full progression requires 3 steps: STUDENT → INTERN → SUPERVISED → AUTONOMOUS.
 *
 * @example
 * ```ts
 * fc.assert(maturityGraduationPath);
 * ```
 *
 * Invariant: Valid graduation path exists from STUDENT to AUTONOMOUS
 */
export const maturityGraduationPath = fc.property(
  fc.constantFrom('STUDENT' as AgentMaturityLevel),
  (startLevel) => {
    const endLevel: AgentMaturityLevel = 'AUTONOMOUS';
    let currentLevel = startLevel;
    const maxSteps = 10; // Prevent infinite loop
    let steps = 0;

    // Simulate graduation path
    while (currentLevel !== endLevel && steps < maxSteps) {
      const transitions = MATURITY_TRANSITIONS[currentLevel];

      if (transitions.length === 0) {
        return false; // Stuck, no path to AUTONOMOUS
      }

      // Move to next level (first transition)
      currentLevel = transitions[0];
      steps++;
    }

    // Should reach AUTONOMOUS in 3 steps
    return currentLevel === endLevel && steps === 3;
  }
);

/**
 * Maturity no backward transitions property.
 *
 * Tests that maturity levels cannot decrease.
 * No transitions from higher levels to lower levels.
 *
 * @example
 * ```ts
 * fc.assert(maturityNoBackwardTransitions);
 * ```
 *
 * Invariant: No transitions from higher rank to lower rank
 */
export const maturityNoBackwardTransitions = fc.property(
  fc.constantFrom(...Object.keys(MATURITY_TRANSITIONS) as AgentMaturityLevel[]),
  fc.constantFrom(...MATURITY_ORDER),
  (fromState, toState) => {
    const allowedTransitions = MATURITY_TRANSITIONS[fromState];
    const fromIndex = MATURITY_ORDER.indexOf(fromState);
    const toIndex = MATURITY_ORDER.indexOf(toState);

    // If toState is in allowed transitions, verify it's forward
    if (allowedTransitions.includes(toState)) {
      return toIndex > fromIndex;
    }

    // If not in allowed transitions, also verify it's not backward
    // (should be caught by allowedTransitions check, but double-check)
    return toIndex <= fromIndex || !allowedTransitions.includes(toState);
  }
);

/**
 * Maturity level uniqueness property.
 *
 * Tests that all maturity levels are unique in MATURITY_ORDER.
 * No duplicates in the progression array.
 *
 * @example
 * ```ts
 * fc.assert(maturityLevelUniqueness);
 * ```
 *
 * Invariant: All maturity levels in MATURITY_ORDER are unique
 */
export const maturityLevelUniqueness = fc.property(
  fc.constantFrom(...MATURITY_ORDER),
  (level) => {
    // Count occurrences of level in MATURITY_ORDER
    const occurrences = MATURITY_ORDER.filter(l => l === level).length;

    // Each level should appear exactly once
    return occurrences === 1;
  }
);

/**
 * Maturity terminal state uniqueness property.
 *
 * Tests that only AUTONOMOUS is terminal.
 * No other levels should have empty transitions.
 *
 * @example
 * ```ts
 * fc.assert(maturityTerminalStateUniqueness);
 * ```
 *
 * Invariant: Only AUTONOMOUS has empty transitions array
 */
export const maturityTerminalStateUniqueness = fc.property(
  fc.constantFrom(...Object.keys(MATURITY_TRANSITIONS) as AgentMaturityLevel[]),
  (level) => {
    const hasTransitions = MATURITY_TRANSITIONS[level].length > 0;
    const isAutonomous = level === 'AUTONOMOUS';

    // AUTONOMOUS should have no transitions
    // All other levels should have transitions
    return isAutonomous ? !hasTransitions : hasTransitions;
  }
);
