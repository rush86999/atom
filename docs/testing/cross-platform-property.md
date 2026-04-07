# Cross-Platform Property Testing Guide

## Overview

Atom is a multi-platform AI automation platform with four distinct codebases: **Backend** (Python/FastAPI), **Frontend** (React/Next.js), **Mobile** (React Native), and **Desktop** (Tauri/Rust). This guide explains the cross-platform property-based testing framework that validates critical invariants across all platforms.

**What is Property-Based Testing?**
Property-based testing (PBT) is a testing approach where you specify *invariants* (properties that must always be true) and the testing framework generates hundreds of random inputs to verify those properties. Unlike example-based testing (specific inputs), PBT finds edge cases you wouldn't think to test.

**Why Cross-Platform Property Testing?**
- **Unified invariants**: Canvas state, agent maturity, and data serialization behave identically across platforms
- **Bug discovery**: Random generation finds edge cases that traditional tests miss
- **Regression prevention**: Properties catch breaking changes across refactors
- **Confidence**: 100+ test cases per property provide stronger guarantees than manual examples

**Frameworks:**
- **FastCheck 4.5.3**: Property-based testing for TypeScript/React Native (frontend, mobile)
- **proptest 1.0**: Property-based testing for Rust (desktop)

**Success Metrics:**
- **12 shared properties** across 3 invariant modules (canvas, agent maturity, serialization)
- **3 platforms** running property tests (frontend Next.js, mobile React Native, desktop Rust)
- **Unified reporting** with platform breakdown and historical trend tracking

**Phase:** 147 - Cross-Platform Property Testing (Complete)
**Status:** Operational in CI/CD

## Quick Start

### Local Execution

Run property tests on all platforms:

```bash
# 1. Frontend (Next.js)
cd frontend-nextjs
npm test -- tests/property/shared-invariants.test.ts

# 2. Mobile (React Native)
cd mobile
npm test -- shared-invariants

# 3. Desktop (Rust/Tauri)
cd frontend-nextjs/src-tauri
cargo test property_tests

# 4. Aggregate results (optional)
python3 backend/tests/scripts/aggregate_property_tests.py \
  --frontend coverage/jest-frontend-property-results.json \
  --mobile coverage/jest-mobile-property-results.json \
  --desktop coverage/proptest-results.json \
  --format text
```

### CI/CD Execution

Property tests run automatically on push/PR to main branch. See `.github/workflows/cross-platform-property-tests.yml` for workflow configuration.

```bash
# Manual trigger (requires GitHub CLI)
gh workflow run cross-platform-property-tests.yml

# View results
gh run list --workflow=cross-platform-property-tests.yml
gh run view [run-id]
```

### Expected Output

```
✓ canvas state machine properties (9 tests)
✓ agent maturity properties (10 tests)
✓ serialization roundtrip properties (13 tests)

Test Suites: 1 passed, 1 total
Tests:       32 passed, 32 total
```

## Architecture

### Components

The cross-platform property testing system consists of three core components:

1. **Shared Property Tests** (`frontend-nextjs/shared/property-tests/`)
   - Common invariants defined once, shared across platforms
   - 3 modules: canvas-invariants.ts, agent-maturity-invariants.ts, serialization-invariants.ts
   - FastCheck arbitraries for random generation (fc.integer(), fc.string(), etc.)

2. **Platform Test Runners**
   - **Frontend**: `frontend-nextjs/tests/property/shared-invariants.test.ts` (imports from @atom/property-tests)
   - **Mobile**: `mobile/src/__tests__/property/shared-invariants.test.ts` (imports via SYMLINK)
   - **Desktop**: `frontend-nextjs/src-tauri/tests/state_machine_proptest.rs` (correspondence documented in README)

3. **Aggregation Infrastructure** (Phase 147-03)
   - `backend/tests/scripts/aggregate_property_tests.py`: Combines FastCheck + proptest results
   - `.github/workflows/cross-platform-property-tests.yml`: 4 CI/CD jobs (3 parallel + 1 aggregate)
   - `backend/tests/coverage_reports/metrics/property_test_results.json`: Historical tracking

### SYMLINK Strategy (Phase 144)

Mobile app shares property tests via SYMLINK to avoid duplication:

```bash
mobile/src/shared/property-tests → ../../frontend-nextjs/shared/property-tests
```

Benefits:
- **Single source of truth**: Properties defined once in frontend
- **No duplication**: Changes automatically apply to mobile
- **Consistent testing**: Both platforms run identical invariants

Verification:
```bash
ls -la mobile/src/shared/property-tests
# lrwxr-xr-x  1 user  staff  64 Mar  6 18:55 property-tests -> ../../frontend-nextjs/shared/property-tests
```

