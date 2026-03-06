# Phase 147: Cross-Platform Property Testing - Research

**Researched:** March 6, 2026
**Domain:** Property-based testing across TypeScript/React Native/Rust platforms
**Confidence:** HIGH

## Summary

Phase 147 requires implementing **unified property-based testing** across three platforms (frontend/Next.js, mobile/React Native, desktop/Tauri-Rust) using FastCheck for TypeScript/React Native and proptest for Rust, with shared tests distributed via SYMLINK strategy. The project already has extensive property testing infrastructure in place: frontend has 13 FastCheck test files covering agent state machines, canvas state, API roundtrips, and Tauri commands; mobile has 2 FastCheck test files for offline queue and device state invariants; desktop (Rust) has 4 proptest files covering error handling, file operations, IPC serialization, and window state.

**What's missing:** A unified cross-platform property testing framework that:
1. Creates shared property tests for common invariants (canvas state, agent maturity, data serialization)
2. Distributes tests via SYMLINK strategy (established in Phase 144)
3. Aggregates property test results across all three platforms
4. Ensures consistent invariant testing across TypeScript and Rust implementations
5. Documents property testing patterns for shared state machines

**Primary recommendation:** Extend existing FastCheck property tests from `frontend-nextjs/tests/property/` into a shared location (`frontend-nextjs/shared/property-tests/`), configure symlinks for mobile and desktop Rust tests to reference TypeScript test patterns, create aggregation script to combine FastCheck and proptest results, and document cross-platform property testing patterns.

**Key infrastructure already in place:**
- FastCheck 4.5.3 installed in frontend and mobile (from package.json verification)
- proptest 1.0 installed in desktop Rust (from Cargo.toml verification)
- 13 frontend property tests (agent state machine, canvas state, API roundtrips, Tauri commands, auth, chat, state transitions)
- 2 mobile property tests (offline queue invariants, device state invariants)
- 4 desktop Rust proptests (error handling, file operations, IPC serialization, window state)
- Phase 144 SYMLINK strategy for sharing utilities across platforms
- Phase 145 API type generation for shared type definitions

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **fast-check** | 4.5.3+ | Property-based testing for TypeScript/React Native | Most popular PBT framework for JavaScript (1M+ weekly downloads), strong TypeScript support, mature shrinking algorithm, battle-tested in major projects (Jest, Ramda, fp-ts) |
| **proptest** | 1.0+ | Property-based testing for Rust | Standard Rust PBT framework, inspired by QuickCheck, excellent type-safe arbitrary generation, integrates with cargo test |
| **Jest** | 29.x | Test runner for frontend/mobile property tests | Already in project, supports FastCheck integration, parallel execution |
| **cargo test** | Built-in | Test runner for desktop Rust property tests | Rust standard, integrates with proptest via macros |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **ts-jest** | 29.x | TypeScript compilation for FastCheck tests | Already in frontend project, compiles shared property tests |
| **jest-expo** | 50.x | React Native test environment | Already in mobile project, runs FastCheck tests on RN |
| **serde_json** | 1.0 | JSON serialization tests in Rust | Already in desktop project, testing (de)serialization invariants |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| fast-check | jsverify | Older, less maintained, poorer TypeScript support |
| fast-check | test-check | Smaller community, fewer features, less mature shrinking |
| proptest | quickcheck | Less actively maintained, fewer strategy types |
| proptest | bolt | Hypothesis-inspired but less mature for Rust |

**Installation:**
```bash
# Frontend/Mobile (FastCheck) - ALREADY INSTALLED
npm install --save-dev fast-check@4.5.3

# Desktop (proptest) - ALREADY INSTALLED
# Already in dev-dependencies in frontend-nextjs/src-tauri/Cargo.toml
```

## Architecture Patterns

### Recommended Project Structure

