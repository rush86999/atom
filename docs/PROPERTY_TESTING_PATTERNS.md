# Property Testing Patterns Guide

**Last Updated:** 2026-02-26
**Applies to:** Atom platform v4.0 (backend, frontend, mobile, desktop)
**Maintainer:** Testing Team

---

## Overview

Property-based testing validates invariants across hundreds of randomly generated inputs, finding edge cases that example-based testing misses. Atom uses 3 frameworks across 4 platforms with ~361 total property tests.

**Quality over Quantity:** Focus on critical business invariants, not maximizing test counts.

**What is a Property Test?**
- Traditional unit test: Verify function behavior for specific inputs
- Property test: Verify invariant (property that must always hold) across thousands of randomly generated inputs

**Example:**
```typescript
// Traditional unit test
test('increment adds 1', () => {
  expect(increment(5)).toBe(6);
});

// Property test
fc.assert(fc.property(fc.integer(), (x) => {
  expect(increment(x)).toBe(x + 1);  // Works for ANY integer
}));
```

**Why Property Testing?**
- Finds edge cases you didn't think of (null, empty strings, large numbers, Unicode)
- Tests business logic invariants, not just specific examples
- Documents system behavior through invariants
- Catches bugs that traditional tests miss (off-by-one, boundary conditions, type errors)

---

## Framework Quick Reference

| Platform | Framework | Version | Config | Generator Example |
|----------|-----------|---------|--------|-------------------|
| Backend Python | Hypothesis | 6.151.5 | `@settings(max_examples=100)` | `st.integers(min=0, max=100)` |
| Frontend TS | FastCheck | 4.5.3 | `{ numRuns: 100 }` | `fc.integer({ min: 0, max: 100 })` |
| Mobile TS | FastCheck | 4.5.3 | `{ numRuns: 100 }` | `fc.integer({ min: 0, max: 100 })` |
| Desktop Rust | proptest | 1.0+ | `proptest! { #![proptest_config(ProptestConfig { cases: 100, .. })] }` | `prop::num::i32::ANY` |

---

## Pattern Catalog

### Pattern 1: Invariant-First Testing

**What:** Define the invariant (property that must always hold), then write tests.

**When to use:** ALL property tests - start here always.

**Backend Example (Hypothesis):**
```python
from hypothesis import given, settings
import hypothesis.strategies as st
import copy

@given(st.integers(), st.text())
@settings(max_examples=100)
def test_state_update_immutability(initial_count, initial_name):
    """
    INVARIANT: State update should not mutate input state
    VALIDATED_BUG: Shallow copy caused reference sharing
    Root cause: Using state.copy() instead of copy.deepcopy()
    """
    state = {"count": initial_count, "name": initial_name}
    state_copy = copy.deepcopy(state)
    update_state(state, {"count": initial_count + 1})
    assert state == state_copy  # Original unchanged
```

**Frontend Example (FastCheck):**
```typescript
import fc from 'fast-check';

fc.assert(
  fc.property(fc.integer(), (initialCount) => {
    const state = { count: initialCount };
    const stateCopy = JSON.stringify(state);
    counterReducer(state, { type: 'INCREMENT' });
    expect(JSON.stringify(state)).toBe(stateCopy);
  }),
  { numRuns: 100, seed: 23001 }
);
```

**Key Points:**
- Document invariant in docstring
- Include VALIDATED_BUG section
- Use deep copy for comparison
- Test across all possible inputs

**See also:** `backend/tests/property_tests/state_management/test_state_management_invariants.py`

---

### Pattern 2: State Machine Testing

**What:** Model stateful systems with explicit state transitions and validate invariants.

**When to use:** Testing sync status, auth flows, workflow states, canvas lifecycle.

**Mobile Example (FastCheck):**
```typescript
const validTransitions: Record<string, string[]> = {
  pending: ['syncing', 'failed'],
  syncing: ['completed', 'failed'],
  completed: [],
  failed: ['syncing'],
};

fc.assert(
  fc.property(
    fc.constantFrom(...['pending', 'syncing', 'completed', 'failed']),
    fc.constantFrom(...['pending', 'syncing', 'completed', 'failed']),
    (fromStatus, toStatus) => {
      if (fromStatus === toStatus) return true;
      const allowed = validTransitions[fromStatus] || [];
      if (allowed.length === 0) {
        expect(toStatus).toBe(fromStatus);  // Terminal state
      } else {
        expect(allowed).toContain(toStatus);  // Valid transition
      }
    }
  ),
  { numRuns: 100 }
);
```

