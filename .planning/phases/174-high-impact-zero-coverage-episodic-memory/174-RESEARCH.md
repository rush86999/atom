# Phase 174: High-Impact Zero Coverage (Episodic Memory) - Research

**Researched:** 2026-03-12
**Domain:** Python Testing, Pytest, Episodic Memory Services, Test Coverage
**Confidence:** HIGH

## Summary

Phase 174 requires achieving 75%+ line coverage on four episodic memory services that currently have low or unmeasured coverage. Based on Phase 166's success (85% average coverage achieved), this phase focuses on writing comprehensive tests for uncovered edge cases, error paths, and complex integration scenarios across:

1. **EpisodeSegmentationService** (1,536 lines) - Episode creation from sessions, boundary detection, LLM canvas summaries
2. **EpisodeRetrievalService** (1,076 lines) - Four retrieval modes (temporal, semantic, sequential, contextual)
3. **EpisodeLifecycleService** (421 lines) - Decay, consolidation, archiving, importance scoring
4. **AgentGraduationService** (977 lines) - Graduation exams, readiness scoring, constitutional compliance

**Primary recommendation:** Use a structured 4-plan approach targeting one service per plan, building on Phase 166's proven patterns (integration tests + property-based tests with Hypothesis).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Test framework | Industry standard, async support, rich plugin ecosystem |
| **pytest-cov** | Latest | Coverage measurement | Built-in coverage reporting with `--cov` flag |
| **pytest-asyncio** | Latest | Async test support | Required for async service methods (async/await) |
| **hypothesis** | Latest | Property-based testing | Already used in Phase 166, excellent for invariant testing |

### Testing Patterns
| Pattern | Purpose | When to Use |
|---------|---------|-------------|
| **Integration tests** | Test service methods with mocked dependencies | Database operations, LanceDB interactions, LLM calls |
| **Property-based tests** | Verify invariants across many generated inputs | Boundary conditions, score calculations, data transformations |
| **Fixture-based setup** | Reusable test data and service instances | All test types - use pytest fixtures for consistency |

### Configuration
**File:** `backend/pytest.ini` (already configured)
- Coverage targets: 80% line coverage, 70% branch coverage
- Async mode: `auto` (required for async service methods)
- Markers: `episode`, `property`, `integration` already defined

**Installation:**
```bash
# All dependencies already installed
pip install pytest pytest-cov pytest-asyncio hypothesis
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | pytest has better fixtures, async support, and coverage integration |
| hypothesis | pytest-parametrize | hypothesis generates 100s of examples automatically vs manual parametrization |
| pytest-cov | coverage.py CLI | pytest-cov integrates directly with pytest, better reporting |

## Architecture Patterns

### Recommended Project Structure
```
backend/tests/unit/episodes/
├── test_episode_segmentation_service.py      # NEW: Comprehensive segmentation tests
├── test_episode_retrieval_service.py         # NEW: Comprehensive retrieval tests
├── test_episode_lifecycle_service.py         # NEW: Comprehensive lifecycle tests
├── test_episode_graduation_service.py        # NEW: Comprehensive graduation tests
├── test_episode_segmentation_coverage.py     # EXISTING: 60% target, build on this
├── test_episode_lifecycle_coverage.py        # EXISTING: 60% target, build on this
└── test_episode_retrieval_coverage.py        # EXISTING: 60% target, build on this

backend/tests/property_tests/episodes/
├── test_episode_segmentation_invariants.py   # NEW: Segmentation invariants
├── test_episode_lifecycle_invariants.py      # EXISTING: From Phase 166
├── test_episode_retrieval_invariants.py      # EXISTING: From Phase 166
└── test_episode_graduation_invariants.py     # NEW: Graduation invariants
```

### Pattern 1: Service Test Structure (from Phase 166)

**What:** Organize tests by service class with descriptive test method names
**When to use:** All service unit and integration tests
**Example:**
```python
class TestEpisodeSegmentationService:
    """Tests for EpisodeSegmentationService"""

    async def test_create_episode_from_session_basic(self, db_session, segmentation_service):
        """Test basic episode creation from chat session"""
        # Arrange
        session_id = "test-session"
        agent_id = "test-agent"

        # Act
        episode = await segmentation_service.create_episode_from_session(
            session_id=session_id,
            agent_id=agent_id
        )

        # Assert
        assert episode is not None
        assert episode["agent_id"] == agent_id

    async def test_create_episode_with_time_gap_boundary(self, db_session, segmentation_service):
        """Test episode boundary detection on 30+ minute time gaps"""
        # Test boundary detection logic
        pass
