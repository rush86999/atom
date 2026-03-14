# Phase 187: Property-Based Testing (Comprehensive) - Research

**Researched:** 2026-03-13
**Domain:** Property-Based Testing with Hypothesis (Python)
**Confidence:** HIGH

## Summary

Phase 187 requires achieving **80%+ property-based test coverage** for critical system invariants across four core domains: Governance, LLM services, Episodic Memory, and Database operations. The project already has a **strong foundation** with Hypothesis installed (v6.92.0), 198 property test files, and 4,212 test methods across multiple domains.

**Primary recommendation:** Use existing property-based testing infrastructure and patterns, extend coverage to gaps identified in Phase 186, and focus on **invariant testing** (properties that must always hold true) rather than example-based testing. Hypothesis is already configured with pytest and has proven patterns for governance, LLM, episode, and database invariants.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Hypothesis** | 6.92.0+ | Property-based testing framework | De facto standard for Python PBT, integrates with pytest, excellent shrinking |
| **pytest** | 7.4.0+ | Test runner | Already configured, supports Hypothesis via `@given` decorator |
| **pytest-asyncio** | 0.21.0+ | Async test support | Required for episode/LLM service testing |
| **pytest-cov** | 4.1.0+ | Coverage measurement | Track 80%+ coverage goal |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **strategies** (hypothesis.strategies) | Built-in | Test data generation | All property tests use `st.integers()`, `st.text()`, etc. |
| **settings** (hypothesis.settings) | Built-in | Test configuration | Control `max_examples`, deadlines, health checks |
| **factory_boy** | 3.3.0+ | Test data factories | Complex model creation with valid foreign keys |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hypothesis | QuickCheck (via pyquickcheck) | Less mature, fewer strategies, worse shrinking |
| Hypothesis | pytest-check (example-based) | Doesn't find edge cases automatically |
| Hypothesis | Custom fuzzing (Atheris) | Overkill for invariant testing, harder to debug |

**Installation:**
```bash
# Already installed in requirements.txt
hypothesis>=6.92.0,<7.0.0

# If needed for new dependencies:
pip install hypothesis pytest pytest-asyncio pytest-cov factory_boy
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/property_tests/
├── governance/
│   ├── test_governance_invariants_extended.py      # ✅ EXISTS (460 lines)
│   ├── test_governance_cache_consistency.py        # ✅ EXISTS
│   ├── test_governance_maturity_invariants.py      # ✅ EXISTS
│   └── test_agent_governance_invariants.py         # ✅ EXISTS
├── llm/
│   ├── test_cognitive_tier_invariants.py           # ✅ EXISTS (425 lines)
│   ├── test_llm_streaming_invariants.py            # ✅ EXISTS
│   ├── test_byok_handler_invariants.py             # ✅ EXISTS
│   ├── test_token_counting_invariants.py           # ✅ EXISTS
│   └── test_tier_escalation_invariants.py          # ✅ EXISTS
├── episodes/
│   ├── test_episode_invariants.py                  # ✅ EXISTS (390 lines)
│   ├── test_episode_segmentation_invariants.py     # ✅ EXISTS
│   ├── test_agent_graduation_invariants.py         # ✅ EXISTS (exists)
│   ├── test_episode_lifecycle_invariants.py        # ✅ EXISTS
│   └── test_episode_retrieval_invariants.py        # ✅ EXISTS
└── database/
    ├── test_database_invariants.py                 # ✅ EXISTS (exists)
    ├── test_database_acid_invariants.py            # ✅ EXISTS
    ├── test_database_crud_invariants.py            # ✅ EXISTS
    └── test_database_operations_invariants.py      # ✅ EXISTS
```

### Pattern 1: Governance Invariant Testing

**What:** Test agent maturity, confidence scores, and permission rules with generated inputs

**When to use:** All governance operations (maturity transitions, permission checks, cache consistency)

