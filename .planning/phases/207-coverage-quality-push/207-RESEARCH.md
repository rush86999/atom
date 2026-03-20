# Phase 207: Coverage Quality Push - Research Document

**Phase:** 207 - Coverage Quality Push
**Date:** 2026-03-18
**Status:** RESEARCH COMPLETE
**Target:** 70% overall coverage, 80% file-level quality, ~400 tests

---

## Executive Summary

Phase 207 is a strategic shift from Phase 206's "test important modules" approach to a "test testable modules" philosophy. Research shows that large, complex modules (>1000 lines) have diminishing returns, while small modules (<500 lines) achieve 75%+ coverage cost-effectively.

**Key Finding:** Phase 206 achieved 56.79% coverage (vs 80% target) with 298 tests. Three collection errors occurred during execution, indicating test infrastructure instability.

**Strategic Pivot:** Prioritize modules by size + simplicity, not business importance. Focus on API routes (10-60 lines), core services (30-60 lines), and tools (300-600 lines).

---

## Phase 206 Retrospective

### What Went Wrong

1. **Unrealistic Target:** 80% coverage was too aggressive given module complexity
2. **Wrong Selection Criteria:**
   - Selected modules by "importance" (governance, LLM, episodic memory)
   - These modules are LARGE (>1000 lines) and COMPLEX (async, external deps)
   - Diminishing returns: 80% coverage took 4x effort vs 70%

3. **Test Infrastructure Issues:**
   - 3 collection errors during execution
   - Tests failed to import properly
   - Indicates test suite instability

4. **Insufficient Branch Coverage:**
   - No branch coverage tracking
   - Easy to hit line coverage targets without testing logic paths

### What Went Right

1. **High Test Count:** 298 tests created (good velocity)
2. **Pass Rate:** 95%+ tests passing
3. **Modular Structure:** Clear plan organization

### Lessons Learned

1. **Small modules are cost-effective:**
   - <500 lines → 75-95% coverage achievable
   - >1000 lines → <60% coverage typical

2. **Testability matters more than importance:**
   - API routes: HIGH testability (simple request/response)
   - Core services: MEDIUM testability (some external deps)
   - Tools: EXCELLENT testability (isolated functions)

3. **Branch coverage is essential:**
   - Line coverage alone is insufficient
   - Need 60%+ branch coverage for quality

---

## Module Selection Methodology

### Selection Criteria (Phase 207)

**Priority Formula:**
```
Score = (1 / size) * simplicity * testability
```

Where:
- `size`: Lines of code (smaller = better)
- `simplicity`: Low complexity, synchronous code (higher = better)
- `testability`: Isolated, few external deps (higher = better)

### Categories Identified

#### Wave 1: API Routes (HIGH testability)
**Characteristics:**
- Size: 10-60 lines
- Complexity: LOW (FastAPI route handlers)
- External deps: Minimal (mostly mocks)
- Est. coverage: 85-95%

**Modules:**
1. `api/reports.py` (10 lines) - 95% est.
2. `api/websocket_routes.py` (25 lines) - 90% est.
3. `api/workflow_analytics_routes.py` (30 lines) - 90% est.
4. `api/time_travel_routes.py` (51 lines) - 85% est.
5. `api/onboarding_routes.py` (55 lines) - 85% est.
6. `api/sales_routes.py` (58 lines) - 85% est.

**Expected Output:** ~120 tests, 85-95% coverage

#### Wave 2: Core Services (GOOD testability)
**Characteristics:**
- Size: 30-60 lines
- Complexity: MEDIUM (business logic, some async)
- External deps: Moderate (database, cache)
- Est. coverage: 75-85%

**Modules:**
1. `core/lux_config.py` (33 lines) - 90% est.
2. `core/messaging_schemas.py` (41 lines) - 95% est.
3. `core/billing.py` (47 lines) - 85% est.
4. `core/llm_service.py` (47 lines) - 80% est.
5. `core/historical_learner.py` (52 lines) - 75% est.
6. `core/external_integration_service.py` (59 lines) - 75% est.

**Expected Output:** ~130 tests, 75-85% coverage

#### Wave 3: Tools (EXCELLENT testability)
**Characteristics:**
- Size: 300-600 lines
- Complexity: MEDIUM (tool logic, but testable)
- External deps: LOW (can mock browser/device)
- Est. coverage: 70-90%