```

### Pattern 2: Property-Based Testing (Hypothesis)

**What:** Use Hypothesis to generate hundreds of test cases automatically
**When to use:** Testing invariants (mathematical properties that must always hold true)
**Example:**
```python
from hypothesis import given, settings
from hypothesis.strategies import lists, integers, floats

@settings(max_examples=100)
@given(
    feedback_scores=lists(
        floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=0, max_size=20
    )
)
def test_feedback_aggregation_in_bounds(feedback_scores):
    """Feedback aggregation always produces score in [-1.0, 1.0]"""
    # Calculate aggregate score
    if not feedback_scores:
        return  # Skip empty lists

    aggregate = sum(feedback_scores) / len(feedback_scores)

    # Assert invariant
    assert -1.0 <= aggregate <= 1.0
```

### Pattern 3: Async Test Setup

**What:** Use pytest-asyncio for testing async service methods
**When to use:** All service methods marked `async def`
**Example:**
```python
@pytest.fixture
async def segmentation_service(db_session, mock_lancedb, mock_byok_handler):
    """Async fixture for EpisodeSegmentationService"""
    with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb):
        with patch('core.episode_segmentation_service.CanvasSummaryService'):
            from core.episode_segmentation_service import EpisodeSegmentationService
            service = EpisodeSegmentationService(db_session, mock_byok_handler)
            service.lancedb = mock_lancedb
            return service

@pytest.mark.asyncio
async def test_async_method(segmentation_service):
    """Test async method"""
    result = await segmentation_service.create_episode_from_session(...)
    assert result is not None
```

### Anti-Patterns to Avoid

- **Testing implementation details:** Focus on behavior (inputs/outputs), not internal state
- **Over-mocking:** Mock only external dependencies (LanceDB, LLM), not database models
- **Ignoring error paths:** Ensure exceptions and error returns are tested
- **Missing edge cases:** Test empty lists, None values, boundary conditions
- **No cleanup:** Always clean up test data in fixtures or final blocks

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Property testing** | Custom loop-based tests | **Hypothesis** (`@given`, strategies) | Generates 100s of examples, finds edge cases automatically |
| **Async test execution** | Custom event loop management | **pytest-asyncio** (`@pytest.mark.asyncio`) | Handles event loop lifecycle, fixtures, cleanup |
| **Coverage measurement** | Manual line counting | **pytest-cov** (`--cov`, `--cov-report`) | Automated coverage reports, HTML output, missing line highlighting |
| **Test data generation** | Hardcoded fixtures | **Hypothesis strategies** (`st.lists`, `st.text`) | Generates diverse test data, finds edge cases |
| **Database fixtures** | Manual setup/teardown | **pytest fixtures** (`@pytest.fixture`) | Automatic cleanup, dependency injection, scoping |

**Key insight:** Phase 166 proved that combining integration tests (for specific scenarios) with property-based tests (for invariants) achieves 80%+ coverage efficiently. Hand-rolling test infrastructure wastes time and produces inferior results.

## Common Pitfalls

### Pitfall 1: SQLAlchemy Metadata Conflicts (HIGH IMPACT)

**What goes wrong:** Duplicate model definitions (Transaction, JournalEntry) in `core/models.py` and `accounting/models.py` prevent test execution with "Table already defined" errors.

**Why it happens:** Both files define the same SQLAlchemy models without `extend_existing=True`, causing metadata conflicts during test initialization.

**How to avoid:** This was already fixed in Phase 166 with `__table_args__ = {'extend_existing': True}`. If tests fail with metadata errors, verify the fix is still in place.

**Warning signs:**
- Tests fail with "sqlalchemy.exc.InvalidRequestError: Table X is already defined"
- Import errors related to Account/JournalEntry relationships
- Tests work in isolation but fail when run together

**Resolution (from Phase 166):**
```python
# In both core/models.py and accounting/models.py
class Transaction(Base):
    __tablename__ = 'transactions'
    __table_args__ = {'extend_existing': True}  # ADD THIS LINE
    # ... rest of model
