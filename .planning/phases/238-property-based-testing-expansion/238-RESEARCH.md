# Phase 238: Property-Based Testing Expansion - Research

**Researched:** 2026-03-24
**Domain:** Property-Based Testing (Hypothesis), Invariant Testing, API Contract Validation, Security Invariants
**Confidence:** HIGH

## Summary

Phase 238 aims to expand property-based testing coverage from the current 66 documented invariants to 50+ new property tests across five critical areas: (1) agent execution invariants, (2) LLM routing correctness, (3) episodic memory integrity, (4) governance enforcement, and (5) security invariants (SQL injection, XSS, CSRF prevention). The phase leverages the existing Hypothesis 6.92.x infrastructure with 239 property test files and 4,199 individual tests already implemented.

**Primary recommendation:** Use invariant-first thinking documented in PROPERTY_TEMPLATE.md (506 lines) to expand property testing coverage across PROP-01 through PROP-05 requirements. Prioritize CRITICAL invariants (max_examples=200) for agent execution and LLM routing, STANDARD (max_examples=100) for episodic memory and API contracts, and IO-bound (max_examples=50) for database operations.

**Key insight:** The existing property test infrastructure is mature (239 test files, documented invariants in INVARIANTS.md) but lacks coverage in three key areas: (1) API contract fuzzing (malformed JSON, oversized payloads), (2) state machine invariants (agent graduation monotonicity), and (3) security invariants (SQL injection, XSS, CSRF). Phase 238 should fill these gaps using invariant-first documentation patterns before writing tests.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Hypothesis** | 6.92.0 | Property-based testing engine | Industry standard for Python PBT, stateful testing support, automatic counterexample shrinking |
| **pytest** | Latest (via requirements.txt) | Test runner and fixtures | Already configured with `@pytest.mark.property` marker in pytest.ini |
| **SQLAlchemy** | 2.0 | Database ORM for invariants | Existing ORM models (AgentRegistry, Episode, AgentExecution) for invariant testing |
| **FastAPI TestClient** | Latest | API contract testing | OpenAPI schema validation, request/response validation |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **hypothesis.strategies** | Built-in | Test data generation | `st.text()`, `st.integers()`, `st.lists()`, `st.dictionaries()` for input generation |
| **hypothesis.stateful** | Built-in | State machine testing | Agent graduation state transitions, episode lifecycle invariants |
| **hypothesis.settings** | Built-in | Test execution profiles | `@settings(max_examples=200)` for CRITICAL, `100` for STANDARD, `50` for IO-bound |
| **Schemathesis** | Latest (if needed) | API contract fuzzing | Malformed JSON, oversized payloads, response validation (existing in `backend/tests/contract/`) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **Hypothesis** | QuickCheck (Python port) | Hypothesis is more actively maintained, better Python integration |
| **Property-based testing** | Example-based fuzzing | PBT finds deep invariant violations, not just surface-level crashes |
| **Invariant-first** | Test-first (TDD) | Invariant-first prevents implementation-driven tests, catches edge cases earlier |