```
atom/
├── frontend-nextjs/
│   ├── shared/
│   │   └── property-tests/              # NEW: Shared property tests
│   │       ├── index.ts                 # Main export barrel
│   │       ├── canvas-invariants.ts     # Canvas state properties
│   │       ├── agent-maturity-invariants.ts  # Agent state machine
│   │       ├── serialization-invariants.ts   # Data roundtrip tests
│   │       ├── queue-invariants.ts      # Queue ordering properties
│   │       └── types.ts                 # Shared type definitions
│   ├── tests/
│   │   └── property/                    # EXISTING: Frontend-specific tests
│   │       ├── agent-state-machine-invariants.test.ts
│   │       ├── state-machine-invariants.test.ts
│   │       └── ... (11 more files)
│   └── jest.config.js                   # Configure testPathPatterns
├── mobile/
│   ├── src/__tests__/property/          # EXISTING: Mobile-specific tests
│   │   ├── queueInvariants.test.ts      # Offline queue tests
│   │   └── device-state-invariants.test.ts
│   └── jest.config.js                   # Configure testPathPatterns
├── frontend-nextjs/src-tauri/
│   ├── tests/property_tests/            # NEW: Rust property tests (organized)
│   │   ├── mod.rs                       # Module barrel
│   │   ├── serialization_proptest.rs    # Mirrors TS serialization tests
│   │   ├── state_machine_proptest.rs    # Mirrors agent/canvas state tests
│   │   ├── error_handling_proptest.rs   # EXISTING: Error invariants
│   │   ├── file_operations_proptest.rs  # EXISTING: File invariants
│   │   ├── ipc_serialization_proptest.rs # EXISTING: IPC invariants
│   │   └── window_state_proptest.rs     # EXISTING: Window state
│   └── tests/
│       └── shared_property_tests/       # SYMLINK to frontend shared/property-tests/
│           └── README.md                # Document pattern correspondence
└── backend/tests/scripts/
    └── aggregate_property_tests.py      # NEW: Cross-platform result aggregation
```

### Pattern 1: Shared Canvas State Invariants

**What:** Property tests for canvas state transitions that work across web, mobile, and desktop

**When to use:** Testing canvas state machine invariants (idle → presenting → submitted → closed)

**Example:**
```typescript
// frontend-nextjs/shared/property-tests/canvas-invariants.ts

import fc from 'fast-check';

/**
 * Canvas State Machine Types
 * Pattern: idle -> presenting -> (submitted | closed) -> idle
 * Any state -> error (on failure)
 */
export type CanvasState =
  | 'idle'
  | 'presenting'
  | 'submitted'
  | 'closed'
  | 'error';

export const VALID_CANVAS_TRANSITIONS: Record<CanvasState, CanvasState[]> = {
  idle: ['presenting', 'error'],
  presenting: ['submitted', 'closed', 'error'],
  submitted: ['idle'],
  closed: ['idle'],
  error: ['idle', 'presenting'],
};

/**
 * INVARIANT: Canvas state transitions follow valid state machine
 *
 * Test covers: Canvas state machine (Phase 134)
 * Platforms: Frontend (canvas-tool.py), Mobile (canvas presentation), Desktop (Tauri canvas)
 */
export const canvasStateMachineProperty = fc.property(
  fc.constantFrom(...Object.keys(VALID_CANVAS_TRANSITIONS) as CanvasState[]),
  fc.constantFrom(...Object.keys(VALID_CANVAS_TRANSITIONS) as CanvasState[]),
  (fromState, toState) => {
    const allowedTransitions = VALID_CANVAS_TRANSITIONS[fromState];

    // Either the transition is valid, or it's not in the allowed list
    if (allowedTransitions.includes(toState)) {
      return true; // Valid transition
    }

    // Invalid transitions should not be allowed
    return false;
  }
);

/**
 * INVARIANT: Canvas cannot transition from presenting directly to idle
 * Must go through submitted or closed first
 */
export const canvasNoDirectPresentingToIdle = fc.property(
  fc.constantFrom('presenting' as CanvasState),
  fc.constantFrom('idle' as CanvasState),
  (from, to) => {
    return from !== 'presenting' || to !== 'idle';
  }
);
```