**Modules:**
1. `tools/device_tool.py` (~300 lines) - 85% est.
2. `tools/browser_tool.py` (~400 lines) - 80% est.
3. `tools/canvas_tool.py` (~600 lines) - 70% est.

**Expected Output:** ~100 tests, 80-90% coverage

#### Wave 4: Incremental Improvements (MEDIUM testability)
**Characteristics:**
- Size: >1000 lines
- Complexity: HIGH (complex logic, many paths)
- Existing coverage: 25-56%
- Target: +15-20 percentage points

**Modules:**
1. `agent_graduation_service.py` (56.25% → 70% target)
2. `episode_retrieval_service.py` (53.12% → 65% target)
3. `byok_handler.py` (25.22% → 40% target)

**Expected Output:** ~50 additional tests, +15-20pp coverage

---

## Coverage Targets

### Phase 207 Targets (Realistic vs Phase 206)

| Metric | Phase 206 Target | Phase 206 Actual | Phase 207 Target | Rationale |
|--------|------------------|------------------|------------------|-----------|
| Overall Coverage | 80% | 56.79% | 70% | More realistic based on testability |
| File-Level Quality | 60% @ 75%+ | 44% @ 75%+ | 80% @ 75%+ | Focus on small modules |
| Tests Created | ~300 | 298 | ~400 | Incremental increase |
| Collection Errors | 0 | 3 | 0 | Proactive verification |
| Branch Coverage | Not tracked | Not tracked | 60%+ | NEW metric for quality |

### Success Criteria

Phase 207 is **SUCCESSFUL** if:
1. 70% average coverage across new files
2. 80% of files achieve 75%+ file-level coverage
3. ~400 tests created with 95%+ pass rate
4. 0 collection errors (vs 3 in Phase 206)
5. 60%+ branch coverage for new files
6. Comprehensive documentation of results

---

## Test Infrastructure Improvements

### Collection Error Prevention

**Problem:** Phase 206 had 3 collection errors (tests failed to import).

**Solution:** Proactive collection verification in each plan.

**Implementation:**
```bash
# After writing tests, verify collection
pytest tests/unit/test_new_file.py --collect-only

# If errors occur, fix before committing
pytest tests/unit/test_new_file.py --collect-only -q
```

**Task Pattern:** Each plan ends with "Verify no collection errors" task.

### Branch Coverage Tracking

**Problem:** Phase 206 didn't track branch coverage, leading to untested logic paths.

**Solution:** Add branch coverage to pytest configuration.

**Implementation:**
```bash
# Run with branch coverage
pytest tests/unit/test_new_file.py --cov=core/module --cov-branch --cov-report=term-missing

# Verify 60%+ branch coverage
grep -A 1 "branch" coverage_report.txt
```

**Task Pattern:** Each task specifies branch coverage target (60%+ for new files).

### Test Stability Improvements

**Problem:** Test flakiness and collection errors reduce confidence.

**Solution:**
1. Use AsyncMock correctly (no coroutines)
2. Mock internal methods, not non-existent external modules
3. Verify collection before execution
4. Run tests 3x to check for flakiness

---

## Wave Organization

### Wave 1: API Routes (Plans 01-03)

**Timeline:** Days 1-2
**Focus:** Small, simple API route handlers
**Testability:** HIGH
**Expected:** ~120 tests, 85-95% coverage

**Plan 01:** Reports & WebSocket Routes (35 lines total)
- `api/reports.py` (10 lines, 95% est.)
- `api/websocket_routes.py` (25 lines, 90% est.)

**Plan 02:** Analytics & Time Travel Routes (81 lines total)
- `api/workflow_analytics_routes.py` (30 lines, 90% est.)
- `api/time_travel_routes.py` (51 lines, 85% est.)

**Plan 03:** Onboarding & Sales Routes (113 lines total)
- `api/onboarding_routes.py` (55 lines, 85% est.)
- `api/sales_routes.py` (58 lines, 85% est.)

### Wave 2: Core Services (Plans 04-06)

**Timeline:** Days 3-4
**Focus:** Small core services with business logic
**Testability:** GOOD
**Expected:** ~130 tests, 75-85% coverage