**Installation:**
```bash
# Already installed (Phase 237 completion)
pip install hypothesis==6.92.0

# For state machine invariants (PROP-03)
pip install hypothesis[stateful]

# For API contract fuzzing (PROP-02) - optional
pip install schemathesis
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/property_tests/
├── conftest.py                          # Existing: DEFAULT_PROFILE, CI_PROFILE, fixtures
├── INVARIANTS.md                        # Existing: 66 documented invariants
├── README.md                            # Existing: Property testing guide
│
├── agent_execution/                     # NEW: PROP-01 agent execution invariants
│   ├── __init__.py
│   ├── conftest.py                      # Fixtures: test_agent, db_session
│   ├── test_execution_idempotence.py    # Invariant: Execution is idempotent
│   ├── test_execution_termination.py    # Invariant: Execution terminates gracefully
│   └── test_execution_determinism.py    # Invariant: Same inputs → same outputs
│
├── llm_routing/                         # NEW: PROP-01 LLM routing invariants
│   ├── __init__.py
│   ├── conftest.py                      # Fixtures: mock_llm_providers
│   ├── test_routing_consistency.py      # Invariant: Same prompt → same provider
│   ├── test_cognitive_tier_mapping.py   # Invariant: Token count maps to correct tier
│   └── test_cache_aware_routing.py      # Invariant: Cached prompts bypass classification
│
├── episodic_memory/                     # NEW: PROP-01 episodic memory invariants
│   ├── __init__.py
│   ├── conftest.py                      # Fixtures: test_episodes, db_session
│   ├── test_segmentation_contiguity.py  # Invariant: Segments are contiguous
│   ├── test_retrieval_ranking.py        # Invariant: Relevant episodes ranked higher
│   └── test_lifecycle_transitions.py    # Invariant: Episodes follow lifecycle DAG
│
├── governance/                          # EXPAND: PROP-01 governance invariants
│   ├── test_governance_invariants_property.py  # Existing: 9 tests (maturity, permissions, cache)
│   ├── test_authorization_invariants.py  # NEW: Invariant: Authorization checks are monotonic
│   └── test_governance_cache_invariants.py # NEW: Invariant: Cache invalidation propagates correctly
│
├── api_contracts/                       # NEW: PROP-02 API contract invariants
│   ├── __init__.py
│   ├── conftest.py                      # Fixtures: authenticated_client, api_client
│   ├── test_malformed_json.py           # Invariant: Malformed JSON rejected gracefully
│   ├── test_oversized_payloads.py       # Invariant: Oversized payloads return 413
│   └── test_response_validation.py      # Invariant: Responses conform to OpenAPI schema
│
├── state_machines/                      # NEW: PROP-03 state machine invariants
│   ├── __init__.py
│   ├── conftest.py                      # Fixtures: test_agents, training_sessions
│   ├── test_graduation_state_machine.py # Invariant: Graduation is monotonic (no regression)
│   ├── test_episode_lifecycle.py        # Invariant: Episode lifecycle forms DAG
│   └── test_training_transitions.py     # Invariant: Training sessions follow valid transitions
│
└── security/                            # NEW: PROP-04 security invariants
    ├── __init__.py
    ├── conftest.py                      # Fixtures: malicious_inputs, attack_vectors
    ├── test_sql_injection.py            # Invariant: SQL injection attempts are sanitized
    ├── test_xss_prevention.py           # Invariant: XSS payloads are escaped
    └── test_csrf_protection.py          # Invariant: CSRF tokens validated on state-changing requests
```

### Pattern 1: Invariant-First Test Development

**What:** Document invariant in docstring BEFORE writing test code (PROPERTY_TEMPLATE.md line 35-87).

**When to use:** ALL new property tests in Phase 238 (PROP-05 requirement).

**Example:**
```python
# Source: backend/tests/bug_discovery/TEMPLATES/PROPERTY_TEMPLATE.md lines 64-87
@pytest.mark.property
@given(st.lists(st.builds(WorkflowStep)))
@settings(DEFAULT_PROFILE)
def test_workflow_serialization_roundtrip(steps):
    """
    Test that workflow serialization is lossless for all step lists.

    Invariant: For any list of workflow steps, serializing and deserializing
    produces an equivalent workflow with the same steps.

    Domain:
    - Input: List of workflow steps (dict with 'action', 'params', 'order')
    - Size: 0-100 steps per workflow

    Preconditions:
    - All steps have valid 'action' field
    - All steps have 'order' field (integer, 0-1000)
    - 'params' is a dict (can be empty)

    Postconditions:
    - Deserialized workflow has same number of steps as input
    - All steps are present in same order
    - All step fields are preserved (action, params, order)
    """
    # Test implementation follows...
```

**Why this matters:** PROP-05 requires "invariant-first thinking" - documenting invariants before writing tests prevents implementation-driven tests and ensures clarity about what must be true.

### Pattern 2: Strategic max_examples Configuration

**What:** Use `@settings(max_examples=N)` based on invariant criticality (STRATEGIC_MAX_EXAMPLES_GUIDE.md).

**When to use:** ALL property tests in Phase 238.

**Example:**
```python
# CRITICAL invariants (max_examples=200)
@settings(max_examples=200, deadline=None)
def test_maturity_levels_total_ordering(...):
    """Invariant: Maturity levels form total ordering (STUDENT < INTERN < SUPERVISED < AUTONOMOUS)"""
    # Criticality: CRITICAL (200 examples explores all 16 pairwise comparisons)

# STANDARD invariants (max_examples=100)
@settings(max_examples=100, deadline=None)
def test_permission_check_idempotent(...):
    """Invariant: Permission checks are idempotent (same inputs → same result)"""
    # Criticality: STANDARD (100 examples sufficient for maturity-capability pairs)

# IO-bound operations (max_examples=50)
@settings(max_examples=50, deadline=None)
def test_cache_lookup_under_1ms(...):
    """Invariant: Cached governance checks complete in <1ms (P99)"""
    # Criticality: IO-bound (50 examples for database operations)
```