### Rust Correspondence (Desktop)

Desktop Rust tests don't use SYMLINK (different language). Instead, correspondence is documented in `frontend-nextjs/src-tauri/tests/property_tests/README.md`:

```
TypeScript Property                | Rust Property
-----------------------------------|-----------------------------------
canvasStateMachineProperty         | test_canvas_state_machine_invariants
maturityMonotonicProgression       | test_agent_maturity_monotonic
jsonRoundtripPreservesData         | proptest_json_roundtrip
```

Rust tests use proptest macros with equivalent invariants, adapted to Rust type system.

### Aggregation Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │     │    Mobile       │     │    Desktop      │
│  (FastCheck)    │     │  (FastCheck)    │     │  (proptest)     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                      │                        │
         │ Jest JSON            │ Jest JSON              │ cargo test
         │ output               │ output                 │ output (formatter)
         │                      │                        │
         └──────────────────────┴────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Aggregation Script   │
                    │ (aggregate_property_) │
                    │   tests.py            │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │   PR Comment          │
                    │   Platform Breakdown  │
                    │   Historical Trends   │
                    └───────────────────────┘
```

## Property Library

### Canvas State Invariants (9 properties)

**Module**: `shared/property-tests/canvas-invariants.ts`

Canvas presentation state machine properties:

| Property | Description | Arbitrary | Test Cases |
|----------|-------------|-----------|------------|
| `canvasStateMachineProperty` | All transitions respect state machine rules | fc.boolean(), fc.string() | 100+ |
| `canvasNoDirectPresentingToIdle` | Cannot skip from PRESENTING to IDLE | fc.array(fc.string()) | 100+ |
| `canvasErrorRecoveryToIdle` | ERROR state recovers to IDLE | fc.string() | 100+ |
| `canvasTerminalStatesLeadToIdle` | CLOSED/COMPLETED lead to IDLE | fc.string() | 100+ |
| `canvasIdleToPresenting` | IDLE transitions to PRESENTING | fc.string() | 100+ |
| `canvasPresentingTransitions` | PRESENTING state transitions valid | fc.string(), fc.boolean() | 100+ |
| `canvasErrorStateRecoverability` | ERROR state is recoverable | fc.string() | 100+ |
| `canvasNoTerminalStateLoops` | Terminal states don't loop | fc.string() | 100+ |
| `canvasStateSequenceValidity` | State sequences are valid | fc.array(fc.string()) | 100+ |

**Example:**
```typescript
export const canvasNoDirectPresentingToIdle = fc.property(
  fc.array(fc.string()), // Canvas actions
  (actions) => {
    const stateMachine = new CanvasStateMachine();
    let currentState = CanvasState.IDLE;

    for (const action of actions) {
      const previousState = currentState;
      currentState = stateMachine.transition(currentState, action);

      // Invariant: Cannot transition directly from PRESENTING to IDLE
      if (previousState === CanvasState.PRESENTING && currentState === CanvasState.IDLE) {
        throw new Error('Invalid transition: PRESENTING → IDLE');
      }
    }

    return true;
  }
);
```

### Agent Maturity Invariants (10 properties)

**Module**: `shared/property-tests/agent-maturity-invariants.ts`

Agent maturity level state machine properties:

| Property | Description | Arbitrary | Test Cases |
|----------|-------------|-----------|------------|
| `maturityMonotonicProgression` | Maturity only increases (STUDENT → INTERN → SUPERVISED → AUTONOMOUS) | fc.array(fc.string()) | 100+ |
| `autonomousIsTerminal` | AUTONOMOUS is terminal state | fc.string() | 100+ |
| `studentCannotSkipToAutonomous` | STUDENT cannot skip to AUTONOMOUS | fc.array(fc.string()) | 100+ |
| `maturityTransitionsAreForward` | All transitions move forward | fc.string(), fc.string() | 100+ |
| `maturityOrderConsistency` | Order is preserved across transitions | fc.array(fc.string()) | 100+ |
| `maturityGraduationPath` | Graduation follows defined path | fc.array(fc.string()) | 100+ |
| `maturityNoBackwardTransitions` | No backward transitions allowed | fc.string(), fc.string() | 100+ |
| `maturityLevelUniqueness` | Each maturity level is unique | fc.constantFrom() | 4 |
| `maturityTerminalStateUniqueness` | Only AUTONOMOUS is terminal | fc.string() | 100+ |

**Example:**
```typescript
export const maturityMonotonicProgression = fc.property(
  fc.array(fc.string()), // Maturity transitions
  (transitions) => {
    const stateMachine = new AgentMaturityStateMachine();
    let currentLevel = MaturityLevel.STUDENT;
    const levels = [MaturityLevel.STUDENT, MaturityLevel.INTERN, MaturityLevel.SUPERVISED, MaturityLevel.AUTONOMOUS];

    for (const transition of transitions) {
      const previousLevel = currentLevel;
      currentLevel = stateMachine.transition(currentLevel, transition);

      // Invariant: Maturity only increases (ordinal value)
      if (levels.indexOf(currentLevel) < levels.indexOf(previousLevel)) {
        throw new Error('Maturity cannot decrease');
      }
    }

    return true;
  }
);
```

### Serialization Invariants (13 properties)

**Module**: `shared/property-tests/serialization-invariants.ts`

JSON serialization roundtrip properties:

| Property | Description | Arbitrary | Test Cases |
|----------|-------------|-----------|------------|
| `jsonRoundtripPreservesData` | JSON stringify/parse preserves data | fc.anything() | 100+ |
| `agentDataRoundtrip` | Agent data serializes correctly | fc.agentData() | 100+ |
| `canvasDataRoundtrip` | Canvas data serializes correctly | fc.canvasData() | 100+ |
| `arrayOrderPreserved` | Array order preserved | fc.array(fc.integer()) | 100+ |
| `nullAndUndefinedHandling` | null/undefined handled correctly | fc.option(fc.string()) | 100+ |
| `dateSerialization` | Date serialization preserves timestamp | fc.date() | 100+ |
| `nestedObjectSerialization` | Nested objects preserved | fc.dictionary() | 100+ |
| `specialCharactersInStrings` | Special characters preserved | fc.string() | 100+ |
| `numberPrecisionPreservation` | Number precision preserved | fc.float() | 100+ |
| `booleanSerialization` | Boolean values preserved | fc.boolean() | 100+ |
| `emptyValuesHandling` | Empty arrays/objects preserved | fc.oneof() | 100+ |

**Example:**
```typescript
export const jsonRoundtripPreservesData = fc.property(
  fc.anything(), // Arbitrary JSON-compatible data
  (data) => {
    const serialized = JSON.stringify(data);
    const deserialized = JSON.parse(serialized);

    // Invariant: Roundtrip preserves data
    assertDeepEqual(data, deserialized);
    return true;
  }
);