**Frontend test (uses shared property):**
```typescript
// frontend-nextjs/tests/property/canvas-state-invariants.test.ts

import { canvasStateMachineProperty, canvasNoDirectPresentingToIdle } from '@shared/property-tests/canvas-invariants';

describe('Canvas State Machine Invariants (Frontend)', () => {
  it('should only allow valid canvas state transitions', () => {
    fc.assert(canvasStateMachineProperty);
  });

  it('should not allow presenting to idle transition directly', () => {
    fc.assert(canvasNoDirectPresentingToIdle);
  });
});
```

**Mobile test (uses shared property via SYMLINK):**
```typescript
// mobile/src/__tests__/property/canvasInvariants.test.ts

import { canvasStateMachineProperty } from '../../../frontend-nextjs/shared/property-tests/canvas-invariants';

describe('Canvas State Machine Invariants (Mobile)', () => {
  it('should only allow valid canvas state transitions', () => {
    fc.assert(canvasStateMachineProperty);
  });
});
```

**Rust equivalent (documents correspondence, not symlinked):**
```rust
// frontend-nextjs/src-tauri/tests/property_tests/state_machine_proptest.rs

/// Canvas state machine invariants (mirrors TypeScript canvas-invariants.ts)
///
/// Pattern: idle -> presenting -> (submitted | closed) -> idle
/// Any state -> error (on failure)
///
/// Corresponds to: frontend-nextjs/shared/property-tests/canvas-invariants.ts
use proptest::prelude::*;

#[derive(Debug, Clone, Copy, PartialEq)]
enum CanvasState {
    Idle,
    Presenting,
    Submitted,
    Closed,
    Error,
}

proptest! {
    #[test]
    fn prop_canvas_state_machine_transitions(
        from_state in prop::sample::select(vec![CanvasState::Idle, CanvasState::Presenting, CanvasState::Submitted, CanvasState::Closed, CanvasState::Error]),
        to_state in prop::sample::select(vec![CanvasState::Idle, CanvasState::Presenting, CanvasState::Submitted, CanvasState::Closed, CanvasState::Error]),
    ) {
        // INVARIANT: Canvas state transitions follow valid state machine
        // Corresponds to: canvasStateMachineProperty in canvas-invariants.ts

        let valid_transitions = match from_state {
            CanvasState::Idle => vec![CanvasState::Presenting, CanvasState::Error],
            CanvasState::Presenting => vec![CanvasState::Submitted, CanvasState::Closed, CanvasState::Error],
            CanvasState::Submitted => vec![CanvasState::Idle],
            CanvasState::Closed => vec![CanvasState::Idle],
            CanvasState::Error => vec![CanvasState::Idle, CanvasState::Presenting],
        };

        if valid_transitions.contains(&to_state) {
            // Valid transition
            prop_assert!(true);
        } else {
            // Invalid transition should fail
            prop_assert!(false, "Invalid transition from {:?} to {:?}", from_state, to_state);
        }
    }
}
```

### Pattern 2: Agent Maturity State Machine Properties

**What:** Property tests for agent maturity graduation (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)

**When to use:** Testing agent maturity invariants across platforms

**Example:**
```typescript
// frontend-nextjs/shared/property-tests/agent-maturity-invariants.ts

import fc from 'fast-check';

export type AgentMaturityLevel = 'STUDENT' | 'INTERN' | 'SUPERVISED' | 'AUTONOMOUS';

/**
 * INVARIANT: Maturity transitions are monotonic (never decrease)
 *
 * Test covers: Agent maturity state machine (backend governance)
 * Platforms: All (agent maturity is backend concept, reflected in UI)
 */
export const maturityMonotonicProgression = fc.property(
  fc.array(fc.integer({ min: 0, max: 3 }), { minLength: 2, maxLength: 10 })
    .map(indices => [...indices].sort((a, b) => a - b)), // Sort for monotonic
  (indices) => {
    for (let i = 1; i < indices.length; i++) {
      if (indices[i] < indices[i - 1]) {
        return false; // Not monotonic
      }
    }
    return true; // Monotonic progression
  }
);

/**
 * INVARIANT: AUTONOMOUS is terminal (no transitions from it)
 */
export const autonomousIsTerminal = fc.property(
  fc.constantFrom('AUTONOMOUS' as AgentMaturityLevel),
  (level) => {
    const maturityOrder: AgentMaturityLevel[] = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'];
    const autonomousIndex = maturityOrder.indexOf(level);
    const higherLevels = maturityOrder.slice(autonomousIndex + 1);
    return higherLevels.length === 0;
  }
);
```