**Configuration profiles (from conftest.py lines 42-59):**
- **CI_PROFILE**: `max_examples=50, deadline=None` (fast for PR checks)
- **DEFAULT_PROFILE**: `max_examples=200, deadline=None` (thorough for local)
- **Auto-selection**: `CI` env var uses CI profile, otherwise DEFAULT

### Pattern 3: Hypothesis State Machine Testing

**What:** Use `hypothesis.stateful.RuleBasedStateMachine` for state transition invariants (PROP-03).

**When to use:** Agent graduation state transitions, episode lifecycle, training session flows.

**Example:**
```python
# Source: Hypothesis stateful testing pattern
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize

class AgentGraduationStateMachine(RuleBasedStateMachine):
    """Property: Agent graduation is monotonic (maturity never decreases)."""

    def __init__(self):
        super().__init__()
        self.agent = None
        self.graduation_history = []

    @initialize()
    def init_agent(self):
        """Initialize STUDENT agent (confidence < 0.5)."""
        self.agent = AgentRegistry(
            name="GraduationTestAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4
        )
        self.graduation_history = [AgentStatus.STUDENT.value]

    @rule(confidence_boost=floats(min_value=0.0, max_value=0.3, allow_nan=False, allow_infinity=False))
    def boost_confidence(self, confidence_boost):
        """Boost agent confidence (simulating successful execution)."""
        if self.agent:
            old_confidence = self.agent.confidence_score
            new_confidence = min(1.0, old_confidence + confidence_boost)
            self.agent.confidence_score = new_confidence

            # Update maturity based on new confidence
            if new_confidence < 0.5:
                new_maturity = AgentStatus.STUDENT.value
            elif new_confidence < 0.7:
                new_maturity = AgentStatus.INTERN.value
            elif new_confidence < 0.9:
                new_maturity = AgentStatus.SUPERVISED.value
            else:
                new_maturity = AgentStatus.AUTONOMOUS.value

            self.agent.status = new_maturity
            self.graduation_history.append(new_maturity)

    @invariant()
    def maturity_never_decreases(self):
        """Invariant: Maturity progression is monotonic (never decreases)."""
        if len(self.graduation_history) >= 2:
            maturity_order = {
                AgentStatus.STUDENT.value: 0,
                AgentStatus.INTERN.value: 1,
                AgentStatus.SUPERVISED.value: 2,
                AgentStatus.AUTONOMOUS.value: 3
            }

            for i in range(1, len(self.graduation_history)):
                prev_maturity = self.graduation_history[i - 1]
                curr_maturity = self.graduation_history[i]

                prev_order = maturity_order[prev_maturity]
                curr_order = maturity_order[curr_maturity]

                # Invariant: Current order >= previous order (no regression)
                assert curr_order >= prev_order, \
                    f"Maturity decreased from {prev_maturity} to {curr_maturity}"

TestGraduationStateMachine = AgentGraduationStateMachine.TestCase
```

**Why this matters:** PROP-03 requires "state machine invariants" - RuleBasedStateMachine automatically generates random rule sequences to find invariant violations in state transitions.

### Pattern 4: API Contract Fuzzing with Hypothesis

**What:** Use Hypothesis strategies to generate malformed/edge-case API inputs (PROP-02).

**When to use:** Testing API robustness against malformed JSON, oversized payloads, invalid UTF-8.

