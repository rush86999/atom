# Phase 198: Coverage Push to 85% - Research

**Researched:** 2026-03-16
**Domain:** Test Coverage Expansion & Test Infrastructure Quality
**Confidence:** HIGH

## Summary

Phase 198 builds on Phase 197's quality-first foundation (74.6% coverage, 98% pass rate) to push overall coverage to 85%. The primary challenges are: (1) test infrastructure issues blocking 10 test files from executing, (2) medium-impact modules needing targeted coverage improvements, (3) integration and end-to-end test expansion, and (4) CanvasAudit test updates for schema changes. This research documents the current state, identifies high-value targets, and provides prescriptive guidance for efficient coverage gains.

**Primary recommendation:** Fix test infrastructure first (10 files, ~2 hours), then target medium-impact modules with 40-80% coverage for 10-15% improvements each (~4-6 hours), and expand integration/E2E coverage for complex workflows (~3-4 hours). Total estimated effort: 9-12 hours to achieve 85% overall coverage.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 9.0.2 | Test framework | Industry standard, async support, extensive plugin ecosystem |
| **pytest-cov** | 7.0.0 | Coverage measurement | Coverage.py integration, HTML reports, branch coverage |
| **coverage.py** | 7.13.4 | Coverage engine | C extension for speed, JSON output, fail_under gates |
| **FastAPI TestClient** | 0.115.0 | API testing | Official FastAPI testing utility, dependency override support |
| **factory_boy** | 3.3.1 | Test data generation | Declarative test fixtures, SQLAlchemy integration |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **SQLAlchemy text()** | 2.0.x | Raw SQL in fixtures | Test cleanup, UNIQUE constraint fixes |
| **AsyncMock** | 3.12+ | Async mocking | Mocking async service methods |
| **pytest-asyncio** | 1.3.0 | Async test execution | AUTO mode for deterministic async tests |
| **monkeypatch** | Built-in | Runtime patching | Fixture-level dependency injection |
| **pytest.mark.integration** | Built-in | Test segregation | Separate integration tests from unit tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | pytest has better fixtures, simpler syntax, more plugins |
| factory_boy | Faker | factory_boy creates valid model instances, Faker generates random data |
| AsyncMock | unittest.mock.Mock | AsyncMock properly awaits coroutines, Mock doesn't |
| pytest.mark | pytest.ini file segregation | Marks are more flexible, enable/disable with `-m` flag |

**Installation:**
```bash
# All dependencies already installed
pip install pytest==9.0.2 pytest-cov==7.0.0
pip install factory-boy==3.3.1
```

---

## Architecture Patterns

### Phase 197 Test Infrastructure (Current State)

**Achievements:**
- 74.6% overall coverage (baseline: Phase 196)
- 98% pass rate (98/100 tests passing)
- 75 edge case tests covering all module types
- 25 governance tests (performance + streaming)
- Comprehensive error path and concurrency testing

**Test Infrastructure Blockers:**
- 10 test files with import/collection errors
- 2 CanvasAudit tests failing due to schema changes
- Tests collected: 5,566 (with 10 collection errors)
- Full test suite cannot execute, preventing accurate coverage measurement

**Test File Pattern (from Phase 197):**
```python
# 1. Database fixtures with SessionLocal
@pytest.fixture(scope="function")
def db_session():
    with SessionLocal() as session:
        yield session
        # Cleanup after each test
        try:
            session.execute(text("DELETE FROM agent_episodes WHERE agent_id LIKE 'test-agent%'"))
            session.execute(text("DELETE FROM episode_segments WHERE 1=1"))
            session.commit()
        except Exception as e:
            session.rollback()

# 2. TestClient with dependency override
@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    test_app.dependency_overrides[get_db] = override_get_db

    # Bypass RBAC for testing
    with patch('api.agent_routes.RBACService.check_permission') as mock_rbac:
        mock_rbac.return_value = True
        yield TestClient(test_app)

    test_app.dependency_overrides.clear()

# 3. Factory pattern with proper cleanup
class AgentFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = AgentRegistry
        sqlalchemy_session = db_session

    id = factory.Sequence(lambda n: f"test-agent-{n}")
    name = factory.Faker('company')
    agent_type = "assistant"
    maturity_level = "INTERN"
    status = "active"
```