**Frontend Example (Canvas State Machine):**
```typescript
const canvasStates = ['draft', 'presenting', 'presented', 'closed'] as const;
const validTransitions: Record<string, string[]> = {
  draft: ['presenting', 'closed'],
  presenting: ['presented', 'closed'],
  presented: ['closed'],
  closed: [],
};

fc.assert(
  fc.property(
    fc.constantFrom(...canvasStates),
    fc.constantFrom(...canvasStates),
    (fromState, toState) => {
      if (fromState === toState) return true;
      const allowed = validTransitions[fromState] || [];
      expect(allowed).toContain(toState);
    }
  ),
  { numRuns: 100, seed: 23001 }
);
```

**Key Points:**
- Define valid transitions explicitly
- Test terminal states (no outgoing transitions)
- Validate state machine correctness
- Test state history preservation

**See also:** `mobile/src/__tests__/property/advanced-sync-invariants.test.ts`

---

### Pattern 3: Round-Trip Invariants

**What:** Verify serialize → deserialize returns original data.

**When to use:** Testing JSON encoding, file I/O, API contracts, IPC messages.

**Desktop Example (Rust proptest):**
```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn prop_ipc_roundtrip(cmd in any::<ICommand>()) {
        /// INVARIANT: IPC serialization round-trip preserves data
        let serialized = serde_json::to_string(&cmd).unwrap();
        let deserialized: ICommand = serde_json::from_str(&serialized).unwrap();
        prop_assert_eq!(cmd, deserialized);
    }
}
```

**Frontend Example (API Round-Trip):**
```typescript
fc.assert(
  fc.property(
    fc.record({
      id: fc.uuid(),
      type: fc.constantFrom('agent_message', 'workflow_trigger'),
      priority: fc.integer({ min: 1, max: 10 }),
      created_at: fc.integer({ min: 1000000000, max: 9999999999 }),
      payload: fc.object(),
    }),
    (action) => {
      const serialized = JSON.stringify(action);
      const deserialized = JSON.parse(serialized);
      expect(deserialized).toEqual(action);
    }
  ),
  { numRuns: 100, seed: 23001 }
);
```

**Backend Example (API Contract):**
```python
@given(st.builds(Request, id=st.uuid(), method=st.sampled_from(['GET', 'POST'])))
@settings(max_examples=100)
def test_request_roundtrip(request):
    """
    INVARIANT: Request serialization round-trip preserves data
    VALIDATED_BUG: JSON.stringify() converts undefined to null
    Root cause: JSON spec doesn't support undefined
    """
    serialized = request.to_json()
    deserialized = Request.from_json(serialized)
    assert deserialized == request
```

**Key Points:**
- Test serialization/deserialization symmetry
- Document JSON limitations (undefined, NaN, Infinity)
- Test complex data types (nested objects, arrays)
- Validate type preservation

**See also:** `frontend-nextjs/tests/property/api-roundtrip-invariants.test.ts`

---

### Pattern 4: Generator Composition

**What:** Build complex test data generators from simple primitives.

**When to use:** Testing complex data structures, business logic with nested objects.

**Frontend Example (FastCheck):**
```typescript
const actionGenerator = fc.record({
  id: fc.uuid(),
  type: fc.constantFrom('agent_message', 'workflow_trigger'),
  priority: fc.integer({ min: 1, max: 10 }),
  created_at: fc.integer({ min: 1000000000, max: 9999999999 }),
  payload: fc.object(),
});

fc.assert(fc.property(actionGenerator, (action) => {
  expect(action.priority).toBeGreaterThanOrEqual(1);
  expect(action.priority).toBeLessThanOrEqual(10);
  expect(action.type).toBeOneOf(['agent_message', 'workflow_trigger']);
}));
```

