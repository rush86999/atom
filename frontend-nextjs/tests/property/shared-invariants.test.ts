/**
 * Shared Cross-Platform Property Invariants (Frontend)
 *
 * Tests shared property test invariants across all platforms.
 * Imports all properties from @atom/property-tests and asserts them using FastCheck.
 *
 * These tests validate:
 * - Canvas state machine invariants (9 properties)
 * - Agent maturity state machine invariants (10 properties)
 * - Serialization roundtrip invariants (13 properties)
 *
 * @module tests/property/shared-invariants
 */

import fc from 'fast-check';
import { describe, it, expect } from '@jest/globals';
import {
  // Canvas state machine properties
  canvasStateMachineProperty,
  canvasNoDirectPresentingToIdle,
  canvasErrorRecoveryToIdle,
  canvasTerminalStatesLeadToIdle,
  canvasIdleToPresenting,
  canvasPresentingTransitions,
  canvasErrorStateRecoverability,
  canvasNoTerminalStateLoops,
  canvasStateSequenceValidity,
  // Agent maturity properties
  maturityMonotonicProgression,
  autonomousIsTerminal,
  studentCannotSkipToAutonomous,
  maturityTransitionsAreForward,
  maturityOrderConsistency,
  maturityGraduationPath,
  maturityNoBackwardTransitions,
  maturityLevelUniqueness,
  maturityTerminalStateUniqueness,
  // Serialization properties
  jsonRoundtripPreservesData,
  agentDataRoundtrip,
  canvasDataRoundtrip,
  arrayOrderPreserved,
  nullAndUndefinedHandling,
  dateSerialization,
  nestedObjectSerialization,
  specialCharactersInStrings,
  numberPrecisionPreservation,
  booleanSerialization,
  emptyValuesHandling,
} from '@atom/property-tests';
import { PROPERTY_TEST_CONFIG } from '@atom/property-tests';

describe('Shared Cross-Platform Property Invariants (Frontend)', () => {

  // ============================================================================
  // Canvas State Machine Tests
  // ============================================================================

  describe('Canvas State Machine Invariants', () => {
    it('canvas state machine transitions are valid', () => {
      fc.assert(canvasStateMachineProperty, PROPERTY_TEST_CONFIG);
    });

    it('canvas cannot transition from presenting to idle directly', () => {
      fc.assert(canvasNoDirectPresentingToIdle, PROPERTY_TEST_CONFIG);
    });

    it('canvas error state can recover to idle', () => {
      fc.assert(canvasErrorRecoveryToIdle, PROPERTY_TEST_CONFIG);
    });

    it('canvas terminal states lead to idle', () => {
      fc.assert(canvasTerminalStatesLeadToIdle, PROPERTY_TEST_CONFIG);
    });

    it('canvas idle to presenting transition is valid', () => {
      fc.assert(canvasIdleToPresenting, PROPERTY_TEST_CONFIG);
    });

    it('canvas presenting has exactly 3 transitions', () => {
      fc.assert(canvasPresentingTransitions, PROPERTY_TEST_CONFIG);
    });

    it('canvas error state has 2 recovery paths', () => {
      fc.assert(canvasErrorStateRecoverability, PROPERTY_TEST_CONFIG);
    });

    it('canvas terminal states cannot loop', () => {
      fc.assert(canvasNoTerminalStateLoops, PROPERTY_TEST_CONFIG);
    });

    it('canvas state sequences are valid', () => {
      fc.assert(canvasStateSequenceValidity, PROPERTY_TEST_CONFIG);
    });
  });

  // ============================================================================
  // Agent Maturity State Machine Tests
  // ============================================================================

  describe('Agent Maturity State Machine Invariants', () => {
    it('agent maturity progression is monotonic', () => {
      fc.assert(maturityMonotonicProgression, PROPERTY_TEST_CONFIG);
    });

    it('AUTONOMOUS is terminal maturity level', () => {
      fc.assert(autonomousIsTerminal, PROPERTY_TEST_CONFIG);
    });

    it('STUDENT cannot skip directly to AUTONOMOUS', () => {
      fc.assert(studentCannotSkipToAutonomous, PROPERTY_TEST_CONFIG);
    });

    it('agent maturity transitions are always forward', () => {
      fc.assert(maturityTransitionsAreForward, PROPERTY_TEST_CONFIG);
    });

    it('maturity order is consistent', () => {
      fc.assert(maturityOrderConsistency, PROPERTY_TEST_CONFIG);
    });

    it('valid graduation path exists from STUDENT to AUTONOMOUS', () => {
      fc.assert(maturityGraduationPath, PROPERTY_TEST_CONFIG);
    });

    it('maturity levels cannot transition backward', () => {
      fc.assert(maturityNoBackwardTransitions, PROPERTY_TEST_CONFIG);
    });

    it('all maturity levels are unique', () => {
      fc.assert(maturityLevelUniqueness, PROPERTY_TEST_CONFIG);
    });

    it('only AUTONOMOUS is terminal', () => {
      fc.assert(maturityTerminalStateUniqueness, PROPERTY_TEST_CONFIG);
    });
  });

  // ============================================================================
  // Serialization Roundtrip Tests
  // ============================================================================

  describe('Serialization Roundtrip Invariants', () => {
    it('JSON roundtrip preserves data', () => {
      fc.assert(jsonRoundtripPreservesData, PROPERTY_TEST_CONFIG);
    });

    it('agent data roundtrip preserves all fields', () => {
      fc.assert(agentDataRoundtrip, PROPERTY_TEST_CONFIG);
    });

    it('canvas data roundtrip preserves state', () => {
      fc.assert(canvasDataRoundtrip, PROPERTY_TEST_CONFIG);
    });

    it('array order is preserved in JSON roundtrip', () => {
      fc.assert(arrayOrderPreserved, PROPERTY_TEST_CONFIG);
    });

    it('null and undefined are handled correctly', () => {
      fc.assert(nullAndUndefinedHandling, PROPERTY_TEST_CONFIG);
    });

    it('date serialization preserves timestamp', () => {
      fc.assert(dateSerialization, PROPERTY_TEST_CONFIG);
    });

    it('nested objects survive JSON roundtrip', () => {
      fc.assert(nestedObjectSerialization, PROPERTY_TEST_CONFIG);
    });

    it('special characters in strings are preserved', () => {
      fc.assert(specialCharactersInStrings, PROPERTY_TEST_CONFIG);
    });

    it('number precision is preserved', () => {
      fc.assert(numberPrecisionPreservation, PROPERTY_TEST_CONFIG);
    });

    it('boolean values are preserved', () => {
      fc.assert(booleanSerialization, PROPERTY_TEST_CONFIG);
    });

    it('empty values are handled correctly', () => {
      fc.assert(emptyValuesHandling, PROPERTY_TEST_CONFIG);
    });
  });
});
