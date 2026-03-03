# Phase 113: Episodic Memory Coverage - Research

**Researched:** 2026-03-01
**Domain:** Python test coverage expansion (pytest-cov)
**Confidence:** HIGH

## Summary

Phase 113 aims to achieve 60%+ coverage for three episodic memory services that are currently showing critically low coverage (8-10%) despite having passing tests. **Critical finding**: The coverage drop from Phase 101 (83%/61%/100%) to Phase 111 (23%/34%/60%) is **NOT a measurement methodology change** - these are actual uncovered lines that need tests.

The discrepancy stems from **which test files were measured**:
- Phase 101 measured coverage from Phase 101's new test files in `tests/unit/episodes/test_episode_*_coverage.py`
- Phase 111 measured coverage from **existing** test files (e.g., `tests/test_episode_segmentation.py`)
- The "coverage drop" is because Phase 111 reverted to measuring old, incomplete test suites

**Primary recommendation**: Write comprehensive tests for the 43 functions in `episode_segmentation_service.py`, 37 functions in `episode_retrieval_service.py`, and 7 functions in `episode_lifecycle_service.py` to reach 60% coverage. Follow Phase 112's proven pattern: fix model mismatches, add realistic test data, and test all execution paths.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 7.4.4+ | Test runner | Industry standard for Python testing |
| pytest-cov | 4.1.0+ | Coverage measurement | De facto standard for coverage reporting |
| pytest-asyncio | 0.21.0+ | Async test support | Required for testing async service methods |
| sqlalchemy | 2.0+ | Database mocking | Test models without real database |
| unittest.mock | stdlib | Mock dependencies | Python standard library |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-mock | 3.12.0+ | Mock fixtures | Cleaner mock API than unittest.mock |
| coverage.py | 7.4+ | Coverage backend | Used internally by pytest-cov |
| factory-boy | 3.3.0+ | Test data generation | EpisodeFactory exists in `/tests/factories/` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-cov | coverage.py CLI | pytest-cov integrates better with pytest discovery |
| unittest.mock | monkeypatch | More explicit but verbose for complex mocks |
| Factory Boy | Faker | Factory Boy maintains model relationships better |

**Installation:**
```bash
# All dependencies already installed in backend/
pip install pytest pytest-cov pytest-asyncio pytest-mock factory-boy
```

## Architecture Patterns

### Recommended Project Structure
```
backend/tests/unit/episodes/
├── test_episode_segmentation_coverage.py  # NEW: 30+ tests for segmentation
├── test_episode_retrieval_coverage.py    # NEW: 25+ tests for retrieval
├── test_episode_lifecycle_coverage.py    # NEW: 15+ tests for lifecycle
├── conftest.py                           # Shared fixtures
└── __init__.py
```

### Pattern 1: Three-Layer Test Organization
**What:** Organize tests by service layer (unit → integration → e2e)
**When to use:** Multi-service systems with clear boundaries
**Example:**
```python
# unit/episodes/test_episode_segmentation_coverage.py
class TestEpisodeBoundaryDetector:
    """Unit tests for boundary detection logic"""

    def test_detect_time_gap(self, detector):
        """Test time gap detection between messages"""
        # Arrange
        now = datetime.now()
        messages = [
            ChatMessage(id="1", created_at=now),
            ChatMessage(id="2", created_at=now + timedelta(minutes=45))  # Gap
        ]
        # Act
        gaps = detector.detect_time_gap(messages)
        # Assert
        assert len(gaps) == 1
```

### Pattern 2: Fixture Hierarchy
**What:** Compose fixtures from granular to complex
**When to use:** Tests requiring realistic test data
**Example:**
```python
# conftest.py
@pytest.fixture
def db_session():
    """Base mock session"""
    session = MagicMock(spec=Session)
    session.commit.return_value = None
    return session

@pytest.fixture
def mock_lancedb(db_session):
    """LanceDB with mock embedding"""
    handler = MagicMock()
    handler.embed_text = Mock(return_value=[0.1, 0.2, 0.3])
    return handler

@pytest.fixture
def segmentation_service(db_session, mock_lancedb):
    """Fully configured service"""
    return EpisodeSegmentationService(db_session)
```

### Pattern 3: Async Test Pattern
**What:** Use pytest-asyncio for async service methods
**When to use:** Testing service methods with `async def`
**Example:**
```python
@pytest.mark.asyncio
async def test_create_episode_from_session(segmentation_service, db_session):
    """Test episode creation from chat session"""
    # Arrange
    session = ChatSession(id=str(uuid.uuid4()), user_id="user1")
    db_session.query.return_value.filter.return_value.first.return_value = session

    # Act
    episode = await segmentation_service.create_episode_from_session(
        session_id=session.id,
        agent_id="agent1"
    )

    # Assert
    assert episode is not None
    assert episode.agent_id == "agent1"
```

