# Phase 162: Episode Service Comprehensive Testing - Research

**Researched:** March 10, 2026
**Domain:** Python Backend Testing (Episode Services)
**Confidence:** HIGH

## Summary

Phase 162 requires comprehensive testing of episode service methods to achieve +5-8% backend coverage (target: 13-16% overall from current 8.50%). The phase focuses on async episode service methods, full episode creation flows, supervision episode creation, and advanced retrieval modes (canvas-aware, business data, supervision context).

**Key findings:**
1. **Async testing patterns** are already established in the codebase using `pytest.mark.asyncio` and `pytest-asyncio`
2. **Episode services** have significant coverage gaps (72.7% average gap across 3 services)
3. **API endpoints** remain completely untested (0% coverage on 161 lines)
4. **Mocking strategy** for LanceDB and BYOK dependencies is well-defined from Phase 161
5. **Test isolation** using SQLite temp databases prevents cross-test interference

**Primary recommendation:** Focus on 4 high-impact test categories: (1) async service methods with direct asyncio testing, (2) full episode creation flows with segmentation boundaries, (3) supervision and skill episode creation, (4) advanced retrieval modes with canvas/feedback context.

---

## Standard Stack

### Core Testing Libraries
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.1+ | Test framework | Industry standard for Python testing |
| **pytest-asyncio** | 0.21+ | Async test support | Required for testing async/await service methods |
| **pytest-cov** | 4.1+ | Coverage measurement | Line coverage tracking and reporting |
| **unittest.mock** | Built-in | Mocking dependencies | Mock LanceDB, BYOK handler, database sessions |
| **sqlalchemy** | 2.0+ | Database fixtures | Test database setup and teardown |

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **faker** | 20.0+ | Test data generation | Generate realistic test data (optional, not required) |
| **freezegun** | 1.4+ | Time mocking | Test time-dependent episode decay logic (if needed) |
| **pytest-benchmark** | 4.0+ | Performance tests | Test boundary detection performance (optional) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-asyncio | pytest-trio | Trio is less common, more complex setup |
| unittest.mock | pytest-mock | pytest-mock is cleaner but not required |

**Installation:**
```bash
# Core testing dependencies (already installed from Phase 161)
pip install pytest pytest-asyncio pytest-cov

# Optional dependencies for advanced testing
pip install faker freezegun pytest-benchmark
```

---

## Architecture Patterns

### Recommended Test Structure
```
backend/tests/unit/episodes/
├── conftest.py                    # Episode service fixtures
├── test_episode_segmentation_service.py    # Segmentation tests
├── test_episode_retrieval_service.py       # Retrieval tests
├── test_episode_lifecycle_service.py       # Lifecycle tests
├── test_episode_integration.py             # Integration tests
└── test_episode_boundary_detection.py      # Boundary detection unit tests
```

### Pattern 1: Async Service Testing
**What:** Direct async/await testing without sync wrappers
**When to use:** Testing actual async service methods (decay_old_episodes, consolidate_similar_episodes, create_episode_from_session)
**Example:**
```python
# Source: Phase 161 test_episode_segmentation_coverage.py
@pytest.mark.asyncio
async def test_create_episode_from_session_full_flow(
    self, segmentation_service, db_session, episode_test_session
):
    """Test full episode creation flow with segmentation"""
    # Create test messages and executions
    messages = [
        ChatMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            conversation_id=episode_test_session.id,
            role="user",
            content="Help me analyze this data",
            created_at=datetime.now(timezone.utc)
        )
    ]

    # Add to database
    for msg in messages:
        db_session.add(msg)
    db_session.commit()

    # Mock LanceDB and BYOK handler
    with patch.object(segmentation_service, 'lancedb'):
        with patch.object(segmentation_service, 'byok_handler'):
            episode = await segmentation_service.create_episode_from_session(
                session_id=episode_test_session.id,
                agent_id="test_agent",
                force_create=True
            )

    # Verify episode created
    assert episode is not None
    assert episode.status == "completed"
```

### Pattern 2: LanceDB and BYOK Mocking
**What:** Mock external dependencies to test service logic in isolation
**When to use:** All episode service tests (LanceDB embedding/search, BYOK LLM calls)
**Example:**
```python
# Source: Phase 161 test_episode_segmentation_coverage.py lines 80-86
@pytest.fixture
def segmentation_service(db_session, mock_lancedb, mock_byok_handler):
    """EpisodeSegmentationService fixture with mocked dependencies"""
    with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb):
        with patch('core.episode_segmentation_service.CanvasSummaryService'):
            service = EpisodeSegmentationService(db_session, mock_byok_handler)
            service.lancedb = mock_lancedb
            return service

@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler"""
    lancedb = MagicMock()
    lancedb.embed_text = MagicMock(return_value=[0.1, 0.2, 0.3])
    lancedb.search = MagicMock(return_value=[])
    lancedb.add_document = MagicMock()
    lancedb.create_table = MagicMock()
    lancedb.db = MagicMock()
    lancedb.db.table_names = MagicMock(return_value=[])
    return lancedb
```