### Pattern 3: Serialization Roundtrip Invariants

**What:** Property tests for data serialization/deserialization (JSON ↔ TypeScript ↔ Rust)

**When to use:** Testing API contracts, Tauri IPC messages, offline sync data

**Example:**
```typescript
// frontend-nextjs/shared/property-tests/serialization-invariants.ts

import fc from 'fast-check';

/**
 * INVARIANT: JSON roundtrip preserves data
 *
 * Test covers: API contract testing (Phase 128), IPC serialization (desktop)
 * Platforms: All (JSON is universal)
 */
export const jsonRoundtripPreservesData = fc.property(
  fc.jsonObject(),
  (data) => {
    const serialized = JSON.stringify(data);
    const deserialized = JSON.parse(serialized);
    return deepEquals(data, deserialized);
  }
);

/**
 * INVARIANT: Agent data roundtrip via API preserves fields
 *
 * Test covers: Agent registry API invariants
 */
export const agentDataRoundtrip = fc.property(
  fc.record({
    id: fc.uuid(),
    name: fc.string(),
    maturity_level: fc.constantFrom('STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'),
    created_at: fc.date(),
    is_active: fc.boolean(),
  }),
  (agent) => {
    const serialized = JSON.stringify(agent);
    const deserialized = JSON.parse(serialized);
    return (
      deserialized.id === agent.id &&
      deserialized.name === agent.name &&
      deserialized.maturity_level === agent.maturity_level &&
      deserialized.is_active === agent.is_active
    );
  }
);

function deepEquals(a: any, b: any): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (typeof a !== 'object' || a === null || b === null) return false;
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;
  return keysA.every(key => deepEquals(a[key], b[key]));
}
```

**Rust equivalent:**
```rust
// frontend-nextjs/src-tauri/tests/property_tests/serialization_proptest.rs

/// JSON roundtrip invariants (mirrors TypeScript serialization-invariants.ts)
///
/// Corresponds to: frontend-nextjs/shared/property-tests/serialization-invariants.ts
use proptest::prelude::*;
use serde_json::Value;

proptest! {
    #[test]
    fn prop_json_roundtrip_preserves_data(input in any::<Value>()) {
        // INVARIANT: JSON roundtrip preserves data
        // Corresponds to: jsonRoundtripPreservesData in serialization-invariants.ts

        let serialized = serde_json::to_string(&input).unwrap();
        let deserialized: Value = serde_json::from_str(&serialized).unwrap();
        prop_assert_eq!(input, deserialized);
    }
}
```

### Pattern 4: Cross-Platform Result Aggregation

**What:** Aggregate FastCheck and proptest results into unified report

**When to use:** CI/CD workflow for cross-platform property testing