### Anti-Patterns to Avoid
- **Mock-only tests without assertions**: Tests that mock everything and assert nothing
- **Database-dependent tests**: Tests requiring real PostgreSQL instead of mocks
- **God-object fixtures**: Fixtures that create entire database state
- **Fragile time assertions**: Tests asserting exact timestamps (use timedelta comparisons)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test data generation | Manual object creation | Factory Boy | EpisodeFactory already exists, handles relationships |
| Async mocking | Custom async mocks | pytest-asyncio | Handles event loop cleanup automatically |
| Coverage reporting | Custom coverage scripts | pytest-cov --cov-report | Standard format, CI integration |
| Mock verification | Manual call counting | Mock.assert_called_once_with() | Built-in, clear error messages |
| Database isolation | Manual transaction rollback | pytest fixtures with yield | Automatic cleanup, even on failure |

**Key insight:** The episode services already have extensive code (1500+ lines total). Writing comprehensive tests from scratch would take weeks. Use pytest's built-in features and existing factories to accelerate test development.

## Common Pitfalls

### Pitfall 1: Mock Configuration Mismatch
**What goes wrong:** Mock returns wrong type (e.g., `Mock()` instead of `MagicMock(spec=Session)`)
**Why it happens:** pytest fixtures don't match real object interfaces
**How to avoid:** Use `spec=` parameter to enforce interface compliance
**Warning signs:** `AttributeError: 'Mock' object has no attribute 'query'`

```python
# BAD
def db_session():
    return Mock()  # No spec, allows any attribute

# GOOD
def db_session():
    return MagicMock(spec=Session)  # Enforces Session interface
```

### Pitfall 2: Async Event Loop Issues
**What goes wrong:** `RuntimeError: This event loop is already closed`
**Why it happens:** Mixing async and sync test code without proper markers
**How to avoid:** Always use `@pytest.mark.asyncio` for async tests
**Warning signs:** Tests pass individually but fail in suite

### Pitfall 3: Database Session Not Committed
**What goes wrong:** Query returns None for objects added in test
**Why it happens:** Mock session doesn't persist objects across queries
**How to avoid:** Configure mock query chain to return added objects
**Warning signs:** `assert episode is not None` fails

```python
# BAD
session.query.return_value.filter.return_value.first.return_value = None  # Always None

# GOOD
session.query.return_value.filter.return_value.first.return_value = session  # Return self
session.add = Mock(side_effect=lambda obj: setattr(obj, 'id', str(uuid.uuid4())))
```

### Pitfall 4: Coverage Measured from Wrong Test Files
**What goes wrong:** Coverage report shows 8% despite 30 passing tests
**Why it happens:** pytest-cov measuring different test file than intended
**How to avoid:** Explicitly specify test file in coverage command
**Warning signs:** Coverage doesn't match test execution

```bash
# BAD - measures all tests
pytest --cov=core.episode_segmentation_service

# GOOD - measures specific test file
pytest tests/unit/episodes/test_episode_segmentation_coverage.py --cov=core.episode_segmentation_service
```

### Pitfall 5: Model Field Mismatches
**What goes wrong:** `TypeError: __init__() got an unexpected keyword argument 'workspace_id'`
**Why it happens:** Test uses old model schema (Phase 101 used ChatSession with workspace_id)
**How to avoid:** Verify model fields in `core/models.py` before writing tests
**Warning signs:** Tests fail with TypeError on model instantiation

```python
# WRONG (Phase 101 error)
ChatSession(id="x", workspace_id="default")  # Field doesn't exist

# CORRECT (Phase 112 fix)
ChatSession(id="x")  # No workspace_id field
```

## Code Examples

Verified patterns from Phase 112 success:

### Governance Coverage Achievement (82%+)
```python
# Source: backend/tests/unit/governance/test_agent_governance_coverage.py
class TestAgentGovernanceService:
    """Comprehensive governance tests"""

    def test_student_agent_cannot_execute_critical_actions(self, service, db_session):
        """STUDENT agents blocked from action_complexity >= 3"""
        # Arrange
        agent = AgentRegistry(id="student", status=AgentStatus.STUDENT)
        db_session.query.return_value.filter.return_value.first.return_value = agent

        # Act
        result = service.can_perform_action(
            agent_id="student",
            action_type="execute",
            action_complexity=3  # HIGH complexity
        )

        # Assert
        assert result["allowed"] is False
        assert "STUDENT" in result["reason"]
```

### Context Resolver Coverage (96%+)
```python
# Source: backend/tests/unit/governance/test_agent_context_resolver.py
class TestAgentContextResolver:
    """Agent context resolution with correct model usage"""

    def test_resolve_agent_from_session_with_cached_agent(self, resolver, db_session):
        """Resolve agent from session when agent already cached"""
        # Arrange
        session_id = str(uuid.uuid4())  # Unique ID prevents constraint violations
        session = ChatSession(id=session_id, user_id="user1", agent_id="agent1")
        db_session.query.return_value.filter.return_value.first.return_value = session

        # Act
        result = resolver.resolve_agent_from_session(session_id)

        # Assert
        assert result["agent_id"] == "agent1"
        assert result["source"] == "session"
```