**Example:**
```python
# Source: API contract fuzzing pattern for PROP-02
@pytest.mark.property
@given(
    # Malformed JSON strategies
    json_payload=st.one_of(
        st.text(min_size=0, max_size=10000),  # Random text (not valid JSON)
        st.dictionaries(st.text(), st.none()),  # Dict with None values (invalid JSON)
        st.lists(st.none()),  # List with None values
        st.just('{"invalid": json}'),  # Specifically malformed JSON
        st.just('null'),  # Null payload
        st.just(''),  # Empty string
        st.just('[]'),  # Empty array
        st.just('{}'),  # Empty object
    )
)
@settings(CI_PROFILE)  # 50 examples (API calls are IO-bound)
def test_api_rejects_malformed_json(authenticated_client, json_payload):
    """
    Test that API rejects malformed JSON gracefully.

    Invariant: Malformed JSON returns 400 Bad Request (not 500 Internal Server Error)

    Strategy: Random text, invalid JSON structures, null/empty payloads

    Preconditions: Authenticated client

    Postconditions: Response is 400 (client error) or 422 (validation error), never 500 (server error)
    """
    from fastapi import status

    response = authenticated_client.post(
        "/api/v1/agents/execute",
        content=json_payload,
        headers={"Content-Type": "application/json"}
    )

    # Invariant: Malformed JSON should return client error (4xx), not server error (5xx)
    assert response.status_code in [400, 422, 413], \
        f"Malformed JSON returned unexpected status: {response.status_code}"

    # Invariant: Should never crash with 500 Internal Server Error
    assert response.status_code != 500, \
        "Server crashed on malformed JSON (possible unhandled exception)"


@pytest.mark.property
@given(
    # Oversized payload strategies
    payload_size=st.integers(min_value=1, max_value=100_000_000)  # Up to 100MB
)
@settings(CI_PROFILE)  # 50 examples (IO-bound)
def test_api_rejects_oversized_payloads(authenticated_client, payload_size):
    """
    Test that API rejects oversized payloads with 413 Payload Too Large.

    Invariant: Payloads exceeding max size return 413 (not OOM or crash)

    Strategy: Random payload sizes up to 100MB

    Preconditions: Authenticated client

    Postconditions: Oversized payloads return 413 or 400, never 500
    """
    # Generate oversized payload
    oversized_payload = {"data": "x" * payload_size}

    response = authenticated_client.post(
        "/api/v1/agents/execute",
        json=oversized_payload
    )

    # Invariant: Oversized payload should return 413 (Payload Too Large)
    # or 400 (Bad Request), not 500 (server crash)
    assert response.status_code in [400, 413], \
        f"Oversized payload ({payload_size} bytes) returned {response.status_code}"

    # Invariant: Should not cause memory issues
    # (If 500, likely OOM or unhandled exception)
    assert response.status_code != 500, \
        "Server crashed on oversized payload (possible OOM)"
```

**Why this matters:** PROP-02 requires "API contract invariants" - Hypothesis strategies can systematically test edge cases that manual testing misses (e.g., 50MB payloads, invalid UTF-8, malformed JSON).

### Anti-Patterns to Avoid

- **Implementation-driven tests**: Writing tests based on code structure rather than invariants. **Instead**: Document invariant first in docstring (PROP-05).
- **Max examples too high**: Using `max_examples=10000` for slow tests. **Instead**: Use strategic defaults (200 for CRITICAL, 100 for STANDARD, 50 for IO-bound).
- **Skipping database isolation**: Creating separate DB fixtures for property tests. **Instead**: Reuse `db_session` from `tests/e2e_ui/fixtures/database_fixtures.py` (FIXTURE_REUSE_GUIDE.md).
- **Missing invariant documentation**: Writing test without explaining what invariant it validates. **Instead**: Follow PROPERTY_TEMPLATE.md structure (Purpose, Invariant, Strategy, Preconditions, Postconditions).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Random input generation** | Custom random number generators | `hypothesis.strategies` (`st.text()`, `st.integers()`, `st.lists()`) | Hypothesis provides reproducible randomness, shrinking, and strategy composition |
| **State machine testing** | Custom state transition logic | `hypothesis.stateful.RuleBasedStateMachine` | Automatic rule sequence generation, invariant checking after each step |
| **Counterexample shrinking** | Manual binary search for minimal failing case | Hypothesis automatic shrinking | Hypothesis automatically reduces 1000-item failing input to minimal 2-item counterexample |
| **Test data factories** | Hand-rolled test data generators | `hypothesis.strategies.builds()` + existing factories | `agent_factory`, `user_factory` from `test_data_factory.py` (FIXTURE_REUSE_GUIDE.md) |
| **API fuzzing** | Manual malformed JSON creation | `hypothesis.strategies` for fuzzing | Systematic exploration of input space (malformed JSON, oversized payloads, invalid UTF-8) |
| **Malicious input generation** | Hardcoded XSS/SQL injection payloads | `hypothesis.strategies` + security pattern libraries | Hypothesis strategies can generate infinite variations of attack vectors |

**Key insight:** Hypothesis is a mature property-based testing framework with 10+ years of development. Hand-rolling any of these components is reinventing the wheel and missing out on shrinking, reproducibility, and strategy composition.

## Common Pitfalls

### Pitfall 1: Skipping Invariant Documentation

**What goes wrong:** Tests become implementation-driven, fail to capture true invariants.