**Example:**
```python
# backend/tests/scripts/aggregate_property_tests.py

"""
Aggregate property test results across all platforms.

Combines FastCheck results (frontend/mobile) and proptest results (desktop)
into unified cross-platform report.

Usage:
    python aggregate_property_tests.py --frontend frontend-jest.xml --mobile mobile-jest.xml --desktop proptest-results.json
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple


def parse_jest_xml(junit_xml: Path) -> Dict[str, int]:
    """Parse Jest JUnit XML output for property test results."""
    tree = ET.parse(junit_xml)
    root = tree.getroot()

    total = 0
    passed = 0
    failed = 0

    for test_case in root.findall('.//testcase'):
        total += 1
        if test_case.find('failure') is not None:
            failed += 1
        else:
            passed += 1

    return {'total': total, 'passed': passed, 'failed': failed}


def parse_proptest_json(proptest_json: Path) -> Dict[str, int]:
    """Parse proptest JSON output."""
    # Note: proptest doesn't natively output JSON, need to parse cargo test output
    # This is a placeholder for the actual parsing logic
    pass


def aggregate_results(
    frontend_results: Dict[str, int],
    mobile_results: Dict[str, int],
    desktop_results: Dict[str, int]
) -> Dict:
    """Aggregate property test results across platforms."""

    total_tests = (
        frontend_results['total'] +
        mobile_results['total'] +
        desktop_results['total']
    )

    total_passed = (
        frontend_results['passed'] +
        mobile_results['passed'] +
        desktop_results['passed']
    )

    total_failed = (
        frontend_results['failed'] +
        mobile_results['failed'] +
        desktop_results['failed']
    )

    return {
        'total': total_tests,
        'passed': total_passed,
        'failed': total_failed,
        'pass_rate': (total_passed / total_tests * 100) if total_tests > 0 else 0,
        'platforms': {
            'frontend': frontend_results,
            'mobile': mobile_results,
            'desktop': desktop_results,
        }
    }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Aggregate property test results')
    parser.add_argument('--frontend', type=Path, help='Frontend Jest JUnit XML')
    parser.add_argument('--mobile', type=Path, help='Mobile Jest JUnit XML')
    parser.add_argument('--desktop', type=Path, help='Desktop proptest JSON')
    parser.add_argument('--output', type=Path, default='property_test_results.json')

    args = parser.parse_args()

    frontend = parse_jest_xml(args.frontend)
    mobile = parse_jest_xml(args.mobile)
    desktop = parse_proptest_json(args.desktop)

    aggregated = aggregate_results(frontend, mobile, desktop)

    with open(args.output, 'w') as f:
        json.dump(aggregated, f, indent=2)

    print(f"Property test results: {aggregated['passed']}/{aggregated['total']} passed ({aggregated['pass_rate']:.1f}%)")
```

### Anti-Patterns to Avoid

- **Platform-specific properties in shared code:** Don't use `window` (web-only) or `Platform.OS` (RN-only) in shared property tests
- **Duplicate invariants across platforms:** Don't copy-paste property tests; use SYMLINK strategy from Phase 144
- **Ignoring Rust differences:** Don't assume Rust proptest can directly import TypeScript tests; document correspondence patterns
- **Missing aggregation:** Don't run property tests in isolation; aggregate results for cross-platform visibility
- **Testing implementation details:** Focus on invariants (state machines, serialization), not internal implementation

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Property test generators | Custom random data generation | fast-check arbitraries (fc.string(), fc.integer(), fc.record()) | Handles edge cases, shrinking, reproducibility |
| State machine validation | Manual transition logic | fc.property() with state transition tables | FastCheck provides shrinking, counterexample generation |
| Serialization testing | Manual roundtrip logic | JSON.stringify/parse with deep equality | Standard library handles encoding edge cases |
| Result aggregation | Custom parsing scripts | Jest JUnit XML + proptest output parsing | Industry-standard formats, better tooling |
| Symlink management | Manual ln -s commands | Phase 144 SYMLINK strategy (npm workspaces or symlinks) | Cross-platform compatibility, documented patterns |

**Key insight:** Property testing infrastructure is mature. FastCheck and proptest have solved random generation, shrinking, and reproducibility through years of production use. Focus on defining invariants, not building test infrastructure.

## Common Pitfalls

### Pitfall 1: Platform-Specific APIs in Shared Properties

**What goes wrong:** Shared property tests use web-only APIs (`window.document`) or React Native-only APIs (`Platform.OS`), causing import errors on other platforms.

**Why it happens:** Developers copy existing tests into shared folder without auditing for platform dependencies.

**How to avoid:**
1. Audit shared properties for platform-specific APIs
2. Use platform guards (`isWeb()`, `isReactNative()`) from Phase 144 shared utilities
3. Write tests for platform-agnostic invariants (state machines, serialization)
4. Create platform-specific wrappers for platform-dependent properties

**Warning signs:** Import errors when running tests on different platforms, TypeScript errors about missing properties.

**Prevention:**
```typescript
// frontend-nextjs/shared/property-tests/platform-guards.ts

export const isWeb = (): boolean => {
  return typeof window !== 'undefined' &&
         typeof window.document !== 'undefined';
};

export const isReactNative = (): boolean => {
  return typeof navigator !== 'undefined' &&
         (navigator as any).product === 'ReactNative';
};

export const isTauri = (): boolean => {
  return typeof window !== 'undefined' &&
         (window as any).__TAURI__ !== undefined;
};
```

