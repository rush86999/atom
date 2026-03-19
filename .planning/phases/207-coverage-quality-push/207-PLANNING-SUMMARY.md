# Phase 207: Coverage Quality Push - Planning Summary

**Date:** March 18, 2026
**Status:** PLANNING COMPLETE ✅
**Plans:** 10 executable plans created

---

## Executive Summary

Phase 207 represents a **strategic shift** from Phase 206's "test important modules" approach to a "test testable modules" philosophy. Research shows that small modules (<500 lines) achieve 75%+ coverage cost-effectively, while large modules (>1000 lines) have diminishing returns.

**Key Changes from Phase 206:**
- **Lower Coverage Target:** 70% vs 80% (more realistic)
- **Focus on Testability:** Select by size + simplicity, not importance
- **Branch Coverage:** 60%+ target (NEW metric)
- **Collection Stability:** Proactive verification (0 errors goal)

---

## Wave Structure

### Wave 1: API Routes (Plans 01-03)
**Timeline:** Days 1-2
**Modules:** 6 API route files
**Testability:** HIGH (10-60 lines each)
**Expected Output:** ~120 tests, 85-95% coverage

| Plan | Modules | Lines | Est. Coverage |
|------|---------|-------|---------------|
| 207-01 | reports.py, websocket_routes.py | 35 | 90-95% |
| 207-02 | workflow_analytics_routes.py, time_travel_routes.py | 81 | 85-90% |
| 207-03 | onboarding_routes.py, sales_routes.py | 113 | 85% |

**Wave 1 Total:** 229 lines, ~120 tests, 85-95% coverage

### Wave 2: Core Services (Plans 04-06)
**Timeline:** Days 3-4
**Modules:** 6 core service files
**Testability:** GOOD (30-60 lines each)
**Expected Output:** ~130 tests, 75-95% coverage

| Plan | Modules | Lines | Est. Coverage |
|------|---------|-------|---------------|
| 207-04 | lux_config.py, messaging_schemas.py | 74 | 90-95% |
| 207-05 | billing.py, llm_service.py | 94 | 80-85% |
| 207-06 | historical_learner.py, external_integration_service.py | 111 | 75% |

**Wave 2 Total:** 279 lines, ~130 tests, 75-95% coverage

### Wave 3: Tools (Plans 07-08)
**Timeline:** Days 5-6
**Modules:** 3 tool files
**Testability:** EXCELLENT (300-600 lines)
**Expected Output:** ~100 tests, 70-90% coverage

| Plan | Modules | Lines | Est. Coverage |
|------|---------|-------|---------------|
| 207-07 | device_tool.py, browser_tool.py | ~700 | 80-85% |
| 207-08 | canvas_tool.py | ~600 | 70% |

**Wave 3 Total:** ~1300 lines, ~100 tests, 70-90% coverage

### Wave 4: Incremental Improvements (Plan 09)
**Timeline:** Day 7
**Modules:** 3 existing Phase 206 files
**Testability:** MEDIUM (large, complex)
**Expected Output:** ~50 additional tests, +15-20pp coverage

| Plan | Module | Current | Target | Improvement |
|------|--------|---------|--------|-------------|
| 207-09 | agent_graduation_service.py | 56.25% | 70% | +13.75pp |
| 207-09 | episode_retrieval_service.py | 53.12% | 65% | +11.88pp |
| 207-09 | byok_handler.py | 25.22% | 40% | +14.78pp |

**Wave 4 Total:** ~50 tests, +15-20pp per module

### Wave 5: Verification (Plan 10)
**Timeline:** Day 8
**Focus:** Aggregation, reporting, lessons learned

| Plan | Deliverables |
|------|-------------|
| 207-10 | Coverage report, lessons learned, phase summary |

---

## Phase Targets

### Quantitative Targets

| Metric | Phase 206 | Phase 207 | Change |
|--------|-----------|-----------|--------|
| **Overall Coverage** | 80% (target)<br>56.79% (actual) | 70% (target) | More realistic |
| **File-Level Quality** | 44% @ 75%+ | 80% @ 75%+ | +36 percentage points |
| **Tests Created** | 298 | ~400 | +102 tests |
| **Collection Errors** | 3 | 0 | Proactive verification |
| **Branch Coverage** | Not tracked | 60%+ | NEW metric |

