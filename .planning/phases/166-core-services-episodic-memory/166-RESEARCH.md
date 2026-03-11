# Phase 166: Core Services Coverage (Episodic Memory) - Research

**Researched:** 2026-03-11
**Domain:** Python test coverage, episodic memory services, property-based testing
**Confidence:** HIGH

## Summary

Phase 166 focuses on achieving **80%+ line coverage** on three episodic memory services: `EpisodeSegmentationService` (1,548 lines), `EpisodeRetrievalService` (1,076 lines), and `EpisodeLifecycleService` (421 lines). These services implement AI agent episodic memory with time-based segmentation, semantic retrieval, and lifecycle management (decay, consolidation, archival).

**Key insight:** Phase 162 achieved **79.2% coverage** on episode services but with gaps: 27 failing tests (57 total failures), service code incompatibility with CanvasAudit schema, and incomplete testing of edge cases in segmentation boundaries. Phase 166 must build on Phase 162's test infrastructure while addressing remaining gaps and achieving the 80% target.

**Primary recommendation:** Follow Phase 165's proven three-tier testing strategy: (1) Integration tests with mocked LanceDB for algorithm coverage, (2) Property-based tests with Hypothesis for invariants (time gap >30min exclusive, semantic similarity thresholds, decay formula bounds), (3) Coverage measurement scripts with actual line coverage from coverage.py JSON output (not service-level estimates). **Critical:** Run tests in isolated mode to avoid SQLAlchemy metadata conflicts identified in Phase 165.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 7.4+ | Test framework | Industry standard for Python testing, fixtures, parametrization |
| coverage.py | 7.0+ | Actual line coverage measurement | Official Python coverage tool, produces JSON for parsing |
| Hypothesis | 6.92+ | Property-based testing | Standard Python PBT library, integrates with pytest |
| pytest-asyncio | 0.21+ | Async test support | Required for testing async service methods |
| SQLAlchemy | 2.0+ | Database mocking | ORM for models, Session for test fixtures |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock | 3.11+ | Mock LanceDB, LLM handlers | Mock external dependencies to test business logic |
| pytest-cov | 4.1+ | Coverage plugin for pytest | Enable --cov flags for pytest integration |
| faker | 19.0+ | Test data generation | Generate realistic test messages, sessions |
| freezegun | 1.2+ | Time freezing | Test time-based segmentation with deterministic timestamps |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hypothesis | pytest-parametrize | Hypothesis generates 200+ examples automatically, parametrize requires manual test cases |
| unittest.mock | pytest-mock | pytest-mock provides cleaner fixture API, but unittest.mock is built-in |
| coverage.py | pytest-cov only | coverage.py provides JSON output for programmatic threshold checking |

**Installation:**
```bash
# Already installed in backend/
pip install pytest pytest-cov pytest-asyncio hypothesis faker freezegun
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── integration/services/
│   └── test_episode_services_coverage_episodic.py  # Integration tests (300+ lines)
├── unit/episodes/
│   ├── test_episode_segmentation_coverage.py  # Existing from Phase 162
│   ├── test_episode_retrieval_coverage.py  # Existing from Phase 162
│   └── test_episode_lifecycle_coverage.py  # Existing from Phase 162
├── property_tests/episodes/
│   ├── test_episode_segmentation_invariants.py  # Existing (Hypothesis)
│   ├── test_episode_retrieval_invariants.py  # Existing (Hypothesis)
│   └── test_episode_lifecycle_invariants.py  # Existing (Hypothesis)
└── scripts/
    └── measure_phase_166_coverage.py  # Coverage measurement script
```

### Pattern 1: Integration Tests with Mocked LanceDB

**What:** Test episode segmentation/retrieval algorithms with mocked LanceDB and LLM handlers to focus on business logic without external dependencies.

**When to use:** Testing segmentation boundary detection, retrieval mode logic, lifecycle operations (decay, consolidation).