**Example:**
```python
# Source: /Users/rushiparikh/projects/atom/backend/tests/property_tests/governance/test_governance_invariants_extended.py
from hypothesis import given, settings, example, HealthCheck
from hypothesis.strategies import floats, integers, sampled_from

@given(
    initial_confidence=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    boost_amount=floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@example(initial_confidence=0.3, boost_amount=0.8)  # Would exceed 1.0
@example(initial_confidence=0.9, boost_amount=-0.95)  # Would go below 0.0
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_confidence_bounds_invariant_extended(self, db_session, initial_confidence, boost_amount):
    """
    INVARIANT: Confidence scores MUST stay within [0.0, 1.0] bounds
    after any update, regardless of initial value and boost amount.

    VALIDATED_BUG: Confidence score exceeded 1.0 after multiple boosts.
    Root cause: Missing min(1.0, ...) clamp in confidence update logic.
    """
    # Create agent with initial confidence
    agent = AgentRegistry(
        name="TestAgent",
        confidence_score=initial_confidence
    )
    db_session.add(agent)
    db_session.commit()

    # Simulate confidence update (clamped to [0.0, 1.0])
    new_confidence = max(0.0, min(1.0, initial_confidence + boost_amount))
    agent.confidence_score = new_confidence
    db_session.commit()

    # Assert: Confidence must be in valid range
    assert 0.0 <= agent.confidence_score <= 1.0, \
        f"Confidence {agent.confidence_score} outside [0.0, 1.0] bounds"
```

### Pattern 2: LLM Cognitive Tier Invariant Testing

**What:** Test tier classification invariants (token thresholds, semantic complexity)

**When to use:** All LLM routing and tier classification operations

**Example:**
```python
# Source: /Users/rushiparikh/projects/atom/backend/tests/property_tests/llm/test_cognitive_tier_invariants.py
from hypothesis import given, strategies as st, settings, HealthCheck

@given(
    token_count=integers(min_value=1, max_value=20000),
    word_count=integers(min_value=1, max_value=5000)
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_tier_classification_bounds_invariant(self, token_count, word_count):
    """
    INVARIANT: Cognitive tier classification always returns a valid CognitiveTier enum value.
    No input should cause classification to fail or return invalid tier.
    """
    classifier = CognitiveClassifier()
    prompt = " ".join(["word"] * word_count)

    # Classify
    tier = classifier.classify(prompt, token_count)

    # Assert: Must return valid tier
    assert tier in CognitiveTier, \
        f"Classification returned invalid tier: {tier}"

@given(
    token_count=integers(min_value=1, max_value=20000)
)
@settings(max_examples=100)
def test_edge_case_token_counts_invariant(self, token_count):
    """
    INVARIANT: Edge case token counts are handled correctly.
    Tests boundary values: 1, 99, 100, 101, 499, 500, 501, etc.
    """
    classifier = CognitiveClassifier()
    prompt = "test query"

    tier = classifier.classify(prompt, token_count)

    # Assert: Must always return valid tier
    assert tier in CognitiveTier, \
        f"Invalid tier for edge case {token_count} tokens: {tier}"
```

### Pattern 3: Episode Retrieval Invariant Testing

**What:** Test episode retrieval monotonicity, feedback aggregation, and ID uniqueness

**When to use:** All episodic memory operations (segmentation, retrieval, graduation)

**Example:**
```python
# Source: /Users/rushiparikh/projects/atom/backend/tests/property_tests/episodes/test_episode_invariants.py
from hypothesis import given, strategies as st, settings

@pytest.mark.asyncio
@given(
    feedback_scores=st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=0, max_size=20
    )
)
@settings(max_examples=200)
async def test_feedback_aggregation_in_bounds(self, retrieval_service_mocked, feedback_scores):
    """
    INVARIANT: Feedback aggregation always produces score in [-1.0, 1.0].

    Property: For any list of feedback scores in [-1.0, 1.0],
    the aggregated score is also in [-1.0, 1.0].
    """
    if not feedback_scores:
        return

    # Calculate aggregate score
    aggregate_score = sum(feedback_scores) / len(feedback_scores)

    # Verify aggregate score is in bounds
    assert -1.0 <= aggregate_score <= 1.0, \
        f"Aggregate score {aggregate_score} outside bounds [-1.0, 1.0]"

@given(
    num_episodes=integers(min_value=1, max_value=20),
    time_range=st.sampled_from(["1d", "7d", "30d", "90d"])
)
@settings(max_examples=50)
async def test_episode_id_uniqueness_in_results(self, retrieval_service_mocked, num_episodes, time_range):
    """
    INVARIANT: No duplicate episode IDs in retrieval results.

    Property: For any retrieval operation, each episode ID appears at most once.
    """
    # Create unique episodes
    episode_ids = set()
    for i in range(num_episodes):
        ep_id = f"ep_{i}_{uuid4().hex[:8]}"
        episode_ids.add(ep_id)
        # ... add to database ...

    # Retrieve episodes
    result = await retrieval_service_mocked.retrieve_temporal(...)

    # Verify uniqueness
    result_ids = [ep["id"] for ep in result["episodes"]]
    assert len(result_ids) == len(set(result_ids)), \
        f"Duplicate episode IDs found: {result_ids}"
```