**Backend Example (Hypothesis):**
```python
from hypothesis import strategies as st

episode_strategy = st.builds(
    Episode,
    id=st.uuid(),
    agent_id=st.uuid(),
    started_at=st.datetimes(min_value=datetime(2020, 1, 1)),
    segments=st.lists(st.builds(
        EpisodeSegment,
        id=st.uuid(),
        content=st.text(),
        timestamp=st.datetimes()
    ), min_size=0, max_size=100)
)

@given(episode_strategy)
@settings(max_examples=50)
def test_episode_segments_ordered(episode):
    """
    INVARIANT: Episode segments must be ordered by timestamp
    """
    timestamps = [s.timestamp for s in episode.segments]
    assert timestamps == sorted(timestamps)
```

**Mobile Example (Sync Action Generator):**
```typescript
const syncActionGenerator = fc.record({
  id: fc.uuid(),
  type: fc.constantFrom('create', 'update', 'delete'),
  priority: fc.integer({ min: 1, max: 10 }),
  timestamp: fc.integer({ min: 1000000000, max: 9999999999 }),
  payload: fc.object(),
  retryCount: fc.integer({ min: 0, max: 4 }),
});

fc.assert(fc.property(syncActionGenerator, (action) => {
  expect(action.retryCount).toBeGreaterThanOrEqual(0);
  expect(action.retryCount).toBeLessThanOrEqual(4);
  expect(['create', 'update', 'delete']).toContain(action.type);
}));
```

**Key Points:**
- Build complex generators from simple primitives
- Use `fc.record()` / `st.builds()` for structured data
- Set reasonable bounds on generators (min/max)
- Compose generators for nested structures

**See also:** `mobile/src/__tests__/property/queueInvariants.test.ts`

---

### Pattern 5: Idempotency Testing

**What:** Verify calling function multiple times produces same result.

**When to use:** Testing retry logic, state machine transitions, cache operations.

**Frontend Example (useUndoRedo Idempotency):**
```typescript
fc.assert(
  fc.property(fc.array(fc.integer()), (actions) => {
    const { undo, redo } = useUndoRedo();
    actions.forEach(a => redo(a));
    undo();  // Undo all
    undo();  // Second undo should be idempotent
    expect(undo()).toBe(undefined);  // No-op
  }),
  { numRuns: 100 }
);
```

**Backend Example (Operation Idempotency):**
```python
@given(st.integers(min_value=0, max_value=100))
@settings(max_examples=100)
def test_operation_idempotency(operation_id):
    """
    INVARIANT: Idempotent operations can be called multiple times safely
    """
    result1 = execute_operation(operation_id)
    result2 = execute_operation(operation_id)
    assert result1 == result2  # Same result
    assert result1.status == 'completed'  # Operation completed
```

**Desktop Example (Window Fullscreen Toggle):**
```rust
proptest! {
    #[test]
    fn prop_fullscreen_toggle_idempotence(initial_state in prop::sample::select(vec![true, false])) {
        /// INVARIANT: Fullscreen toggle is idempotent (even toggles = original state)
        let mut window = WindowState::new();
        window.set_fullscreen(initial_state);
        window.toggle_fullscreen();
        window.toggle_fullscreen();
        prop_assert_eq!(window.is_fullscreen(), initial_state);
    }
}
```

**Key Points:**
- Test idempotent operations (undo, toggle, delete)
- Verify calling twice produces same result as calling once
- Test retry logic is idempotent
- Validate no side effects from repeated calls

**See also:** `frontend-nextjs/tests/property/state-machine-invariants.test.ts`

---

### Pattern 6: Boundary Value Testing

**What:** Test behavior at boundaries (min, max, empty, null, negative).

**When to use:** Testing numeric ranges, array sizes, string lengths.

**Frontend Example (Array Boundary Testing):**
```typescript
fc.assert(
  fc.property(fc.array(fc.integer()), (items) => {
    const queue = new PriorityQueue();
    items.forEach(item => queue.enqueue(item, 1));
    expect(queue.size()).toBe(items.length);
    expect(queue.isEmpty()).toBe(items.length === 0);
  }),
  { numRuns: 100, seed: 23001 }
);
```