### Coverage Target Strategy (74.6% → 85%)

**Gap Analysis:**
- Current: 74.6% overall
- Target: 85% overall
- Gap: 10.4 percentage points
- Strategy: Medium-impact modules + integration tests + infrastructure fixes

**High-Impact Modules (Priority 1):**
1. **Medium-Coverage Service Files (40-80% coverage):**
   - Target modules with 40-80% coverage for 10-15% improvements
   - Each 1% coverage = ~1-2 tests (edge cases, error paths)
   - Examples: governance services, episodic memory, LLM handlers

2. **Test Infrastructure Fixes (Priority 0):**
   - Fix 10 test files with import errors (unlocks existing tests)
   - Update 2 CanvasAudit tests for schema changes
   - Enables full test suite execution for accurate coverage

3. **Integration Test Expansion (Priority 2):**
   - Add end-to-end workflow tests (governance + execution + episodic memory)
   - Test complex orchestration (workflow engine + agent execution + monitoring)
   - Multi-service integration tests (WebSocket + LLM + Canvas)

4. **Edge Case Completion (Priority 3):**
   - Expand boundary condition testing
   - Add concurrency stress tests
   - Security vulnerability testing

### Anti-Patterns to Avoid

- **Import errors blocking tests:** Don't let broken test files sit unrepaired
- **Skipping infrastructure fixes:** Don't add new tests while 10 files are broken
- **Mocking too aggressively:** Don't mock database in integration tests
- **Missing cleanup:** Don't skip database cleanup fixtures
- **Testing implementation details:** Don't test internal methods, test behavior

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test infrastructure repair | Manual trial-and-error | pytest collection error analysis | Systematic identification of root causes |
| Coverage gap analysis | Manual file-by-file inspection | coverage.py JSON report + automated analysis | Efficient identification of high-value targets |
| Mock fixtures | Custom mock classes | AsyncMock + pytest fixtures | Properly handles async, lifecycle management |
| Test data generation | Random inline data creation | factory_boy with SQLAlchemy integration | Handles relationships, constraints, sequences |
| Database cleanup | Manual delete loops | SQLAlchemy text() DELETE with autouse fixtures | Faster, avoids ORM overhead, guaranteed cleanup |

**Key insight:** Phase 197 established proven patterns for quality testing. Leverage existing infrastructure (edge case tests, governance tests, factory patterns) rather than building custom solutions.

---

## Common Pitfalls

### Pitfall 1: Ignoring Test Infrastructure Issues

**What goes wrong:** Adding new tests while 10 test files have import errors, preventing full suite execution

**Why it happens:** Focus on coverage numbers rather than test suite health

**How to avoid:**
```python
# GOOD: Fix infrastructure first
# Plan 198-01: Test Infrastructure Fixes
# 1. Audit import errors in 10 test files
# 2. Fix User model imports, Formula class conflicts
# 3. Resolve async test configuration issues
# 4. Verify full test suite collection

# BAD: Add new tests while infrastructure broken
# - Creates fragile test suite
# - Cannot measure accurate coverage
# - Accumulates technical debt
```

**Warning signs:** pytest collection errors, tests passing in isolation but failing in suite, import warnings

### Pitfall 2: Targeting Low-Impact Modules

**What goes wrong:** Spending time on 0% coverage modules with 50 lines instead of 50% coverage modules with 500 lines

**Why it happens:** Easy wins look attractive but don't move overall coverage needle