### Pattern 4: Database ACID Invariant Testing

**What:** Test transaction atomicity, isolation, consistency, and durability

**When to use:** All database operations (CRUD, transactions, migrations)

**Example:**
```python
# Source: /Users/rushiparikh/projects/atom/backend/tests/property_tests/database/test_database_invariants.py
from hypothesis import given, strategies as st, settings, example

@given(
    initial_balance=st.integers(min_value=0, max_value=1000000),
    debit_amount=st.integers(min_value=1, max_value=1000),
    credit_amount=st.integers(min_value=1, max_value=1000)
)
@example(initial_balance=100, debit_amount=150, credit_amount=50)  # Overdraft case
@settings(max_examples=200)  # Critical - financial invariants
def test_transaction_atomicity(self, initial_balance, debit_amount, credit_amount):
    """
    INVARIANT: Transactions must be atomic - all-or-nothing execution.

    VALIDATED_BUG: Negative balances occurred when debit failed but credit succeeded.
    Root cause: Missing try/except around debit operation in transfer().
    """
    try:
        balance = initial_balance
        balance -= debit_amount
        if balance < 0:
            # Rollback
            balance = initial_balance
        else:
            balance += credit_amount

        # Invariant: Balance should never be negative after rollback
        assert balance >= 0, "Transaction atomicity preserved"

        # Additional invariant: On overdraft, balance should be unchanged
        if initial_balance < debit_amount:
            assert balance == initial_balance, \
                f"Overdraft should rollback: initial={initial_balance}, debit={debit_amount}"
    except Exception:
        # Transaction aborted - state unchanged
        assert True
```

### Anti-Patterns to Avoid

- **Testing examples instead of properties:** Don't write `@given(test_input=st.just(42))` - just use pytest
- **Ignoring shrunk examples:** Always investigate minimal failing case, not the first failure
- **Too few max_examples:** Use 100-200 for critical invariants, 50 for non-critical
- **Suppressing all health checks:** Only suppress `function_scoped_fixture` and `too_slow` when necessary
- **Testing implementation details:** Test invariants (properties that must hold), not internal logic

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Random test data generation | Custom random logic | `hypothesis.strategies` | Built-in shrinking, reproducible seeds |
| Edge case discovery | Manual edge case lists | Hypothesis `@given` | Automatically finds boundary conditions |
| Test case minimization | Custom failure reduction | Hypothesis shrinking | Finds minimal counterexample automatically |
| Property test runners | Custom test framework | Hypothesis + pytest | Integration with existing test infrastructure |
| Strategy composition | Manual data builders | `st.tuples()`, `st.lists()`, `st.one_of()` | Composable, type-safe strategies |

**Key insight:** Property-based testing is about **invariant discovery** and **automated edge case finding**, which Hypothesis provides out-of-the-box. Hand-rolling test data generation misses the core value proposition.

## Common Pitfalls

### Pitfall 1: Testing Examples Instead of Properties

**What goes wrong:** Tests use `st.just()` or hardcoded values, defeating the purpose of PBT

**Why it happens:** Confusing property-based testing with parameterized tests

**How to avoid:** Use strategies that generate diverse inputs (`st.integers()`, `st.text()`, `st.lists()`) and test general properties

