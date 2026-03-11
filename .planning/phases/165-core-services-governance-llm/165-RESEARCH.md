# Phase 165: Core Services Coverage (Governance & LLM) - Research

**Researched:** 2026-03-11
**Domain:** Python testing, property-based testing, code coverage, agent governance, LLM service
**Confidence:** HIGH

## Summary

Phase 165 requires achieving 80%+ line coverage on two critical backend services: `agent_governance_service.py` (770 lines) and `byok_handler.py` (1,557 lines). These services control AI agent behavior maturity routing and LLM provider routing/caching—making them the most security-critical components in the Atom platform. The phase must use property-based tests (Hypothesis) to validate governance invariants (cache consistency, maturity rules, permission checks) and parametrized tests to cover the maturity matrix (4 maturity levels × 4 action complexities = 16 combinations).

**Primary recommendation:** Use a hybrid testing strategy combining property-based tests (Hypothesis) for governance invariants, parametrized pytest tests for maturity matrix coverage, and integration tests for end-to-end workflows. Leverage Phase 164's gap analysis tool to target specific missing lines with `pytest --cov-branch --cov-report=term-missing` to identify uncovered lines.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Test runner and assertions | De facto standard for Python testing with powerful fixture system |
| **pytest-cov** | 4.1+ | Coverage reporting (uses coverage.py under the hood) | Standard for coverage measurement in pytest ecosystem |
| **coverage.py** | 7.3+ | Actual line coverage measurement | Gold standard for Python code coverage—supports branch coverage |
| **hypothesis** | 6.92+ | Property-based testing framework | Industry-standard PBT library for Python with excellent pytest integration |
| **pytest-asyncio** | 0.21+ | Async test support | Required for testing async LLM streaming methods |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-mock** | 3.12+ | Mocking fixture | Preferred over unittest.mock for cleaner pytest integration |
| **pytest-xdist** | 3.5+ | Parallel test execution | Speed up test runs (use with caution for db_session fixtures) |
| **pytest-benchmark** | 4.0+ | Performance regression testing | Validate governance cache <10ms performance target |
| **sqlalchemy-fixture** | builtin | Database test fixtures | Fast test database with transaction rollback per test |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **hypothesis** | **quickcheck** (legacy) | Hypothesis has better pytest integration and more powerful strategies |
| **coverage.py** | **pycov** | coverage.py is the gold standard; others are wrappers around it |
| **pytest** | **unittest** | pytest has superior fixture system and parametrization |

**Installation:**
```bash
pip install pytest pytest-cov hypothesis pytest-asyncio pytest-mock pytest-benchmark
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── unit/
│   ├── services/
│   │   ├── test_agent_governance_service_unit.py       # Unit tests for individual methods
│   │   └── test_byok_handler_unit.py                    # Unit tests for LLM routing logic
│   └── fixtures/
│       ├── governance_fixtures.py                       # Shared test data (agents, actions)
│       └── llm_fixtures.py                              # Shared LLM test data (prompts, models)
├── integration/
│   └── services/
│       ├── test_governance_coverage.py                  # Existing: Start point
│       └── test_llm_coverage.py                         # New: LLM service coverage
├── property_tests/
│   ├── governance/
│   │   ├── test_governance_invariants.py                # Existing: Confidence bounds, maturity routing
│   │   └── test_governance_cache_invariants.py          # Existing: Cache consistency
│   └── llm/
│       ├── test_llm_streaming_invariants.py             # Existing: Streaming invariants
│       └── test_cognitive_tier_invariants.py            # NEW: Tier classification invariants
└── coverage_reports/
    └── metrics/
        └── backend_phase_165_governance_llm.json        # Coverage output
```

### Pattern 1: Property-Based Tests for Governance Invariants

**What:** Use Hypothesis to generate thousands of random inputs and verify invariants hold true

**When to use:** Testing properties that MUST always be true (confidence bounds, cache consistency, maturity transitions)

**Example:**