**Example:**
```python
# Source: Phase 162 test_episode_services_coverage.py
@pytest.fixture
def segmentation_service_mocked(db_session, mock_lancedb_embeddings):
    """EpisodeSegmentationService with mocked LanceDB."""
    with patch('core.episode_segmentation_service.get_lancedb_handler') as mock_get_db:
        mock_get_db.return_value = mock_lancedb_embeddings
        with patch('core.episode_segmentation_service.BYOKHandler'):
            service = EpisodeSegmentationService(db_session)
            yield service

def test_detect_time_gaps(self, segmentation_service_mocked, test_messages):
    """
    Test detection of time gaps >30 minutes between messages.

    Verifies:
    - Time gaps >30min trigger boundary detection (exclusive: > not >=)
    - Boundary index is correct (message after gap)
    - Gap duration is calculated accurately
    """
    detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)
    boundaries = detector.detect_time_gap(test_messages)

    # Should detect 2 time gaps:
    # 1. After message 1 (45min - 10min = 35min gap)
    # 2. After message 3 (90min - 50min = 40min gap)
    assert len(boundaries) == 2
    assert 2 in boundaries  # Index of message after first gap
    assert 4 in boundaries  # Index of message after second gap
```

### Pattern 2: Property-Based Tests with Hypothesis

**What:** Use Hypothesis @given decorator to test invariants across 200+ automatically generated examples.

**When to use:** Testing mathematical invariants (time gap >30min exclusive, decay score bounds [0.0, 1.0], semantic similarity thresholds).

**Example:**
```python
# Source: Phase 162 test_episode_segmentation_invariants.py
from hypothesis import given, settings, example
from hypothesis.strategies import integers, timedeltas

@settings(max_examples=200)  # Memory integrity invariant
@example(gap_minutes=30, threshold_minutes=30)  # Boundary: exactly threshold
@example(gap_minutes=31, threshold_minutes=30)  # Boundary: just over
@given(
    gap_minutes=integers(min_value=0, max_value=500),
    threshold_minutes=integers(min_value=1, max_value=120)
)
def test_time_gap_exclusive_boundary(self, gap_minutes, threshold_minutes):
    """
    INVARIANT: Time gap detection is EXCLUSIVE (> threshold, not >=).

    Gap of exactly threshold minutes does NOT trigger new segment.
    Gap of threshold+1 minutes DOES trigger new segment.

    VALIDATED_BUG: Inclusive boundary (>=) caused incorrect segmentation.
    Fixed by changing to exclusive (>) for proper episode separation.
    """
    # Simulate gap detection logic
    triggers_new_segment = gap_minutes > threshold_minutes

    # Boundary case: exactly threshold should NOT trigger
    if gap_minutes == threshold_minutes:
        assert not triggers_new_segment, \
            f"Gap of {gap_minutes}min == threshold {threshold_minutes}min should NOT trigger"

    # Just over threshold should trigger
    if gap_minutes == threshold_minutes + 1:
        assert triggers_new_segment, \
            f"Gap of {gap_minutes}min > threshold {threshold_minutes}min should trigger"
```

### Pattern 3: Async Service Testing with AsyncMock

**What:** Test async service methods (decay_old_episodes, consolidate_similar_episodes) using AsyncMock for database operations.

**When to use:** Testing EpisodeLifecycleService async methods that interact with LanceDB and PostgreSQL.

**Example:**
```python
# Source: Phase 162 test_episode_lifecycle_coverage.py
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_decay_old_episodes_applies_formula(self, db_session):
    """
    Test decay formula: decay_score = max(0, 1 - (days_old / 180))

    Verifies:
    - Decay score decreases linearly from 1.0 to 0.0 over 180 days
    - Episodes older than 180 days are archived
    - Decay score never goes below 0.0
    """
    # Create episode 90 days old
    episode = AgentEpisode(
        id=str(uuid4()),
        agent_id="agent_123",
        started_at=datetime.now() - timedelta(days=90),
        decay_score=1.0,
        status="active"
    )
    db_session.add(episode)
    db_session.commit()

    service = EpisodeLifecycleService(db_session)
    result = await service.decay_old_episodes(days_threshold=90)

    # Verify decay formula: 1 - (90/180) = 0.5
    db_session.refresh(episode)
    assert episode.decay_score == 0.5, \
        f"Decay score should be 0.5 for 90-day-old episode, got {episode.decay_score}"
    assert result["affected"] == 1
```

### Pattern 4: Coverage Measurement Script

**What:** Python script to run pytest with --cov flags, parse coverage.json, and check if actual line coverage meets 80% target.

**When to use:** Automating coverage measurement for verification, generating JSON reports for trend tracking.