### Success Criteria

Phase 207 is **SUCCESSFUL** if:
1. ✅ 70% average coverage across new files
2. ✅ 80% of files achieve 75%+ file-level coverage
3. ✅ ~400 tests created with 95%+ pass rate
4. ✅ 0 collection errors (vs 3 in Phase 206)
5. ✅ 60%+ branch coverage for new files
6. ✅ Comprehensive documentation

---

## Module Selection Methodology

### Phase 206 Approach (What Didn't Work)
```
Priority = Business Importance
→ Selected large, complex modules (governance, LLM, episodic memory)
→ >1000 lines, async, external dependencies
→ Diminishing returns: 80% coverage took 4x effort
```

### Phase 207 Approach (What Works)
```
Priority = (1 / Size) × Simplicity × Testability
→ Selected small, testable modules
→ <500 lines, synchronous, isolated logic
→ 75-95% coverage achievable quickly
```

### Testability Scores

| Category | Size | Complexity | External Deps | Est. Coverage |
|----------|------|------------|---------------|---------------|
| API Routes | 10-60 lines | LOW | Minimal | 85-95% |
| Core Services | 30-60 lines | MEDIUM | Moderate | 75-85% |
| Tools | 300-600 lines | MEDIUM | Low (mockable) | 70-90% |
| Large Modules | >1000 lines | HIGH | Many | 25-70% |

---

## Testing Patterns

### API Route Pattern
```python
def test_endpoint_success(db_session, client):
    # Arrange: Create test data
    entity = EntityFactory()
    db_session.commit()
    
    # Act: Make request
    response = client.get("/api/endpoint")
    
    # Assert: Verify response
    assert response.status_code == 200
    assert response.json()["key"] == "value"

def test_endpoint_error_cases(db_session, client):
    # Test 404, 400, 500 errors
    # Test validation errors
    # Test edge cases
```

### Core Service Pattern
```python
def test_service_method(db_session):
    # Arrange: Create test data
    config = ConfigFactory(key="test", value="true")
    
    # Act: Call service method
    service = Service(db_session)
    result = service.get_value("test")
    
    # Assert: Verify result
    assert result == "true"
```

### Tool Pattern
```python
def test_tool_operation():
    # Arrange: Mock device/browser
    mock_device = Mock()
    mock_device.capture.return_value = b"data"
    
    # Act: Call tool method
    tool = DeviceTool()
    result = tool.capture()
    
    # Assert: Verify result
    assert result == b"data"
```

---

## Risk Mitigation

### Risk 1: Collection Errors (HIGH)
**Impact:** Tests fail to import
**Probability:** MEDIUM (3 errors in Phase 206)
**Mitigation:**
- Run `pytest --collect-only` after writing tests
- Fix import errors before committing
- Add collection verification task to each plan

### Risk 2: Low Branch Coverage (MEDIUM)
**Impact:** Line coverage met, but logic paths untested
**Probability:** MEDIUM (not tracked in Phase 206)
**Mitigation:**
- Add `--cov-branch` to all pytest commands
- Specify 60%+ branch coverage targets
- Review missing branches in coverage report

### Risk 3: Unrealistic Targets (LOW)
**Impact:** Fall short of goals
**Probability:** LOW (learned from Phase 206)
**Mitigation:**
- Set 70% overall target (vs 80%)
- Prioritize small, testable modules
- Incremental improvements for large modules

---

## Expected Outcomes

### Coverage Distribution
```
Wave 1 (API Routes):     85-95%  (6 modules,  ~120 tests)
Wave 2 (Core Services):  75-95%  (6 modules,  ~130 tests)
Wave 3 (Tools):          70-90%  (3 modules,  ~100 tests)
Wave 4 (Improvements):   +15-20pp (3 modules, ~50 tests)
```