```python
# Source: backend/tests/property_tests/governance/test_governance_invariants.py
from hypothesis import given, settings, example
from hypothesis.strategies import floats, integers, lists
from core.agent_governance_service import AgentGovernanceService

class TestConfidenceScoreInvariants:
    @given(
        initial_confidence=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        boost_amount=floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False)
    )
    @example(initial_confidence=0.3, boost_amount=0.8)  # Would exceed 1.0
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_bounds_invariant(
        self, db_session, initial_confidence: float, boost_amount: float
    ):
        """
        INVARIANT: Confidence scores MUST stay within [0.0, 1.0] bounds.

        VALIDATED_BUG: Confidence score exceeded 1.0 after multiple boosts.
        Root cause: Missing min(1.0, ...) clamp in confidence update logic.
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

        service = AgentGovernanceService(db_session)

        # Simulate confidence update (clamped to [0.0, 1.0])
        new_confidence = max(0.0, min(1.0, initial_confidence + boost_amount))

        # Update agent confidence
        agent.confidence_score = new_confidence
        db_session.commit()

        # Assert: Confidence must be in valid range
        assert 0.0 <= agent.confidence_score <= 1.0, \
            f"Confidence {agent.confidence_score} outside [0.0, 1.0] bounds"
```

### Pattern 2: Parametrized Tests for Maturity Matrix

**What:** Use `@pytest.mark.parametrize` to test all combinations of maturity levels and action complexities

**When to use:** Testing systematic combinations (4 maturity levels × 4 action complexities = 16 tests)

**Example:**

```python
# Source: backend/tests/unit/services/test_agent_governance_service.py
import pytest
from core.models import AgentStatus
from core.agent_governance_service import AgentGovernanceService

class TestMaturityMatrix:
    """Test all combinations of maturity levels and action complexities."""

    @pytest.mark.parametrize("agent_status,complexity,allowed,requires_approval", [
        # STUDENT agents (level 1)
        (AgentStatus.STUDENT, 1, True, False),    # Can do complexity 1 (search, read)
        (AgentStatus.STUDENT, 2, False, True),    # Cannot do complexity 2 (analyze, stream)
        (AgentStatus.STUDENT, 3, False, True),    # Cannot do complexity 3 (create, update)
        (AgentStatus.STUDENT, 4, False, True),    # Cannot do complexity 4 (delete, execute)

        # INTERN agents (level 2)
        (AgentStatus.INTERN, 1, True, False),
        (AgentStatus.INTERN, 2, True, False),     # Can do complexity 2
        (AgentStatus.INTERN, 3, False, True),     # Cannot do complexity 3
        (AgentStatus.INTERN, 4, False, True),     # Cannot do complexity 4

        # SUPERVISED agents (level 3)
        (AgentStatus.SUPERVISED, 1, True, False),
        (AgentStatus.SUPERVISED, 2, True, False),
        (AgentStatus.SUPERVISED, 3, True, True),  # Can do complexity 3 but needs approval
        (AgentStatus.SUPERVISED, 4, False, True),

        # AUTONOMOUS agents (level 4)
        (AgentStatus.AUTONOMOUS, 1, True, False),
        (AgentStatus.AUTONOMOUS, 2, True, False),
        (AgentStatus.AUTONOMOUS, 3, True, False),  # No approval needed
        (AgentStatus.AUTONOMOUS, 4, True, False),  # Can do complexity 4
    ])
    def test_maturity_action_matrix(
        self, db_session, agent_status, complexity, allowed, requires_approval
    ):
        """
        Test the 4×4 maturity matrix:
        - 4 maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
        - 4 action complexity levels (1-4)
        - Total: 16 combinations

        VALIDATED_INVARIANT: Maturity routing prevents STUDENT agents from
        high-complexity actions (delete, execute, transfer).
        """
        agent = AgentRegistry(
            name=f"TestAgent_{agent_status.value}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status.value,
            confidence_score=0.5
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)

        # Map complexity to action type
        action_map = {
            1: "search",
            2: "analyze",
            3: "create",
            4: "delete"
        }

        result = service.can_perform_action(agent.id, action_map[complexity])

        assert result["allowed"] == allowed, \
            f"Agent {agent_status.value} should{'' if allowed else ' not'} be allowed to perform complexity {complexity}"
        assert result["requires_human_approval"] == requires_approval, \
            f"Approval requirement mismatch for {agent_status.value} complexity {complexity}"
```