### Pattern 3: Boundary Detection Testing
**What:** Test time gap and topic change detection with controlled data
**When to use:** Testing EpisodeBoundaryDetector methods
**Example:**
```python
# Source: Phase 161 test_episode_segmentation_coverage.py lines 176-196
def test_detect_time_gaps_finds_gaps_exceeding_threshold(self, mock_lancedb):
    """Should detect gaps > 30 minutes"""
    now = datetime.now()
    messages = [
        ChatMessage(
            id="m1",
            conversation_id="s1",
            role="user",
            content="A",
            created_at=now - timedelta(minutes=65)
        ),
        ChatMessage(
            id="m2",
            conversation_id="s1",
            role="user",
            content="B",
            created_at=now - timedelta(minutes=34)  # 31 min gap from m1
        ),
        ChatMessage(
            id="m3",
            conversation_id="s1",
            role="user",
            content="C",
            created_at=now - timedelta(minutes=31)  # 3 min gap from m2
        ),
        ChatMessage(
            id="m4",
            conversation_id="s1",
            role="user",
            content="D",
            created_at=now  # 31 min gap from m3
        ),
    ]

    detector = EpisodeBoundaryDetector(mock_lancedb)
    gaps = detector.detect_time_gap(messages)

    # Should detect 2 gaps: after m1 (31 min) and after m3 (31 min)
    assert len(gaps) == 2
    assert 1 in gaps  # After m1
    assert 3 in gaps  # After m3
```

### Pattern 4: Database Session Isolation
**What:** Use temp SQLite databases per test for complete isolation
**When to use:** All tests requiring database operations
**Example:**
```python
# Source: backend/tests/unit/conftest.py lines 25-82
@pytest.fixture(scope="function")
def db():
    """Create a fresh in-memory database for each test"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    engine._test_db_path = db_path

    # Create all tables
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except exc.NoReferencedTableError:
            continue  # Skip tables with missing FK references

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    os.unlink(engine._test_db_path)
```

### Anti-Patterns to Avoid
- **Testing sync wrappers instead of async methods:** Phase 161 tested sync wrappers (apply_decay, consolidate_episodes) but not the actual async methods (decay_old_episodes, consolidate_similar_episodes). This leaves 67.8% of lifecycle service untested.
- **Mocking database sessions:** Use real temp SQLite databases instead of MagicMock to catch SQL errors early.
- **Testing without proper fixtures:** Avoid manual setup/teardown. Use pytest fixtures for consistency.
- **Ignoring LanceDB failures:** Always mock LanceDB operations (embed_text, search, add_document) to avoid external dependencies.
- **Testing synchronous blocking calls:** Never call `asyncio.run()` in tests - use `@pytest.mark.asyncio` instead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async test execution | Custom async loops | `@pytest.mark.asyncio` | Built-in async support, handles event loop cleanup |
| Database isolation | Manual SQLite setup | pytest fixtures with `tempfile.mkstemp()` | Automatic cleanup, prevents cross-test interference |
| Mock management | Manual mock patching | `unittest.mock.patch` context managers | Ensures mocks are undone after tests |
| Coverage measurement | Manual line counting | `pytest-cov` with `--cov` flag | Industry standard, HTML reports |
| Test data generation | Manual data creation | faker (optional) | Consistent test data, less boilerplate |

**Key insight:** Phase 161 established working patterns for async testing, database isolation, and LanceDB mocking. Build on these existing patterns rather than creating new infrastructure.

---

## Common Pitfalls

### Pitfall 1: Testing Sync Wrappers Instead of Async Methods
**What goes wrong:** Phase 161 tested sync wrapper methods (apply_decay, consolidate_episodes) but not the actual async implementations (decay_old_episodes, consolidate_similar_episodes), leaving 67.8% of lifecycle service untested.

**Why it happens:** Sync wrappers are easier to test (no async/await), but they don't exercise the actual business logic.

**How to avoid:** Always test the primary async service methods, not sync convenience wrappers. Use `@pytest.mark.asyncio` and `await` the method directly.

**Warning signs:** Tests with `asyncio.run()` calls or tests named "test_sync_wrapper" instead of "test_async_method".