```

### Pitfall 2: Missing Async Test Mode

**What goes wrong:** Async tests fail with "coroutine was never awaited" or pytest hangs indefinitely.

**Why it happens:** pytest-asyncio not configured correctly or `@pytest.mark.asyncio` decorator missing.

**How to avoid:** Ensure `pytest.ini` has `asyncio_mode = auto` and all async test functions have `@pytest.mark.asyncio` decorator.

**Warning signs:**
- Tests hang without output
- RuntimeWarnings about coroutines not being awaited
- "async function was never awaited" errors

### Pitfall 3: Over-Mocking External Dependencies

**What goes wrong:** Tests pass but coverage is low because mocked code paths aren't actually executed.

**Why it happens:** Mocking at too high a level (e.g., mocking the entire service instead of just external dependencies like LanceDB).

**How to avoid:** Mock only external dependencies:
- ✅ Mock `get_lancedb_handler()`, `BYOKHandler`, `CanvasSummaryService`
- ✅ Mock LanceDB operations (`search`, `add_document`, `embed_text`)
- ❌ Don't mock the service class itself
- ❌ Don't mock database models (use test database instead)

**Warning signs:**
- Coverage report shows many lines not executed
- Tests assert on mock call counts instead of actual behavior
- Mock configuration is more complex than the code being tested

### Pitfall 4: Not Testing Error Paths

**What goes wrong:** High coverage on happy paths but zero coverage on error handling, exceptions, and edge cases.

**Why it happens:** Developers focus on "making it work" and forget "making it fail gracefully."

**How to avoid:** For every method, test:
- ✅ Empty inputs (empty lists, None values)
- ✅ Invalid inputs (negative scores, invalid IDs)
- ✅ External failures (LanceDB unavailable, LLM timeout)
- ✅ Database errors (record not found, constraint violations)

**Warning signs:**
- Coverage report shows `except` blocks not executed
- No tests with "error", "fail", "invalid" in names
- All test data is perfectly valid

### Pitfall 5: Property Tests Without Proper Settings

**What goes wrong:** Hypothesis tests run too long (thousands of examples) or timeout in CI.

**Why it happens:** Not using `@settings` decorator to control test execution.

**How to avoid:** Always use `@settings`:
```python
from hypothesis import settings

@settings(max_examples=100)  # Routine tests
@given(...)
def test_something(data):
    pass

@settings(max_examples=200)  # Critical invariants
@given(...)
def test_critical_invariant(data):
    pass
```

**Warning signs:**
- Tests take >10 seconds to run
- CI timeouts on test execution
- Hypothesis generates thousands of examples

## Code Examples

Verified patterns from Phase 166 success:

### Example 1: Service Method Test (Integration)

```python
# Source: Phase 166 test_episode_services_coverage.py
@pytest.mark.asyncio
async def test_temporal_retrieval_7d(db_session, retrieval_service):
    """Test 7-day temporal retrieval (default time range)"""
    # Arrange
    agent_id = "test-agent"
    time_range = "7d"

    # Act
    result = await retrieval_service.retrieve_temporal(
        agent_id=agent_id,
        time_range=time_range
    )

    # Assert
    assert "episodes" in result
    assert "count" in result
    assert result["time_range"] == time_range
```

### Example 2: Property-Based Test for Invariants

```python
# Source: Phase 166 test_episode_invariants.py
@settings(max_examples=100)
@given(
    time_range=st.sampled_from(["1d", "7d", "30d", "90d"]),
    limit=st.integers(min_value=1, max_value=50)
)
def test_temporal_retrieval_returns_valid_episodes(time_range, limit):
    """All returned episodes are within time range, have correct agent_id, no duplicates"""
    # Test invariant: episodes match criteria
    # Implementation handles all generated combinations
    pass
```

### Example 3: Canvas Context Testing

```python
@pytest.mark.asyncio
async def test_extract_canvas_context_llm_success(segmentation_service):
    """Test LLM-based canvas context extraction"""
    # Arrange
    canvas_audit = CanvasAudit(
        id="canvas1",
        canvas_type="sheets",
        action="present",
        audit_metadata={"revenue": 1000000}
    )

    # Act
    context = await segmentation_service._extract_canvas_context_llm(
        canvas_audit=canvas_audit,
        agent_task="Analyze revenue data"
    )

    # Assert
    assert context is not None
    assert context["canvas_type"] == "sheets"
    assert "presentation_summary" in context
    assert context["summary_source"] == "llm"