// Custom arbitrary for agent data
const fcAgentData = fc.record({
  id: fc.uuid(),
  name: fc.string(),
  maturityLevel: fc.constantFrom('STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'),
  capabilities: fc.array(fc.string()),
  createdAt: fc.date(),
});
```

### Total Property Count

- **Canvas invariants**: 9 properties
- **Agent maturity invariants**: 10 properties
- **Serialization invariants**: 13 properties
- **Total**: 32 shared properties

Each property runs 100+ random test cases, generating **3,200+ test cases** per platform.

## Platform-Specific Guides

### Frontend (Next.js)

**Test Runner**: Jest with ts-jest
**Property Framework**: FastCheck 4.5.3
**Test Location**: `frontend-nextjs/tests/property/shared-invariants.test.ts`

**Configuration** (`frontend-nextjs/jest.config.js`):
```javascript
module.exports = {
  testMatch: [
    // Shared property tests (Phase 147)
    "<rootDir>/shared/property-tests/**/*.ts",
    // Standard test files
    "<rootDir>/tests/**/*.test.(ts|tsx|js)",
    // ... more patterns
  ],
  moduleNameMapper: {
    "^@atom/property-tests(.*)$": "<rootDir>/shared/property-tests$1",
  },
};
```

**Running Tests**:
```bash
# Run all property tests
cd frontend-nextjs
npm test -- tests/property/shared-invariants.test.ts

# Run with verbose output
npm test -- tests/property/shared-invariants.test.ts --verbose

# Run specific property
npm test -- tests/property/shared-invariants.test.ts -t "canvas state machine"
```

**Import Pattern**:
```typescript
import fc from 'fast-check';
import { describe, it, expect } from '@jest/globals';
import {
  canvasStateMachineProperty,
  maturityMonotonicProgression,
  jsonRoundtripPreservesData,
} from '@atom/property-tests';

describe('Canvas State Invariants', () => {
  it('should respect state machine transitions', () => {
    fc.assert(canvasStateMachineProperty);
  });
});
```

### Mobile (React Native)

**Test Runner**: Jest with jest-expo
**Property Framework**: FastCheck 4.5.3 (via SYMLINK)
**Test Location**: `mobile/src/__tests__/property/shared-invariants.test.ts`

**SYMLINK Setup** (Phase 144):
```bash
# Create SYMLINK (already done)
cd mobile/src/shared
ln -s ../../frontend-nextjs/shared/property-tests property-tests
```

**Verification**:
```bash
# Check SYMLINK exists
ls -la mobile/src/shared/property-tests