**Desktop Example (Numeric Boundary Testing):**
```rust
proptest! {
    #[test]
    fn prop_window_size_constraints(width in prop::num::i32::ANY, height in prop::num::i32::ANY) {
        /// INVARIANT: Window size respects min/max constraints
        let window = WindowState::new();
        window.set_size(width, height);
        let (actual_width, actual_height) = window.size();
        prop_assert!(actual_width >= 400 && actual_width <= 4096);
        prop_assert!(actual_height >= 300 && actual_height <= 4096);
    }
}
```

**Backend Example (Database Transaction Boundaries):**
```python
@given(st.integers(min_value=-1000, max_value=1000))
@settings(max_examples=200)
def test_account_balance_boundary(balance_change):
    """
    INVARIANT: Account balance never goes negative
    VALIDATED_BUG: Negative balance from partial transaction
    Root cause: Missing try/except around debit operation
    """
    account = Account(balance=100)
    account.update_balance(balance_change)
    assert account.balance >= 0  # Never negative
```

**Key Points:**
- Test min/max values (integers, floats)
- Test empty/zero cases (arrays, strings)
- Test negative values (if applicable)
- Test overflow/underflow (large numbers)

**See also:** `frontend-nextjs/src-tauri/tests/window_state_proptest.rs`

---

### Pattern 7: Associative/Commutative Testing

**What:** Verify operation order doesn't matter (addition, set union, concatenation).

**When to use:** Testing collections, merge operations, batch processing.

**Frontend Example (State Composition):**
```typescript
fc.assert(
  fc.property(
    fc.record({ x: fc.integer() }),
    fc.record({ y: fc.integer() }),
    fc.record({ z: fc.integer() }),
    (state1, state2, state3) => {
      // Composition is associative
      const merged1 = { ...state1, ...state2, ...state3 };
      const merged2 = { ...{ ...state1, ...state2 }, ...state3 };
      expect(merged1).toEqual(merged2);
    }
  ),
  { numRuns: 100 }
);
```

**Mobile Example (Batch Ordering):**
```typescript
fc.assert(
  fc.property(
    fc.array(fc.integer()),
    fc.array(fc.integer()),
    (batch1, batch2) => {
      const queue = new SyncQueue();
      batch1.forEach(item => queue.enqueue(item, 1));
      batch2.forEach(item => queue.enqueue(item, 1));
      const combined = [...batch1, ...batch2];
      // Batch order preserved
      expect(queue.dequeue()).toBe(combined[0]);
    }
  ),
  { numRuns: 50 }
);
```

**Backend Example (Merge Commutativity):**
```python
@given(st.dictionaries(st.text(), st.integers()), st.dictionaries(st.text(), st.integers()))
@settings(max_examples=100)
def test_merge_commutativity(dict1, dict2):
    """
    INVARIANT: Dictionary merge is commutative (order-independent)
    """
    merged1 = {**dict1, **dict2}
    merged2 = {**dict2, **dict1}
    # Note: Not strictly commutative due to key conflicts, but should be same keys
    assert set(merged1.keys()) == set(merged2.keys())
```

**Key Points:**
- Test associative operations ((a + b) + c == a + (b + c))
- Test commutative operations (a + b == b + a)
- Validate merge/ordering invariants
- Test collection operations

**See also:** `frontend-nextjs/tests/property/reducer-invariants.test.ts`

---

## Best Practices

### 1. VALIDATED_BUG Documentation

Every property test must document edge cases found or validated:

**Format:**
```typescript
/**
 * INVARIANT: [Description of invariant that must always hold]
 *
 * VALIDATED_BUG: [Description of bug found or "None - invariant validated"]
 * Root cause: [Why bug occurred]
 * Fixed in: [Commit hash or "N/A"]
 * Scenario: [Example that triggered bug]
 */
```

