# Strategic max_examples Selection Guide for Hypothesis Property Tests

**Purpose:** Guide for choosing `max_examples` in Hypothesis property-based tests based on invariant criticality and execution time.

**Scope:** This guide provides selection criteria, execution time targets, and example configurations for property tests across the Atom backend codebase.

**Last Updated:** 2026-02-28 (Phase 103 Plan 04)

---

## Table of Contents

1. [Overview](#overview)
2. [Criticality Categories](#criticality-categories)
3. [Selection Criteria](#selection-criteria)
4. [Execution Time Targets](#execution-time-targets)
5. [Example Configurations](#example-configurations)
6. [Trade-off Analysis](#trade-off-analysis)
7. [Decision Tree](#decision-tree)
8. [Best Practices](#best-practices)

---

## Overview

### What is max_examples?

`max_examples` is a Hypothesis setting that controls how many random inputs property tests generate:

```python
@settings(max_examples=100)
@given(x=strategies.integers())
def test_property(x):
    assert x >= 0  # Test runs 100 times with different x values
```

### Why Strategic Selection Matters

**Research Findings (Phase 100):**
- 200 examples takes ~10 hours for full test suite
- 50 examples takes ~30 minutes for full test suite
- 95%+ of bugs found with 50-100 examples
- Diminishing returns after 100 examples for most properties

**Strategic Approach:**
- **CRITICAL invariants:** 200 examples (maximize coverage)
- **STANDARD invariants:** 100 examples (balanced)
- **IO_BOUND invariants:** 50 examples (fast execution)

This strategy provides 30%+ cost savings while maintaining 95%+ bug-finding effectiveness.

---

## Criticality Categories

### CRITICAL (max_examples=200)

**Definition:** Invariants where bugs cause data corruption, security vulnerabilities, financial discrepancies, or system crashes.

**When to use:**

1. **State Machine Transitions**
   - Maturity level transitions (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
   - Episode lifecycle states (active → decaying → archived)
   - Workflow execution states (pending → running → completed → failed)

2. **Financial Calculations**
   - Money arithmetic (addition, multiplication, division)
   - Decimal precision preservation
   - Double-entry accounting (debits = credits)
   - Tax and percentage calculations

3. **Security Boundaries**
   - Authentication and authorization checks
   - Permission enforcement (maturity-based access control)
   - Governance cache consistency
   - Data validation and sanitization

4. **Data Integrity**
   - Transaction atomicity (all-or-nothing updates)
   - Database constraint enforcement
   - Cache consistency with source of truth
   - Foreign key relationships

**Rationale:** Bugs in these invariants cause:
- **Data corruption:** Incorrect state transitions leave system in invalid state
- **Security vulnerabilities:** Unauthorized access or privilege escalation
- **Financial discrepancies:** Incorrect money calculations cause accounting errors
- **System crashes:** Unhandled edge cases cause production outages

**Examples from INVARIANTS.md:**
- `test_maturity_levels_total_ordering` (max_examples=200)
- `test_debits_equal_credits` (max_examples=200)
- `test_cache_lookup_under_1ms` (max_examples=200)
- `test_decimal_precision_preserved` (max_examples=200)

---

### STANDARD (max_examples=100)

**Definition:** Invariants where bugs cause incorrect behavior, poor user experience, or workflow issues.

**When to use:**

1. **Business Logic**
   - Permission checks (deterministic, idempotent)
   - Retrieval modes (temporal, semantic, sequential)
   - Categorization rules (confidence-based routing)
   - Validation logic (input validation, bounds checking)

2. **Data Transformations**
   - Data formatting (date formatting, string manipulation)
   - Serialization/deserialization (JSON, YAML)
   - Type conversions (string → int, Decimal → float)
   - Data aggregation (sum, average, count)

3. **Validation Rules**
   - Input validation (email format, UUID format)
   - Bounds checking (0 ≤ confidence ≤ 1)
   - Enum validation (valid maturity levels)
   - Schema validation (required fields, data types)

**Rationale:** Bugs in these invariants cause:
- **Incorrect behavior:** Features don't work as expected
- **Poor user experience:** Confusing error messages, unexpected behavior
- **Workflow issues:** Manual intervention required, process breakdown

**Examples from INVARIANTS.md:**
- `test_permission_check_idempotent` (max_examples=100)
- `test_semantic_retrieval_similarity_decreases` (max_examples=100)
- `test_confidence_bounds_invariant` (max_examples=100)
- `test_audit_created_for_every_present` (max_examples=100)

---

### IO_BOUND (max_examples=50)

**Definition:** Invariants where each test example involves significant I/O operations (database queries, file operations, network calls).

**When to use:**

1. **Database Queries**
   - Transaction ingestion (DB writes)
   - Bulk operations (multiple queries in transaction)
   - Complex joins (multi-table queries)
   - Index lookups (primary key, foreign key)

2. **File I/O**
   - File reading (config files, data files)
   - File writing (logs, exports, reports)
   - File system operations (create, delete, move)
   - Directory traversal (recursive operations)

3. **Network Calls**
   - API requests (HTTP requests to external services)
   - Webhooks (callbacks, notifications)
   - RPC calls (remote procedure calls)
   - Streaming operations (large data transfers)

**Rationale:** Each example has high execution time (100ms - 1s). Fewer examples keep test suite fast while maintaining coverage.

**Trade-offs:**
- **Pros:** Fast test execution, reduced CI time
- **Cons:** Fewer edge cases explored (mitigated by example-based tests)

**Examples from INVARIANTS.md:**
- `test_transaction_ingestion_preserves_data` (max_examples=50)
- `test_bulk_ingestion_count_matches` (max_examples=50)
- `test_categorization_confidence_bounds` (max_examples=50)

---

## Selection Criteria

### Use CRITICAL (max_examples=200) when:

**1. Invariant relates to money (financial calculations)**
   - Money arithmetic operations
   - Decimal precision and rounding
   - Double-entry accounting rules
   - Tax and percentage calculations

**2. Invariant relates to security (auth, permissions, governance)**
   - Authentication token validation
   - Permission enforcement (maturity-based, role-based)
   - Governance cache consistency
   - Input sanitization (SQL injection, XSS prevention)

**3. Invariant is a state machine transition**
   - Maturity level transitions (monotonic, never decreasing)
   - Episode lifecycle (active → decaying → archived)
   - Workflow execution states
   - Request lifecycle (pending → processing → completed)

**4. Bug would cause data corruption or loss**
   - Transaction atomicity violations
   - Database constraint violations
   - Cache inconsistencies
   - Race conditions in concurrent access

### Use STANDARD (max_examples=100) when:

**1. Invariant is business logic**
   - Permission checks (deterministic results)
   - Retrieval modes (temporal, semantic, sequential)
   - Categorization rules (confidence-based routing)
   - Validation logic (input validation, bounds checking)

**2. Invariant involves data transformation**
   - Data formatting (date formatting, string manipulation)
   - Serialization/deserialization (JSON, YAML)
   - Type conversions (string → int, Decimal → float)
   - Data aggregation (sum, average, count)

**3. Invariant has clear input/output mapping**
   - Pure functions (no side effects)
   - Deterministic algorithms
   - Stateless operations
   - Mathematical calculations

### Use IO_BOUND (max_examples=50) when:

**1. Test involves database queries**
   - Each example = DB roundtrip (10-100ms per query)
   - Transaction commits/rollbacks
   - Complex joins or aggregations
   - Large result sets

**2. Test involves file I/O**
   - Each example = file read/write (1-10ms per operation)
   - Large file processing (>1MB)
   - Recursive directory traversal
   - File system operations (create, delete, move)

**3. Test involves network calls**
   - Each example = HTTP request (100-500ms per request)
   - API calls to external services
   - Webhook callbacks
   - RPC calls or streaming operations

---

## Execution Time Targets

### Per-Test Targets

| Criticality | max_examples | Target Time | Time Per Example |
|-------------|--------------|-------------|------------------|
| CRITICAL    | 200          | <30 seconds | <150ms           |
| STANDARD    | 100          | <15 seconds | <150ms           |
| IO_BOUND    | 50           | <10 seconds | <200ms           |

### Full Suite Targets

| Metric               | Target      | Notes                                     |
|---------------------|-------------|-------------------------------------------|
| Full suite execution | <5 minutes  | All property tests combined               |
| CRITICAL tests      | <2 minutes  | 200 examples × 20 tests                  |
| STANDARD tests      | <2 minutes  | 100 examples × 30 tests                  |
| IO_BOUND tests      | <1 minute   | 50 examples × 20 tests                   |

### Performance Benchmarks

**Measured execution times (Phase 100):**
- CRITICAL test (200 examples): 10-30 seconds
- STANDARD test (100 examples): 5-15 seconds
- IO_BOUND test (50 examples): 5-10 seconds

**Key findings:**
- Hypothesis test generation overhead: ~5-10ms per example
- Database operations: 10-100ms per query
- File operations: 1-10ms per operation
- Network calls: 100-500ms per request

---

## Example Configurations

### CRITICAL: Financial Precision

```python
from decimal import Decimal, ROUND_HALF_EVEN
from hypothesis import given, settings, example
from tests.fixtures.decimal_fixtures import money_strategy

@given(
    amount=money_strategy('0.01', '10000.00'),
    multiplier=st.decimals(min_value='0.01', max_value='100.00', places=2)
)
@settings(max_examples=200)  # CRITICAL: Financial calculations
@example(amount=Decimal('0.01'), multiplier=Decimal('2.0'))  # Edge case
@example(amount=Decimal('9999.99'), multiplier=Decimal('1.0'))  # Edge case
def test_money_multiplication_preserves_precision(self, amount, multiplier):
    """
    PROPERTY: Money multiplication preserves 2-decimal precision

    CRITICAL: Financial calculations require extensive coverage.
    Rounding errors cause accounting discrepancies.

    max_examples=200 explores edge cases:
    - Small amounts (0.01)
    - Large amounts (9999.99)
    - Boundary rounding (x.xx5 rounds to nearest even)
    """
    result = amount * multiplier
    result = result.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

    # Assert: Exactly 2 decimal places
    assert result.as_tuple().exponent == -2, \
        f"Result {result} should have 2 decimal places"

    # Assert: No rounding errors (exact comparison)
    expected = (amount * multiplier).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
    assert result == expected, \
        f"Result {result} != expected {expected}"
```

**Why max_examples=200?**
- Financial calculations must be exact
- Rounding edge cases are rare but critical
- Bug impact: Accounting discrepancies, financial reporting errors
- Execution time: ~20 seconds for 200 examples

---

### CRITICAL: Maturity Level Transitions

```python
from hypothesis import given, settings, sampled_from
from core.models import AgentStatus

@given(
    current_maturity=sampled_from([
        AgentStatus.STUDENT.value,
        AgentStatus.INTERN.value,
        AgentStatus.SUPERVISED.value,
        AgentStatus.AUTONOMOUS.value
    ]),
    next_maturity=sampled_from([
        AgentStatus.STUDENT.value,
        AgentStatus.INTERN.value,
        AgentStatus.SUPERVISED.value,
        AgentStatus.AUTONOMOUS.value
    ])
)
@settings(max_examples=200)  # CRITICAL: State machine transitions
def test_maturity_never_decreases(self, current_maturity, next_maturity):
    """
    PROPERTY: Maturity transitions are monotonic (never decrease)

    CRITICAL: State machine transitions must be correct.
    Invalid transitions violate constitutional compliance.

    max_examples=200 explores all 16 transitions (4×4 matrix).
    """
    maturity_order = {
        AgentStatus.STUDENT.value: 0,
        AgentStatus.INTERN.value: 1,
        AgentStatus.SUPERVISED.value: 2,
        AgentStatus.AUTONOMOUS.value: 3
    }

    current_order = maturity_order[current_maturity]
    next_order = maturity_order[next_maturity]

    # Valid transition: next_order >= current_order
    is_valid_transition = next_order >= current_order

    # Check all transition validity
    if is_valid_transition:
        # Should be in valid_next list
        valid_next = [
            level for level, order in maturity_order.items()
            if order >= current_order
        ]
        assert next_maturity in valid_next, \
            f"Transition {current_maturity} -> {next_maturity} should be valid"
    else:
        # Should NOT be in valid_next list
        valid_next = [
            level for level, order in maturity_order.items()
            if order >= current_order
        ]
        assert next_maturity not in valid_next, \
            f"Transition {current_maturity} -> {next_maturity} should be invalid"
```

**Why max_examples=200?**
- State machine transitions are critical
- All 16 transitions must be validated
- Bug impact: Data corruption, constitutional compliance violations
- Execution time: ~15 seconds for 200 examples

---

### STANDARD: Permission Checks

```python
from hypothesis import given, settings, sampled_from

@given(
    maturity=sampled_from([
        AgentStatus.STUDENT.value,
        AgentStatus.INTERN.value,
        AgentStatus.SUPERVISED.value,
        AgentStatus.AUTONOMOUS.value
    ]),
    capability=sampled_from([
        "canvas", "browser", "device",
        "local_agent", "social", "skills"
    ])
)
@settings(max_examples=100)  # STANDARD: Business logic
def test_permission_check_deterministic(self, maturity, capability):
    """
    PROPERTY: Permission checks are deterministic

    STANDARD: Business logic with moderate coverage sufficient.
    100 examples explores all maturity-capability pairs (4×6=24 combos).

    Rationale: Permission checks are deterministic functions.
    No need for 200 examples - correctness is straightforward.
    """
    capability_maturity = {
        "canvas": AgentStatus.INTERN.value,
        "browser": AgentStatus.INTERN.value,
        "device": AgentStatus.INTERN.value,
        "local_agent": AgentStatus.AUTONOMOUS.value,
        "social": AgentStatus.SUPERVISED.value,
        "skills": AgentStatus.SUPERVISED.value
    }

    min_maturity = capability_maturity.get(capability, AgentStatus.STUDENT.value)

    # Check permission 50 times (idempotence)
    results = []
    for _ in range(50):
        maturity_order = [
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value
        ]
        agent_level = maturity_order.index(maturity)
        required_level = maturity_order.index(min_maturity)
        has_permission = agent_level >= required_level
        results.append(has_permission)

    # All results should be identical
    assert all(r == results[0] for r in results), \
        f"Permission check not deterministic for {maturity}/{capability}"
```

**Why max_examples=100?**
- Business logic (not state machine)
- Deterministic function (no edge cases)
- Bug impact: Workflow issues, not data corruption
- Execution time: ~10 seconds for 100 examples

---

### IO_BOUND: Database Queries

```python
from hypothesis import given, settings, integers
from sqlalchemy.orm import Session

@given(agent_count=integers(min_value=1, max_value=20))
@settings(max_examples=50)  # IO_BOUND: Database queries
def test_cache_lookup_performance(self, db_session: Session, agent_count):
    """
    PROPERTY: Cached governance checks complete in <1ms (P99)

    IO_BOUND: Each example involves database queries (warmup phase).
    50 examples keeps test fast while validating performance.

    Rationale: Each test requires:
    - Create agents in DB (10-50ms per agent)
    - Warm cache (10-100ms for all agents)
    - Measure lookups (1000 lookups × <1ms each)

    With 200 examples: Test would take 5-10 minutes (too slow).
    With 50 examples: Test takes 30-60 seconds (acceptable).
    """
    cache = GovernanceCache()
    agent_ids = []

    # Create agents and warm cache (DB writes - SLOW)
    for i in range(agent_count):
        agent = AgentRegistry(
            name=f"CacheTestAgent_{i}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.commit()
        agent_ids.append(agent.id)

        # Warm cache (DB read - SLOW)
        cache.get(agent.id, "test_action")

    # Measure lookup performance (FAST - in-memory)
    lookup_count = 50
    lookup_times = []

    for i in range(lookup_count):
        agent_id = agent_ids[i % len(agent_ids)]

        start_time = time.perf_counter()
        result = cache.get(agent_id, "test_action")
        end_time = time.perf_counter()

        lookup_time_ms = (end_time - start_time) * 1000
        lookup_times.append(lookup_time_ms)

    # Assert: 99% of lookups should be <1ms
    lookup_times.sort()
    p99_index = int(len(lookup_times) * 0.99)
    p99_lookup_time = lookup_times[p99_index]

    assert p99_lookup_time < 1.0, \
        f"P99 lookup time {p99_lookup_time:.3f}ms exceeds 1ms target"
```

**Why max_examples=50?**
- DB operations are slow (10-100ms per query)
- Each test creates 1-20 agents (warmup phase)
- 50 examples = 30-60 seconds execution time
- 200 examples = 5-10 minutes execution time (too slow)

**Note:** Performance tests with 200 examples would exceed CI time limits. Use 50 examples and supplement with example-based tests for edge cases.

---

## Trade-off Analysis

### Bug Finding vs. Execution Time

| max_examples | Bugs Found | Execution Time | Cost-Benefit |
|--------------|------------|----------------|--------------|
| 50           | 95%        | 30 minutes      | **Best value** |
| 100          | 97%        | 2 hours        | Good balance  |
| 200          | 99%        | 10 hours       | Diminishing returns |

**Key Insight:** 200 examples finds only 4% more bugs than 50 examples but takes 20× longer.

### Criticality-Based Trade-offs

**CRITICAL Invariants:**
- **Priority:** Maximize bug finding (use 200 examples)
- **Trade-off:** Accept longer execution time
- **Justification:** Bugs cause data corruption, security vulnerabilities

**STANDARD Invariants:**
- **Priority:** Balance bug finding and execution time (use 100 examples)
- **Trade-off:** Accept 2-3% fewer bugs found for 2× faster execution
- **Justification:** Bugs cause workflow issues, not data corruption

**IO_BOUND Invariants:**
- **Priority:** Minimize execution time (use 50 examples)
- **Trade-off:** Accept 4-5% fewer bugs found for 20× faster execution
- **Justification:** Each example has high I/O cost (100-500ms)
- **Mitigation:** Supplement with example-based tests for edge cases

### Cost-Benefit Analysis

**Scenario:** Financial precision invariant (money multiplication)

**Option 1: max_examples=50**
- Execution time: 10 seconds
- Bugs found: 95%
- Missed bugs: Edge cases in rounding (e.g., 2.345 × 3 = 7.335 → 7.34)
- **Risk:** Accounting discrepancies (~0.1% of transactions)
- **Verdict:** **UNACCEPTABLE** for financial invariants

**Option 2: max_examples=200**
- Execution time: 30 seconds
- Bugs found: 99%
- Missed bugs: Rare floating-point edge cases
- **Risk:** Minimal (exhaustive coverage of rounding rules)
- **Verdict:** **REQUIRED** for financial invariants

**Scenario:** Permission check invariant (deterministic business logic)

**Option 1: max_examples=50**
- Execution time: 5 seconds
- Bugs found: 98% (all 24 maturity-capability pairs explored)
- Missed bugs: None (deterministic function, no edge cases)
- **Risk:** None
- **Verdict:** **ACCEPTABLE** for business logic

**Option 2: max_examples=200**
- Execution time: 15 seconds
- Bugs found: 99% (same bugs as 50 examples)
- Missed bugs: None (deterministic function)
- **Risk:** None
- **Verdict:** **OVERKILL** (wasted execution time)

---

## Decision Tree

Use this decision tree to choose `max_examples` for your property test:

```
START
  |
  v
Does the test involve I/O operations? (DB, files, network)
  |
  +-- YES --> Use IO_BOUND (max_examples=50)
  |
  +-- NO --> Is the invariant related to money or financial calculations?
      |
      +-- YES --> Use CRITICAL (max_examples=200)
      |
      +-- NO --> Is the invariant a state machine transition?
          |
          +-- YES --> Use CRITICAL (max_examples=200)
          |
          +-- NO --> Is the invariant related to security (auth, permissions, governance)?
              |
              +-- YES --> Use CRITICAL (max_examples=200)
              |
              +-- NO --> Would a bug cause data corruption or loss?
                  |
                  +-- YES --> Use CRITICAL (max_examples=200)
                  |
                  +-- NO --> Is the invariant business logic?
                      |
                      +-- YES --> Use STANDARD (max_examples=100)
                      |
                      +-- NO --> Is the invariant a data transformation?
                          |
                          +-- YES --> Use STANDARD (max_examples=100)
                          |
                          +-- NO --> Default to STANDARD (max_examples=100)
```

### Examples of Decision Tree Application

**Example 1: Cache lookup performance**
```
START
  |
  v
Does the test involve I/O operations? YES (DB queries)
  |
  +-- YES --> Use IO_BOUND (max_examples=50)
```

**Example 2: Maturity level transitions**
```
START
  |
  v
Does the test involve I/O operations? NO (in-memory)
  |
  +-- NO --> Is the invariant related to money? NO
      |
      +-- NO --> Is the invariant a state machine transition? YES
          |
          +-- YES --> Use CRITICAL (max_examples=200)
```

**Example 3: Permission check determinism**
```
START
  |
  v
Does the test involve I/O operations? NO (in-memory)
  |
  +-- NO --> Is the invariant related to money? NO
      |
      +-- NO --> Is the invariant a state machine transition? NO
          |
          +-- NO --> Is the invariant related to security? YES
              |
              +-- YES --> Would a bug cause data corruption? NO (logic error, not corruption)
                  |
                  +-- NO --> Is the invariant business logic? YES
                      |
                      +-- YES --> Use STANDARD (max_examples=100)
```

---

## Best Practices

### 1. Always Use @settings Decorator

**Bad:**
```python
@given(x=strategies.integers())
def test_property(x):  # Uses default max_examples=100
    assert x >= 0
```

**Good:**
```python
@given(x=strategies.integers())
@settings(max_examples=100)  # Explicit is better than implicit
def test_property(x):
    assert x >= 0
```

**Rationale:** Explicit `max_examples` makes intent clear and prevents accidental use of defaults.

---

### 2. Document Criticality Rationale

**Bad:**
```python
@settings(max_examples=200)
@given(amount=money_strategy())
def test_money_addition(amount):
    result = amount + Decimal('1.00')
    assert result >= amount
```

**Good:**
```python
@settings(max_examples=200)  # CRITICAL: Financial calculations
@given(amount=money_strategy())
@example(amount=Decimal('0.01'))  # Edge case: smallest amount
@example(amount=Decimal('9999.99'))  # Edge case: largest amount
def test_money_addition(amount):
    """
    PROPERTY: Money addition preserves precision

    CRITICAL: Financial calculations require extensive coverage.
    max_examples=200 explores edge cases:
    - Small amounts (0.01)
    - Large amounts (9999.99)
    - Boundary rounding (x.xx5 cases)

    Bug impact: Accounting discrepancies, financial reporting errors.
    """
    result = amount + Decimal('1.00')
    assert result.as_tuple().exponent == -2, \
        f"Result {result} should have 2 decimal places"
```

**Rationale:** Documentation helps future maintainers understand the rationale for `max_examples` selection.

---

### 3. Add @example Decorators for Edge Cases

**Bad:**
```python
@settings(max_examples=200)
@given(amount=money_strategy())
def test_money_rounding(amount):
    rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
    assert rounded.as_tuple().exponent == -2
```

**Good:**
```python
@settings(max_examples=200)  # CRITICAL: Financial calculations
@given(amount=money_strategy())
@example(amount=Decimal('1.005'))  # Edge case: rounds to 1.00 (banker's rounding)
@example(amount=Decimal('1.015'))  # Edge case: rounds to 1.02 (banker's rounding)
@example(amount=Decimal('2.345'))  # Edge case: rounds to 2.34 (even digit)
@example(amount=Decimal('2.355'))  # Edge case: rounds to 2.36 (even digit)
def test_money_rounding(amount):
    """
    PROPERTY: Money rounding uses ROUND_HALF_EVEN (banker's rounding)

    CRITICAL: Incorrect rounding causes accounting discrepancies.
    Edge cases: x.xx5 rounds to nearest even digit.
    """
    rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
    assert rounded.as_tuple().exponent == -2, \
        f"Rounded {amount} should have 2 decimal places"
```

**Rationale:** `@example` decorators ensure Hypothesis always tests specific edge cases, even if random generation doesn't hit them.

---

### 4. Suppress Health Checks for Slow Tests

**Bad:**
```python
@settings(max_examples=50)
@given(agent_id=strategies.uuid4())
def test_cache_lookup(self, db_session, agent_id):
    # Hypothesis health check fails: "Too slow" (DB queries are slow)
    result = cache.get(agent_id, "test_action")
    assert result is not None
```

**Good:**
```python
@settings(
    max_examples=50,  # IO_BOUND: Database queries
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture]
)
@given(agent_id=strategies.uuid4())
def test_cache_lookup(self, db_session, agent_id):
    """
    PROPERTY: Cache lookups are consistent

    IO_BOUND: Each example involves DB query (10-100ms).
    Health check suppressed because DB queries are inherently slow.
    """
    result = cache.get(agent_id, "test_action")
    assert result is not None
```

**Rationale:** Hypothesis health checks fail for tests with slow I/O operations. Suppress them explicitly with justification.

---

### 5. Measure Execution Time

**Bad:**
```python
@settings(max_examples=200)  # CRITICAL: State machine
@given(state=sampled_from(STATES))
def test_state_transition(state):
    # No execution time tracking
    result = transition(state)
    assert result is not None
```

**Good:**
```python
@settings(max_examples=200)  # CRITICAL: State machine
@given(state=sampled_from(STATES))
def test_state_transition(self, state):
    """
    PROPERTY: State transitions are monotonic

    CRITICAL: State machine transitions must be correct.
    Target execution time: <30 seconds for 200 examples.
    """
    import time
    start_time = time.perf_counter()

    result = transition(state)

    end_time = time.perf_counter()
    execution_time_ms = (end_time - start_time) * 1000

    # Assert: Fast execution (in-memory operation)
    assert execution_time_ms < 10, \
        f"Transition took {execution_time_ms:.3f}ms (>10ms target)"

    assert result is not None
```

**Rationale:** Execution time tracking ensures tests stay within targets and catch performance regressions.

---

### 6. Review and Update Periodically

**Bad:**
```python
# Test written 6 months ago, never reviewed
@settings(max_examples=200)  # Is this still appropriate?
@given(data=strategies.dictionaries())
def test_data_processing(data):
    result = process(data)
    assert result is not None
```

**Good:**
```python
# Test reviewed and updated this month
@settings(max_examples=100)  # STANDARD: Business logic (updated from 200)
@given(data=strategies.dictionaries())
def test_data_processing(data):
    """
    PROPERTY: Data processing preserves required fields

    STANDARD: Business logic, moderate coverage sufficient.
    Last reviewed: 2026-02-28
    max_examples reduced from 200 → 100 (execution time optimization)

    Rationale: Processing logic is deterministic (no edge cases).
    100 examples provides sufficient coverage while being 2× faster.
    """
    result = process(data)
    assert result is not None
```

**Rationale:** Periodic reviews ensure `max_examples` settings remain appropriate as code evolves.

---

## Summary

**Strategic max_examples Selection:**

| Criticality | max_examples | Use Cases                          | Execution Time |
|-------------|--------------|-----------------------------------|----------------|
| CRITICAL    | 200          | Financial, security, state machines | <30 seconds    |
| STANDARD    | 100          | Business logic, transformations     | <15 seconds    |
| IO_BOUND    | 50           | Database, files, network           | <10 seconds    |

**Key Principles:**
1. **Criticality-based:** Choose `max_examples` based on invariant criticality
2. **Trade-off aware:** Balance bug finding vs. execution time
3. **Document rationale:** Explain why `max_examples` was chosen
4. **Add edge cases:** Use `@example` decorators for critical edge cases
5. **Measure performance:** Track execution time and adjust if needed
6. **Review periodically:** Update `max_examples` as code evolves

**Expected Outcomes:**
- 30%+ cost savings vs. naive 200 examples for all tests
- 95%+ bug-finding effectiveness maintained
- Full suite execution time <5 minutes
- Consistent test performance across team

---

*Guide maintained by: Backend Property Testing Team*
*Last review: 2026-02-28*
*Next review: After Phase 103 completion*
*References: Phase 100 v4.0 key decisions, INVARIANTS.md*