**Plan 04:** Lux Config & Messaging Schemas (74 lines total)
- `core/lux_config.py` (33 lines, 90% est.)
- `core/messaging_schemas.py` (41 lines, 95% est.)

**Plan 05:** Billing & LLM Service (94 lines total)
- `core/billing.py` (47 lines, 85% est.)
- `core/llm_service.py` (47 lines, 80% est.)

**Plan 06:** Historical Learner & External Integration (111 lines total)
- `core/historical_learner.py` (52 lines, 75% est.)
- `core/external_integration_service.py` (59 lines, 75% est.)

### Wave 3: Tools (Plans 07-08)

**Timeline:** Days 5-6
**Focus:** Medium-size tool modules with isolated logic
**Testability:** EXCELLENT
**Expected:** ~100 tests, 80-90% coverage

**Plan 07:** Device & Browser Tools (~700 lines total)
- `tools/device_tool.py` (~300 lines, 85% est.)
- `tools/browser_tool.py` (~400 lines, 80% est.)

**Plan 08:** Canvas Tool (~600 lines)
- `tools/canvas_tool.py` (~600 lines, 70% est.)

### Wave 4: Incremental Improvements (Plan 09)

**Timeline:** Day 7
**Focus:** Improve existing Phase 206 modules incrementally
**Testability:** MEDIUM (large, complex modules)
**Expected:** ~50 additional tests, +15-20pp coverage

**Plan 09:** Incremental Coverage Improvements
- `agent_graduation_service.py` (56.25% → 70% target)
- `episode_retrieval_service.py` (53.12% → 65% target)
- `byok_handler.py` (25.22% → 40% target)

### Wave 5: Verification (Plan 10)

**Timeline:** Day 8
**Focus:** Aggregate coverage, branch coverage verification, collection error verification
**Expected:** Full coverage report, documentation

**Plan 10:** Coverage Aggregation & Verification
- Aggregate coverage across all plans
- Verify branch coverage targets met
- Verify zero collection errors
- Document lessons learned

---

## Testing Patterns

### API Route Testing Pattern

```python
# Standard API route test structure
def test_get_report_success(db_session, client):
    """Test GET /api/reports returns 200 with data."""
    # Arrange: Create test data
    report = ReportFactory(title="Test Report")
    db_session.commit()

    # Act: Make request
    response = client.get("/api/reports")

    # Assert: Verify response
    assert response.status_code == 200
    assert response.json()["title"] == "Test Report"

def test_get_report_not_found(db_session, client):
    """Test GET /api/reports/{id} returns 404 for non-existent report."""
    # Act: Request non-existent report
    response = client.get("/api/reports/nonexistent-id")

    # Assert: Verify 404
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
```

**Branch Coverage:** Test success path + error paths (404, 400, 500)

### Core Service Testing Pattern

```python
# Standard service test structure
def test_lux_config_get_value(db_session):
    """Test LuxConfig.get_value returns correct config."""
    # Arrange: Create config entry
    config = LuxConfigFactory(key="test_key", value="test_value")

    # Act: Get value
    service = LuxConfigService(db_session)
    result = service.get_value("test_key")

    # Assert: Verify value
    assert result == "test_value"

def test_lux_config_get_value_not_found(db_session):
    """Test LuxConfig.get_value returns None for missing key."""
    # Act: Get non-existent key
    service = LuxConfigService(db_session)
    result = service.get_value("missing_key")

    # Assert: Verify None
    assert result is None
```

**Branch Coverage:** Test happy path + error cases + edge cases

### Tool Testing Pattern

```python
# Standard tool test structure
def test_device_tool_camera_capture():
    """Test DeviceTool.camera_capture returns image."""
    # Arrange: Mock device camera
    mock_camera = Mock()
    mock_camera.capture.return_value = b"fake_image_data"

    # Act: Capture image
    tool = DeviceTool()
    result = tool.camera_capture()

    # Assert: Verify image captured
    assert result == b"fake_image_data"
    mock_camera.capture.assert_called_once()

def test_device_tool_camera_capture_permission_denied():
    """Test DeviceTool.camera_capture raises PermissionError for STUDENT agent."""
    # Arrange: Create STUDENT agent
    agent = AgentFactory(maturity=AgentStatus.STUDENT)

    # Act/Assert: Should raise PermissionError
    tool = DeviceTool()
    with pytest.raises(PermissionError, match="STUDENT.*camera"):
        tool.camera_capture(agent=agent)
```