**Examples from Phase 098:**
```typescript
/**
 * INVARIANT: JSON serialization round-trip preserves data
 *
 * VALIDATED_BUG: JSON.stringify() converts undefined to null
 * Root cause: JSON spec doesn't support undefined
 * Fixed in: N/A (language limitation)
 * Scenario: { field: undefined } -> JSON -> { field: null }
 */

/**
 * INVARIANT: fc.date() generates valid ISO 8601 dates
 *
 * VALIDATED_BUG: fc.date() can generate negative years (BC dates)
 * Root cause: FastCheck date generator includes entire Date range
 * Fixed in: Filter to year 2000-2100
 * Scenario: Year -1 -> ISO string "-000001-12-31..." (breaks regex)
 */
```

**Purpose:**
- Document bugs found during testing
- Provide root cause analysis
- Reference fix commits
- Share knowledge across team

### 2. Deterministic Seeds

Always set seeds for reproducibility:

**FastCheck:**
```typescript
fc.assert(fc.property(fc.integer(), (x) => {
  // Test logic
}), { seed: 23001 });  // Deterministic seed
```

**Hypothesis:**
```python
@given(st.integers())
@settings(seed=12345, max_examples=100)
def test_with_seed(x):
    # Test logic
    pass
```

**proptest:**
```bash
PROCTEST_SEED=12345 cargo test
```

**Purpose:**
- Reproducible test failures
- Debug edge cases with known inputs
- CI consistency across runs
- Investigate flaky tests

**How to choose seeds:**
- Use sequential seeds across related tests (23001, 23002, 23003)
- Use memorable seeds (12345, 99999)
- Document seed in test description

### 3. numRuns Tuning

Balance test coverage vs. execution time:

| Test Type | numRuns | Examples |
|-----------|---------|----------|
| Fast (in-memory) | 100 | State machines, reducers, pure functions |
| Medium (file I/O) | 50 | File operations, API calls (mocked) |
| Slow (network) | 10-20 | Database queries, network calls |
| Security-critical | 200 | Path traversal, transaction atomicity |

**Frontend (FastCheck):**
```typescript
fc.assert(fc.property(fc.integer(), (x) => {
  // Fast test - 100 runs
}), { numRuns: 100 });
```

**Mobile (FastCheck):**
```typescript
fc.assert(fc.property(fc.integer(), (x) => {
  // Medium test - 50 runs
}), { numRuns: 50 });
```

**Backend (Hypothesis):**
```python
@given(st.integers())
@settings(max_examples=200)  # Security-critical
def test_path_traversal_prevention(path):
    # Test logic
    pass
```

**Purpose:**
- Fast tests: More runs = better coverage
- Slow tests: Fewer runs = faster feedback
- Security tests: Maximum runs = thorough validation

### 4. Test Isolation

Property tests should not depend on shared state:

**Do:**
```typescript
fc.assert(fc.property(fc.integer(), (x) => {
  const state = { count: x };  // Fresh state per run
  const result = increment(state);
  expect(result.count).toBe(x + 1);
}));
```

**Don't:**
```typescript
let sharedState = { count: 0 };  // BAD: Shared state

fc.assert(fc.property(fc.integer(), (x) => {
  sharedState.count = x;  // BAD: Modifies shared state
  const result = increment(sharedState);
  expect(result.count).toBe(x + 1);
}));
```

**Best Practices:**
- Create fresh state per test run
- Mock external dependencies (databases, APIs)
- Use pure functions when possible
- Avoid global state

### 5. Generator Customization

Customize generators for realistic test data:

**Do:**
```typescript
const emailGenerator = fc.emailAddress();  // Realistic emails
const dateGenerator = fc.date().filter(d => {
  const year = d.getFullYear();
  return year >= 2000 && year <= 2100;  // Filter BC dates
});
const urlGenerator = fc.webUrl();  // Valid URLs
```

**Don't:**
```typescript
const emailGenerator = fc.string();  // BAD: Any string, not realistic
const dateGenerator = fc.date();  // BAD: Includes BC dates (year -1000)
const urlGenerator = fc.string();  // BAD: Invalid URLs
```

**Purpose:**
- Test realistic data, not any data
- Filter out invalid inputs early
- Improve signal-to-noise ratio

### 6. Error Message Quality

Property tests fail with shrinking (minimal counterexample):

**Good failure message:**
```
Property failed after 64 tests
Counterexample: { x: -1, y: 0 }
Shrunk 15 times
Error: Division by zero
```