**Example:**
```python
# Source: Phase 165 measure_phase_165_coverage.py
#!/usr/bin/env python3
"""Coverage measurement script for Phase 166: Episodic Memory Services"""
import subprocess
import json
from pathlib import Path

TARGET_LINE_COVERAGE = 80.0

SERVICES = [
    "core.episode_segmentation_service",
    "core.episode_retrieval_service",
    "core.episode_lifecycle_service",
]

TEST_FILES = [
    "tests/integration/services/test_episode_services_coverage_episodic.py",
    "tests/unit/episodes/test_episode_segmentation_coverage.py",
    "tests/unit/episodes/test_episode_retrieval_coverage.py",
    "tests/unit/episodes/test_episode_lifecycle_coverage.py",
    "tests/property_tests/episodes/test_episode_segmentation_invariants.py",
    "tests/property_tests/episodes/test_episode_retrieval_invariants.py",
    "tests/property_tests/episodes/test_episode_lifecycle_invariants.py",
]

def run_coverage_measurement():
    """Run pytest with coverage and generate report."""
    cmd = [
        "pytest",
    ] + TEST_FILES + [
        "--cov", "core.episode_segmentation_service",
        "--cov", "core.episode_retrieval_service",
        "--cov", "core.episode_lifecycle_service",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-report=json:tests/coverage_reports/metrics/backend_phase_166_episodic.json",
        "-v"
    ]

    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent.parent)
    return result.returncode

def check_coverage_thresholds():
    """Check if coverage meets 80% target."""
    report_path = "tests/coverage_reports/metrics/backend_phase_166_episodic.json"

    with open(report_path) as f:
        report = json.load(f)

    # Check individual files
    for filename, file_data in report["files"].items():
        if any(s in filename for s in ["episode_segmentation", "episode_retrieval", "episode_lifecycle"]):
            line_pct = file_data["summary"]["percent_covered"]
            print(f"{filename}: {line_pct:.1f}%")

            if line_pct < TARGET_LINE_COVERAGE:
                print(f"✗ FAILED: {line_pct:.1f}% < {TARGET_LINE_COVERAGE}% target")
                return False

    print(f"✓ PASSED: All episodic memory services >= {TARGET_LINE_COVERAGE}%")
    return True
```

### Anti-Patterns to Avoid

- **Service-level coverage estimates:** Don't aggregate boolean coverage per service. Use actual line coverage from coverage.py JSON (line_covered / num_statements).
- **Testing without branch coverage:** Don't omit --cov-branch flag. Branch coverage reveals missing conditional paths.
- **Combined test execution with SQLAlchemy conflicts:** Phase 165 identified SQLAlchemy metadata conflicts (duplicate model definitions). Run episodic memory tests in isolation to avoid import errors.
- **Testing service code incompatibility as test bugs:** Phase 162 identified 22 failing tests due to service code expecting CanvasAudit fields that don't exist (canvas_type, session_id). These are service code bugs, not test bugs.
- **Using time.sleep() for time-based tests:** Don't use sleep() for time gap detection. Use freezegun.freeze_time() for deterministic timestamps.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Property-based testing framework | Custom random test generators | Hypothesis @given decorator | Hypothesis provides shrinking, reproducibility, and 200+ examples automatically |
| Coverage calculation | Manual line counting | coverage.py JSON output | coverage.py is the standard, produces accurate line/branch metrics |
| Async test mocking | Custom async mock classes | unittest.mock.AsyncMock | AsyncMock handles coroutine scheduling, await semantics |
| Test data generation | Manual message/session creation | faker + pytest fixtures | Faker provides realistic names, emails, text for test data |

**Key insight:** Phase 162 already created comprehensive test infrastructure (180 tests, 79.2% coverage). Phase 166 should extend existing tests rather than rebuilding from scratch. Focus on gaps: (1) Fix 27 failing tests due to CanvasAudit schema incompatibility, (2) Add edge case tests for segmentation boundaries, (3) Add property tests for decay formula invariants.

## Common Pitfalls

### Pitfall 1: SQLAlchemy Metadata Conflicts in Combined Execution

**What goes wrong:** Running episodic memory tests with other backend tests causes SQLAlchemy import errors: "SAWarning: duplicate class name for Artifact", "unresolvable table cycles". This prevents combined test execution and reduces measured coverage.

