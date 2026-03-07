# Rust-TypeScript Property Test Correspondence

This document describes the correspondence between Rust property tests (using `proptest`) and TypeScript property tests (using `fast-check`). Both platforms validate the same invariants, ensuring cross-platform consistency for critical system behaviors.

## Overview

**Why Two Testing Frameworks?**

- **TypeScript (Frontend/Mobile)**: Uses `fast-check` for property-based testing
- **Rust (Desktop)**: Uses `proptest` for property-based testing
- **Same Invariants**: Both platforms test identical system invariants
- **No Code Sharing**: Rust cannot import TypeScript files (different compilation pipelines)

**Solution**: Documented correspondence via comments and this README. Each Rust test includes a comment referencing its TypeScript counterpart, ensuring both platforms validate the same behavior.

## Property Mapping

### Canvas State Machine Properties

| TypeScript Property | Rust Proptest | Module | Description |
|---------------------|--------------|--------|-------------|
| `canvasStateMachineProperty` | `prop_canvas_state_machine_transitions` | state_machine_proptest.rs | Canvas state transitions are valid |
| `canvasNoDirectPresentingToIdle` | `prop_canvas_no_presenting_to_idle` | state_machine_proptest.rs | Presenting cannot go to Idle |
| `canvasErrorRecoveryToIdle` | `prop_canvas_error_to_idle` | state_machine_proptest.rs | Error can recover to Idle |
| `canvasTerminalStatesLeadToIdle` | `prop_canvas_terminal_states_to_idle` | state_machine_proptest.rs | Terminal states lead to Idle |
| `canvasIdleToPresenting` | `prop_canvas_idle_to_presenting` | state_machine_proptest.rs | Idle to Presenting is valid |
| `canvasPresentingTransitions` | `prop_canvas_presenting_transitions` | state_machine_proptest.rs | Presenting has 3 transitions |
| `canvasErrorStateRecoverability` | `prop_canvas_error_state_recoverability` | state_machine_proptest.rs | Error has 2 recovery paths |
| `canvasNoTerminalStateLoops` | (not yet implemented) | state_machine_proptest.rs | Terminal states cannot loop |
| `canvasStateSequenceValidity` | (not yet implemented) | state_machine_proptest.rs | State sequences are valid |

**TypeScript Source**: `frontend-nextjs/shared/property-tests/canvas-invariants.ts`

### Agent Maturity State Machine Properties

| TypeScript Property | Rust Proptest | Module | Description |
|---------------------|--------------|--------|-------------|
| `maturityMonotonicProgression` | `prop_maturity_monotonic_progression` | state_machine_proptest.rs | Maturity only increases |
| `autonomousIsTerminal` | `prop_autonomous_is_terminal` | state_machine_proptest.rs | AUTONOMOUS is final level |
| `studentCannotSkipToAutonomous` | `prop_student_cannot_skip_to_autonomous` | state_machine_proptest.rs | STUDENT → INTERN only |
| `maturityTransitionsAreForward` | `prop_maturity_transitions_are_forward` | state_machine_proptest.rs | All transitions are forward |
| `maturityOrderConsistency` | (not yet implemented) | state_machine_proptest.rs | Order is consistent |
| `maturityGraduationPath` | `prop_maturity_graduation_path` | state_machine_proptest.rs | Valid path to AUTONOMOUS |
| `maturityNoBackwardTransitions` | `prop_maturity_no_backward_transitions` | state_machine_proptest.rs | No backward transitions |
| `maturityLevelUniqueness` | (not yet implemented) | state_machine_proptest.rs | All levels are unique |
| `maturityTerminalStateUniqueness` | (not yet implemented) | state_machine_proptest.rs | Only AUTONOMOUS is terminal |

**TypeScript Source**: `frontend-nextjs/shared/property-tests/agent-maturity-invariants.ts`

### Serialization Roundtrip Properties