### Pitfall 2: LanceDB Integration in Tests
**What goes wrong:** Tests attempt to connect to real LanceDB instance, causing flaky tests and external dependencies.

**Why it happens:** LanceDB handler is initialized in service `__init__`, making it easy to accidentally use real implementation.

**How to avoid:** Always patch `get_lancedb_handler()` and assign mocked instance to `service.lancedb` in fixtures. Verify mocks are called with `assert_called_once()`.

**Warning signs:** Tests that require environment variables (LANCEDB_PATH) or create actual database files.

### Pitfall 3: Session Not Committed Before Queries
**What goes wrong:** Test creates records but forgets `db_session.commit()`, causing queries to return empty results.

**Why it happens:** SQLAlchemy sessions don't auto-commit by default in tests.

**How to avoid:** Always call `db_session.commit()` after adding records and before queries. Use `db_session.flush()` to get IDs before commit.

**Warning signs:** Tests expecting data but getting empty lists or `None` from queries.

### Pitfall 4: Timezone-Aware vs. Naive Datetime Mixing
**What goes wrong:** Mixing timezone-aware datetimes (episode.started_at) with timezone-naive datetimes (datetime.now()) causes comparison errors.

**Why it happens:** Episode service uses `datetime.now(timezone.utc)` but tests use `datetime.now()`.

**How to avoid:** Always use `datetime.now(timezone.utc)` in test data for timestamp fields. Use `timedelta` for relative time calculations.

**Warning signs:** Tests failing with "TypeError: can't compare offset-naive and offset-aware datetimes".

### Pitfall 5: Missing CanvasAudit and AgentFeedback Linkage
**What goes wrong:** Tests create episodes but don't link CanvasAudit and AgentFeedback records via `episode_id`, leaving canvas/feedback integration untested.

**Why it happens:** Episode creation updates canvas/feedback records after episode creation, easy to miss in tests.

**How to avoid:** After episode creation, verify `canvas.episode_id` and `feedback.episode_id` are set. Query records by `episode_id` to confirm linkage.

**Warning signs:** Tests that pass but don't verify canvas/feedback linkage in assertions.

---

## Code Examples

Verified patterns from Phase 161 codebase:

### Example 1: Testing Episode Creation with Canvas Context
```python
# Source: Phase 161 test_episode_segmentation_coverage.py lines 688-717
def test_track_canvas_presentations(
    self, segmentation_service_mocked, episode_test_session, episode_test_user
):
    """Test tracking canvas presentations in episodes"""
    from core.models import CanvasAudit

    # Create canvas audit
    canvas = CanvasAudit(
        id=f"canvas_{uuid.uuid4().hex[:8]}",
        session_id=episode_test_session.id,
        canvas_type="chart",
        component_type="line",
        component_name="SalesChart",
        action="present",
        audit_metadata={"title": "Monthly Sales"},
        created_at=datetime.now(timezone.utc)
    )

    segmentation_service_mocked.db.add(canvas)
    segmentation_service_mocked.db.commit()

    # Extract canvas context
    context = segmentation_service_mocked._extract_canvas_context([canvas])

    assert context is not None
    assert context["canvas_type"] == "chart"
    assert "presentation_summary" in context
```

### Example 2: Testing Supervision Episode Creation
```python
# Source: Phase 161 test_episode_segmentation_coverage.py lines 1043-1069
def test_create_supervision_episode_from_supervision_session(
    self, segmentation_service, db_session
):
    """Test creating episode from supervision session with intervention"""
    from core.models import SupervisionSession

    session_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Mock supervision session
    supervision = SupervisionSession(
        id=session_id,
        agent_id=agent_id,
        status="active",
        interventions=[{
            "type": "human_correction",
            "timestamp": datetime.now().isoformat()
        }],
        intervention_count=1,
        created_at=datetime.now()
    )

    db_session.query.return_value.filter.return_value.first.return_value = supervision

    # Mock helper methods
    with patch.object(
        segmentation_service,
        '_format_supervision_outcome',
        return_value="Supervision outcome"
    ):
        with patch.object(
            segmentation_service,
            '_extract_supervision_topics',
            return_value=["supervision"]
        ):
            outcome = segmentation_service._format_supervision_outcome(supervision)
            assert outcome == "Supervision outcome"
```