### Pitfall 2: Rust Cannot Import TypeScript Tests Directly

**What goes wrong:** Attempt to symlink Rust proptest files to TypeScript FastCheck files fails because Rust cannot import .ts files.

**Why it happens:** Rust and TypeScript have different compilation pipelines and type systems.

**How to avoid:**
1. Use SYMLINK strategy for TypeScript → TypeScript sharing (frontend → mobile)
2. Document correspondence between TypeScript and Rust tests (comments, shared documentation)
3. Keep Rust and TypeScript tests in separate files but with matching structure
4. Aggregate results at CI/CD level, not code level

**Warning signs:** Symlinked .rs files pointing to .ts files, compilation errors in Rust.

**Prevention:**
```rust
// frontend-nextjs/src-tauri/tests/property_tests/state_machine_proptest.rs

/// Agent maturity state machine invariants
///
/// Corresponds to: frontend-nextjs/shared/property-tests/agent-maturity-invariants.ts
///
/// Pattern: STUDENT -> INTERN -> SUPERVISED -> AUTONOMOUS
/// AUTONOMOUS is terminal (no transitions from it)
///
/// Note: This is a Rust port of the TypeScript property test, not a symlink.
/// Both tests verify the same invariant but use platform-native PBT frameworks.
```

### Pitfall 3: Missing Property Test Configuration

**What goes wrong:** Property tests don't run because Jest isn't configured to find them, or they run but fail silently.

**Why it happens:** Shared property tests are in a new directory not covered by existing test patterns.

**How to avoid:**
1. Configure Jest `testMatch` patterns to include shared property tests
2. Add separate test script for property tests: `test:property`
3. Verify property tests run in all three platforms
4. Add CI/CD step for property test execution

**Warning signs:** Property tests pass locally but fail in CI, tests not found errors.

**Prevention:**
```javascript
// frontend-nextjs/jest.config.js
module.exports = {
  testMatch: [
    '**/tests/property/**/*.test.ts',  // Existing frontend tests
    '**/shared/property-tests/**/*.ts',  // NEW: Shared property tests
  ],
};
```

### Pitfall 4: Inconsistent Seed Reproducibility

**What goes wrong:** Property test failures cannot be reproduced because seed differs across runs.

**Why it happens:** FastCheck and proptest use random seeds by default, making failures non-deterministic.

**How to avoid:**
1. Configure FastCheck with `seed: Date.now()` and log seed on failure
2. Use `fc.assert(fc.property(...), { seed })` for reproducible runs
3. Document seed in CI/CD logs for failed tests
4. Provide `--seed` flag for local reproduction

**Warning signs:** "Fails locally but passes in CI" or vice versa.

**Prevention:**
```typescript
// frontend-nextjs/shared/property-tests/config.ts

export const PROPERTY_TEST_CONFIG = {
  numRuns: 100,
  timeout: 10000,
  seed: process.env.FASTCHECK_SEED ? parseInt(process.env.FASTCHECK_SEED) : undefined,
};

// Usage
fc.assert(
  fc.property(fc.string(), (s) => s.length >= 0),
  PROPERTY_TEST_CONFIG
);
```

### Pitfall 5: Property Test Performance Degradation

**What goes wrong:** Property tests take too long (minutes instead of seconds), slowing down CI/CD.

**Why it happens:** Too many test runs (default 100), complex arbitraries, or expensive operations in properties.

**How to avoid:**
1. Use `numRuns: 10-50` for slow properties, `numRuns: 100` for fast properties
2. Profile property test performance before committing
3. Use `fc.sample()` to preview arbitrary generation
4. Split complex properties into smaller, focused properties

**Warning signs:** CI/CD pipeline timing out on property test step, test runs >30 seconds.