**Branch Coverage:** Test success + permission errors + device errors

---

## Risk Mitigation

### Risk 1: Collection Errors (HIGH)

**Impact:** Tests fail to import, blocking execution
**Probability:** MEDIUM (3 errors in Phase 206)

**Mitigation:**
1. Run `pytest --collect-only` after writing tests
2. Fix import errors before committing
3. Verify in CI before merge
4. Add collection verification task to each plan

### Risk 2: Low Branch Coverage (MEDIUM)

**Impact:** Line coverage targets met, but logic paths untested
**Probability:** MEDIUM (not tracked in Phase 206)

**Mitigation:**
1. Add `--cov-branch` to pytest commands
2. Specify 60%+ branch coverage targets
3. Review missing branches in coverage report
4. Add tests for untested branches

### Risk 3: Test Flakiness (MEDIUM)

**Impact:** Tests fail intermittently, reducing confidence
**Probability:** LOW (good infrastructure from Phase 206)

**Mitigation:**
1. Use AsyncMock correctly (no coroutines)
2. Mock internal methods, not non-existent modules
3. Run tests 3x to detect flakiness
4. Fix flaky tests before committing

### Risk 4: Unrealistic Targets (LOW)

**Impact:** Fall short of goals, wasted effort
**Probability:** LOW (learned from Phase 206)

**Mitigation:**
1. Set 70% overall target (vs 80% in Phase 206)
2. Prioritize small, testable modules
3. Incremental improvements for large modules
4. Document estimates vs actuals

---

## Success Metrics

### Quantitative Metrics

1. **Overall Coverage:** 70% average across new files
   - Measurement: `pytest --cov-report=term`
   - Target: 70% (vs 56.79% in Phase 206)

2. **File-Level Quality:** 80% of files at 75%+ coverage
   - Measurement: Count files with >=75% coverage
   - Target: 80% (vs 44% in Phase 206)

3. **Test Count:** ~400 tests created
   - Measurement: Count test functions
   - Target: ~400 (vs 298 in Phase 206)

4. **Pass Rate:** 95%+ tests passing
   - Measurement: `pytest --tb=no | grep passed`
   - Target: 95%+ (consistent with Phase 206)

5. **Collection Errors:** 0 errors
   - Measurement: `pytest --collect-only 2>&1 | grep ERROR`
   - Target: 0 (vs 3 in Phase 206)

6. **Branch Coverage:** 60%+ for new files
   - Measurement: `pytest --cov-branch --cov-report=term`
   - Target: 60%+ (NEW metric)

### Qualitative Metrics

1. **Test Stability:** Tests pass consistently across 3 runs
2. **Code Quality:** Tests follow patterns from Phase 206
3. **Documentation:** Comprehensive SUMMARY.md files

---

## Research Summary

**Phase 207 represents a strategic shift based on Phase 206 learnings:**

1. **Test testable modules, not important modules**
   - Small modules (<500 lines) provide 3-5x better ROI
   - API routes → 85-95% coverage achievable
   - Large modules (>1000 lines) → 60-70% realistic

2. **Lower coverage target, higher quality**
   - 70% overall (vs 80% in Phase 206)
   - 80% file-level quality (vs 44% in Phase 206)
   - Branch coverage tracking (NEW)

3. **Proactive collection error prevention**
   - Verify collection before execution
   - Fix import errors early
   - Zero collection errors goal

4. **Wave organization for parallel execution**
   - Wave 1: API routes (3 plans, 2 days)
   - Wave 2: Core services (3 plans, 2 days)
   - Wave 3: Tools (2 plans, 2 days)
   - Wave 4: Improvements (1 plan, 1 day)
   - Wave 5: Verification (1 plan, 1 day)

**Expected Outcome:** 70% coverage, 400 tests, 80% file-level quality, 0 collection errors, 60%+ branch coverage.

---

**Status:** RESEARCH COMPLETE ✅
**Next Step:** Create 10 execution plans (207-01 through 207-10)
**Timeline:** 8 days (parallel waves)
**Confidence:** HIGH (based on Phase 206 data)