# Verify it points to correct location
readlink mobile/src/shared/property-tests
# Output: ../../frontend-nextjs/shared/property-tests
```

**Configuration** (`mobile/jest.config.js`):
```javascript
module.exports = {
  testMatch: [
    // Shared property tests (Phase 147)
    "<rootDir>/src/shared/property-tests/**/*.ts",
    // Standard test files
    "<rootDir>/src/**/__tests__/**/*.test.(ts|tsx)",
    // ... more patterns
  ],
  moduleNameMapper: {
    "^@atom/property-tests(.*)$": "<rootDir>/src/shared/property-tests$1",
  },
};
```

**Running Tests**:
```bash
# Run all property tests
cd mobile
npm test -- shared-invariants

# Run with verbose output
npm test -- shared-invariants --verbose
```

**Import Pattern** (same as frontend):
```typescript
import fc from 'fast-check';
import { canvasStateMachineProperty } from '@atom/property-tests';
// ... same test code
```

### Desktop (Tauri-Rust)

**Test Runner**: cargo test
**Property Framework**: proptest 1.0
**Test Location**: `frontend-nextjs/src-tauri/tests/state_machine_proptest.rs`

**Correspondence Documentation** (`README.md`):
```markdown
# Property Tests Correspondence

This document maps TypeScript properties to Rust proptests.

## Canvas State Properties

| TypeScript Property | Rust Property | Notes |
|---------------------|---------------|-------|
| canvasStateMachineProperty | test_canvas_state_machine_invariants | Equivalent state machine rules |
| canvasNoDirectPresentingToIdle | test_no_direct_presenting_to_idle | Same invariant |

## Agent Maturity Properties

| TypeScript Property | Rust Property | Notes |
|---------------------|---------------|-------|
| maturityMonotonicProgression | test_agent_maturity_monotonic | Ordinal comparison |
| autonomousIsTerminal | test_autonomous_is_terminal | Terminal state check |
```

**Configuration** (`Cargo.toml`):
```toml
[dev-dependencies]
proptest = "1.0"
serde_json = "1.0"
```

**Running Tests**:
```bash
# Run all property tests
cd frontend-nextjs/src-tauri
cargo test property_tests

# Run specific property
cargo test test_canvas_state_machine_invariants

# Run with output
cargo test property_tests -- --nocapture
```

**Example (Rust proptest)**:
```rust
use proptest::prelude::*;

proptest! {
  #[test]
  fn test_canvas_state_machine_invariants(
    actions in prop::collection::vec(".*", 0..10)
  ) {
    let mut state_machine = CanvasStateMachine::new();
    let mut current_state = CanvasState::Idle;

    for action in actions {
      let previous_state = current_state;
      current_state = state_machine.transition(current_state, &action);

      // Invariant: Cannot transition directly from Presenting to Idle
      if previous_state == CanvasState::Presenting && current_state == CanvasState::Idle {
        panic!("Invalid transition: Presenting → Idle");
      }
    }
  }
}
```

## CI/CD Integration

### Workflow Overview

**File**: `.github/workflows/cross-platform-property-tests.yml`

**Jobs** (4 jobs: 3 parallel + 1 sequential):

#### Job 1: Frontend Property Tests
```yaml
frontend-property-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-node@v3
      with:
        node-version: '20'
        cache: 'npm'
        cache-dependency-path: frontend-nextjs/package-lock.json
    - name: Install dependencies
      run: cd frontend-nextjs && npm ci
    - name: Run property tests
      run: |
        cd frontend-nextjs
        npm test -- tests/property/shared-invariants.test.ts --ci --json \
          --outputFile=coverage/jest-frontend-property-results.json
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: jest-frontend-property-results
        path: frontend-nextjs/coverage/jest-frontend-property-results.json
        retention-days: 7
```

#### Job 2: Mobile Property Tests
```yaml
mobile-property-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-node@v3
      with:
        node-version: '20'
        cache: 'npm'
        cache-dependency-path: mobile/package-lock.json
    - name: Install dependencies
      run: cd mobile && npm ci
    - name: Run property tests
      run: |
        cd mobile
        npm test -- shared-invariants --ci --json \
          --outputFile=coverage/jest-mobile-property-results.json
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: jest-mobile-property-results
        path: mobile/coverage/jest-mobile-property-results.json
        retention-days: 7