**Bad failure message:**
```
Test failed
```

**Best Practices:**
- Use descriptive test names
- Document invariants in docstrings
- Include VALIDATED_BUG sections
- Provide context in assertions

---

## Anti-Patterns to Avoid

### Weak Properties

**Bad:**
```typescript
fc.assert(fc.property(fc.integer(), (x) => {
  expect(x).toBe(x);  // Always passes - no invariant tested
}));
```

**Good:**
```typescript
fc.assert(fc.property(fc.integer(), (initialCount) => {
  const state = { count: initialCount };
  const stateCopy = JSON.stringify(state);
  counterReducer(state, { type: 'INCREMENT' });
  expect(JSON.stringify(state)).toBe(stateCopy);  // Immutability invariant
}));
```

**Lesson:** Test business logic that could fail, not tautologies

### Over-Constrained Generators

**Bad:**
```typescript
fc.assert(fc.property(
  fc.integer().filter(x => x > 0 && x < 100 && x % 2 === 0),
  (evenNumber) => {
    // Only 50 numbers pass filter - poor coverage
  }
));
```

**Good:**
```typescript
fc.assert(fc.property(
  fc.integer({ min: 0, max: 99 }),
  (number) => {
    if (number % 2 === 0) {
      // Test even number logic
    } else {
      // Test odd number logic
    }
  }
));
```

**Lesson:** Test validation logic itself, don't filter out edge cases

### Ignoring Reproducibility

**Bad:**
```typescript
fc.assert(fc.property(fc.integer(), (x) => {
  // No seed set - flaky test on failure
}));
```

**Good:**
```typescript
fc.assert(fc.property(fc.integer(), (x) => {
  // Deterministic seed for reproducible failures
}), { seed: 23001 });
```

**Lesson:** Always set seed, investigate failures with known inputs

### Testing Implementation Details

**Bad:**
```typescript
fc.assert(fc.property(fc.integer(), (x) => {
  const result = increment(x);
  expect(result).toBe(x + 1);  // Tests implementation, not invariant
}));
```

**Good:**
```typescript
fc.assert(fc.property(fc.integer(), (x) => {
  const state1 = { count: x };
  const state2 = { count: x };
  increment(state1);
  expect(state2.count).toBe(x);  // Tests immutability invariant
}));
```

**Lesson:** Test invariants (properties that must hold), not implementation

### Missing VALIDATED_BUG Documentation

**Bad:**
```typescript
fc.assert(fc.property(fc.integer(), (x) => {
  expect(increment(x)).toBe(x + 1);  // No docstring
}));
```

**Good:**
```typescript
/**
 * INVARIANT: Increment adds 1 to input
 *
 * VALIDATED_BUG: None - invariant validated during implementation
 * Root cause: N/A
 * Fixed in: N/A
 * Scenario: Tested for integers from -2^31 to 2^31-1
 */
fc.assert(fc.property(fc.integer(), (x) => {
  expect(increment(x)).toBe(x + 1);
}));
```

**Lesson:** Document invariants and bug findings for knowledge sharing

---

## Adding New Property Tests

### Step 1: Identify Invariant

**Questions:**
- What property MUST always hold true?
- What are the failure modes?
- Is this business-critical?

**Examples:**
- "State updates must be immutable"
- "API round-trip preserves data"
- "Sync conflicts resolved deterministically"

**Tools:**
- Review bug reports for patterns
- Talk to domain experts
- Look for critical business logic

### Step 2: Choose Framework

| Platform | Framework | When to Use |
|----------|-----------|-------------|
| Backend Python | Hypothesis | Testing Python business logic |
| Frontend TS | FastCheck | Testing React state, reducers, API clients |
| Mobile TS | FastCheck | Testing React Native state, sync logic |
| Desktop Rust | proptest | Testing Rust IPC, window management |

### Step 3: Write Test