| TypeScript Property | Rust Proptest | Module | Description |
|---------------------|--------------|--------|-------------|
| `jsonRoundtripPreservesData` | `prop_json_roundtrip_preserves_data` | serialization_proptest.rs | JSON roundtrip preserves data |
| `agentDataRoundtrip` | `prop_agent_data_roundtrip` | serialization_proptest.rs | Agent data survives serialization |
| `canvasDataRoundtrip` | `prop_canvas_data_roundtrip` | serialization_proptest.rs | Canvas data survives serialization |
| `arrayOrderPreserved` | `prop_array_order_preserved` | serialization_proptest.rs | Array order preserved |
| `nullAndUndefinedHandling` | `prop_null_and_undefined_handling` | serialization_proptest.rs | Null/undefined handled correctly |
| `dateSerialization` | `prop_date_serialization` | serialization_proptest.rs | Date serialization preserves timestamp |
| `nestedObjectSerialization` | `prop_nested_object_serialization` | serialization_proptest.rs | Nested objects survive roundtrip |
| `specialCharactersInStrings` | `prop_special_characters_in_strings` | serialization_proptest.rs | Special characters preserved |
| `numberPrecisionPreservation` | `prop_number_precision_preservation` | serialization_proptest.rs | Number precision preserved |
| `booleanSerialization` | `prop_boolean_serialization` | serialization_proptest.rs | Boolean values preserved |
| `emptyValuesHandling` | `prop_empty_values_handling` | serialization_proptest.rs | Empty values handled correctly |

**TypeScript Source**: `frontend-nextjs/shared/property-tests/serialization-invariants.ts`

## Framework Differences

### FastCheck (TypeScript)

```typescript
import fc from 'fast-check';

// Define property
const myProperty = fc.property(
  fc.string(),        // Arbitrary generator
  fc.integer(),       // Arbitrary generator
  (input1, input2) => {
    // Property predicate (must return boolean)
    return input1.length > input2;
  }
);

// Assert property
fc.assert(myProperty, { numRuns: 100 });
```

**Key Features**:
- Uses `fc.property()` for property definition
- Uses `fc.assert()` for property verification
- Arbitrary generators: `fc.string()`, `fc.integer()`, `fc.record()`, etc.
- Configuration via object: `{ numRuns, timeout, seed }`

### proptest (Rust)

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn prop_my_test(
        input1 in "[a-z]{1,10}",   // Strategy (regex)
        input2 in 0i32..100i32,    // Strategy (range)
    ) {
        // Property predicate (must return boolean or use prop_assert!)
        prop_assert!(input1.len() > input2 as usize);
    }
}
```

**Key Features**:
- Uses `proptest!` macro for property definition
- Uses `prop_assert!` for property verification
- Strategies: `any::<T>()`, regex patterns, ranges, `prop::sample::select`, etc.
- Configuration via `proptest!` macro attributes or `proptest` config file

### Generation Strategies Comparison

| TypeScript (FastCheck) | Rust (proptest) | Description |
|------------------------|-----------------|-------------|
| `fc.string()` | `prop::string::string_regex(".{0,100}")` | Arbitrary strings |
| `fc.integer({ min, max })` | `min..max` (range) | Integer range |
| `fc.constantFrom(...)` | `prop::sample::select(vec![...])` | Constant selection |
| `fc.record({ ... })` | Custom struct + strategies | Object/struct generation |
| `fc.array(...)` | `prop::collection::vec(..., min..max)` | Array/vector generation |
| `fc.jsonObject()` | `any::<serde_json::Value>()` | Arbitrary JSON |
| `fc.boolean()` | `prop::bool::ANY` | Boolean values |

### Assertion Macros Comparison

| TypeScript (FastCheck) | Rust (proptest) | Description |
|------------------------|-----------------|-------------|
| `return true/false` | `prop_assert!(condition)` | Property predicate |
| `expect().toBe()` | `prop_assert_eq!(left, right)` | Equality assertion |
| N/A | `prop_assert_ne!(left, right)` | Inequality assertion |

## Why Not SYMLINK for Rust?

**Rust Cannot Import TypeScript Files**:

1. **Different Compilation Pipelines**:
   - TypeScript: Compiled by `tsc` (TypeScript compiler)
   - Rust: Compiled by `rustc` (Rust compiler)
   - No cross-language import mechanism exists

2. **Different Type Systems**:
   - TypeScript: Structural typing, dynamic at runtime
   - Rust: Nominal typing, static at compile time
   - Type information not compatible across languages

3. **Different Runtime Models**:
   - TypeScript: Runs in Node.js / browser (JavaScript runtime)
   - Rust: Native binary (no JavaScript runtime)

**Solution**: Documented Correspondence

- Each Rust test includes a comment: `// Corresponds to: <typescript_property_name>`
- This README provides complete property mapping table
- Both platforms validate the same invariants using native frameworks

## Running Property Tests

### Frontend (TypeScript)

```bash
cd frontend-nextjs

# Run all property tests
npm test -- shared-invariants

# Run specific test suite
npm test -- shared-invariants --testNamePattern="Canvas State Machine"

# Run with custom configuration
FASTCHECK_NUM_RUNS=1000 FASTCHECK_SEED=12345 npm test -- shared-invariants
```