```

#### Job 3: Desktop Property Tests
```yaml
desktop-property-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - uses: actions-rs/toolchain@v1
      with:
        toolchain: stable
        cache: true
    - name: Run property tests
      run: |
        cd frontend-nextjs/src-tauri
        cargo test property_tests 2>&1 | tee proptest-output.txt
    - name: Format results
      run: |
        python3 tests/proptest_formatter.py \
          --input proptest-output.txt \
          --output proptest-results.json
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: proptest-results
        path: frontend-nextjs/src-tauri/coverage/proptest-results.json
        retention-days: 7
```

#### Job 4: Aggregate Results
```yaml
aggregate-results:
  needs: [frontend-property-tests, mobile-property-tests, desktop-property-tests]
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - name: Download all artifacts
      uses: actions/download-artifact@v3
      with:
        path: artifacts
    - name: Run aggregation script
      run: |
        python3 backend/tests/scripts/aggregate_property_tests.py \
          --frontend artifacts/jest-frontend-property-results/jest-frontend-property-results.json \
          --mobile artifacts/jest-mobile-property-results/jest-mobile-property-results.json \
          --desktop artifacts/proptest-results/proptest-results.json \
          --output property_test_results.json \
          --format json
    - name: Upload aggregated results
      uses: actions/upload-artifact@v3
      with:
        name: property-test-results
        path: property_test_results.json
        retention-days: 30
    - name: Update historical tracking
      run: |
        # Merge with backend/tests/coverage_reports/metrics/property_test_results.json
        # Keep last 30 runs for trend analysis
    - name: Post PR comment
      uses: actions/github-script@v6
      if: github.event_name == 'pull_request'
      with:
        script: |
          const fs = require('fs');
          const results = JSON.parse(fs.readFileSync('property_test_results.json', 'utf8'));
          const markdown = generatePRComment(results);
          github.rest.issues.createComment({
            issue_number: context.issue.number,
            owner: context.repo.owner,
            repo: context.repo.repo,
            body: markdown
          });
```

### PR Comment Format

```markdown
## 🧪 Property Test Results

**Platform Breakdown:**

| Platform | Total | Passed | Failed | Pass Rate |
|----------|-------|--------|--------|-----------|
| Frontend | 32 | 32 | 0 | 100% ✅ |
| Mobile | 32 | 32 | 0 | 100% ✅ |
| Desktop | 27 | 27 | 0 | 100% ✅ |
| **Total** | **91** | **91** | **0** | **100%** |

**Trends:** Frontend ↑ 2% | Mobile → | Desktop ↓ 1%

**Details:**
- All canvas state invariants passed (9/9)
- All agent maturity invariants passed (10/10)
- All serialization invariants passed (13/13)
```

### Historical Tracking

**File**: `backend/tests/coverage_reports/metrics/property_test_results.json`

```json
{
  "total": 91,
  "passed": 91,
  "failed": 0,
  "pass_rate": 100.0,
  "platforms": {
    "frontend": {"total": 32, "passed": 32, "failed": 0},
    "mobile": {"total": 32, "passed": 32, "failed": 0},
    "desktop": {"total": 27, "passed": 27, "failed": 0}
  },
  "timestamp": "2026-03-06T10:30:00Z",
  "history": [
    {"timestamp": "2026-03-05T10:00:00Z", "pass_rate": 98.9},
    {"timestamp": "2026-03-04T10:00:00Z", "pass_rate": 97.8},
    // ... last 30 runs
  ]
}
```

Trend indicators (↑↓→) calculated from last 3 runs in history array.

## Property Testing Patterns

### State Machine Invariants

**Pattern**: Test all valid state transitions and reject invalid ones.

**Example (Canvas State)**:
```typescript
// Valid: IDLE → PRESENTING → CLOSED → IDLE
// Invalid: IDLE → CLOSED (missing PRESENTING)

export const canvasStateMachineProperty = fc.property(
  fc.array(fc.string()), // Random action sequence
  (actions) => {
    const stateMachine = new CanvasStateMachine();
    let currentState = CanvasState.IDLE;

    for (const action of actions) {
      const previousState = currentState;
      currentState = stateMachine.transition(currentState, action);

      // Check all transition rules
      assertValidTransition(previousState, currentState, action);
    }

    return true;
  }
);
```

**What to test**:
- ✅ All defined transitions work correctly
- ✅ Invalid transitions are rejected
- ✅ Terminal states cannot transition further
- ✅ Recovery paths exist from error states

### Serialization Roundtrips

**Pattern**: Data must survive serialization/deserialization unchanged.

**Example (JSON)**:
```typescript
export const jsonRoundtripPreservesData = fc.property(
  fc.anything(), // Random JSON-compatible data
  (data) => {
    const serialized = JSON.stringify(data);
    const deserialized = JSON.parse(serialized);

    // Deep equality check
    assertDeepEqual(data, deserialized);
    return true;
  }
);
```

**What to test**:
- ✅ All data types serialize correctly (strings, numbers, booleans, null, arrays, objects)
- ✅ Nested structures preserve hierarchy
- ✅ Special characters don't break serialization
- ✅ Dates preserve timestamps (or ISO string format)
- ✅ Precision is maintained (floating-point numbers)

### Monotonic Progression

**Pattern**: Values only increase (or decrease) along a sequence.

**Example (Agent Maturity)**:
```typescript
const MATURITY_LEVELS = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'];