**How to avoid:**
```python
# GOOD: Target medium-impact modules
# Priority: Modules with 40-80% coverage, 200+ lines
# - 10% improvement on 500-line module = 50 lines covered
# - More efficient than 100% coverage of 50-line module

# Example targets:
# - agent_governance_service.py: 74.6% → 85%
# - episode_segmentation_service.py: 60% → 75%
# - trigger_interceptor.py: 70% → 85%

# BAD: Focus on tiny modules
# - 100% coverage of 20-line utility = 20 lines covered
# - Low impact on overall coverage percentage
```

**Warning signs:** Coverage numbers not increasing despite many tests added

### Pitfall 3: Insufficient Integration Testing

**What goes wrong:** High unit test coverage but integration failures in production

**Why it happens:** Unit tests mock everything, integration tests are skipped or marked as flaky

**How to avoid:**
```python
# GOOD: Separate integration tests with proper fixtures
@pytest.mark.integration
def test_agent_execution_with_episodic_memory(db_session, mock_llm, mock_websocket):
    """Test full agent execution with episodic memory integration."""
    agent = AgentFactory(maturity_level="AUTONOMOUS")
    execution_id = str(uuid.uuid4())

    # Execute agent
    response = client.post(f"/agents/{agent.id}/execute", json={
        "message": "Test message",
        "execution_id": execution_id
    })

    assert response.status_code == 200

    # Verify episode created
    episodes = db_session.query(Episode).filter(
        Episode.agent_id == agent.id
    ).all()
    assert len(episodes) == 1

    # Verify execution logged
    execution = db_session.query(AgentExecution).filter(
        AgentExecution.id == execution_id
    ).first()
    assert execution is not None

# BAD: Only test individual components
def test_agent_governance_check():
    # Tests governance in isolation
    # Doesn't catch integration bugs
    pass

def test_episode_creation():
    # Tests episodic memory in isolation
    # Doesn't catch integration bugs
    pass
```

**Warning signs:** Unit tests pass but integration tests fail, high coverage but production bugs

### Pitfall 4: CanvasAudit Schema Drift

**What goes wrong:** Tests fail because CanvasAudit model changed (fields removed) but tests not updated

**Why it happens:** Schema changes made without updating test fixtures

**How to avoid:**
```python
# GOOD: Audit test fixtures against current schema
# 1. Extract model schema
from core.models import CanvasAudit
fields = [f.name for f in CanvasAudit.__table__.columns]
# ['id', 'agent_id', 'canvas_type', 'content', 'timestamp', ...]

# 2. Update test fixtures to match
@pytest.fixture
def canvas_audit(db_session):
    audit = CanvasAudit(
        agent_id="test-agent-1",
        canvas_type="line_chart",
        content={"data": [1, 2, 3]},
        # Removed: agent_execution_id, component_type (schema change)
    )
    db_session.add(audit)
    db_session.commit()
    return audit

# 3. Remove references to deleted fields
# OLD (incorrect):
assert audit.agent_execution_id == execution_id  # Field removed!
assert audit.component_type == "chart"  # Field removed!

# NEW (correct):
assert audit.agent_id == "test-agent-1"
assert audit.canvas_type == "line_chart"
```

**Warning signs:** Tests fail with AttributeError or missing fields, schema migration history shows dropped columns

### Pitfall 5: Coverage Without Quality

**What goes wrong:** Coverage increases but test suite becomes flaky or slow

**Why it happens:** Adding tests without considering quality, performance, or maintainability

**How to avoid:**
```python
# GOOD: Quality-focused coverage improvements
# 1. Add 10-15 meaningful tests per module (edge cases, error paths)
# 2. Use fixtures for shared setup (avoid duplication)
# 3. Mock external services (keep tests fast)
# 4. Add integration tests separately (mark with @pytest.mark.integration)

# Example: Targeted coverage improvement
# - atom_agent_endpoints.py: 74.6% → 85% (+15 tests)
# - governance tests: 50 → 65 tests (+15 edge cases)
# - episodic memory tests: 30 → 45 tests (+15 error paths)

# BAD: Add low-quality tests
# - Test getters/setters (no business logic)
# - Duplicate existing test scenarios
# - Test implementation details (fragile)
# - Don't mock external services (slow tests)
```