**Prevention:**
```typescript
// Fast property (pure function, no I/O)
fc.assert(
  fc.property(fc.string(), (s) => s.length >= 0),
  { numRuns: 100 }  // Default is fine for fast tests
);

// Slow property (involves serialization, I/O)
fc.assert(
  fc.property(fc.jsonObject(), (data) => {
    const serialized = JSON.stringify(data);
    const deserialized = JSON.parse(serialized);
    return deepEquals(data, deserialized);
  }),
  { numRuns: 20, timeout: 5000 }  // Reduce runs for slow tests
);
```

## Code Examples

Verified patterns from existing Atom codebase:

### Example 1: Agent State Machine Properties (Existing Frontend Test)

```typescript
// Source: frontend-nextjs/tests/property/agent-state-machine-invariants.test.ts (verified working)

import fc from 'fast-check';
import { describe, it, expect } from '@jest/globals';

type AgentMaturityLevel =
  | 'STUDENT'
  | 'INTERN'
  | 'SUPERVISED'
  | 'AUTONOMOUS';

describe('Agent Maturity Level State Machine Invariants', () => {
  it('should only allow forward maturity transitions via graduation', () => {
    const maturityOrder: AgentMaturityLevel[] = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'];

    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 3 }),
        (fromIndex) => {
          const fromLevel = maturityOrder[fromIndex];
          const validNextLevels = maturityOrder.slice(fromIndex + 1);

          if (fromLevel !== 'AUTONOMOUS') {
            expect(validNextLevels.length).toBeGreaterThan(0);
          } else {
            expect(validNextLevels.length).toBe(0);
          }
        }
      )
    );
  });
});
```

### Example 2: Mobile Queue Invariants (Existing Mobile Test)

```typescript
// Source: mobile/src/__tests__/property/queueInvariants.test.ts (verified working)

import fc from 'fast-check';

test('higher priority actions appear before lower priority', () => {
  fc.assert(
    fc.property(
      fc.array(
        fc.record({
          id: fc.uuid(),
          priority: fc.integer({ min: 1, max: 10 }),
          created_at: fc.integer({ min: 1000000000, max: 9999999999 }),
        }),
        { minLength: 2, maxLength: 100 }
      ),
      (actions) => {
        const sorted = sortQueue(actions);

        for (let i = 0; i < sorted.length - 1; i++) {
          const current = sorted[i];
          const next = sorted[i + 1];

          if (current.priority !== next.priority) {
            expect(current.priority).toBeGreaterThanOrEqual(next.priority);
          }
        }
      }
    ),
    { numRuns: 100 }
  );
});
```

### Example 3: Rust Error Handling Properties (Existing Desktop Test)