export const maturityMonotonicProgression = fc.property(
  fc.array(fc.string()), // Random maturity transitions
  (transitions) => {
    const stateMachine = new AgentMaturityStateMachine();
    let currentLevel = MaturityLevel.STUDENT;

    for (const transition of transitions) {
      const previousLevel = currentLevel;
      currentLevel = stateMachine.transition(currentLevel, transition);

      // Invariant: Maturity only increases
      const previousOrdinal = MATURITY_LEVELS.indexOf(previousLevel);
      const currentOrdinal = MATURITY_LEVELS.indexOf(currentLevel);

      if (currentOrdinal < previousOrdinal) {
        throw new Error(`Maturity decreased: ${previousLevel} → ${currentLevel}`);
      }
    }

    return true;
  }
);
```

**What to test**:
- ✅ Sequence respects ordering (A < B < C < D)
- ✅ No backward transitions allowed
- ✅ Terminal state cannot progress further
- ✅ Skipping levels is blocked (unless explicitly allowed)

### Guards and Constraints

**Pattern**: Certain state transitions are guarded by conditions.

**Example (Canvas Presenting Guard)**:
```typescript
export const canvasNoDirectPresentingToIdle = fc.property(
  fc.array(fc.string()), // Random action sequence
  (actions) => {
    const stateMachine = new CanvasStateMachine();
    let currentState = CanvasState.IDLE;

    for (const action of actions) {
      const previousState = currentState;
      currentState = stateMachine.transition(currentState, action);

      // Guard: Cannot transition directly from PRESENTING to IDLE
      // Must go through CLOSED or COMPLETED first
      if (previousState === CanvasState.PRESENTING && currentState === CanvasState.IDLE) {
        throw new Error('Guard violated: PRESENTING → IDLE (blocked)');
      }
    }

    return true;
  }
);
```

**What to test**:
- ✅ Guards prevent specific transitions
- ✅ Alternative paths exist (guard → intermediate → target)
- ✅ Guards apply consistently regardless of action sequence

## Troubleshooting

### FastCheck Seed Reproduction

**Problem**: Property test failed, but you can't reproduce it locally.

**Solution**: Use the `FASTCHECK_SEED` environment variable.

```bash
# CI/CD output shows: "Error: Property failed after 42 tests, seed: 12345"
# Reproduce locally:

FASTCHECK_SEED=12345 npm test -- tests/property/shared-invariants.test.ts
```

**In code**:
```typescript
// Set global seed (for debugging)
fc.configureGlobal({ seed: 12345 });

// Run single property
fc.assert(canvasStateMachineProperty);
```

### SYMLINK Issues

**Problem**: Mobile tests can't find `@atom/property-tests`.

**Solution**: Verify SYMLINK exists and points to correct location.

```bash
# Check SYMLINK exists
ls -la mobile/src/shared/property-tests

# Expected output:
# lrwxr-xr-x  1 user  staff  64 Mar  6 18:55 property-tests -> ../../frontend-nextjs/shared/property-tests

# If missing, recreate SYMLINK
cd mobile/src/shared
ln -s ../../frontend-nextjs/shared/property-tests property-tests

# Verify relative path
readlink mobile/src/shared/property-tests
# Output: ../../frontend-nextjs/shared/property-tests
```

**Common issues**:
- ❌ SYMLINK points to wrong directory (check relative path)
- ❌ SYMLINK is absolute instead of relative (breaks on other machines)
- ❌ Target directory doesn't exist (verify frontend-nextjs/shared/property-tests)

### Jest Not Finding Tests

**Problem**: `npm test -- shared-invariants` reports "No tests found".

**Solution**: Check `testMatch` pattern in `jest.config.js`.

```javascript
// frontend-nextjs/jest.config.js
module.exports = {
  testMatch: [
    // ✅ Correct: Matches shared property tests
    "<rootDir>/shared/property-tests/**/*.ts",

    // ❌ Wrong: Doesn't match .ts files in shared/
    // "<rootDir>/shared/**/*.test.ts",  // Requires .test.ts extension

    // ❌ Wrong: Doesn't include shared/ directory
    // "<rootDir>/tests/**/*.test.ts",  // Only tests/ directory
  ],
};
```

**Verification**:
```bash
# Check which files Jest matches
cd frontend-nextjs
npx jest --showConfig | grep testMatch