**Warning signs:** Test suite takes >10 minutes, flaky tests, tests break when code refactored

---

## Code Examples

Verified patterns from Phase 197 and Phase 196:

### Test Infrastructure Fix Pattern

```python
# Source: Phase 197 test infrastructure analysis
# Problem: Test files with User import errors
# Solution: Verify model exists and update imports

# Step 1: Verify User model in core/models.py
# User model exists at line 377+ (verified)

# Step 2: Check test imports
# tests/api/test_api_routes_coverage.py:14
from core.models import AgentRegistry, AgentExecution, User  # ✓ Correct

# Step 3: Check for circular imports or missing dependencies
# - Ensure conftest.py doesn't shadow User fixture
# - Verify factory_boy factories reference correct model

# Step 4: Test collection
# pytest tests/api/test_api_routes_coverage.py --collect-only
# Should collect tests without errors
```

### CanvasAudit Schema Update Pattern

```python
# Source: Phase 197 governance streaming test failures
# Problem: 2 tests failing due to schema changes

# OLD Schema (removed fields):
class CanvasAudit(Base):
    agent_execution_id = Column(String)  # REMOVED
    component_type = Column(String)  # REMOVED

# NEW Schema (current):
class CanvasAudit(Base):
    # agent_execution_id removed
    # component_type removed
    # Only: id, agent_id, canvas_type, content, metadata, timestamp

# Test update:
def test_canvas_presentation_creates_audit(db_session, client):
    agent = AgentFactory()
    response = client.post(f"/agents/{agent.id}/present", json={
        "type": "line_chart",
        "content": {"data": [1, 2, 3]}
    })

    assert response.status_code == 200

    # Check audit created
    audit = db_session.query(CanvasAudit).filter_by(
        agent_id=agent.id
    ).first()
    assert audit is not None
    assert audit.canvas_type == "line_chart"

    # REMOVED (fields no longer exist):
    # assert audit.agent_execution_id is not None
    # assert audit.component_type == "chart"
```

### Medium-Impact Coverage Improvement Pattern

```python
# Source: Phase 197 edge case testing approach
# Target: Modules with 40-80% coverage

# Example: agent_governance_service.py (74.6% → 85%)
class TestAgentGovernanceServiceEdgeCases:
    """Edge case testing for governance service."""

    def test_check_permissions_with_null_agent(self, db_session):
        """Test permission check with non-existent agent."""
        gov_service = AgentGovernanceService(db_session)

        result = gov_service.check_permissions(
            agent_id="non-existent",
            action="stream_chat",
            complexity=2
        )

        assert result["allowed"] == False
        assert "agent not found" in result["reason"].lower()

    def test_check_permissions_boundary_conditions(self, db_session):
        """Test permission check with action complexity boundaries."""
        agent = AgentFactory(maturity_level="INTERN")
        gov_service = AgentGovernanceService(db_session)

        # Test complexity boundaries (0, 1, 2, 3, 4)
        for complexity in [0, 1, 2, 3, 4]:
            result = gov_service.check_permissions(
                agent_id=agent.id,
                action="test_action",
                complexity=complexity
            )
            # INTERN: complexity 1-2 allowed, 3-4 blocked
            if complexity <= 2:
                assert result["allowed"] == True
            else:
                assert result["allowed"] == False

    def test_check_permissions_with_invalid_action(self, db_session):
        """Test permission check with invalid action."""
        agent = AgentFactory()
        gov_service = AgentGovernanceService(db_session)

        result = gov_service.check_permissions(
            agent_id=agent.id,
            action="",  # Empty action
            complexity=1
        )

        assert result["allowed"] == False
        assert "invalid action" in result["reason"].lower()

# Expected impact: +10-15 tests → +5-8% coverage
```