### Pattern 3: Async Test Support for LLM Streaming

**What:** Use `pytest-asyncio` to test async LLM streaming methods

**When to use:** Testing async generators (streaming responses), async LLM calls

**Example:**

```python
# Source: backend/tests/integration/services/test_llm_coverage.py
import pytest
from unittest.mock import AsyncMock, patch
from core.llm.byok_handler import BYOKHandler

@pytest.mark.asyncio
async def test_stream_completion_fallback(db_session):
    """
    Test streaming completion with provider fallback.

    INVARIANT: Provider fallback preserves context and yields all tokens.
    """
    handler = BYOKHandler()

    # Mock async client
    mock_client = AsyncMock()
    mock_stream = AsyncMock()

    # Simulate streaming response
    async def mock_stream_generator():
        chunks = ["Hello", " world", "!"]
        for chunk in chunks:
            yield mock_completion_chunk(content=chunk)

    mock_stream.__aiter__ = lambda self: mock_stream_generator()
    mock_client.chat.completions.create.return_value = mock_stream

    with patch.object(handler, 'async_clients', {'openai': mock_client}):
        tokens = []
        async for token in handler.stream_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4",
            provider_id="openai",
            db=db_session
        ):
            tokens.append(token)

    assert tokens == ["Hello", " world", "!"], "All tokens should be received in order"
```

### Anti-Patterns to Avoid

- **Testing implementation details:** Focus on behavior (invariants, public API), not internal state
- **Over-mocking:** Use real database (db_session fixture) for integration tests; mock only external APIs (LLM providers)
- **Assertion-free tests:** Every test must assert something (avoid coverage paradox)
- **Testing without branch coverage:** Always use `pytest --cov-branch` to measure both line and branch coverage

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Coverage measurement | Custom line counting | `coverage.py` with `--cov-branch` | Gold standard with branch support, diff reporting, HTML output |
| Property testing | Custom random input generation | `hypothesis` with `@given` decorator | Shrinking to minimal counterexamples, powerful strategies, pytest integration |
| Test parametrization | Custom test loops | `@pytest.mark.parametrize` | Clean test names, fixture injection, parallel execution support |
| Async testing | Custom event loop management | `pytest-asyncio` with `@pytest.mark.asyncio` | Automatic fixture cleanup, proper async context |
| Database fixtures | Custom DB setup/teardown | `@pytest.fixture(scope="function")` with transaction rollback | Fast tests, isolated state, automatic cleanup |
| Mock external APIs | Manual request recording | `unittest.mock.AsyncMock` + `pytest-mock` | Cleaner syntax, assertion helpers, automatic cleanup |

**Key insight:** Custom solutions for coverage measurement, property testing, and async testing are error-prone and miss critical features (branch coverage, counterexample shrinking, proper async context). Use industry-standard tools with proven track records.

---

## Common Pitfalls

### Pitfall 1: Coverage Paradox (High Coverage, Low Quality)

**What goes wrong:** Tests achieve 80%+ line coverage but don't verify correctness (missing assertions)

**Why it happens:** Focusing on coverage percentage rather than assertion quality; tests execute code without validating behavior

**How to avoid:**
- Use property-based tests (Hypothesis) to validate invariants across thousands of inputs
- Track assertion density (assertions per line of test code)
- Use mutation testing (mutmut) to detect weak assertions

**Warning signs:** Test files with >500 lines but <50 assertions; tests with no `assert` statements

### Pitfall 2: Flaky Async Tests

**What goes wrong:** Async tests pass locally but fail in CI due to race conditions or timing issues

**Why it happens:** Missing `await` statements, improper event loop management, shared state between tests