**Why it happens:** Developers jump straight to test code without documenting what invariant is being tested.

**How to avoid:** Follow PROPERTY_TEMPLATE.md invariant-first pattern (lines 35-87). Every property test MUST have invariant documentation in docstring BEFORE writing test code.

**Warning signs:** Test names like `test_agent_execution()` without invariant statement. Docstring doesn't explain "what must be true for all inputs."

### Pitfall 2: Overusing max_examples=10000

**What goes wrong:** Tests take hours to run, CI timeouts, developer frustration.

**Why it happens:** Belief that "more examples = better testing" without understanding diminishing returns.

**How to avoid:** Use strategic `max_examples` based on criticality:
- **CRITICAL invariants**: `max_examples=200` (explores input space thoroughly)
- **STANDARD invariants**: `max_examples=100` (sufficient for most cases)
- **IO-bound operations**: `max_examples=50` (database, API calls)

**Warning signs:** Property tests taking >30s per test. CI runs exceeding 10 minutes for property tests alone.

### Pitfall 3: Ignoring Fixture Reuse

**What goes wrong:** Duplicate fixtures, slower tests (no worker isolation), maintenance burden.

**Why it happens:** Property tests created as separate suite with own fixtures.

**How to avoid:** Import existing fixtures from `tests/e2e_ui/fixtures/`:
- `db_session` for database isolation (worker-specific schemas)
- `authenticated_user` for API tokens
- `authenticated_page` for browser tests (10-100x faster than UI login)
- `agent_factory`, `user_factory` for test data

**Source:** FIXTURE_REUSE_GUIDE.md (1,085 lines documenting all reusable fixtures).

**Warning signs:** Duplicate `@pytest.fixture` for `db_session` or `test_user` in property test `conftest.py`.

### Pitfall 4: Missing Preconditions in Invariants

**What goes wrong:** Invariants fail for inputs that should be excluded (e.g., empty strings, negative IDs).

**Why it happens:** Invariant documented without specifying domain restrictions (preconditions).

**How to avoid:** Document preconditions explicitly in invariant docstring (PROPERTY_TEMPLATE.md lines 49-51):

```python
"""
Invariant: Workflow serialization is lossless for all step lists.

Domain:
- Input: List of workflow steps (dict with 'action', 'params', 'order')
- Size: 0-100 steps per workflow

Preconditions:
- All steps have valid 'action' field
- All steps have 'order' field (integer, 0-1000)
- 'params' is a dict (can be empty)

Postconditions:
- Deserialized workflow has same number of steps as input
- All steps are present in same order
"""
```

**Warning signs:** Tests failing with `AssumeError` from Hypothesis (using `assume()` to filter invalid inputs). Instead, constrain strategies using `st.text(min_size=1)` or `st.integers(min_value=0)`.

### Pitfall 5: Not Using Stateful Testing for State Machines

**What goes wrong:** State transition invariants tested manually (enumerating all transitions), missing edge cases.

**Why it happens:** Developers unfamiliar with `hypothesis.stateful.RuleBasedStateMachine`.

**How to avoid:** Use RuleBasedStateMachine for state machine invariants (PROP-03):
- Agent graduation state transitions (monotonic maturity progression)
- Episode lifecycle transitions (ACTIVE → ARCHIVED → DELETED)
- Training session flows (PENDING → IN_PROGRESS → COMPLETED)

**Warning signs:** Tests with names like `test_all_graduation_transitions()` manually enumerating 16 possible state pairs. Use RuleBasedStateMachine to generate random transition sequences automatically.

## Code Examples

Verified patterns from existing Atom codebase:

### Example 1: Maturity Level Ordering Invariant (CRITICAL)