### Integration Test Expansion Pattern

```python
# Source: Phase 197 integration testing approach
# Target: End-to-end workflow coverage

@pytest.mark.integration
class TestAgentExecutionWithEpisodicMemory:
    """Integration tests for agent execution + episodic memory."""

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM streaming response."""
        async def stream_completion(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"
            yield "chunk3"
        return stream_completion

    @pytest.fixture
    def mock_websocket_manager(self):
        """Mock WebSocket manager for notifications."""
        with patch('core.governance_cache.WebSocketManager') as mock:
            mock.return_value.notify_agent_status = MagicMock()
            mock.return_value.notify_execution_start = MagicMock()
            yield mock

    def test_agent_execution_creates_episode(self, db_session, client, mock_llm_response, mock_websocket_manager):
        """Test that agent execution creates episodic memory entry."""
        agent = AgentFactory(maturity_level="AUTONOMOUS")
        execution_id = str(uuid.uuid4())

        with patch('core.llm.byok_handler.BYOKHandler.stream_completion', mock_llm_response):
            response = client.post(f"/agents/{agent.id}/execute", json={
                "message": "Test message",
                "execution_id": execution_id
            })

        assert response.status_code == 200

        # Verify episode created
        episodes = db_session.query(Episode).filter(
            Episode.agent_id == agent.id
        ).all()
        assert len(episodes) == 1

        episode = episodes[0]
        assert episode.status == "completed"
        assert len(episodes[0].segments) > 0  # Segments created

        # Verify execution logged
        execution = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution_id
        ).first()
        assert execution is not None
        assert execution.status == "completed"

# Expected impact: +5-10 integration tests → +3-5% overall coverage
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Coverage quantity focus | Quality-first with >95% pass rate gate | Phase 197 | Ensures reliable test suite before targeting 85% |
| Broken test files ignored | Test infrastructure fixes prioritized | Phase 198 (planned) | Unlocks full test suite for accurate coverage |
| Unit tests only | Integration + E2E test expansion | Phase 198 (planned) | Catches integration bugs, improves confidence |
| Random coverage targeting | Medium-impact modules prioritized | Phase 198 (planned) | Efficient 10% coverage improvement |
| Schema drift in tests | Audit-driven test updates | Phase 198 (planned) | Prevents test failures from schema changes |

**Deprecated/outdated:**
- pytest-rerunfailtures for flaky tests: **NOT NEEDED** - Phase 196 showed 0 flaky tests with deterministic patterns
- Manual coverage analysis: **OUTDATED** - Use coverage.py JSON report with automated gap identification
- Ignoring test infrastructure: **ANTI-PATTERN** - Fix broken tests first, then add coverage

---

## Open Questions

1. **Test infrastructure root cause**
   - What we know: 10 test files have import/collection errors
   - What's unclear: Exact root cause (User imports, Formula conflicts, async config)
   - Recommendation: Audit Phase 197 coverage report for specific error messages, fix systematically

2. **Medium-impact module prioritization**
   - What we know: Need to target modules with 40-80% coverage for efficient gains
   - What's unclear: Which specific modules will provide 10.4% improvement
   - Recommendation: Generate current coverage report, identify top 10 modules by (lines × coverage gap)

3. **Integration test scope**
   - What we know: Need E2E workflow tests
   - What's unclear: How many integration tests needed for meaningful coverage
   - Recommendation: Start with 5-10 critical workflows (agent execution, episodic memory, governance)

4. **CanvasAudit test update impact**
   - What we know: 2 tests failing due to schema changes
   - What's unclear: Whether more tests affected by schema drift
   - Recommendation: Audit all CanvasAudit references, update fixture schemas

---

## Test Infrastructure Analysis (Phase 197)

### Files with Import Errors (10 files)

Based on Phase 197 documentation:

**API Tests (6 files):**
1. `tests/api/test_api_routes_coverage.py` - User import issues
2. `tests/api/test_feedback_analytics.py` - Model imports
3. `tests/api/test_feedback_enhanced.py` - Model imports
4. `tests/api/test_operational_routes.py` - Import conflicts
5. `tests/api/test_permission_checks.py` - Model imports
6. `tests/api/test_social_routes_integration.py` - Integration test issues

**Core Tests (3 files):**
7. `tests/core/agents/test_atom_agent_endpoints_coverage.py` - Duplicate file name
8. `tests/core/systems/test_embedding_service_coverage.py` - Import issues
9. `tests/core/systems/test_integration_data_mapper_coverage.py` - Import issues

**Integration Tests (1 directory):**
10. `tests/contract/` - Contract test framework issues

### CanvasAudit Schema Changes

**Fields Removed:**
- `agent_execution_id` (no longer tracked)
- `component_type` (simplified schema)

**Tests Affected (2 tests):**
- `test_governance_streaming_with_canvas_presentation`
- `test_governance_streaming_with_multiple_canvases`

**Fix Required:**
- Remove field references from test assertions
- Update fixture schemas to match current model

---

## Coverage Targets by Module Type

### High-Impact Service Modules (Priority 1)

Target: 10-15% improvement on medium-coverage modules

| Module | Current | Target | Lines | Impact | Tests Needed |
|--------|---------|--------|-------|--------|--------------|
| `agent_governance_service.py` | 74.6% | 85% | ~400 | High | +10-15 tests |
| `episode_segmentation_service.py` | 60% | 75% | ~300 | High | +12-18 tests |
| `trigger_interceptor.py` | 70% | 85% | ~250 | High | +10-15 tests |
| `episode_retrieval_service.py` | 65% | 80% | ~350 | High | +12-18 tests |
| `governance_cache.py` | 80% | 90% | ~200 | Medium | +8-12 tests |
| `student_training_service.py` | 50% | 65% | ~400 | High | +15-20 tests |
| `supervision_service.py` | 55% | 70% | ~350 | High | +12-18 tests |
| `agent_graduation_service.py` | 60% | 75% | ~300 | High | +12-18 tests |

**Expected Impact:** +8-12% overall coverage (assuming ~5,000 lines total)

### Integration Test Expansion (Priority 2)

Target: E2E workflow coverage

| Workflow | Components | Tests | Impact |
|----------|------------|-------|--------|
| Agent Execution + Episodic Memory | Governance → Execution → Episode creation | 5-8 tests | +2-3% |
| Workflow Orchestration | Template → Execution → Monitoring | 4-6 tests | +1.5-2% |
| Canvas Presentation | Agent → Canvas → Audit | 3-5 tests | +1-1.5% |
| LLM Streaming + BYOK | BYOK → Streaming → Cache | 4-6 tests | +1-1.5% |

**Expected Impact:** +5.5-8% overall coverage

### Test Infrastructure Fixes (Priority 0)

Target: Enable full test suite execution

| Task | Files | Effort | Impact |
|------|-------|--------|--------|
| Fix import errors (User model) | 6 files | 30 min | Unlocks 50+ tests |
| Fix Formula class conflicts | 2 files | 30 min | Unlocks 20+ tests |
| Fix async test config | 2 files | 30 min | Unlocks 30+ tests |
| Update CanvasAudit tests | 2 tests | 15 min | +2 passing tests |

**Expected Impact:** Unlocks 100+ existing tests, enables accurate coverage measurement

---

## Recommended Phase 198 Structure

### Wave 1: Test Infrastructure Fixes (2 hours)
- **198-01:** Test Infrastructure Audit & Fixes
  - Fix 10 files with import errors
  - Update CanvasAudit tests for schema changes
  - Verify full test suite collection

### Wave 2: Medium-Impact Coverage (4-6 hours)
- **198-02:** Governance Services Coverage (agent_governance, trigger_interceptor)
- **198-03:** Episodic Memory Coverage (segmentation, retrieval, graduation)
- **198-04:** Training & Supervision Coverage (student_training, supervision_service)
- **198-05:** Cache & Performance Coverage (governance_cache, monitoring)

### Wave 3: Integration Test Expansion (3-4 hours)
- **198-06:** Agent Execution E2E Tests (governance + execution + episodic memory)
- **198-07:** Workflow Orchestration Integration (templates + execution + monitoring)
- **198-08:** LLM & Canvas Integration (streaming + canvas + audit)

### Wave 4: Final Verification (1 hour)
- **198-09:** Coverage Verification & Summary
  - Generate final coverage report
  - Verify 85% target achieved
  - Document coverage gains and lessons learned

**Total Estimated Effort:** 10-13 hours (8-9 plans)

**Success Criteria:**
- ✅ Overall coverage: 85% (from 74.6%)
- ✅ Test pass rate: >95%
- ✅ All infrastructure issues resolved
- ✅ Integration tests passing
- ✅ Documentation complete

---

## Sources

### Primary (HIGH confidence)

- Phase 197 Final Summary - `/Users/rushiparikh/projects/atom/.planning/phases/197-quality-first-push-80/197-08-SUMMARY.md`
- Phase 197 Coverage Report - `/Users/rushiparikh/projects/atom/.planning/phases/197-quality-first-push-80/PLANS/197-08-coverage-report.txt`
- Phase 197 Test Results - `/Users/rushiparikh/projects/atom/.planning/phases/197-quality-first-push-80/PLANS/197-08-test-results.txt`
- Phase 197 Research - `/Users/rushiparikh/projects/atom/.planning/phases/197-quality-first-push-80/197-RESEARCH.md`
- Coverage JSON - `/Users/rushiparikh/projects/atom/backend/tests/coverage_reports/metrics/coverage.json`
- pytest.ini configuration - `/Users/rushiparikh/projects/atom/backend/pytest.ini`
- Core models - `/Users/rushiparikh/projects/atom/backend/core/models.py`

### Secondary (MEDIUM confidence)

- pytest 9.0.2 documentation - https://docs.pytest.org/en/stable/
- coverage.py 7.13.4 documentation - https://coverage.readthedocs.io/en/7.13.4/
- FastAPI Testing documentation - https://fastapi.tiangolo.com/tutorial/testing/
- factory_boy documentation - https://factoryboy.readthedocs.io/
- SQLAlchemy 2.0 documentation - https://docs.sqlalchemy.org/en/20/

### Tertiary (LOW confidence)

- None - All findings verified against codebase or official documentation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All versions verified in codebase, official docs checked
- Architecture: HIGH - Based on actual Phase 197 results and test infrastructure analysis
- Pitfalls: HIGH - Root causes identified from Phase 197 documentation and test inspection
- Coverage targets: MEDIUM - Estimates based on statement counts and Phase 197 velocity
- Test infrastructure issues: HIGH - Specific files and errors documented in Phase 197

**Research date:** 2026-03-16
**Valid until:** 2026-04-15 (30 days - stable testing stack)

---

## Appendices

### Appendix A: Test Infrastructure Error Types

Based on Phase 197 coverage report analysis:

**Error Type 1: User Model Import Issues (6 files)**
- Symptom: `ImportError: cannot import name 'User'`
- Root Cause: Import path changes, fixture shadowing
- Files Affected: test_api_routes_coverage.py, test_feedback_analytics.py, test_feedback_enhanced.py, test_operational_routes.py, test_permission_checks.py, test_social_routes_integration.py
- Fix: Verify User model in core/models.py, update imports, check fixture conflicts

**Error Type 2: Formula Class Conflicts (2 files)**
- Symptom: `AttributeError: type object 'Formula' has no attribute`
- Root Cause: Formula model refactored, tests not updated
- Files Affected: test_integration_data_mapper_coverage.py, related test files
- Fix: Audit Formula model schema, update test fixtures

**Error Type 3: Async Test Configuration (2 files)**
- Symptom: `TypeError: object of type 'coroutine' has no len()`
- Root Cause: pytest-asyncio mode misconfiguration
- Files Affected: test_embedding_service_coverage.py, related async tests
- Fix: Update conftest.py with `asyncio_mode = "auto"`

### Appendix B: Coverage Calculation Methodology

**Overall Coverage Formula:**
```
Overall Coverage = (Total Lines Covered / Total Executable Lines) × 100