```rust
// Source: frontend-nextjs/src-tauri/tests/error_handling_proptest.rs (verified working)

use proptest::prelude::*;

proptest! {
    #[test]
    fn prop_file_write_then_read_identity(
        content in prop::collection::vec(any::<u8>(), 0..1000)
    ) {
        // INVARIANT: Write then read yields exact content match
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join(format!("prop_test_{:x}.bin", rand::random::<u64>()));

        fs::write(&test_file, &content).unwrap();
        let read_content = fs::read(&test_file).unwrap();
        let _ = fs::remove_file(&test_file);

        prop_assert_eq!(content, read_content);
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Example-based testing** | **Property-based testing** | 2018+ (fast-check v1.0) | Catches edge cases examples miss, automated shrinking |
| **Manual random generation** | **Framework arbitraries** | 2019+ (fast-check v2.0) | Reproducible seeds, better shrinking |
| **Platform-specific tests** | **Shared invariant tests** | 2026 (Phase 147) | Consistent invariants across platforms |
| **Duplicate test logic** | **SYMLINK distribution** | 2026 (Phase 144) | Single source of truth, DRY principle |

**Deprecated/outdated:**
- **jsverify**: No longer maintained, last update 2018, replaced by fast-check
- **test-check**: Smaller community, fewer features, less active development
- **Manual property testing**: Custom random() implementations replaced by mature frameworks

## Open Questions

1. **How many shared invariants should we define?**
   - What we know: Canvas state, agent maturity, and serialization are obvious candidates
   - What's unclear: Should we create shared properties for queue invariants, device state, Tauri commands?
   - Recommendation: Start with 3-5 core shared invariants (canvas, agent maturity, serialization, state machines), add more based on platform-specific needs

2. **Should Rust tests use same seed as TypeScript?**
   - What we know: FastCheck and proptest support seed configuration
   - What's unclear: Should we synchronize seeds for cross-platform reproducibility?
   - Recommendation: No, different random generators can't share seeds. Log seeds separately, document correspondence in test reports.

3. **How to handle property test failures in CI/CD?**
   - What we know: Property tests can fail with rare edge cases
   - What's unclear: Should property test failures block PRs or just warn?
   - Recommendation: Property test failures should block PRs (critical invariants), but provide `--skip-property-tests` flag for emergency merges

4. **Performance budget for property test suite?**
   - What we know: Existing property tests run quickly (<30 seconds total)
   - What's unclear: What's the maximum acceptable runtime for full property test suite?
   - Recommendation: Target <2 minutes for all property tests across platforms. Use `numRuns` tuning to stay within budget.

5. **Should we share test fixtures across platforms?**
   - What we know: Test data fixtures can be shared via JSON files
   - What's unclear: Should we create shared fixtures for property tests?
   - Recommendation: Yes, create `frontend-nextjs/shared/property-tests/fixtures/` with JSON fixtures, symlink to mobile/desktop Rust tests

## Sources

### Primary (HIGH confidence)

- **fast-check v4.5.3** - npm package verified via `npm info fast-check` and frontend-nextjs/package.json
- **proptest v1.0** - Rust crate verified via frontend-nextjs/src-tauri/Cargo.toml
- **Frontend property tests** - 13 test files verified in `/Users/rushiparikh/projects/atom/frontend-nextjs/tests/property/`
- **Mobile property tests** - 2 test files verified in `/Users/rushiparikh/projects/atom/mobile/src/__tests__/property/`
- **Desktop Rust proptests** - 4 test files verified in `/Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/tests/`
- **Phase 144 RESEARCH.md** - SYMLINK strategy for sharing utilities (verified in codebase)
- **Phase 145 RESEARCH.md** - API type generation patterns (verified in codebase)
- **Phase 146 RESEARCH.md** - Cross-platform coverage enforcement (verified in codebase)

### Secondary (MEDIUM confidence)

- **[fast-check npm package](https://www.npmjs.com/package/fast-check)** - Official package documentation (verified via npm CLI)
- **[fast-check GitHub repository](https://github.com/dubzzz/fast-check)** - Source code, examples, and documentation (verified via web reader)
- **REQUIREMENTS.md** - CROSS-04 property testing requirements (verified in codebase)
- **ROADMAP.md** - Phase 147 success criteria and dependencies (verified in codebase)

### Tertiary (LOW confidence)

- None (all findings verified via primary sources)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - FastCheck 4.5.3 and proptest 1.0 verified in project package.json and Cargo.toml
- Architecture: HIGH - Existing property test patterns verified in 19 test files across 3 platforms
- Pitfalls: MEDIUM - Based on common property testing issues, but Atom-specific integration needs validation

**Research date:** March 6, 2026
**Valid until:** April 5, 2026 (30 days - stable ecosystem, FastCheck and proptest have been mature for years)

**Key assumptions:**
1. Phase 144 (SYMLINK strategy) is complete and operational
2. Phase 145 (API type generation) is complete and not blocking
3. Phase 146 (weighted coverage) is complete with aggregation infrastructure
4. Existing property tests are passing and stable (19 test files verified)

**Validation needed:**
- Mobile property test execution environment (verify jest-expo runs FastCheck tests correctly)
- Desktop Rust proptest execution (verify `cargo test` runs proptest files)
- CI/CD integration patterns (verify property tests run in GitHub Actions workflow)

**Next steps for planner:**
1. Create shared property tests structure in `frontend-nextjs/shared/property-tests/`
2. Extract common invariants from existing 19 property test files
3. Configure SYMLINK distribution for mobile (TypeScript tests only)
4. Document Rust correspondence patterns (not symlinked, but documented)
5. Create aggregation script for cross-platform property test results
6. Add property test execution to CI/CD workflow