```python
# Source: backend/tests/property_tests/governance/test_governance_invariants_property.py lines 62-113
@given(
    level_a=sampled_from([
        AgentStatus.STUDENT.value,
        AgentStatus.INTERN.value,
        AgentStatus.SUPERVISED.value,
        AgentStatus.AUTONOMOUS.value
    ]),
    level_b=sampled_from([
        AgentStatus.STUDENT.value,
        AgentStatus.INTERN.value,
        AgentStatus.SUPERVISED.value,
        AgentStatus.AUTONOMOUS.value
    ])
)
@settings(**HYPOTHESIS_SETTINGS_CRITICAL)  # max_examples=200
def test_maturity_levels_total_ordering(
    self, db_session: Session, level_a: str, level_b: str
):
    """
    PROPERTY: Maturity levels form total ordering (STUDENT < INTERN < SUPERVISED < AUTONOMOUS)

    STRATEGY: st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"])

    INVARIANT: For any two levels a, b: a < b OR b < a OR a == b

    RADII: 200 examples explores all 16 pairwise comparisons (4x4 matrix)

    VALIDATED_BUG: None found (invariant holds)
    """
    maturity_order = {
        AgentStatus.STUDENT.value: 0,
        AgentStatus.INTERN.value: 1,
        AgentStatus.SUPERVISED.value: 2,
        AgentStatus.AUTONOMOUS.value: 3
    }

    order_a = maturity_order[level_a]
    order_b = maturity_order[level_b]

    # Total ordering: one of these must be true
    is_total_order = (
        (order_a < order_b) or
        (order_b < order_a) or
        (order_a == order_b)
    )

    assert is_total_order, \
        f"Maturity levels {level_a} and {level_b} violate total ordering"
```

**Key pattern:** Use `@settings(max_examples=200)` for CRITICAL invariants where 200 examples thoroughly explores the input space (4x4 matrix = 16 pairwise comparisons, 200 examples provides 12.5x coverage).

### Example 2: Confidence Bounds Invariant with Boundary Cases

```python
# Source: backend/tests/property_tests/governance/test_governance_invariants_property.py lines 664-715
@given(
    initial_confidence=floats(
        min_value=0.0, max_value=1.0,
        allow_nan=False, allow_infinity=False
    ),
    boost_amount=floats(
        min_value=-0.5, max_value=0.5,
        allow_nan=False, allow_infinity=False
    )
)
@example(initial_confidence=0.3, boost_amount=0.8)  # Would exceed 1.0
@example(initial_confidence=0.9, boost_amount=-0.95)  # Would go below 0.0
@settings(**HYPOTHESIS_SETTINGS_STANDARD)  # max_examples=100
def test_confidence_bounds_invariant(
    self, db_session: Session, initial_confidence: float, boost_amount: float
):
    """
    PROPERTY: Confidence scores MUST stay within [0.0, 1.0] bounds

    STRATEGY: st.tuples(initial_confidence, boost_amount)

    INVARIANT: max(0.0, min(1.0, confidence + boost)) in [0.0, 1.0]

    RADII: 100 examples explores boundary conditions

    VALIDATED_BUG: Confidence score exceeded 1.0 after multiple boosts
    Root cause: Missing min(1.0, ...) clamp in confidence update logic
    Fixed in commit abc123 by adding bounds checking
    """
    # Create agent with initial confidence
    agent = AgentRegistry(
        name="TestAgent",
        category="test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence_score=initial_confidence
    )
    db_session.add(agent)
    db_session.commit()

    # Simulate confidence update (clamped to [0.0, 1.0])
    new_confidence = max(0.0, min(1.0, initial_confidence + boost_amount))

    # Update agent confidence
    agent.confidence_score = new_confidence
    db_session.commit()

    # Assert: Confidence must be in valid range
    assert 0.0 <= agent.confidence_score <= 1.0, \
        f"Confidence {agent.confidence_score} outside [0.0, 1.0] bounds"
```

**Key pattern:** Use `@example()` decorator to test specific boundary cases (confidence = 0.3 + 0.8 = 1.1 → clamped to 1.0). Hypothesis always runs `@example()` cases first before random generation.

### Example 3: Cache Performance Invariant with P99 Measurement