**Test File**: `frontend-nextjs/tests/property/shared-invariants.test.ts`

### Mobile (TypeScript via SYMLINK)

```bash
cd mobile

# Run all property tests
npm test -- shared-invariants

# Run specific test suite
npm test -- shared-invariants --testNamePattern="Agent Maturity"

# Run with custom configuration
FASTCHECK_NUM_RUNS=1000 FASTCHECK_SEED=12345 npm test -- shared-invariants
```

**Test File**: `mobile/src/__tests__/property/shared-invariants.test.ts`

**SYMLINK**: `mobile/src/shared/property-tests → ../../frontend-nextjs/shared/property-tests`

### Desktop (Rust)

```bash
cd frontend-nextjs/src-tauri

# Run all property tests
cargo test state_machine_proptest serialization_proptest

# Run specific test suite
cargo test state_machine_proptest

# Run specific test
cargo test prop_canvas_state_machine_transitions

# Run with custom configuration
cargo test -- --test-threads=1 state_machine_proptest
```

**Test Files**:
- `frontend-nextjs/src-tauri/tests/state_machine_proptest.rs`
- `frontend-nextjs/src-tauri/tests/serialization_proptest.rs`

## Adding New Properties

When adding a new shared property test:

1. **Create TypeScript Property** (if not exists):
   ```bash
   # Add to frontend-nextjs/shared/property-tests/
   touch frontend-nextjs/shared/property-tests/new-invariants.ts
   ```

2. **Export from Index**:
   ```typescript
   // frontend-nextjs/shared/property-tests/index.ts
   export * from './new-invariants';
   ```

3. **Add to Frontend Test Suite**:
   ```typescript
   // frontend-nextjs/tests/property/shared-invariants.test.ts
   import { newProperty } from '@atom/property-tests';

   describe('New Invariants', () => {
     it('new property test', () => {
       fc.assert(newProperty, PROPERTY_TEST_CONFIG);
     });
   });
   ```

4. **Add to Mobile Test Suite** (same as frontend, uses SYMLINK):
   ```typescript
   // mobile/src/__tests__/property/shared-invariants.test.ts
   import { newProperty } from '../../shared/property-tests';

   describe('New Invariants', () => {
     it('new property test', () => {
       fc.assert(newProperty, PROPERTY_TEST_CONFIG);
     });
   });
   ```

5. **Create Rust Equivalent**:
   ```rust
   // frontend-nextjs/src-tauri/tests/new_proptest.rs

   proptest! {
       #[test]
       fn prop_new_property(
           input in any::<serde_json::Value>(),
       ) {
           // Corresponds to: newProperty in new-invariants.ts
           prop_assert!(/* invariant check */);
       }
   }
   ```

6. **Update This README**:
   ```markdown
   ## Property Mapping

   ### New Invariants

   | TypeScript Property | Rust Proptest | Module | Description |
   |---------------------|--------------|--------|-------------|
   | `newProperty` | `prop_new_property` | new_proptest.rs | Description |
   ```

## Verification

To verify that all platforms are testing the same invariants:

1. **Count Properties**: Ensure TypeScript and Rust have same property count
2. **Check Comments**: Each Rust test has `// Corresponds to:` comment
3. **Update README**: Keep property mapping table in sync
4. **Run All Tests**: Ensure all platforms pass

```bash
# Frontend
cd frontend-nextjs && npm test -- shared-invariants

# Mobile
cd mobile && npm test -- shared-invariants

# Desktop
cd frontend-nextjs/src-tauri && cargo test state_machine_proptest serialization_proptest
```

## References

- **FastCheck Documentation**: https://github.com/dubzzz/fast-check
- **proptest Documentation**: https://altsysrq.github.io/proptest-book/
- **Phase 147 Plan 02**: `.planning/phases/147-cross-platform-property-testing/147-02-PLAN.md`
- **TypeScript Property Tests**: `frontend-nextjs/shared/property-tests/`
- **Rust Property Tests**: `frontend-nextjs/src-tauri/tests/`

## Status

- ✅ Canvas state machine properties (7/9 implemented in Rust)
- ✅ Agent maturity properties (7/9 implemented in Rust)
- ✅ Serialization properties (11/11 implemented in Rust)
- ⏳ Remaining properties to be implemented in future plans

**Last Updated**: Phase 147 Plan 02 (2026-03-06)