# Run with --debug flag
npx jest shared-invariants --debug
```

### Proptest Failures

**Problem**: Rust proptest failed with obscure error message.

**Solution**: Run `cargo test` with `-- --nocapture` for details.

```bash
# Run proptest with output
cd frontend-nextjs/src-tauri
cargo test test_canvas_state_machine_invariants -- --nocapture

# Output shows:
# [2016-03-06T10:30:00Z INFO  proptest] # Config: proptest
# [2016-03-06T10:30:00Z INFO  proptest] # Tests: 100
# [2016-03-06T10:30:00Z INFO  proptest] # Failures: 1
# [2016-03-06T10:30:00Z INFO  proptest] # Failing input: test_canvas_state_machine_invariants
#     actions = ["present", "idle"]  # Minimal failing case
```

**Reproduce specific case**:
```rust
// Paste failing input into test
#[test]
fn test_reproduce_failure() {
    let actions = vec!["present", "idle"];
    let mut state_machine = CanvasStateMachine::new();
    // ... test logic
}
```

### Module Resolution Errors

**Problem**: `Cannot find module '@atom/property-tests'`.

**Solution**: Check `moduleNameMapper` in `jest.config.js`.

```javascript
// frontend-nextjs/jest.config.js
module.exports = {
  moduleNameMapper: {
    // ✅ Correct: Maps @atom/property-tests to shared/property-tests
    "^@atom/property-tests(.*)$": "<rootDir>/shared/property-tests$1",

    // ❌ Wrong: Missing path alias
    // (no entry for @atom/property-tests)

    // ❌ Wrong: Incorrect capture group syntax
    // "^@atom/property-tests$": "<rootDir>/shared/property-tests",  // No (.*) capture
  },
};
```

**Verification**:
```bash
# Check Jest resolves module correctly
cd frontend-nextjs
node -e "console.log(require.resolve('@atom/property-tests'))"
# Output: /Users/.../frontend-nextjs/shared/property-tests/index.ts
```

### FastCheck API Changes

**Problem**: `fc.jsonObject()` throws "is not a function".

**Solution**: FastCheck 4.5.3 doesn't have `fc.jsonObject()`. Use `fc.anything()` instead.

```typescript
// ❌ Wrong (FastCheck 3.x API)
export const jsonRoundtripPreservesData = fc.property(
  fc.jsonObject(),  // Doesn't exist in FastCheck 4.x
  (data) => { /* ... */ }
);

// ✅ Correct (FastCheck 4.x API)
export const jsonRoundtripPreservesData = fc.property(
  fc.anything(),  // Correct for 4.x
  (data) => { /* ... */ }
);
```

**Check FastCheck version**:
```bash
cd frontend-nextjs
npm list fast-check
# fast-check@4.5.3
```

## Best Practices

### Start with Shared Invariants

**Rule**: Begin with state machine and serialization properties (highest ROI).

**Why**: These catch the most bugs with the least effort.

**Priority order**:
1. **State machines** (canvas state, agent maturity) - High value, easy to write
2. **Serialization** (JSON roundtrips) - Critical for data integrity
3. **Custom business logic** (ordering, pagination) - Medium value
4. **UI behavior** (form validation) - Lower value (use E2E tests)

**Example**:
```typescript
// ✅ Good: Start with state machine invariants
export const canvasStateMachineProperty = fc.property(/* ... */);
export const maturityMonotonicProgression = fc.property(/* ... */);

// ❌ Avoid: Complex UI properties (hard to maintain)
export const formValidationProperty = fc.property(
  fc.record({
    username: fc.string(),
    email: fc.email(),
    password: fc.string(),
  }),
  (formData) => {
    // UI validation logic (better tested with E2E)
  }
);
```

### Use Property Tests for Critical Business Logic

**Rule**: Focus properties on core invariants, not edge cases.

**What to test with properties**:
- ✅ State machine transitions (canvas, agent maturity)
- ✅ Data serialization (JSON roundtrips)
- ✅ Ordering invariants (monotonic progression)
- ✅ Idempotent operations (calling twice = same result)

**What to test with example-based tests**:
- ✅ UI interactions (button clicks, form submissions)
- ✅ API integrations (third-party services)
- ✅ Error messages (user-facing text)

**Example**:
```typescript
// ✅ Good: Property test for state machine
export const canvasStateMachineProperty = fc.property(/* ... */);

// ✅ Good: Example-based test for API integration
test('canvas API returns 404 for invalid canvas ID', async () => {
  const response = await fetch(`/api/canvases/invalid-id`);
  expect(response.status).toBe(404);
});