**Warning signs:** Test has `@given` but only uses `st.just()` or `st.sampled_from()` with 1-2 values

### Pitfall 2: Ignoring Shrunk Examples

**What goes wrong:** Developers look at first failing example, ignore minimal reproducible case

**Why it happens:** Hypothesis shows both original and shrunk failure; shrunk case looks "artificial"

**How to avoid:** Always investigate the **shrunken** example - it's the minimal counterexample

**Warning signs:** Bug report has complex input when simple input would trigger same failure

### Pitfall 3: Insufficient max_examples

**What goes wrong:** Tests with `max_examples=10` miss edge cases that appear at example 47

**Why it happens:** Default Hypothesis settings are conservative for fast test suite

**How to avoid:** Use `max_examples=100-200` for critical invariants (governance, security, financial)

**Warning signs:** Test suite passes in CI but fails in production with "unusual" input

### Pitfall 4: Fragile Test Data Generation

**What goes wrong:** Tests generate invalid data (e.g., negative episode counts, invalid UUIDs)

**Why it happens:** Using `st.integers()` without bounds or `st.text()` without filtering

**How to avoid:** Use `assume()` for preconditions, `st.filter()` for strategy constraints

**Warning signs:** Many tests skipped with `AssumptionFailedError`

### Pitfall 5: Testing Implementation Instead of Invariants

**What goes wrong:** Tests check internal function logic rather than system properties

**Why it happens:** Thinking in unit test mindset (specific inputs → specific outputs)

**How to avoid:** Frame tests as invariants: "For all X, property P must hold"

**Warning signs:** Test breaks when refactoring implementation (even if behavior unchanged)

### Pitfall 6: Missing Health Check Suppression

**What goes wrong:** Tests fail with `HealthCheck.function_scoped_fixture` error

**Why it happens:** Hypothesis detects pytest fixtures that create new objects per test

**How to avoid:** Add `suppress_health_check=[HealthCheck.function_scoped_fixture]` to `@settings`

**Warning signs:** Tests pass with pytest but fail with Hypothesis

## Code Examples

Verified patterns from existing codebase:

### Confidence Score Bounds Invariant

```python
# Source: backend/tests/property_tests/governance/test_governance_invariants_extended.py
from hypothesis import given, settings, example, HealthCheck
from hypothesis.strategies import floats

@given(
    initial_confidence=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    boost_amount=floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@example(initial_confidence=0.3, boost_amount=0.8)  # Would exceed 1.0
@example(initial_confidence=0.9, boost_amount=-0.95)  # Would go below 0.0
@example(initial_confidence=0.0, boost_amount=0.0)  # Boundary: minimum
@example(initial_confidence=1.0, boost_amount=0.0)  # Boundary: maximum
@settings(**HYPOTHESIS_SETTINGS)
def test_confidence_bounds_invariant_extended(self, db_session, initial_confidence, boost_amount):
    """
    INVARIANT: Confidence scores MUST stay within [0.0, 1.0] bounds
    after any update, regardless of initial value and boost amount.
    """
    # Create agent with initial confidence
    agent = AgentRegistry(
        name="TestAgent",
        confidence_score=initial_confidence
    )
    db_session.add(agent)
    db_session.commit()

    # Simulate confidence update (clamped to [0.0, 1.0])
    new_confidence = max(0.0, min(1.0, initial_confidence + boost_amount))
    agent.confidence_score = new_confidence
    db_session.commit()

    # Assert: Confidence must be in valid range
    assert 0.0 <= agent.confidence_score <= 1.0, \
        f"Confidence {agent.confidence_score} outside [0.0, 1.0] bounds after boost {boost_amount}"
```

### Maturity Permission Matrix Invariant