```python
# Source: backend/tests/property_tests/governance/test_governance_invariants_property.py lines 452-512
@given(
    agent_count=integers(min_value=10, max_value=100),
    lookup_count=integers(min_value=1, max_value=50)
)
@settings(**HYPOTHESIS_SETTINGS_CRITICAL)  # max_examples=200
def test_cache_lookup_under_1ms(
    self, db_session: Session, agent_count: int, lookup_count: int
):
    """
    PROPERTY: Cached governance checks complete in <1ms (P99)

    STRATEGY: st.lists of agent_ids for batch lookup

    INVARIANT: 99% of cached lookups complete in <1ms

    RADII: 200 examples with varying cache sizes

    VALIDATED_BUG: Cache lookups exceeded 1ms under load
    Root cause: Cache miss storm causing DB queries
    Fixed in commit jkl012 by adding cache warming
    """
    cache = GovernanceCache()
    agent_ids = []

    # Create agents and warm cache
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

        # Warm cache
        cache.get(agent.id, "test_action")

    # Measure lookup performance
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

**Key pattern:** Performance invariant using P99 metric (99th percentile). Sort lookup times, compute index at 99th percentile, assert against threshold. Hypothesis generates varying cache sizes (10-100 agents) and lookup patterns (1-50 lookups).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Example-based testing** | Property-based testing (Hypothesis) | Phase 237 (Feb 2026) | 4,199 property tests catch edge cases example-based tests miss |
| **Hand-rolled fuzzing** | Hypothesis strategies (`st.text()`, `st.lists()`) | Phase 237 (Feb 2026) | Reproducible counterexamples with automatic shrinking |
| **TDD (test-first)** | Invariant-first testing (PROP-05) | Phase 238 (Mar 2026) | Documentation-driven tests prevent implementation coupling |
| **Enumerating state transitions** | RuleBasedStateMachine (PROP-03) | Phase 238 (Mar 2026) | Automatic state transition sequence generation finds deep invariant violations |

**Current best practices (2026):**
- **Invariant documentation first**: PROPERTY_TEMPLATE.md (506 lines) mandates invariant documentation in docstring before test code
- **Strategic max_examples**: CRITICAL=200, STANDARD=100, IO-bound=50 (STRATEGIC_MAX_EXAMPLES_GUIDE.md)
- **Fixture reuse**: Import from `tests/e2e_ui/fixtures/` (FIXTURE_REUSE_GUIDE.md, 1,085 lines)
- **State machine testing**: Use `hypothesis.stateful.RuleBasedStateMachine` for state transition invariants

**Deprecated/outdated:**
- **Example-based testing for invariants**: Old pattern of testing specific examples (`test_agent_can_delete()`) insufficient for invariant validation. Use property tests instead.
- **Manual counterexample shrinking**: Hypothesis automatically shrinks failing inputs to minimal cases. Don't implement manual binary search.
- **UI login for tests**: Use `authenticated_page` fixture (10-100x faster than UI login). FIXTURE_REUSE_GUIDE.md lines 117-174 explain why UI login is slow and flaky.

## Open Questions

1. **API contract fuzzing tool choice: Schemathesis vs. Hypothesis?**
   - What we know: Hypothesis is already installed (6.92.0), Schemathesis is newer tool for API contract testing based on Hypothesis.
   - What's unclear: Whether Schemathesis adds value over Hypothesis for PROP-02 (malformed JSON, oversized payloads).
   - Recommendation: Start with Hypothesis strategies for PROP-02 (lower overhead, no new dependency). If Schemathesis provides OpenAPI schema validation benefits, evaluate after initial tests implemented. Hypothesis `st.text()`, `st.dictionaries()` can generate malformed JSON and oversized payloads without Schemathesis.

2. **State machine invariant coverage: Which state machines need testing?**
   - What we know: PROP-03 requires "state machine invariants (agent graduation monotonic transitions, episode lifecycle)". Agent graduation is clearly a state machine (STUDENT → INTERN → SUPERVISED → AUTONOMOUS). Episode lifecycle is documented in `backend/core/episode_lifecycle_service.py`.
   - What's unclear: Whether other state machines exist (e.g., training session flows, supervision session lifecycle, agent proposal workflow).
   - Recommendation: Start with agent graduation state machine (highest priority, clearly documented in PROP-03). Then expand to episode lifecycle (documented in `episode_lifecycle_service.py`). Investigate training/supervision state machines by reading `core/student_training_service.py` and `core/supervision_service.py` for state transitions.

3. **Security invariant scope: SQL injection, XSS, CSRF only?**
   - What we know: PROP-04 lists "SQL injection, XSS, CSRF prevention" as required security invariants. Existing security tests in `backend/tests/test_skill_security.py` and `backend/tests/unit/security/` provide patterns.
   - What's unclear: Whether other security invariants are needed (e.g., command injection, path traversal, LDAP injection, XXE).
   - Recommendation: Focus on PROP-04 requirements (SQL injection, XSS, CSRF) for Phase 238. Document other security invariants as "future work" in RESEARCH.md. Security testing is deep - Phase 238 should establish patterns, not exhaustively test all attack vectors.

4. **Performance targets for property tests: How slow is too slow?**
   - What we know: STRATEGIC_MAX_EXAMPLES_GUIDE.md defines performance targets (<10s fast tier, <60s medium tier, <100s slow tier). Existing property tests use `max_examples=200` for CRITICAL, `100` for STANDARD, `50` for IO-bound.
   - What's unclear: Whether 50+ new property tests will exceed CI timeout (currently 10 minutes for full test suite).
   - Recommendation: Use CI_PROFILE (`max_examples=50`) for all new property tests to keep CI fast. Run DEFAULT_PROFILE (`max_examples=200`) locally for thorough testing. If CI timeout becomes issue, use `@pytest.mark.property` marker to run property tests in separate CI job (not every PR).

5. **Invariant documentation format: PROPERTY_TEMPLATE.md vs. INVARIANTS.md?**
   - What we know: PROPERTY_TEMPLATE.md (506 lines) provides test-level invariant documentation format (invariant in docstring). INVARIANTS.md documents all 66 existing invariants with formal mathematical definitions.
   - What's unclear: Whether Phase 238 should update INVARIANTS.md or only use PROPERTY_TEMPLATE.md format in test docstrings.
   - Recommendation: Both. Document invariant in test docstring (PROPERTY_TEMPLATE.md format) for developer accessibility. Add high-level invariant summary to INVARIANTS.md (formal specification, mathematical definition, test location) for architectural documentation. INVARIANTS.md is the authoritative catalog of all invariants - new tests should add entries there.

## Sources

### Primary (HIGH confidence)

- **backend/tests/property_tests/INVARIANTS.md** - 66 documented invariants with formal mathematical definitions (maturity levels, confidence scores, action complexity, cache performance)
- **backend/tests/bug_discovery/TEMPLATES/PROPERTY_TEMPLATE.md** - 506-line template for invariant-first test development (Purpose, Invariant, Strategy, Preconditions, Postconditions)
- **backend/tests/bug_discovery/FIXTURE_REUSE_GUIDE.md** - 1,085-line guide documenting all reusable fixtures (auth_fixtures, database_fixtures, api_fixtures, test_data_factory)
- **backend/tests/property_tests/conftest.py** - Hypothesis configuration profiles (CI_PROFILE=50 examples, DEFAULT_PROFILE=200 examples, auto-selection based on CI env var)
- **backend/tests/property_tests/governance/test_governance_invariants_property.py** - 836 lines of production-grade property tests (maturity ordering, action complexity, confidence bounds, cache performance, permission checks)

### Secondary (MEDIUM confidence)

- **Hypothesis official documentation** - https://hypothesis.readthedocs.io/ (general Hypothesis usage, strategies, stateful testing)
- **backend/tests/property_tests/README.md** - Property testing guide explaining key differences from example-based testing
- **backend/tests/property_tests/STRATEGIC_MAX_EXAMPLES_GUIDE.md** - Guide for configuring max_examples based on invariant criticality
- **backend/tests/contract/** - Existing API contract testing infrastructure using Schemathesis (test_browser_api_contract.py, test_canvas_api_contract.py, test_agent_api_contract.py)

### Tertiary (LOW confidence)

- **backend/tests/test_skill_security.py** - Security testing patterns (potential patterns for PROP-04 security invariants)
- **backend/tests/unit/security/** - Existing security unit tests (possible patterns for SQL injection, XSS, CSRF testing)
- **Property-Based Testing: A QuickCheck Tutorial** - General PBT concepts (not specific to Hypothesis/Python)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Hypothesis 6.92.0 already installed, 239 property test files exist, invariant documentation patterns established in Phase 237
- Architecture: HIGH - PROPERTY_TEMPLATE.md (506 lines), FIXTURE_REUSE_GUIDE.md (1,085 lines), INVARIANTS.md (66 invariants) provide clear patterns
- Pitfalls: HIGH - Common property testing mistakes well-documented in Hypothesis community, existing 4,199 tests demonstrate anti-patterns to avoid

**Research date:** 2026-03-24
**Valid until:** 2026-04-23 (30 days - property testing patterns stable, Hypothesis API mature)

**Researcher notes:**
- Phase 238 builds on solid foundation from Phase 237 (bug discovery infrastructure, property testing templates, fixture reuse patterns).
- Key challenge: Expanding from 66 to 116+ invariants (50+ new tests) while maintaining quality (invariant-first documentation, strategic max_examples).
- PROP-05 (invariant-first thinking) is most critical requirement - prevents implementation-driven tests and ensures clarity.
- Existing security tests (372 tests in backend/tests) provide patterns for PROP-04 security invariants.
- API contract fuzzing (PROP-02) can use Hypothesis strategies without new dependencies (Schemathesis optional).
