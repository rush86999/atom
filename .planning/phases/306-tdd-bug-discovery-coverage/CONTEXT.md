# Phase 306: TDD Bug Discovery & Coverage Completion - Context

**Phase**: 306 - TDD Bug Discovery & Coverage Completion
**Goal**: Fix all remaining test failures and achieve 100% test coverage through TDD methodology
**Duration**: 1-2 weeks
**Effort**: 40-60 hours
**Created**: 2026-04-30

---

## Current State

### Recent Progress (Phase 301 & Bug Discovery Session)
- ✅ **Phase 301 Complete**: 112 property tests created, 14 bugs discovered
- ✅ **Bug Fixes**: 2 real code bugs fixed via TDD
  - Bug #1: POST /api/agents/custom returns 201 (HTTP standard)
  - Bug #2: GET /api/agents returns list directly (REST standard)
- ✅ **Infrastructure**: SQLite TestClient database issue fixed
- ✅ **Test Suite**: 110 property tests (90 passing, 20 failing)

### Remaining Test Failures: 20

**Test Design Issues** (8 failures - not code bugs):
1. test_post_agents_returns_422_on_invalid_input - Outdated test (maturity field doesn't exist)
2. test_post_agents_rejects_empty_name - Already fixed in Phase 303
3. test_post_agents_rejects_invalid_maturity - Test design issue
4. test_post_agents_requires_non_empty_capabilities - Wrong field name
5. test_delete_agents_id_returns_204_on_success - Fixture missing required fields
6. test_post_workflows_requires_name_field - Need investigation
7. test_post_canvas_requires_type_field - Need investigation
8. test_post_agents_handles_extra_fields_gracefully - Need investigation

**Potential Real Bugs** (5 failures - need investigation):
9. test_get_agents_id_rejects_invalid_uuid - UUID validation missing
10. test_put_agents_id_returns_403_without_permission - Authorization issue
11. test_get_agents_id_returns_403_for_non_owned_agents - Authorization issue
12. test_get_agents_response_is_list - May be stale (just fixed Bug #2)
13. test_post_agents_handles_large_payloads - Payload size limits

**Edge Cases & Other** (7 failures):
14. test_get_agents_handles_pagination - Pagination not implemented
15. test_post_workflows_returns_workflow_with_status_field - Need investigation
16. test_get_canvas_id_returns_canvas_data_structure - Need investigation
17. test_get_agents_id_rejects_invalid_uuid - Duplicate entry
18. test_post_agents_handles_extra_fields_gracefully - Duplicate entry
19. test_post_agents_handles_large_payloads - Duplicate entry
20. (Other edge case tests)

### Current Coverage
- **Backend**: 54% (21pp above 50% target, but far from 100%)
- **Frontend**: 18.75% (1.25pp below 20% target)
- **Property Tests**: 110 tests (90 passing, 20 failing)
- **Unit Tests**: 195 backend tests (100% passing)

---

## Dependencies

**Completed Phases**:
- ✅ Phase 300: TDD Methodology Establishment
- ✅ Phase 301: Property Testing Expansion
- ✅ Phase 303: Bug Fixing Sprint 1 (partial - 3 bugs fixed)

**Current Work**:
- TDD bug discovery session ongoing (2 bugs fixed, 20 tests failing)
- Property tests operational (file-based SQLite fix applied)
- Test infrastructure working (TestClient, fixtures)

---

## Requirements

### TDD-08: Comprehensive Bug Discovery & Fixing

**Goal**: Fix all remaining test failures and achieve 100% test coverage

**Success Criteria**:
1. All 110 property tests passing
2. All unit tests passing (maintain 100%)
3. Backend coverage ≥ 80% (from 54%)
4. Frontend coverage ≥ 30% (from 18.75%)
5. Test infrastructure robust (no fixture issues)

**Approach**:
- TDD methodology for all fixes (RED → GREEN → REFACTOR)
- Systematic test failure analysis
- Coverage gap identification
- Targeted test creation for uncovered code

---

## Technical Context

### Backend Tech Stack
- Python 3.11
- FastAPI
- SQLAlchemy 2.0
- Pytest (testing framework)
- Hypothesis (property-based testing)

### Frontend Tech Stack
- Next.js
- React Testing Library
- Jest

### Test Infrastructure
- **Property Tests**: 110 tests in `tests/property_tests/`
- **Unit Tests**: 195 tests in `tests/`
- **Regression Tests**: 17 tests in `tests/regression/`
- **Fixtures**: Working (file-based SQLite, auth_headers, test_agent)

### Known Issues
1. **Test Design**: 8 tests based on outdated API understanding
2. **Coverage Gaps**: Large areas of code untested (46% backend, 81% frontend)
3. **Edge Cases**: Pagination, large payloads, invalid UUIDs not handled
4. **Authorization**: Some endpoints missing permission checks

---

## Quality Goals

### Test Pass Rates
- **Target**: 100% property tests passing (from 82%)
- **Target**: 100% unit tests passing (maintain current)
- **Target**: 100% regression tests passing

### Coverage Targets
- **Backend**: 80% (from 54%) - +26 percentage points
- **Frontend**: 30% (from 18.75%) - +11.25 percentage points
- **Critical Paths**: 100% coverage (auth, agents, core services)

### Bug Discovery
- **Fix**: All 5 potential real bugs identified
- **Fix**: All test infrastructure issues
- **Update**: 8 outdated tests to match current API
- **Implement**: Missing features (pagination, payload limits)

---

## Pain Points

### Test Maintenance
1. **Outdated Tests**: 8 tests based on old API structure
2. **Test Design Issues**: Fixtures missing required fields
3. **API Evolution**: Tests need updates as API changes

### Coverage Gaps
1. **Large Uncovered Areas**: 46% backend, 81% frontend
2. **Edge Cases**: Not systematically tested
3. **Integration Paths**: Not tested end-to-end
4. **Error Scenarios**: Not tested comprehensively

### Technical Debt
1. **Property Test Failures**: 20 failing tests block progress
2. **Test Infrastructure**: Recently fixed, need verification
3. **Coverage Measurement**: Need baseline and tracking

---

## Timeline

**Week 1**: Bug Discovery & Fixing
- Days 1-2: Analyze all 20 failing tests, categorize by root cause
- Days 3-4: Fix real bugs (TDD methodology)
- Days 5-7: Update/fix test design issues

**Week 2**: Coverage Expansion
- Days 1-3: Identify coverage gaps, prioritize critical paths
- Days 4-5: Write targeted tests for uncovered code
- Days 6-7: Verify 100% test pass rate, measure final coverage

---

## Success Metrics

**Quantitative**:
- ✅ 110/110 property tests passing (100%)
- ✅ 195/195 unit tests passing (100%)
- ✅ Backend coverage ≥ 80%
- ✅ Frontend coverage ≥ 30%
- ✅ 0 test infrastructure issues

**Qualitative**:
- ✅ All tests use TDD methodology
- ✅ Coverage gaps identified and addressed
- ✅ Test suite maintainable and reliable
- ✅ Documentation updated

---

## Risks

**Risk 1: Outdated Tests Can't Be Fixed**
- **Mitigation**: Update tests to match current API, remove if obsolete
- **Backup**: Document why test was removed

**Risk 2: Coverage Targets Too Aggressive**
- **Mitigation**: Focus on critical paths first, defer nice-to-have areas
- **Backup**: Adjust targets based on feasibility

**Risk 3: Test Infrastructure Issues**
- **Mitigation**: File-based SQLite fix should resolve most issues
- **Backup**: Use integration test environment if needed

**Risk 4: Time Estimate Too Optimistic**
- **Mitigation**: Focus on high-impact fixes first
- **Backup**: Split into multiple phases if needed

---

## Resources

**Documentation**:
- `/docs/testing/TDD_BUG_DISCOVERY_SESSION.md` - Recent session summary
- `/docs/testing/TDD_METHODOLOGY.md` - TDD methodology guide
- `/docs/testing/BUG_FIX_PROCESS.md` - Bug fix process
- `.planning/phases/301-property-testing/` - Property test expansion

**Test Files**:
- `backend/tests/property_tests/test_api_invariants.py` - API contract tests
- `backend/tests/property_tests/test_data_invariants.py` - Data invariant tests
- `backend/tests/regression/` - Regression test suite

**Tools**:
- Pytest (test runner)
- Hypothesis (property-based testing)
- Coverage.py (coverage measurement)
- FastAPI TestClient (API testing)

---

**Last Updated**: 2026-04-30 09:35 UTC
**Status**: READY TO START