### Overall Metrics
- **Modules Tested:** 18 total (15 new + 3 improved)
- **Tests Created:** ~400 total
- **Overall Coverage:** 70% average
- **File-Level Quality:** 80% @ 75%+
- **Branch Coverage:** 60%+ for new files
- **Collection Errors:** 0 (proactive verification)

### Comparison to Phase 206
| Metric | Phase 206 | Phase 207 (Expected) | Improvement |
|--------|-----------|---------------------|-------------|
| Target vs Actual | 56.79% vs 80% target | 70% vs 70% target | ✅ Realistic target |
| File-Level Quality | 44% @ 75%+ | 80% @ 75%+ | +36pp |
| Collection Errors | 3 | 0 | -3 errors |
| Branch Coverage | Not tracked | 60%+ | NEW metric |

---

## Execution Roadmap

### Week 1: Waves 1-2
- Days 1-2: API Routes (Plans 01-03)
- Days 3-4: Core Services (Plans 04-06)

### Week 2: Waves 3-5
- Days 5-6: Tools (Plans 07-08)
- Day 7: Incremental Improvements (Plan 09)
- Day 8: Verification (Plan 10)

### Parallel Execution
All plans within a wave are **independent** and can run in parallel:
- Wave 1: Plans 01, 02, 03 (parallel)
- Wave 2: Plans 04, 05, 06 (parallel)
- Wave 3: Plans 07, 08 (parallel)
- Wave 4: Plan 09 (independent)
- Wave 5: Plan 10 (depends on all)

---

## Next Steps

1. **Execute Wave 1:**
   ```bash
   /gsd:execute-phase 207-coverage-quality-push
   ```

2. **Monitor Progress:**
   - Track coverage after each plan
   - Verify collection stability
   - Check branch coverage

3. **Adjust as Needed:**
   - If coverage lags: Add more tests
   - If collection errors occur: Fix immediately
   - If branch coverage low: Add branch-specific tests

4. **Final Verification:**
   - Run Plan 10 for aggregation
   - Verify all targets met
   - Document lessons learned

---

## Files Created

1. `207-RESEARCH.md` - Research document (15,654 bytes)
2. `207-01-PLAN.md` - Reports & WebSocket routes (22,738 bytes)
3. `207-02-PLAN.md` - Analytics & Time Travel routes (30,752 bytes)
4. `207-03-PLAN.md` - Onboarding & Sales routes (38,165 bytes)
5. `207-04-PLAN.md` - Lux Config & Messaging Schemas (36,188 bytes)
6. `207-05-PLAN.md` - Billing & LLM Service (14,859 bytes)
7. `207-06-PLAN.md` - Historical Learner & External Integration (2,904 bytes)
8. `207-07-PLAN.md` - Device & Browser Tools (2,896 bytes)
9. `207-08-PLAN.md` - Canvas Tool (2,186 bytes)
10. `207-09-PLAN.md` - Incremental Improvements (4,215 bytes)
11. `207-10-PLAN.md` - Verification & Reporting (7,643 bytes)
12. `207-PLANNING-SUMMARY.md` - This file

**Total:** 12 files, ~178,000 bytes of planning documentation

---

## Conclusion

Phase 207 is a **strategic pivot** based on Phase 206 learnings. By focusing on **testable modules** rather than **important modules**, we expect to achieve:

✅ **Higher Success Rate:** 70% target (vs 56.79% actual in Phase 206)
✅ **Better Quality:** 80% file-level quality (vs 44% in Phase 206)
✅ **Zero Collection Errors:** Proactive verification (vs 3 in Phase 206)
✅ **Branch Coverage:** 60%+ metric (NEW - not tracked in Phase 206)

**Key Innovation:** "Test testable modules" philosophy - prioritize ROI over importance.

**Ready for execution:** 10 comprehensive plans, wave-organized, with clear success criteria.

---

**Phase:** 207 - Coverage Quality Push
**Status:** PLANNING COMPLETE ✅
**Next Action:** Execute Wave 1
**Timeline:** 8 days (2 weeks)

---

*Planning completed: March 18, 2026*
*Planned execution: March 19 - March 26, 2026*