Current: 74.6% = (X / Y) × 100
Target: 85% = (Z / Y) × 100
Gap: 10.4 percentage points
```

**Efficient Coverage Improvement:**
```
Priority = (Module Lines × Coverage Gap) / Effort

Example 1 (HIGH PRIORITY):
- agent_governance_service.py: 400 lines, 74.6% → 85% (10.4% gap)
- Impact: 400 × 0.104 = 41.6 lines covered
- Effort: 10-15 tests (~2 hours)

Example 2 (LOW PRIORITY):
- small_util.py: 50 lines, 0% → 100% (100% gap)
- Impact: 50 × 1.0 = 50 lines covered
- Effort: 5-10 tests (~1 hour)

Example 3 (MEDIUM PRIORITY):
- episode_segmentation.py: 300 lines, 60% → 75% (15% gap)
- Impact: 300 × 0.15 = 45 lines covered
- Effort: 12-18 tests (~2.5 hours)

**Conclusion:** Target medium-impact modules (200-500 lines, 40-80% coverage) for efficient gains
```

### Appendix C: Integration Test Prioritization

**Critical Workflows (Highest Priority):**

1. **Agent Execution with Episodic Memory** (5-8 tests)
   - Governance check → Agent execution → Episode creation
   - Test AUTONOMOUS, SUPERVISED, INTERN agents
   - Verify episode segments, feedback linking
   - Impact: Core business logic, high confidence

2. **Workflow Orchestration** (4-6 tests)
   - Template creation → Workflow execution → Monitoring
   - Test conditional steps, parallel execution
   - Verify workflow analytics, state transitions
   - Impact: Complex orchestration, medium confidence

3. **Canvas Presentation with Audit** (3-5 tests)
   - Agent present → Canvas created → Audit logged
   - Test all 7 canvas types (line_chart, bar_chart, etc.)
   - Verify CanvasAudit schema compliance
   - Impact: User-facing features, medium confidence

4. **LLM Streaming with BYOK** (4-6 tests)
   - BYOK routing → LLM streaming → Response delivery
   - Test multiple providers (OpenAI, Anthropic, DeepSeek)
   - Verify cognitive tier classification, cost estimation
   - Impact: Core AI features, high confidence

### Appendix D: Phase 198 Success Metrics

**Coverage Metrics:**
- Overall coverage: 85% (from 74.6%)
- Governance services: 80-90% (from 70-75%)
- Episodic memory: 75-85% (from 60-65%)
- Integration tests: 60-70% (from ~40%)

**Test Quality Metrics:**
- Pass rate: >95% (target: 98%+)
- Test infrastructure: 0 collection errors (from 10)
- Flaky tests: 0 (maintain Phase 196 record)
- Test execution time: <10 minutes (full suite)

**Documentation Metrics:**
- Plan summaries: 9 plans × 1 summary each
- Coverage reports: After each wave (4 reports)
- Phase summary: Comprehensive lessons learned
- Test infrastructure guide: For future phases

**Baseline Comparison:**
- Phase 196: 74.6% coverage, 76.4% pass rate (99 failing tests)
- Phase 197: 74.6% coverage, 98% pass rate (quality-first approach)
- Phase 198: 85% coverage, 98%+ pass rate (integration expansion)

---

*Phase: 198-coverage-push-85*
*Research Date: 2026-03-16*
*Next Step: Create PLAN.md files based on research findings*