**Why it happens:** Duplicate model definitions in `core/models.py` and `accounting/models.py` create metadata conflicts when both modules are imported.

**How to avoid:** Run episodic memory tests in isolation using pytest path selectors. Don't run full backend test suite (pytest tests/) until duplicate models are refactored.

**Example:**
```bash
# WRONG: Runs all tests, triggers SQLAlchemy conflicts
pytest backend/tests/ --cov=backend

# CORRECT: Run episodic memory tests in isolation
pytest backend/tests/integration/services/test_episode_services_coverage_episodic.py \
       backend/tests/unit/episodes/ \
       backend/tests/property_tests/episodes/ \
       --cov=core.episode_segmentation_service \
       --cov=core.episode_retrieval_service \
       --cov=core.episode_lifecycle_service
```

**Warning signs:** Test run shows "SAWarning" messages, import errors for models, or coverage drops from 80% to 45% when running combined suite.

### Pitfall 2: Service Code Incompatibility with CanvasAudit Schema

**What goes wrong:** 22 retrieval and segmentation tests fail because service code tries to access CanvasAudit fields that don't exist in current schema (canvas_type, component_type, session_id). Tests are blamed for failures, but root cause is service code expecting different schema.

**Why it happens:** CanvasAudit schema stores data in `details_json` field, but service code was written to expect flat columns. Phase 162 added EpisodeSegment.canvas_context and Episode.supervision fields, but didn't update service code to match.

**How to avoid:** Check service code for field access patterns before writing tests. Use `getattr(canvas_audit, 'field_name', default)` with fallback for optional fields. Document schema mismatches as technical debt.

**Example:**
```python
# WRONG: Service code expects non-existent field
canvas_type = canvas_audit.canvas_type  # Fails: field doesn't exist

# CORRECT: Extract from details_json or use getattr fallback
canvas_type = getattr(canvas_audit, 'canvas_type', None)
if canvas_type is None and canvas_audit.details_json:
    canvas_type = canvas_audit.details_json.get('canvas_type')
```

**Warning signs:** Test fixtures fail with AttributeError on model field access, service code references fields not in schema definition.

### Pitfall 3: Testing Inclusive Time Boundaries Instead of Exclusive

**What goes wrong:** Time gap tests fail because they expect `>=` threshold to trigger new segment, but service code uses `>` (exclusive). Gap of exactly 30 minutes should NOT trigger new segment according to specification.

**Why it happens:** Time gap specification says "gap > 30min triggers new episode", but tests written with inclusive boundary (`>=`) by mistake.

**How to avoid:** Document boundary conditions explicitly in test docstrings. Use Hypothesis @example decorators to test boundary cases (exactly 30min, 30min 1sec).

**Example:**
```python
@example(gap_minutes=30, threshold_minutes=30)  # Boundary: exactly threshold
@example(gap_minutes=31, threshold_minutes=30)  # Boundary: just over
@given(gap_minutes=integers(min_value=0, max_value=500),
       threshold_minutes=integers(min_value=1, max_value=120))
def test_time_gap_exclusive_boundary(self, gap_minutes, threshold_minutes):
    """
    INVARIANT: Time gap detection is EXCLUSIVE (> threshold, not >=).

    Gap of exactly threshold minutes does NOT trigger new segment.
    Gap of threshold+1 minutes DOES trigger new segment.
    """
    triggers_new_segment = gap_minutes > threshold_minutes

    if gap_minutes == threshold_minutes:
        assert not triggers_new_segment, \
            f"Gap of {gap_minutes}min == threshold {threshold_minutes}min should NOT trigger"
```

**Warning signs:** Tests fail on exact boundary values, time-based segmentation creates incorrect number of episodes.

### Pitfall 4: Not Testing Async Methods with Proper Async/Await

**What goes wrong:** Tests for async service methods (decay_old_episodes, consolidate_similar_episodes) fail with "coroutine was never awaited" errors or don't actually execute async logic.

**Why it happens:** Forgetting to use `@pytest.mark.asyncio` decorator, or calling async methods without await, or using Mock instead of AsyncMock for async dependencies.

**How to avoid:** Always use `@pytest.mark.asyncio` decorator on async test methods. Use AsyncMock for mocked async dependencies. Await all async calls.