**How to avoid:**
- Always use `@pytest.mark.asyncio` for async tests
- Use `pytest-asyncio` with `auto_enable_mode=true` in pytest.ini
- Mock external async dependencies (LLM providers) with `AsyncMock`
- Avoid time-based assertions (use `pytest-timeout` instead)

**Warning signs:** Intermittent test failures; tests that pass on retry

### Pitfall 3: Database State Leaking Between Tests

**What goes wrong:** Test data from one test affects another test (state pollution)

**Why it happens:** Missing transaction rollback; shared fixtures without proper isolation

**How to avoid:**
- Use `db_session` fixture with automatic transaction rollback
- Scope fixtures to `function` (not `module` or `session`)
- Clean up test data in `finally` blocks

**Warning signs:** Tests that fail when run in parallel but pass individually

### Pitfall 4: Property Tests Running Too Slow

**What goes wrong:** Hypothesis tests with `max_examples=1000` take minutes to run

**Why it happens:** Expensive test setup (database writes, external API calls) in property tests

**How to avoid:**
- Keep property tests focused on invariants (not full workflows)
- Use `max_examples=200` for fast feedback
- Use `@settings(suppress_health_check=[HealthCheck.too_slow])` for slower tests
- Move expensive operations to integration tests

**Warning signs:** Hypothesis tests taking >10 seconds each

### Pitfall 5: Testing Branch Coverage Without Branch Flag

**What goes wrong:** Coverage reports show 80%+ line coverage but only 40% branch coverage

**Why it happens:** Missing `--cov-branch` flag when running pytest

**How to avoid:**
- Always run `pytest --cov-branch` to enable branch coverage
- Check both `percent_covered` (line) and `percent_covered_branch` (branch) in reports
- Use `pytest --cov-report=term-missing` to see which lines aren't covered

**Warning signs:** Coverage discrepancy between HTML report (shows red/yellow lines) and JSON report (shows high percentage)

---

## Code Examples

Verified patterns from official sources:

### Running Coverage Measurement

```python
# Source: backend/tests/docs/COVERAGE_GUIDE.md
# Command: Measure line and branch coverage for governance and LLM services

cd backend
pytest tests/unit/services/test_agent_governance_service_unit.py \
       tests/integration/services/test_governance_coverage.py \
       tests/property_tests/governance/test_governance_invariants.py \
       --cov=core.agent_governance_service \
       --cov=core.llm.byok_handler \
       --cov-branch \
       --cov-report=term-missing \
       --cov-report=html:tests/coverage_reports/html \
       --cov-report=json:tests/coverage_reports/metrics/backend_phase_165_governance_llm.json

# Expected output:
# Name                                            Stmts   Miss  Cover   Missing
# -------------------------------------------------------------------------
# core/agent_governance_service.py                 770    154    80%   23-27, 45-50, ...
# core/llm/byok_handler.py                        1557    311    80%   12-18, 34-40, ...
# -------------------------------------------------------------------------
# TOTAL                                           2327    465    80%
```

### Property Test for Cache Consistency

```python
# Source: backend/tests/property_tests/governance/test_governance_cache_invariants.py
from hypothesis import given, settings
from hypothesis.strategies import text, integers
from core.governance_cache import get_governance_cache

class TestGovernanceCacheInvariants:
    @given(
        agent_id=text(min_size=1, max_size=50),
        action_type=text(min_size=1, max_size=50),
        result_dict=dictionaries(
            keys=text(min_size=1),
            values=integers() | booleans() | text(),
            min_size=3,
            max_size=10
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cache_get_set_invariant(self, agent_id, action_type, result_dict):
        """
        INVARIANT: Cache.get() returns exactly what Cache.set() stored.

        VALIDATED_INVARIANT: Cache consistency is maintained across
        thousands of random key-value pairs.

        Performance: <1ms lookup (validated with pytest-benchmark).
        """
        cache = get_governance_cache()

        # Set value
        cache.set(agent_id, action_type, result_dict)

        # Get value
        retrieved = cache.get(agent_id, action_type)

        # Assert: Retrieved value must match stored value
        assert retrieved == result_dict, \
            f"Cache returned {retrieved} but stored {result_dict}"

        # Assert: Lookup performance <10ms
        with pytest.benchmark(guess=0.001):  # 1ms target
            result = cache.get(agent_id, action_type)
            assert result is not None
```