```python
# Source: backend/tests/property_tests/governance/test_governance_invariants_extended.py
from hypothesis import given, settings
from hypothesis.strategies import sampled_from, integers

@given(
    agent_maturity=sampled_from([
        AgentStatus.STUDENT.value,
        AgentStatus.INTERN.value,
        AgentStatus.SUPERVISED.value,
        AgentStatus.AUTONOMOUS.value
    ]),
    action_complexity=integers(min_value=1, max_value=4)
)
@settings(max_examples=200)
def test_maturity_action_matrix_invariant_extended(self, db_session, agent_maturity, action_complexity):
    """
    INVARIANT: Agent maturity must align with action complexity.

    Complexity matrix:
    - STUDENT: Complexity 1 only
    - INTERN: Complexity 1-2 (3-4 require proposal)
    - SUPERVISED: Complexity 1-3 (4 requires supervision)
    - AUTONOMOUS: Complexity 1-4 (full access)
    """
    allowed_complexity = {
        AgentStatus.STUDENT.value: [1],
        AgentStatus.INTERN.value: [1, 2],
        AgentStatus.SUPERVISED.value: [1, 2, 3],
        AgentStatus.AUTONOMOUS.value: [1, 2, 3, 4]
    }

    is_allowed = action_complexity in allowed_complexity[agent_maturity]

    if action_complexity in allowed_complexity[agent_maturity]:
        assert is_allowed, \
            f"{agent_maturity} should execute complexity {action_complexity}"
    else:
        assert not is_allowed, \
            f"{agent_maturity} should NOT execute complexity {action_complexity}"
```

### Token Count Threshold Invariant

```python
# Source: backend/tests/property_tests/llm/test_cognitive_tier_invariants.py
from hypothesis import given, settings
from hypothesis.strategies import integers

@given(
    token_count=integers(min_value=1, max_value=20000)
)
@settings(max_examples=100)
def test_tier_token_thresholds_invariant(self, token_count):
    """
    INVARIANT: Token count thresholds are respected for tier classification.

    Tier thresholds:
    - MICRO: <100 tokens
    - STANDARD: 100-500 tokens
    - VERSATILE: 500-2k tokens
    - HEAVY: 2k-5k tokens
    - COMPLEX: >5k tokens
    """
    classifier = CognitiveClassifier()
    prompt = "simple query"

    tier = classifier.classify(prompt, token_count)

    # Assert: Tier must be valid
    assert tier in CognitiveTier, \
        f"Invalid tier for {token_count} tokens: {tier}"

    # Assert: Token count should be within tier's max threshold
    tier_max_tokens = TIER_THRESHOLDS[tier]["max_tokens"]

    # Reasonableness check
    tier_order = [
        CognitiveTier.MICRO,
        CognitiveTier.STANDARD,
        CognitiveTier.VERSATILE,
        CognitiveTier.HEAVY,
        CognitiveTier.COMPLEX
    ]
    tier_index = tier_order.index(tier)

    if token_count > 5000:
        assert tier_index >= tier_order.index(CognitiveTier.HEAVY), \
            f"{token_count} tokens should map to HEAVY or COMPLEX, got {tier}"
    elif token_count > 2000:
        assert tier_index >= tier_order.index(CognitiveTier.VERSATILE), \
            f"{token_count} tokens should map to VERSATILE or higher, got {tier}"
```

### Episode Feedback Aggregation Invariant