// ❌ Avoid: Property test for API integration
export const canvasAPIProperty = fc.property(
  fc.string(),
  async (canvasId) => {
    const response = await fetch(`/api/canvases/${canvasId}`);
    // Flaky (network errors, rate limits)
  }
);
```

### Document Correspondence Between Rust and TypeScript

**Rule**: Maintain README.md documenting TypeScript → Rust property mappings.

**Why**: Rust and TypeScript are different languages; direct code sharing isn't possible.

**Example README** (`frontend-nextjs/src-tauri/tests/property_tests/README.md`):
```markdown
# Property Tests Correspondence

## Canvas State Properties

| TypeScript Property | Rust Property | Status | Notes |
|---------------------|---------------|--------|-------|
| canvasStateMachineProperty | test_canvas_state_machine_invariants | ✅ Implemented | Equivalent invariant |
| canvasNoDirectPresentingToIdle | test_no_direct_presenting_to_idle | ✅ Implemented | Same guard logic |
| canvasErrorRecoveryToIdle | test_error_recovery_to_idle | ✅ Implemented | Error state handling |

## Agent Maturity Properties

| TypeScript Property | Rust Property | Status | Notes |
|---------------------|---------------|--------|-------|
| maturityMonotonicProgression | test_agent_maturity_monotonic | ✅ Implemented | Ordinal comparison |
| autonomousIsTerminal | test_autonomous_is_terminal | ✅ Implemented | Terminal state |

## Differences

- TypeScript uses strings for state values, Rust uses enums
- FastCheck generates random inputs with fc.*, proptest uses strategy::*
- Rust tests use `proptest!` macro, TypeScript uses `fc.property()`
```

### Run Property Tests in CI for Every PR

**Rule**: Property tests should block PRs if they fail.

**CI/CD configuration**:
```yaml
# .github/workflows/cross-platform-property-tests.yml
aggregate-results:
  steps:
    - name: Fail on test failures
      run: |
        python3 backend/tests/scripts/aggregate_property_tests.py \
          --frontend results.json \
          --format json
        # Exit code 1 if any failures
        if [ $? -ne 0 ]; then
          echo "❌ Property tests failed"
          exit 1
        fi
```

**Why**: Properties catch regressions that traditional tests miss.

**Example**:
```typescript
// Developer refactors state machine, accidentally allows PRESENTING → IDLE
// Traditional test: Uses specific inputs, might not catch edge case
test('canvas transitions from IDLE to PRESENTING', () => {
  const stateMachine = new CanvasStateMachine();
  expect(stateMachine.transition(CanvasState.IDLE, 'present')).toBe(CanvasState.PRESENTING);
});

// Property test: Generates 100 random inputs, catches bug
export const canvasNoDirectPresentingToIdle = fc.property(
  fc.array(fc.string()),
  (actions) => {
    // Fails when 'present' → 'idle' sequence occurs
    // Developer sees: "Property failed after 47 tests"
  }
);
```

## References

### Framework Documentation

- **FastCheck**: https://github.com/dubzzz/fast-check
  - TypeScript/JavaScript property-based testing framework
  - 100+ arbitraries (fc.integer(), fc.string(), fc.record(), etc.)
  - Excellent shrinking algorithm (minimal failing cases)

- **proptest**: https://altsysrq.github.io/proptest-book/
  - Rust property-based testing framework
  - Inspired by Haskell's QuickCheck
  - Integrates with cargo test

### Related Documentation

- **CROSS_PLATFORM_COVERAGE.md**: Cross-platform coverage enforcement (70/80/50/40 thresholds)
- **API_TYPE_GENERATION.md**: OpenAPI type generation (Phase 145)
- **PHASE_144_SYMLINK_STRATEGY.md**: SYMLINK distribution pattern

### Example Property Tests

- **frontend-nextjs/shared/property-tests/canvas-invariants.ts**: Canvas state machine properties
- **frontend-nextjs/shared/property-tests/agent-maturity-invariants.ts**: Agent maturity properties
- **frontend-nextjs/shared/property-tests/serialization-invariants.ts**: JSON roundtrip properties
- **frontend-nextjs/src-tauri/tests/state_machine_proptest.rs**: Rust state machine proptests

### Aggregation Infrastructure

- **backend/tests/scripts/aggregate_property_tests.py**: Result aggregation script
- **frontend-nextjs/src-tauri/tests/proptest_formatter.py**: Cargo test output formatter
- **backend/tests/coverage_reports/metrics/property_test_results.json**: Historical tracking

---

**Phase**: 147 - Cross-Platform Property Testing (Complete)
**Status**: Operational in CI/CD
**Last Updated**: March 6, 2026