**Template (FastCheck):**
```typescript
import fc from 'fast-check';

/**
 * INVARIANT: [Description]
 *
 * VALIDATED_BUG: [Bug found or "None"]
 * Root cause: [Why bug occurred]
 * Fixed in: [Commit hash]
 * Scenario: [Example]
 */
fc.assert(
  fc.property(generator, (input) => {
    // Test logic
    expect(result).toStrictEqual(expected);
  }),
  { numRuns: 100, seed: 23001 }
);
```

**Template (Hypothesis):**
```python
from hypothesis import given, settings
import hypothesis.strategies as st

@given(st.integers())
@settings(max_examples=100, seed=12345)
def test_invariant(input):
    """
    INVARIANT: [Description]

    VALIDATED_BUG: [Bug found or "None"]
    Root cause: [Why bug occurred]
    Fixed in: [Commit hash]
    Scenario: [Example]
    """
    # Test logic
    assert result == expected
```

**Template (proptest):**
```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn prop_test_invariant(input in prop::num::i32::ANY) {
        /// INVARIANT: [Description]
        /// VALIDATED_BUG: [Bug found or "None"]
        let result = function_under_test(input);
        prop_assert_eq!(result, expected);
    }
}
```

### Step 4: Verify

**Checklist:**
- [ ] Test must pass (100%)
- [ ] Add to INVARIANTS.md catalog
- [ ] Run in CI to catch regressions
- [ ] Document VALIDATED_BUG section
- [ ] Set appropriate numRuns/seed
- [ ] Review test with team

**Run tests:**
```bash
# Frontend/Mobile
npm test -- property-tests

# Backend
pytest tests/property_tests/

# Desktop
cargo test
```

---

## Platform-Specific Guidelines

### Backend (Python/Hypothesis)

**Framework:** Hypothesis 6.151.5

**Imports:**
```python
from hypothesis import given, settings, assume
import hypothesis.strategies as st
```

**Strategies:**
```python
st.integers(min=0, max=100)           # Integers
st.text(min_size=0, max_size=100)     # Strings
st.lists(st.integers())                # Lists
st.dictionaries(st.text(), st.integers())  # Dicts
st.datetimes(min_value=datetime(2020, 1, 1))  # Datetimes
st.uuid()                              # UUIDs
st.builds(MyClass, id=st.uuid())       # Custom objects
```

**Configuration:**
```python
@settings(max_examples=100, seed=12345)
@given(st.integers())
def test_with_config(x):
    pass
```

**See also:** `backend/tests/property_tests/`

### Frontend (TypeScript/FastCheck)

**Framework:** FastCheck 4.5.3

**Imports:**
```typescript
import fc from 'fast-check';
```

**Generators:**
```typescript
fc.integer({ min: 0, max: 100 })        // Integers
fc.string()                             // Strings
fc.array(fc.integer())                  // Arrays
fc.record({ x: fc.integer(), y: fc.string() })  // Objects
fc.date()                               // Dates
fc.uuid()                               // UUIDs
fc.constantFrom('a', 'b', 'c')          // Enums
```

**Configuration:**
```typescript
fc.assert(
  fc.property(fc.integer(), (x) => {
    // Test logic
  }),
  { numRuns: 100, seed: 23001 }
);
```

**Jest Integration:**
```typescript
describe('Property Tests', () => {
  it('should pass', () => {
    fc.assert(fc.property(fc.integer(), (x) => {
      expect(x).toBe(x);
    }));
  });
});
```

**See also:** `frontend-nextjs/tests/property/`

### Mobile (TypeScript/FastCheck)

**Framework:** FastCheck 4.5.3 (same as frontend)

**Generators:** Same as frontend

**Jest-Expo Integration:**
```typescript
import fc from 'fast-check';

describe('Mobile Property Tests', () => {
  fc.assert(
    fc.property(fc.integer(), (x) => {
      // Test logic
    }),
    { numRuns: 50, seed: 23001 }
  );
});
```

**Mock Expo Modules:**
```typescript
// jest.setup.js
jest.mock('expo-local-authentication', () => ({
  authenticateAsync: jest.fn(),
  hasHardwareAsync: jest.fn(() => Promise.resolve(true)),
}));
```

**See also:** `mobile/src/__tests__/property/`

### Desktop (Rust/proptest)

**Framework:** proptest 1.0+