### Cache Performance Coverage (62%+)
```python
# Source: backend/tests/unit/governance/test_governance_cache_performance.py
class TestGovernanceCache:
    """Cache performance and decorator tests"""

    def test_cached_governance_check_decorator(self, cache):
        """@cached_governance_check decorator caches results"""
        # Arrange
        call_count = 0

        @cache.cached_governance_check(ttl=60)
        def expensive_check(agent_id, action):
            nonlocal call_count
            call_count += 1
            return {"allowed": True}

        # Act - First call
        result1 = expensive_check("agent1", "read")

        # Assert - Called once
        assert call_count == 1

        # Act - Second call (should hit cache)
        result2 = expensive_check("agent1", "read")

        # Assert - Not called again
        assert call_count == 1  # Still 1, cache hit
        assert result2 == result1
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual coverage scripts | pytest-cov --cov-report | Phase 101 | Standardized reporting |
| Global test files | Module-specific test files | Phase 101 | Faster test execution |
| Mock everything | Real models with mock DB | Phase 112 | More realistic tests |
| Ad-hoc fixtures | Factory Boy factories | Phase 112 | Reusable test data |

**Deprecated/outdated:**
- **Phase 101 test files**: `tests/unit/episodes/test_episode_*_coverage.py` created but coverage not measured
- **Old test location**: `tests/test_episode_segmentation.py` (should be in `tests/unit/episodes/`)
- **Manual session IDs**: Using hardcoded IDs breaks UNIQUE constraints (use `uuid.uuid4()`)

## Open Questions

1. **Why is episode_segmentation_service.py so large (1503 lines)?**
   - What we know: File contains 43 functions with canvas integration, LLM summaries, supervision episodes, skill episodes
   - What's unclear: Should this be split into multiple services?
   - Recommendation: Keep monolithic for coverage target, refactor after 60% achieved

2. **Should we write tests for all 1500 lines or just reach 60%?**
   - What we know: 60% = ~900 lines need coverage
   - What's unclear: Which 900 lines are most critical?
   - Recommendation: Focus on public API methods first, private methods later

3. **How to handle LanceDB dependencies in tests?**
   - What we know: All 3 services depend on `get_lancedb_handler()`
   - What's unclear: Should we mock LanceDB or use test container?
   - Recommendation: Mock LanceDB handler (follow Phase 112 pattern)

4. **Canvas and feedback integration complexity**
   - What we know: Episodes link to CanvasAudit and AgentFeedback
   - What's unclear: How many test variations needed for canvas types?
   - Recommendation: Test 3 canvas types (generic, sheets, orchestration) + 1 feedback test

## Sources

### Primary (HIGH confidence)
- Phase 101 verification report - `/backend/tests/coverage_reports/PHASE_101_VERIFICATION.md` - Episode service coverage baseline
- Phase 112 verification report - `/.planning/phases/112-agent-governance-coverage/112-VERIFICATION.md` - Proven test patterns
- pytest-cov documentation - https://pytest-cov.readthedocs.io/ - Coverage measurement best practices
- pytest-asyncio documentation - https://pytest-asyncio.readthedocs.io/ - Async testing patterns

### Secondary (MEDIUM confidence)
- Episode service source code - `/backend/core/episode_*_service.py` - 43 functions identified
- Coverage baseline report - `/backend/tests/coverage_reports/COVERAGE_BASELINE_v5.0.md` - Current coverage: 8-10%
- Existing test files - `/backend/tests/unit/episodes/test_episode_*_coverage.py` - Test structure

### Tertiary (LOW confidence)
- None - All findings verified from primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest ecosystem is industry standard, versions verified from project
- Architecture: HIGH - Patterns proven in Phase 112 (96% coverage achieved)
- Pitfalls: HIGH - All pitfalls observed in Phase 101 failures, fixes verified in Phase 112

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (30 days - stable pytest ecosystem)

## Appendix: Episode Service Coverage Target Calculation

### episode_segmentation_service.py (1503 lines)
- Current coverage: 8.25% (124 lines)
- Target coverage: 60% (902 lines)
- Gap: 778 lines need tests
- Functions to test: 43 total
  - 15 public methods (create_episode_from_session, create_supervision_episode, create_skill_episode)
  - 28 private methods (_generate_title, _extract_topics, _format_messages, etc.)

### episode_retrieval_service.py (1034 lines)
- Current coverage: 9.03% (93 lines)
- Target coverage: 60% (620 lines)
- Gap: 527 lines need tests
- Functions to test: 37 total
  - 12 public methods (retrieve_temporal, retrieve_semantic, retrieve_sequential, retrieve_contextual, etc.)
  - 25 private methods (_log_access, _serialize_episode, _fetch_canvas_context, etc.)

### episode_lifecycle_service.py (251 lines)
- Current coverage: 59.69% (150 lines)
- Target coverage: 60% (151 lines)
- Gap: 1 line needs tests (almost there!)
- Functions to test: 7 total
  - 5 public methods (decay_old_episodes, consolidate_similar_episodes, archive_to_cold_storage, etc.)
  - 2 private methods (none - all public)

**Total effort estimate:**
- Segmentation: 30-40 tests needed (60% target)
- Retrieval: 25-30 tests needed (60% target)
- Lifecycle: 2-3 tests needed (already at 59.69%)
- **Total: 57-73 tests** to achieve 60% coverage across all 3 services