**Example:**
```python
# WRONG: Missing decorator, not awaited
def test_decay_old_episodes(self, db_session):
    service = EpisodeLifecycleService(db_session)
    result = service.decay_old_episodes(days_threshold=90)  # Returns coroutine

# CORRECT: Async decorator, awaited
@pytest.mark.asyncio
async def test_decay_old_episodes(self, db_session):
    service = EpisodeLifecycleService(db_session)
    result = await service.decay_old_episodes(days_threshold=90)
    assert result["affected"] >= 0
```

**Warning signs:** Test passes but doesn't execute service logic, coroutine warnings in pytest output, type errors about NoneType when expecting dict.

### Pitfall 5: Property Tests Without Shrinking Strategy

**What goes wrong:** Hypothesis property tests fail with complex 200-event examples, making debugging impossible. No minimal reproducing case provided.

**Why it happens:** Hypothesis tries to shrink failing examples to minimal case, but custom data structures (Episode, ChatMessage) don't implement shrinking strategy.

**How to avoid:** Use Hypothesis strategies for primitives (integers, timedeltas, text). Build complex objects from primitives in test. Add @example decorators with explicit failing cases.

**Example:**
```python
# WRONG: Custom Episode object without shrinking strategy
@given(episodes=st.lists(st.builds(Episode, ...)))  # Can't shrink

# CORRECT: Build episodes from primitives, test logic only
@given(
    num_events=st.integers(min_value=2, max_value=50),
    gap_minutes=st.integers(min_value=0, max_value=500)
)
@example(num_events=3, gap_minutes=30)  # Explicit boundary case
def test_time_gap_detection(self, num_events, gap_minutes):
    # Build test data from primitives
    events = self._build_events(num_events, gap_minutes)
    episodes = segment_events(events)
    assert len(episodes) == expected_count
```

**Warning signs:** Hypothesis fails with "Falsifying example" showing 50+ complex objects, no minimal reproducing case, test takes >10s to fail.

## Code Examples

Verified patterns from official sources:

### Mocking LanceDB for Segmentation Tests

```python
# Source: Phase 162 test_episode_services_coverage.py
@pytest.fixture
def mock_lancedb_embeddings():
    """Mock LanceDB handler for semantic similarity tests."""
    mock_db = Mock()
    mock_db.search.return_value = []  # No similar episodes by default

    # Mock embedding generation
    mock_db.embed.return_value = [0.1, 0.2, 0.3]  # Fake 384-dim vector

    return mock_db

@pytest.fixture
def segmentation_service_mocked(db_session, mock_lancedb_embeddings):
    """EpisodeSegmentationService with mocked LanceDB."""
    with patch('core.episode_segmentation_service.get_lancedb_handler') as mock_get_db:
        mock_get_db.return_value = mock_lancedb_embeddings
        with patch('core.episode_segmentation_service.BYOKHandler'):
            service = EpisodeSegmentationService(db_session)
            yield service
```

### Testing Four Retrieval Modes

```python
# Source: Phase 162 test_episode_retrieval_advanced.py
class TestEpisodeRetrievalModes:
    """Test all four retrieval modes: temporal, semantic, sequential, contextual."""

    async def test_retrieve_temporal(self, retrieval_service, test_episodes):
        """Time-based retrieval: 1d, 7d, 30d, 90d ranges."""
        result = await retrieval_service.retrieve_temporal(
            agent_id="agent_123",
            time_range="7d",
            limit=50
        )

        assert result["count"] <= 50
        assert all(e.started_at >= datetime.now() - timedelta(days=7)
                   for e in result["episodes"])

    async def test_retrieve_semantic(self, retrieval_service, test_episodes):
        """Vector similarity search using LanceDB."""
        result = await retrieval_service.retrieve_semantic(
            agent_id="agent_123",
            query_text="machine learning experiments",
            limit=10
        )

        assert result["retrieval_mode"] == "semantic"
        assert len(result["episodes"]) <= 10
        # Semantic retrieval uses LanceDB vector search

    async def test_retrieve_sequential(self, retrieval_service, test_episodes):
        """Full episode with all segments in chronological order."""
        result = await retrieval_service.retrieve_sequential(
            agent_id="agent_123",
            episode_id="episode_123"
        )

        assert result["retrieval_mode"] == "sequential"
        assert len(result["segments"]) > 0
        # Verify chronological order
        timestamps = [s.created_at for s in result["segments"]]
        assert timestamps == sorted(timestamps)

    async def test_retrieve_contextual(self, retrieval_service, test_episodes):
        """Hybrid score: temporal recency + semantic similarity + feedback boost."""
        result = await retrieval_service.retrieve_contextual(
            agent_id="agent_123",
            query_text="workflow optimization",
            time_range="30d",
            limit=20
        )

        assert result["retrieval_mode"] == "contextual"
        # Contextual retrieval combines signals
        assert "score" in result["episodes"][0]
```