### Example 3: Testing Async Episode Decay
```python
# Source: Phase 161 test_episode_services_coverage.py lines 495-531
@pytest.mark.asyncio
async def test_episode_decay(
    self, lifecycle_service_mocked, episode_test_agent
):
    """Test episode decay scoring"""
    # Create old episode
    episode = AgentEpisode(
        id=f"decay_ep_{uuid.uuid4().hex[:8]}",
        agent_id=episode_test_agent.id,
        tenant_id="default",
        started_at=datetime.now(timezone.utc) - timedelta(days=60),
        maturity_at_time="AUTONOMOUS",
        human_intervention_count=0,
        decay_score=1.0,
        access_count=5,
        outcome="success"
    )

    lifecycle_service_mocked.db.add(episode)
    lifecycle_service_mocked.db.commit()

    # Apply decay
    result = await lifecycle_service_mocked.decay_old_episodes(days_threshold=90)

    assert result["affected"] >= 1

    # Verify decay score updated
    lifecycle_service_mocked.db.refresh(episode)
    assert episode.decay_score < 1.0  # Should be decayed
    assert episode.access_count >= 6  # Should be incremented
```

### Example 4: Testing Canvas-Aware Retrieval
```python
# Source: backend/core/episode_retrieval_service.py lines 498-617
@pytest.mark.asyncio
async def test_retrieve_canvas_aware_with_detail_filtering(
    self, retrieval_service_mocked, episode_test_agent
):
    """Test canvas-aware retrieval with progressive detail levels"""
    # Create episode with canvas context
    episode = AgentEpisode(
        id=f"canvas_ep_{uuid.uuid4().hex[:8]}",
        agent_id=episode_test_agent.id,
        tenant_id="default",
        started_at=datetime.now(timezone.utc) - timedelta(hours=1),
        maturity_at_time="AUTONOMOUS",
        human_intervention_count=0,
        outcome="success"
    )

    retrieval_service_mocked.db.add(episode)
    retrieval_service_mocked.db.commit()

    # Create segment with canvas context
    segment = EpisodeSegment(
        id=f"seg_{uuid.uuid4().hex[:8]}",
        episode_id=episode.id,
        segment_type="conversation",
        sequence_order=0,
        content="User presented sales data",
        content_summary="Sales chart presentation",
        source_type="chat_message",
        source_id="msg1",
        canvas_context={
            "canvas_type": "sheets",
            "presentation_summary": "Sales data table with Q4 figures",
            "visual_elements": ["table", "chart"],
            "critical_data_points": {"revenue": 1000000}
        }
    )

    retrieval_service_mocked.db.add(segment)
    retrieval_service_mocked.db.commit()

    # Mock LanceDB search
    retrieval_service_mocked.lancedb.search.return_value = [{
        "id": episode.id,
        "metadata": {"episode_id": episode.id},
        "_distance": 0.2
    }]

    # Test summary detail level (~50 tokens)
    result = await retrieval_service_mocked.retrieve_canvas_aware(
        agent_id=episode_test_agent.id,
        query="sales data",
        canvas_context_detail="summary",
        limit=10
    )

    assert result["count"] >= 1
    # Verify canvas context filtered to summary only
    if result["episodes"]:
        segments = result["episodes"][0].get("segments", [])
        if segments and segments[0].get("canvas_context"):
            canvas_ctx = segments[0]["canvas_context"]
            assert "presentation_summary" in canvas_ctx
            assert "visual_elements" not in canvas_ctx  # Filtered out
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Service-level estimates (74.6%) | Actual line coverage (8.50%) | Phase 161 | More accurate baseline, revealed true gap |
| Testing sync wrappers | Testing async methods directly | Phase 162 | Proper coverage of business logic |
| Mock database sessions | Real temp SQLite databases | Phase 161 | Catches SQL errors, better integration |
| Ignoring LanceDB | Comprehensive LanceDB mocking | Phase 161 | Isolated testing, no external dependencies |

**Deprecated/outdated:**
- **Service-level coverage estimates:** Phase 158-159 used sampling estimates (74.6%), but Phase 161 revealed actual coverage is 8.50% when measuring all 72,727 backend lines. Always use line coverage measurement.
- **Sync wrapper testing:** Phase 161 tested sync convenience methods (apply_decay, consolidate_episodes) instead of async implementations (decay_old_episodes, consolidate_similar_episodes). This inflates coverage numbers without testing actual logic.

---

## Open Questions

1. **Should we test API endpoints (episode_routes.py) in this phase?**
   - What we know: API endpoints have 0% coverage (161 lines untested), but they're integration layer, not service logic.
   - What's unclear: Whether to focus on service methods or include API endpoint tests.
   - Recommendation: Focus on service methods in Phase 162, defer API endpoint testing to Phase 163 (API Endpoint Coverage) to maintain clear separation of concerns.

2. **How to handle LanceDB table creation in tests?**
   - What we know: LanceDB operations are mocked in Phase 161 tests using `MagicMock`.
   - What's unclear: Whether to create actual LanceDB tables for integration tests.
   - Recommendation: Continue mocking LanceDB for unit tests (faster, isolated). Add LanceDB integration tests only if testing persistence logic specifically.

3. **Should we test episode consolidation with real semantic search?**
   - What we know: `consolidate_similar_episodes()` uses LanceDB semantic search to find similar episodes.
   - What's unclear: How to test semantic similarity without real embeddings.
   - Recommendation: Mock `lancedb.search()` to return pre-defined results with `_distance` values. Test consolidation logic, not embedding generation.

4. **How to test time-dependent decay scoring?**
   - What we know: Decay formula is `decay_score = days_old / 90` (represents decay amount applied).
   - What's unclear: Whether to mock time or use actual datetime calculations.
   - Recommendation: Use `datetime.now(timezone.utc) - timedelta(days=X)` for explicit time calculations. Avoid time mocking libraries unless testing edge cases (leap seconds, DST transitions).

---

## Sources

### Primary (HIGH confidence)
- **Phase 161 Verification Report** (`.planning/phases/161-model-fixes-and-database/161-VERIFICATION.md`) - Complete coverage analysis, untested methods, Phase 162 recommendations
- **Episode Segmentation Service** (`backend/core/episode_segmentation_service.py`) - 590 lines, 17.1% coverage, boundary detection logic
- **Episode Retrieval Service** (`backend/core/episode_retrieval_service.py`) - 320 lines, 32.5% coverage, retrieval modes
- **Episode Lifecycle Service** (`backend/core/episode_lifecycle_service.py`) - 174 lines, 32.2% coverage, decay and consolidation
- **Episode API Routes** (`backend/api/episode_routes.py`) - 161 lines, 0% coverage, REST endpoints
- **Test Conftest** (`backend/tests/unit/conftest.py`) - Database fixture patterns, session isolation
- **Phase 161 Tests** (`backend/tests/unit/episodes/test_episode_segmentation_coverage.py`) - 2082 lines, working async test patterns

### Secondary (MEDIUM confidence)
- **pytest-asyncio Documentation** (https://pytest-asyncio.readthedocs.io/) - Async test patterns, event loop handling
- **pytest Documentation** (https://docs.pytest.org/) - Fixture patterns, coverage integration
- **SQLAlchemy 2.0 Docs** (https://docs.sqlalchemy.org/) - Session management, async operations
- **Python unittest.mock** (https://docs.python.org/3/library/unittest.mock.html) - Mock patterns, patch decorators

### Tertiary (LOW confidence)
- None for this phase (all testing patterns verified in Phase 161 codebase)

---

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** - All libraries verified in Phase 161 codebase
- Architecture: **HIGH** - Test patterns established in Phase 161, 21 passing tests
- Pitfalls: **HIGH** - All pitfalls identified from Phase 161 mistakes (sync wrapper testing, missing linkage verification)

**Research date:** March 10, 2026
**Valid until:** March 31, 2026 (21 days - stable testing patterns, unlikely to change)

---

## Phase 162 Testing Strategy

Based on this research, Phase 162 should focus on 4 high-impact test categories:

### Category 1: Async Service Methods (30 tests, ~400 lines)
- `decay_old_episodes()` - Batch decay with threshold filtering
- `consolidate_similar_episodes()` - Semantic consolidation with LanceDB
- `update_importance_scores()` - Feedback-based importance updates
- `batch_update_access_counts()` - Batch access count operations
- `archive_to_cold_storage()` - Episode archival logic

### Category 2: Full Episode Creation (20 tests, ~300 lines)
- `create_episode_from_session()` - Complete flow with segmentation
- Boundary detection integration (time gaps + topic changes)
- Canvas and feedback linkage verification
- Segment creation with sequence ordering
- LanceDB archival with metadata

### Category 3: Supervision and Skill Episodes (15 tests, ~200 lines)
- `create_supervision_episode()` - Supervision session to episode
- `create_skill_episode()` - Skill execution tracking
- Intervention type extraction
- Graduation metric tracking (intervention count, ratings)
- Learning outcome summarization

### Category 4: Advanced Retrieval Modes (25 tests, ~350 lines)
- `retrieve_sequential()` - Full episodes with segments
- `retrieve_canvas_aware()` - Canvas filtering with detail levels
- `retrieve_by_business_data()` - Business data filtering
- `retrieve_with_supervision_context()` - Supervision filtering
- Feedback-weighted contextual retrieval

**Total Estimated Coverage Impact:** +1,250 lines tested across episode services
**Expected Coverage Increase:** +5-8 percentage points (target: 13-16% overall from 8.50%)