**Imports:**
```rust
use proptest::prelude::*;
```

**Strategies:**
```rust
prop::num::i32::ANY                    // Any i32
prop::num::i32::{-100..100}            // Range
prop::collection::vec(prop::num::i32::ANY, 0..100)  // Vec
prop::string::string_regex("[a-z]+")?  // Regex strings
```

**Configuration:**
```rust
proptest! {
    #![proptest_config(ProptestConfig {
        cases: 100,
        ..Default::default()
    })]
    #[test]
    fn prop_test(input in prop::num::i32::ANY) {
        // Test logic
    }
}
```

**Serde Integration:**
```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ICommand {
    pub cmd: String,
    pub args: serde_json::Value,
}

proptest! {
    #[test]
    fn prop_roundtrip(cmd in any::<ICommand>()) {
        let serialized = serde_json::to_string(&cmd).unwrap();
        let deserialized: ICommand = serde_json::from_str(&serialized).unwrap();
        prop_assert_eq!(cmd, deserialized);
    }
}
```

**See also:** `frontend-nextjs/src-tauri/tests/`

---

## Quality Gates

**Before Committing:**
- [ ] All property tests must pass (100% pass rate)
- [ ] New invariants added to INVARIANTS.md
- [ ] VALIDATED_BUG docstrings required
- [ ] numRuns and seed documented
- [ ] Test file named `*invariants.test.ts` or `*invariants.py`

**CI Requirements:**
- [ ] Property tests run on every PR
- [ ] Failure blocks merge
- [ ] Test execution time <5 minutes
- [ ] Coverage report generated

**Documentation Requirements:**
- [ ] INVARIANTS.md updated with new properties
- [ ] Pattern documented if novel
- [ ] VALIDATED_BUG entries added if bugs found
- [ ] Platform-specific guidelines followed

---

## Further Reading

**Official Documentation:**
- [Hypothesis Docs](https://hypothesis.readthedocs.io/) - Python property testing
- [FastCheck Docs](https://fast-check.dev/) - TypeScript property testing
- [proptest Docs](https://altsysrq.github.io/proptest-book/) - Rust property testing

**Internal Documentation:**
- `backend/tests/property_tests/INVARIANTS.md` - Complete invariant catalog
- `docs/CODE_QUALITY_STANDARDS.md` - Code quality guidelines
- `docs/TESTING_GUIDE.md` - General testing patterns

**External Resources:**
- [Property-Based Testing Introduction](https://hypothesis.works/articles/what-is-property-based-testing/)
- [Property-Based Testing in Practice](https://www.youtube.com/watch?v=sh18l7lHGfk) - Talk by John Hughes
- [FastCheck Examples](https://github.com/dubzzz/fast-check/tree/master/documentation/examples)

**Books:**
- "Property-Based Testing with PropEr, Erlang, and Elixir" by Fred Hebert
- "The Joy of Hypothesis" (online tutorial)

---

## Glossary

**Invariant:** Property that must always hold true for a system

**Property:** Formal statement about system behavior (e.g., "increment adds 1")

**Shrinking:** Process of finding minimal counterexample when test fails

**Generator:** Strategy for generating random test data (e.g., fc.integer())

**Strategy:** Hypothesis term for generator

**Arbitrary:** proptest term for generator

**VALIDATED_BUG:** Docstring section documenting bugs found or prevented

**numRuns:** Number of test iterations (FastCheck)

**max_examples:** Number of test iterations (Hypothesis)

**Seed:** Deterministic random seed for reproducible tests

---

**Document Version:** 1.0
**Last Updated:** 2026-02-26
**Maintainer:** Testing Team

**For questions or contributions, see:** `backend/tests/property_tests/INVARIANTS.md`

## See Also

- [Testing Documentation Index](TESTING_INDEX.md) - Central hub for all testing documentation
- [Testing Onboarding Guide](TESTING_ONBOARDING.md) - 15-minute quick start for all platforms
- [Cross-Platform Coverage](CROSS_PLATFORM_COVERAGE.md) - Weighted coverage calculation
- [E2E Testing Guide](E2E_TESTING_GUIDE.md) - End-to-end testing patterns