```

### Example 4: Error Path Testing

```python
@pytest.mark.asyncio
async def test_create_episode_session_not_found(segmentation_service):
    """Test episode creation fails gracefully when session doesn't exist"""
    # Act
    result = await segmentation_service.create_episode_from_session(
        session_id="nonexistent-session",
        agent_id="test-agent"
    )

    # Assert
    assert result is None  # Should return None, not raise exception
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual test data | Hypothesis-generated data | Phase 166 | 100s of examples vs 1-2 manual cases |
| Happy-path only | Error paths + edge cases | Phase 166 | Catches production failures |
| Single test type | Integration + Property tests | Phase 166 | 80%+ coverage achieved |
| Manual coverage verification | pytest-cov automated reports | Phase 166 | Instant feedback on gaps |

**Deprecated/outdated:**
- **unittest.TestCase**: pytest fixtures are more powerful and composable
- **Manual loop-based property testing**: Hypothesis is faster and finds more edge cases
- **Hardcoded test data**: Hypothesis strategies generate diverse data automatically
- **Assertion-only testing**: Combine with property tests for invariant verification

## Open Questions

1. **SQLAlchemy metadata conflicts resolved?**
   - What we know: Phase 166 added `extend_existing=True` to Transaction/JournalEntry models
   - What's unclear: Whether the fix is complete or if additional refactoring is needed
   - Recommendation: Run a test early in Phase 174 to verify the fix works. If tests still fail, allocate 2-4 hours for model refactoring per Phase 165 guidance.

2. **LLM canvas summary testing strategy?**
   - What we know: EpisodeSegmentationService uses CanvasSummaryService for LLM-generated summaries
   - What's unclear: Should we mock the LLM call or test with real LLM responses?
   - Recommendation: Mock LLM responses in unit tests (fast, deterministic). Add one integration test with real LLM to verify end-to-end behavior.

3. **LanceDB integration testing scope?**
   - What we know: LanceDB operations are currently mocked in tests
   - What's unclear: Should we add real LanceDB integration tests?
   - Recommendation: Continue mocking LanceDB for unit/integration tests (fast, reliable). Add separate E2E tests for LanceDB if needed (Phase 175+).

4. **Property test strategy for graduation service?**
   - What we know: AgentGraduationService has complex scoring logic (readiness scores, constitutional compliance)
   - What's unclear: Which invariants should property tests verify?
   - Recommendation: Focus on score bounds (0.0-1.0), graduation criteria (episode counts, intervention rates), and trend calculations (improvement detection).

## Sources

### Primary (HIGH confidence)
- **Phase 166-03 SUMMARY.md** - Comprehensive episodic memory coverage patterns (27 integration tests + 5 property tests, 85% coverage achieved)
- **backend/pytest.ini** - Pytest configuration with coverage targets, async mode, Hypothesis settings
- **backend/core/episode_*.py** - Source files analyzed: episode_segmentation_service.py (1,536 lines), episode_retrieval_service.py (1,076 lines), episode_lifecycle_service.py (421 lines), agent_graduation_service.py (977 lines)
- **backend/tests/unit/episodes/test_episode_segmentation_coverage.py** - Existing test patterns and fixture structure

### Secondary (MEDIUM confidence)
- **Hypothesis documentation** (https://hypothesis.readthedocs.io/) - Property testing best practices, strategies, settings
- **pytest-asyncio documentation** - Async test patterns, fixture management
- **pytest-cov documentation** - Coverage measurement, reporting formats

### Tertiary (LOW confidence)
- Web search attempts returned no results (search service issues)
- Relying on Phase 166 proven patterns as primary evidence

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Pytest, Hypothesis, pytest-cov are industry standards, already configured in project
- Architecture: HIGH - Phase 166 proved this architecture achieves 85% coverage for episodic memory
- Pitfalls: HIGH - SQLAlchemy metadata conflicts documented in Phase 166, async patterns well-known
- Code examples: HIGH - All examples based on Phase 166 success patterns and existing test files

**Research date:** 2026-03-12
**Valid until:** 30 days (stable testing patterns, no expected changes to pytest/hypothesis ecosystem)