### Testing Lifecycle Operations

```python
# Source: Phase 162 test_episode_lifecycle_coverage.py
class TestEpisodeLifecycle:
    """Test episode decay, consolidation, and archival."""

    @pytest.mark.asyncio
    async def test_decay_formula_bounds(self, db_session):
        """
        Test decay formula: decay_score = max(0, 1 - (days_old / 180))

        Invariants:
        - Decay score stays within [0.0, 1.0] bounds
        - Linear decrease from 1.0 to 0.0 over 180 days
        - Episodes >180 days are archived
        """
        service = EpisodeLifecycleService(db_session)

        # Create episodes at different ages
        episodes = [
            AgentEpisode(started_at=datetime.now() - timedelta(days=0), decay_score=1.0),
            AgentEpisode(started_at=datetime.now() - timedelta(days=90), decay_score=1.0),
            AgentEpisode(started_at=datetime.now() - timedelta(days=180), decay_score=1.0),
            AgentEpisode(started_at=datetime.now() - timedelta(days=200), decay_score=1.0),
        ]
        for ep in episodes:
            db_session.add(ep)
        db_session.commit()

        result = await service.decay_old_episodes(days_threshold=90)

        # Verify decay formula
        db_session.refresh(episodes[0])  # 0 days: decay_score = 1.0
        assert episodes[0].decay_score == 1.0

        db_session.refresh(episodes[1])  # 90 days: decay_score = 0.5
        assert episodes[1].decay_score == 0.5

        db_session.refresh(episodes[2])  # 180 days: decay_score = 0.0
        assert episodes[2].decay_score == 0.0

        db_session.refresh(episodes[3])  # 200 days: archived
        assert episodes[3].status == "archived"
        assert episodes[3].decay_score == 0.0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes(self, db_session):
        """
        Test consolidation: merge semantically similar episodes into parent.

        Verifies:
        - Episodes with similarity >0.85 are consolidated
        - consolidated_into field set to parent episode ID
        - Parent episode count increases
        """
        service = EpisodeLifecycleService(db_session)

        # Create similar episodes (same topic)
        parent = AgentEpisode(
            agent_id="agent_123",
            task_description="Python debugging session",
            status="completed"
        )
        db_session.add(parent)

        child1 = AgentEpisode(
            agent_id="agent_123",
            task_description="Python debugging session",
            status="completed",
            consolidated_into=None
        )
        db_session.add(child1)

        db_session.commit()

        result = await service.consolidate_similar_episodes(
            agent_id="agent_123",
            similarity_threshold=0.85
        )

        # Verify consolidation
        db_session.refresh(child1)
        assert child1.consolidated_into == parent.id
        assert result["consolidated"] >= 1
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Service-level coverage estimates (boolean per service) | Actual line coverage from coverage.py JSON | Phase 165 (Mar 2026) | Eliminates false confidence from 66pp gap (74.6% estimated vs 8.50% actual) |
| Manual test case generation for boundaries | Hypothesis property-based testing with 200+ examples | Phase 165 (Mar 2026) | Automatic edge case discovery, shrinking for minimal reproducing cases |
| Combined test execution (pytest tests/) | Isolated test execution per phase to avoid SQLAlchemy conflicts | Phase 165 (Mar 2026) | Avoids SQLAlchemy metadata conflicts, enables accurate coverage measurement |

**Deprecated/outdated:**
- **Service-level coverage aggregation:** Phase 162 used aggregated percentages (79.2% for episode services) which masked individual file gaps. Phase 165 switched to actual line coverage per file from coverage.py JSON.
- **Boundary testing with pytest-parametrize only:** Hypothesis provides better coverage of edge cases with 200+ auto-generated examples. Use @example decorators for explicit boundary cases.

## Open Questions

1. **CanvasAudit Schema Incompatibility Resolution**
   - What we know: Service code expects canvas_type, session_id fields but current schema uses details_json. 22 tests failing due to this mismatch.
   - What's unclear: Should Phase 166 (a) update service code to extract from details_json, (b) add columns to CanvasAudit schema, (c) mark tests as xfailed and defer schema fix?
   - Recommendation: Check if Phase 166 goal includes service code fixes. If yes, option (a) update service code. If no, option (c) xfail tests with issue reference.

2. **SQLAlchemy Metadata Conflicts**
   - What we know: Duplicate model definitions (AgentEpisode in core/models.py and accounting/models.py) cause combined test execution failures.
   - What's unclear: Should Phase 166 wait for model refactoring before starting, or proceed with isolated test execution?
   - Recommendation: Proceed with isolated test execution (follow Phase 165 pattern). Flag model refactoring as technical debt for separate phase.

3. **Baseline Coverage for Episodic Memory Services**
   - What we know: Phase 162 achieved 79.2% combined coverage (segmentation 79.5%, retrieval 83.4%, lifecycle 70.1%).
   - What's unclear: What is current baseline after Phase 165 changes (SQLAlchemy fixes, governance service updates)? Have episodic memory services been affected?
   - Recommendation: Run baseline coverage measurement before starting Phase 166 tests. Use `measure_phase_166_coverage.py --baseline` flag.

## Sources

### Primary (HIGH confidence)

- **Phase 162 Final Verification:** `.planning/phases/162-episode-service-comprehensive-testing/162-FINAL-VERIFICATION.md` - Episode service coverage details (79.2% combined, 180 tests created)
- **Phase 165 Verification:** `.planning/phases/165-core-services-governance-llm/165-VERIFICATION.md` - SQLAlchemy metadata conflicts, isolated test execution pattern
- **Coverage Guide:** `backend/docs/COVERAGE_GUIDE.md` - Actual line coverage methodology, coverage.py configuration
- **Coverage Baseline v5.0:** `backend/tests/coverage_reports/COVERAGE_BASELINE_v5.0.md` - Baseline: 8.25% segmentation, 9.03% retrieval, lifecycle not measured
- **Service Source Code:** `backend/core/episode_segmentation_service.py` (1,548 lines), `backend/core/episode_retrieval_service.py` (1,076 lines), `backend/core/episode_lifecycle_service.py` (421 lines)
- **Existing Tests:** `backend/tests/unit/episodes/`, `backend/tests/property_tests/episodes/` - Phase 162 test infrastructure (180 tests)
- **Hypothesis Documentation:** https://hypothesis.readthedocs.io/en/latest/ - @given decorator, strategies, settings
- **coverage.py Documentation:** https://coverage.readthedocs.io/en/7.4.0/ - JSON output format, line/branch coverage

### Secondary (MEDIUM confidence)

- **Episodic Memory Implementation:** `docs/EPISODIC_MEMORY_IMPLEMENTATION.md` - Service architecture, retrieval modes, lifecycle operations
- **Property Testing Patterns:** `backend/tests/property_tests/governance/test_governance_invariants_extended.py` - Hypothesis usage examples from Phase 165
- **Coverage Measurement Scripts:** `backend/tests/scripts/measure_phase_165_coverage.py` - Script template for Phase 166

### Tertiary (LOW confidence)

- None. All findings verified against primary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest, coverage.py, Hypothesis are industry standards, verified in Phase 165
- Architecture: HIGH - Phase 162 test patterns verified working (79.2% coverage), Phase 165 governance patterns (88% governance, 94% cognitive tier)
- Pitfalls: HIGH - SQLAlchemy conflicts documented in Phase 165, CanvasAudit schema issues documented in Phase 162

**Research date:** 2026-03-11
**Valid until:** 2026-04-10 (30 days - stable testing domain)

**Key assumptions:**
- Phase 162 test infrastructure is still valid (no breaking schema changes since Feb 2026)
- SQLAlchemy metadata conflicts from Phase 165 still exist (not yet resolved)
- Coverage baseline measured in Phase 162 (79.2%) is starting point for Phase 166