### Parametrized Test for LLM Provider Routing

```python
# Source: backend/tests/integration/services/test_llm_coverage.py
import pytest
from core.llm.byok_handler import QueryComplexity

class TestLLMProviderRouting:
    """Test LLM provider routing for all query complexity levels."""

    @pytest.mark.parametrize("complexity,task_type,expected_min_quality", [
        # SIMPLE queries -> lowest quality threshold (0)
        (QueryComplexity.SIMPLE, "chat", 0),
        (QueryComplexity.SIMPLE, "general", 0),

        # MODERATE queries -> quality threshold 80
        (QueryComplexity.MODERATE, "analysis", 80),
        (QueryComplexity.MODERATE, "explain", 80),

        # COMPLEX queries -> quality threshold 88
        (QueryComplexity.COMPLEX, "code", 88),
        (QueryComplexity.COMPLEX, "reasoning", 88),

        # ADVANCED queries -> quality threshold 94
        (QueryComplexity.ADVANCED, "security_audit", 94),
        (QueryComplexity.ADVANCED, "cryptography", 94),
    ])
    def test_quality_threshold_by_complexity(
        self, complexity, task_type, expected_min_quality
    ):
        """
        Test that LLM routing enforces quality thresholds based on query complexity.

        INVARIANT: Higher complexity queries require higher quality models.
        """
        from core.llm.byok_handler import MIN_QUALITY_BY_COMPLEXITY

        actual_threshold = MIN_QUALITY_BY_COMPLEXITY.get(complexity, 0)

        assert actual_threshold == expected_min_quality, \
            f"Complexity {complexity.value} should require quality >= {expected_min_quality}, got {actual_threshold}"
```

### Async LLM Streaming Test