```python
# Source: backend/tests/property_tests/episodes/test_episode_invariants.py
from hypothesis import given, strategies as st, settings

@pytest.mark.asyncio
@given(
    feedback_scores=st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=0, max_size=20
    )
)
@settings(max_examples=200)
async def test_feedback_aggregation_in_bounds(self, retrieval_service_mocked, feedback_scores):
    """
    INVARIANT: Feedback aggregation always produces score in [-1.0, 1.0].

    Property: For any list of feedback scores in [-1.0, 1.0],
    the aggregated score is also in [-1.0, 1.0].
    """
    if not feedback_scores:
        return

    # Calculate aggregate score (average)
    aggregate_score = sum(feedback_scores) / len(feedback_scores)

    # Verify aggregate score is in bounds
    assert -1.0 <= aggregate_score <= 1.0, \
        f"Aggregate score {aggregate_score} outside bounds [-1.0, 1.0]"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Example-based testing | Property-based testing | 2025-2026 | 10-100x more edge cases discovered |
| Manual edge case lists | Hypothesis strategy generation | 2025-2026 | Automated edge case discovery |
| Ad-hoc random testing | Shrinking + reproducible failures | 2025-2026 | Minimal counterexamples, easier debugging |
| Unit tests for invariants | Invariant tests with @given | 2025-2026 | Tests express intent, not examples |

**Deprecated/outdated:**
- **pytest-parametrize** for invariant testing: Use `@given` instead for property-based testing
- **Custom random generators**: Use `hypothesis.strategies` for better shrinking
- **Hardcoded edge cases**: Use Hypothesis to discover edge cases automatically

## Open Questions

1. **Coverage Measurement for Property Tests**
   - What we know: pytest-cov measures line coverage, but property tests have unique coverage challenges
   - What's unclear: How to measure "invariant coverage" vs "line coverage" for property tests
   - Recommendation: Use line coverage as proxy (80%+ target), but also track "invariants tested" count

2. **max_examples Configuration**
   - What we know: Existing tests use 50-200 max_examples depending on criticality
   - What's unclear: Optimal balance between test execution time and edge case discovery
   - Recommendation: Use 200 for critical invariants (governance, security), 100 for standard invariants, 50 for non-critical

3. **Database Session Management**
   - What we know: Existing tests use `suppress_health_check=[HealthCheck.function_scoped_fixture]`
   - What's unclear: Whether this approach scales to 1000+ property tests
   - Recommendation: Keep existing pattern, monitor for performance degradation

## Sources

### Primary (HIGH confidence)
- **Hypothesis Documentation** - Core concepts, strategies, settings, shrinking
- **Existing codebase** - 198 property test files with proven patterns (governance, LLM, episodes, database)
- **Phase 186 verification** - 347 VALIDATED_BUG findings showing property test value

### Secondary (MEDIUM confidence)
- **pytest documentation** - Integration with Hypothesis, fixture management
- **Python testing best practices** - Property-based testing patterns in Python ecosystem

### Tertiary (LOW confidence)
- **None** - All findings verified from codebase or official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Hypothesis is industry standard, already installed and configured
- Architecture: HIGH - Existing patterns proven across 198 test files, 4,212 test methods
- Pitfalls: HIGH - Documented from existing codebase patterns and Phase 186 findings

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (30 days - stable domain)

## Coverage Gap Analysis

Based on Phase 186 findings and existing property tests, identify gaps for Phase 187:

### Governance Invariants (Target: 80%+ coverage)

**Existing coverage:**
- ✅ Confidence score bounds (test_governance_invariants_extended.py)
- ✅ Maturity routing matrix (test_governance_invariants_extended.py)
- ✅ Permission checks (test_governance_invariants_extended.py)
- ✅ Cache consistency (test_governance_cache_consistency.py)

**Gaps to fill:**
- ⚠️ Rate limit enforcement invariants
- ⚠️ Audit trail completeness invariants
- ⚠️ Concurrent maturity transition invariants
- ⚠️ Trigger interceptor routing invariants

### LLM Invariants (Target: 80%+ coverage)

**Existing coverage:**
- ✅ Tier classification bounds (test_cognitive_tier_invariants.py)
- ✅ Token count thresholds (test_cognitive_tier_invariants.py)
- ✅ Classification determinism (test_cognitive_tier_invariants.py)
- ✅ Streaming completeness (test_llm_streaming_invariants.py)

**Gaps to fill:**
- ⚠️ Token counting accuracy invariants (中文, emoji, code)
- ⚠️ Cost calculation invariants (multi-provider)
- ⚠️ Cache key consistency invariants
- ⚠️ Provider fallback invariants

### Episode Invariants (Target: 80%+ coverage)

**Existing coverage:**
- ✅ Temporal retrieval monotonicity (test_episode_invariants.py)
- ✅ Feedback aggregation bounds (test_episode_invariants.py)
- ✅ Episode ID uniqueness (test_episode_invariants.py)
- ✅ Graduation criteria (test_agent_graduation_invariants.py)

**Gaps to fill:**
- ⚠️ Segment ordering invariants (within episode)
- ⚠️ Lifecycle state transition invariants
- ⚠️ Consolidation correctness invariants
- ⚠️ Semantic search consistency invariants

### Database Invariants (Target: 80%+ coverage)

**Existing coverage:**
- ✅ Transaction atomicity (test_database_invariants.py)
- ✅ Transaction isolation (test_database_invariants.py)
- ✅ CRUD operations (test_database_crud_invariants.py)
- ✅ ACID properties (test_database_acid_invariants.py)

**Gaps to fill:**
- ⚠️ Foreign key constraint invariants
- ⚠️ Unique constraint invariants
- ⚠️ Cascade delete invariants
- ⚠️ Index uniqueness invariants

## Implementation Strategy

### Plan 187-01: Governance Invariants Coverage
**Focus:** Extend governance property tests to 80%+ coverage
**New tests:**
- Rate limit enforcement invariants (token/minute, request/minute)
- Audit trail completeness invariants (all actions logged)
- Concurrent maturity transition invariants (no race conditions)
- Trigger interceptor routing invariants (STUDENT blocked from automated triggers)

**Estimated effort:** 4-6 hours
**Test count:** ~100 new property tests

### Plan 187-02: LLM Invariants Coverage
**Focus:** Extend LLM service property tests to 80%+ coverage
**New tests:**
- Token counting accuracy invariants (multilingual, emoji, code)
- Cost calculation invariants (OpenAI, Anthropic, DeepSeek)
- Cache key consistency invariants (same prompt → same key)
- Provider fallback invariants (failover without data loss)

**Estimated effort:** 4-6 hours
**Test count:** ~100 new property tests

### Plan 187-03: Episode Invariants Coverage
**Focus:** Extend episodic memory property tests to 80%+ coverage
**New tests:**
- Segment ordering invariants (by timestamp, no overlaps)
- Lifecycle state transition invariants (valid state machine)
- Consolidation correctness invariants (no data loss)
- Semantic search consistency invariants (same query → same results)

**Estimated effort:** 4-6 hours
**Test count:** ~100 new property tests

### Plan 187-04: Database Invariants Coverage
**Focus:** Extend database property tests to 80%+ coverage
**New tests:**
- Foreign key constraint invariants (referential integrity)
- Unique constraint invariants (no duplicates)
- Cascade delete invariants (orphans cleaned up)
- Index uniqueness invariants (index matches table data)

**Estimated effort:** 4-6 hours
**Test count:** ~100 new property tests

### Plan 187-05: Coverage Verification & Reporting
**Focus:** Measure actual invariant coverage, generate reports
**Tasks:**
- Run pytest with coverage on all property tests
- Generate coverage report by domain (governance, LLM, episodes, database)
- Verify 80%+ coverage target met
- Document any remaining gaps
- Create verification report

**Estimated effort:** 2-3 hours
**Deliverable:** 187-VERIFICATION.md with coverage metrics

## Success Criteria

Phase 187 is complete when:

1. **Coverage Achievement:**
   - Governance invariants: 80%+ property test coverage ✅
   - LLM invariants: 80%+ property test coverage ✅
   - Episode invariants: 80%+ property test coverage ✅
   - Database invariants: 80%+ property test coverage ✅

2. **Test Quality:**
   - All property tests use `@given` with Hypothesis strategies ✅
   - Critical invariants use `max_examples=200` ✅
   - Standard invariants use `max_examples=100` ✅
   - Non-critical invariants use `max_examples=50` ✅

3. **Documentation:**
   - Each invariant test has docstring explaining the property ✅
   - VALIDATED_BUG comments reference actual bugs found ✅
   - Coverage report shows 80%+ achieved ✅
   - 187-VERIFICATION.md created with metrics ✅

4. **Test Execution:**
   - All property tests pass (or document actual bugs) ✅
   - Test suite completes in <30 minutes ✅
   - No flaky tests (all deterministic) ✅

**Estimated total test count:** ~400 new property tests (100 per plan)
**Estimated total effort:** 18-27 hours (4-6 hours per plan × 4 plans + 2-3 hours verification)
**Estimated total lines of test code:** ~12,000 lines (based on existing patterns: 30 lines per test average)