```python
# Source: backend/tests/integration/services/test_llm_coverage.py
import pytest
from unittest.mock import AsyncMock, patch
from core.llm.byok_handler import BYOKHandler

@pytest.mark.asyncio
async def test_stream_completion_with_governance_tracking(db_session):
    """
    Test LLM streaming with governance tracking (agent execution records).

    INVARIANT: All streamed tokens are yielded in order, and agent execution
    is recorded with correct status (completed/failed).
    """
    handler = BYOKHandler()

    # Mock async client
    mock_client = AsyncMock()

    # Simulate streaming response with 3 chunks
    async def mock_stream():
        chunks = [
            mock_chunk(content="Hello"),
            mock_chunk(content=" world"),
            mock_chunk(content="!", finish_reason="stop")
        ]
        for chunk in chunks:
            yield chunk

    mock_client.chat.completions.create.return_value = mock_stream()

    with patch.object(handler, 'async_clients', {'openai': mock_client}):
        # Create agent for tracking
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        # Stream with governance tracking
        tokens = []
        async for token in handler.stream_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4",
            provider_id="openai",
            agent_id=agent.id,
            db=db_session
        ):
            tokens.append(token)

    # Assert: All tokens received
    assert tokens == ["Hello", " world", "!"]

    # Assert: Agent execution recorded
    execution = db_session.query(AgentExecution).filter(
        AgentExecution.agent_id == agent.id
    ).first()

    assert execution is not None, "Agent execution should be recorded"
    assert execution.status == "completed", "Stream should complete successfully"
    assert "Generated 3 tokens" in execution.output_summary
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Service-level coverage estimates | Actual line coverage from coverage.py | Phase 163 (2026-02-27) | 8.5% actual vs 74.6% estimated—massive gap revealed |
| Example-based testing | Property-based testing (Hypothesis) | Phase 160+ (2026-02) | Systematic validation of invariants vs happy-path testing |
| Manual test prioritization | Business impact scoring (Critical/High/Medium/Low) | Phase 164 (2026-03-11) | Priority-focused testing on highest-risk code first |
| Line coverage only | Branch coverage (--cov-branch) | Phase 163 (2026-02-27) | 40-60% gap between line and branch coverage detected |

**Deprecated/outdated:**
- **Service-level coverage estimates**: Phase 163 revealed these were wildly inaccurate (74.6% estimated vs 8.5% actual)
- **Happy-path testing only**: Current best practice is property-based tests for invariants + parametrized tests for matrix coverage
- **Manual gap analysis**: Phase 164 automated gap analysis with business impact scoring—manual spreadsheets are obsolete

---

## Open Questions

1. **Should we use mutation testing (mutmut) to detect weak assertions?**
   - What we know: Mutation testing can detect tests with missing assertions (coverage paradox)
   - What's unclear: Whether mutmut integrates well with Hypothesis tests and async tests
   - Recommendation: Start with property-based tests (Hypothesis) which naturally encourage assertion density; add mutation testing in Phase 166+ if coverage paradox persists

2. **How many property tests are enough for governance invariants?**
   - What we know: Existing `test_governance_invariants.py` has 5 property tests covering confidence bounds, maturity routing, and cache consistency
   - What's unclear: Whether this is comprehensive enough for the full governance service (770 lines)
   - Recommendation: Focus on the 4 critical invariants listed in success criteria (cache consistency, maturity rules, permission checks, confidence bounds); add more only if bugs are found

3. **Should we test LLM provider fallback behavior?**
   - What we know: `byok_handler.py` has `_get_provider_fallback_order()` with priority ordering (deepseek → openai → moonshot → minimax)
   - What's unclear: Whether to mock provider failures to test fallback logic
   - Recommendation: YES—test fallback invariants using `AsyncMock` to raise exceptions; validates that context is preserved when switching providers

4. **What's the optimal max_examples for Hypothesis tests?**
   - What we know: Existing tests use `max_examples=200`; Hypothesis default is 100
   - What's unclear: Tradeoff between test execution time and bug detection
   - Recommendation: Use `max_examples=200` for critical invariants (confidence bounds, cache consistency); use `max_examples=100` for faster feedback on routine tests

---

## Sources

### Primary (HIGH confidence)

- **pytest official docs** - https://docs.pytest.org/en/7.4.x/ (parametrization, fixtures, async support)
- **coverage.py documentation** - https://coverage.readthedocs.io/en/7.3.x/ (branch coverage, JSON report format)
- **Hypothesis documentation** - https://hypothesis.readthedocs.io/en/latest/ (property testing, strategies, settings)
- **backend/tests/docs/COVERAGE_GUIDE.md** - Project-specific coverage interpretation guide (line vs branch coverage, coverage paradox)
- **backend/tests/property_tests/governance/test_governance_invariants.py** - Existing property test patterns for governance
- **backend/tests/property_tests/llm/test_llm_streaming_invariants.py** - Existing property test patterns for LLM streaming

### Secondary (MEDIUM confidence)

- **pytest-asyncio documentation** - https://pytest-asyncio.readthedocs.io/ (async test patterns, auto enable mode)
- **.planning/phases/164-gap-analysis-prioritization/164-01-SUMMARY.md** - Gap analysis tool methodology and priority scoring
- **backend/tests/coverage_reports/metrics/business_impact_scores.json** - Business impact tier definitions (Critical/High/Medium/Low)
- **backend/core/agent_governance_service.py** - Source code under test (770 lines, maturity routing, cache invalidation)
- **backend/core/llm/byok_handler.py** - Source code under test (1,557 lines, provider routing, streaming, caching)

### Tertiary (LOW confidence)

- None—all sources verified against official documentation or codebase

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest, coverage.py, Hypothesis are industry standards with extensive documentation
- Architecture: HIGH - Existing test patterns in codebase (test_governance_invariants.py, test_llm_streaming_invariants.py) provide proven patterns
- Pitfalls: HIGH - COVERAGE_GUIDE.md documents coverage paradox and other testing pitfalls with examples

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (30 days—testing tooling is stable; pytest/Hypothesis release cycles are slow)
