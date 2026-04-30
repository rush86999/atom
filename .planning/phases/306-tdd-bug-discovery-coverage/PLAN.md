# Plan 306: TDD Bug Discovery & Coverage Completion

**Phase**: 306 - TDD Bug Discovery & Coverage Completion
**Goal**: Fix all remaining test failures and achieve 100% test coverage through TDD methodology
**Duration**: 1-2 weeks
**Effort**: 40-60 hours

---

## Executive Summary

Comprehensive TDD-driven bug fixing and coverage expansion to achieve 100% test pass rate and significantly improve code coverage. This phase focuses on systematic test failure resolution, targeted coverage improvements, and establishing a robust test suite.

**Current State**:
- 110 property tests: 90 passing (82%), 20 failing
- 195 unit tests: 100% passing
- Backend coverage: 54% (target: 80%)
- Frontend coverage: 18.75% (target: 30%)

**Goals**:
- Fix all 20 failing property tests
- Achieve 100% test pass rate (all tests)
- Increase backend coverage to 80% (+26pp)
- Increase frontend coverage to 30% (+11.25pp)

---

## Wave Structure

### Wave 1: Test Failure Analysis & Bug Fixing (Days 1-7)
**Goal**: Fix all remaining test failures and categorize by root cause

**Plans**:
- 306-01: Analyze all 20 failing property tests
- 306-02: Fix real bugs via TDD methodology
- 306-03: Update/fix test design issues

**Deliverables**:
- All 110 property tests passing
- Bug catalog with root cause analysis
- Test suite improvements

### Wave 2: Coverage Expansion & Verification (Days 8-14)
**Goal**: Achieve coverage targets through targeted test creation

**Plans**:
- 306-04: Identify coverage gaps and prioritize
- 306-05: Write targeted tests for uncovered code
- 306-06: Verify 100% pass rate and measure final coverage

**Deliverables**:
- Backend coverage ≥ 80%
- Frontend coverage ≥ 30%
- Coverage measurement report
- Test suite documentation

---

## Plan 306-01: Test Failure Analysis

**Goal**: Categorize all 20 failing tests by root cause

### Analysis Process

1. **Run Each Test Individually**
   ```bash
   pytest tests/property_tests/test_api_invariants.py::TestName::test_name -v
   ```

2. **Categorize Failure Type**
   - **Code Bug**: API returns wrong status code, wrong data format, missing validation
   - **Test Design Issue**: Test based on outdated API, fixture missing fields
   - **Feature Missing**: Pagination, payload limits, UUID validation not implemented
   - **Infrastructure Issue**: Database, fixtures, test setup problems

3. **Document Findings**
   - Root cause for each failure
   - Expected vs actual behavior
   - Fix complexity (1-line vs feature)
   - Priority (P0/P1/P2)

### Known Failure Categories (from TDD Bug Discovery Session)

**Test Design Issues** (8 tests):
1. test_post_agents_returns_422_on_invalid_input - Outdated (maturity field doesn't exist)
2. test_post_agents_rejects_empty_name - Already fixed, test needs update
3. test_post_agents_rejects_invalid_maturity - Test design issue
4. test_post_agents_requires_non_empty_capabilities - Wrong field name
5. test_delete_agents_id_returns_204_on_success - Fixture missing module_path/class_name
6. test_post_workflows_requires_name_field - Unknown
7. test_post_canvas_requires_type_field - Unknown
8. test_post_agents_handles_extra_fields_gracefully - Unknown

**Potential Real Bugs** (5 tests):
9. test_get_agents_id_rejects_invalid_uuid - Need UUID validation
10. test_put_agents_id_returns_403_without_permission - Authorization check
11. test_get_agents_id_returns_403_for_non_owned_agents - Authorization check
12. test_get_agents_response_is_list - May be stale (Bug #2 just fixed)
13. test_post_agents_handles_large_payloads - Need payload limits

**Edge Cases** (2 tests):
14. test_get_agents_handles_pagination - Pagination not implemented
15. test_post_workflows_returns_workflow_with_status_field - Unknown
16. test_get_canvas_id_returns_canvas_data_structure - Unknown

**Duplicates/Other** (remaining tests)

### Success Criteria
- ✅ All 20 tests analyzed and categorized
- ✅ Root cause documented for each
- ✅ Priority assigned (P0/P1/P2)
- ✅ Fix complexity estimated (hours)

---

## Plan 306-02: Fix Real Bugs via TDD

**Goal**: Fix all real code bugs using TDD methodology

### TDD Process (Red-Green-Refactor)

1. **RED**: Verify failing test exists
   ```bash
   pytest tests/property_tests/test_name.py -v  # Should fail
   ```

2. **GREEN**: Make minimal fix to pass test
   - Change 1 line of code if possible
   - Don't refactor yet
   - Just make test pass

3. **REFACTOR**: Improve code while tests pass
   - Clean up code
   - Add comments if needed
   - Ensure no regressions

4. **VERIFY**: Run full test suite
   ```bash
   pytest tests/ -v  # Ensure no regressions
   ```

### Expected Bugs to Fix

**Bug #3**: UUID Validation Missing
- **Test**: test_get_agents_id_rejects_invalid_uuid
- **Fix**: Add UUID validation in route or Pydantic model
- **Complexity**: Low (1-2 hours)

**Bug #4**: Authorization Check Missing
- **Test**: test_put_agents_id_returns_403_without_permission
- **Fix**: Add permission check to PUT endpoint
- **Complexity**: Low (1-2 hours)

**Bug #5**: Ownership Check Missing
- **Test**: test_get_agents_id_returns_403_for_non_owned_agents
- **Fix**: Add ownership check to GET endpoint
- **Complexity**: Medium (2-4 hours)

**Bug #6**: Payload Size Limits
- **Test**: test_post_agents_handles_large_payloads
- **Fix**: Add request size validation in FastAPI
- **Complexity**: Low (1-2 hours)

### Success Criteria
- ✅ All real bugs fixed (estimated 4-6 bugs)
- ✅ All tests pass
- ✅ No regressions introduced
- ✅ Each fix documented with commit message

---

## Plan 306-03: Fix Test Design Issues

**Goal**: Update or remove outdated tests

### Test Fixes Needed

**Fix 1**: Update test_post_agents_returns_422_on_invalid_input
- **Issue**: Test expects maturity field validation (doesn't exist)
- **Action**: Update test to check for existing validation (name, category)
- **Effort**: 30 minutes

**Fix 2**: Update test_post_agents_rejects_empty_name
- **Issue**: Test may be using wrong endpoint or validation changed
- **Action**: Verify validation is working, update test if needed
- **Effort**: 30 minutes

**Fix 3**: Remove/Update test_post_agents_rejects_invalid_maturity
- **Issue**: Maturity not in request model
- **Action**: Remove test or update to test database field
- **Effort**: 15 minutes

**Fix 4**: Update test_post_agents_requires_non_empty_capabilities
- **Issue**: Test checks for "capabilities" (should be "configuration")
- **Action**: Update field name
- **Effort**: 30 minutes

**Fix 5**: Fix test_delete_agents_id_returns_204_on_success
- **Issue**: Test fixture missing module_path and class_name
- **Action**: Add required fields to AgentRegistry creation
- **Effort**: 15 minutes

**Fixes 6-8**: Investigate workflow and canvas tests
- **Action**: Check if endpoints exist, update tests
- **Effort**: 1-2 hours

### Success Criteria
- ✅ All test design issues resolved
- ✅ Tests updated to match current API
- ✅ Outdated tests removed or documented
- ✅ All tests passing

---

## Plan 306-04: Coverage Gap Analysis

**Goal**: Identify and prioritize coverage gaps

### Coverage Measurement

```bash
# Backend coverage
pytest tests/ --cov=core --cov=backend --cov-report=html

# Frontend coverage
npm test -- --coverage

# Generate report
coverage report --fail-under=80
```

### Analysis Process

1. **Generate Coverage Reports**
   - Backend: HTML report in `htmlcov/`
   - Frontend: HTML report in `coverage/`

2. **Identify Gaps**
   - List all files with <80% coverage (backend)
   - List all files with <30% coverage (frontend)
   - Prioritize critical paths (auth, agents, core services)

3. **Categorize Gaps**
   - **Critical**: Auth, agent execution, core services (target 100%)
   - **Important**: API routes, business logic (target 80%)
   - **Nice-to-have**: Utilities, helpers (target 60%)

4. **Estimate Effort**
   - Number of tests needed per file
   - Complexity of test setup (fixtures, mocks)
   - Total hours to reach target

### Success Criteria
- ✅ Coverage baseline measured
- ✅ Gaps identified and prioritized
- ✅ Test plan created for each gap
- ✅ Effort estimated (hours)

---

## Plan 306-05: Write Targeted Tests for Coverage

**Goal**: Increase coverage through focused test creation

### Test Creation Strategy

**Priority 1: Critical Paths** (100% coverage target)
- Authentication & authorization
- Agent creation, execution, deletion
- Core services (governance, LLM, world model)

**Priority 2: API Routes** (80% coverage target)
- All endpoints tested
- Error paths tested
- Edge cases tested

**Priority 3: Business Logic** (80% coverage target)
- Service layer functions
- Business rules
- Data validation

### Test Types to Write

1. **Unit Tests**: Test individual functions/classes
   ```python
   def test_agent_governance_service_check_permission():
       service = AgentGovernanceService(db)
       result = service.check_permission(user_id, permission)
       assert result == expected
   ```

2. **Integration Tests**: Test component interactions
   ```python
   def test_agent_execution_with_governance():
       # Create agent with governance check
       # Execute and verify governance enforced
   ```

3. **Edge Case Tests**: Test boundary conditions
   ```python
   @given(st.text(min_size=0, max_size=100))
   def test_agent_name_validation(name):
       # Test various name inputs
   ```

### Success Criteria
- ✅ Backend coverage ≥ 80%
- ✅ Frontend coverage ≥ 30%
- ✅ Critical paths 100% covered
- ✅ All new tests passing

---

## Plan 306-06: Verification & Documentation

**Goal**: Verify 100% test pass rate and document results

### Verification Steps

1. **Run Full Test Suite**
   ```bash
   # Backend
   pytest tests/ -v --cov=core --cov=backend

   # Frontend
   npm test -- --coverage --watchAll=false

   # Verify 100% pass rate
   ```

2. **Check Coverage Reports**
   ```bash
   # Backend coverage
   coverage report | grep TOTAL

   # Frontend coverage
   cat coverage/coverage-summary.json
   ```

3. **Verify No Regressions**
   - All previously fixed bugs still fixed
   - No new test failures
   - Performance acceptable

### Documentation

1. **Create Coverage Report**
   - Before/after coverage metrics
   - Files improved
   - Remaining gaps (if any)

2. **Update Bug Catalog**
   - All bugs fixed
   - Test design issues resolved
   - Remaining work documented

3. **Phase Summary**
   - Achievements (tests passing, coverage %)
   - Lessons learned
   - Recommendations for next phase

### Success Criteria
- ✅ 100% test pass rate verified
- ✅ Backend coverage ≥ 80%
- ✅ Frontend coverage ≥ 30%
- ✅ Documentation complete

---

## Implementation Order

### Week 1: Bug Fixing
1. **Days 1-2**: Plan 306-01 (Analyze failures)
2. **Days 3-5**: Plan 306-02 (Fix real bugs)
3. **Days 6-7**: Plan 306-03 (Fix test issues)

### Week 2: Coverage Expansion
1. **Days 1-2**: Plan 306-04 (Analyze coverage gaps)
2. **Days 3-5**: Plan 306-05 (Write targeted tests)
3. **Days 6-7**: Plan 306-06 (Verify and document)

---

## Success Metrics

**Quantitative**:
- ✅ 110/110 property tests passing (100%)
- ✅ 195/195 unit tests passing (100%)
- ✅ Backend coverage ≥ 80% (from 54%)
- ✅ Frontend coverage ≥ 30% (from 18.75%)
- ✅ 0 test infrastructure issues

**Qualitative**:
- ✅ All bugs fixed via TDD methodology
- ✅ Test suite robust and maintainable
- ✅ Coverage gaps identified and addressed
- ✅ Documentation comprehensive

---

## Deliverables

1. **Bug Fix Commits** (estimated 6-8 commits)
   - Each bug fixed in separate commit
   - Commit message follows conventional format
   - TDD process documented

2. **Test Updates** (estimated 4-6 commits)
   - Test design issues fixed
   - Outdated tests updated or removed
   - New tests added for coverage

3. **Coverage Reports**
   - `htmlcov/` (backend HTML coverage)
   - `coverage/` (frontend HTML coverage)
   - `docs/testing/PHASE_306_COVERAGE_REPORT.md`

4. **Documentation**
   - `.planning/phases/306-tdd-bug-discovery-coverage/CONTEXT.md` ✅
   - `.planning/phases/306-tdd-bug-discovery-coverage/PLAN.md` ✅
   - `docs/testing/PHASE_306_SUMMARY.md` (final report)
   - `docs/testing/PHASE_306_BUG_CATALOG.md` (all bugs fixed)

---

## Risks & Mitigations

**Risk 1: Some Tests Can't Be Fixed**
- **Mitigation**: Update tests to match current API
- **Backup**: Document why test was removed

**Risk 2: Coverage Targets Too Aggressive**
- **Mitigation**: Focus on critical paths first
- **Backup**: Adjust targets based on feasibility

**Risk 3: Time Estimate Too Optimistic**
- **Mitigation**: Focus on high-impact fixes
- **Backup**: Split into multiple phases if needed

**Risk 4: Regressions Introduced**
- **Mitigation**: Run full test suite after each fix
- **Backup**: Keep detailed commit history for easy revert

---

## Conclusion

Phase 306 will systematically fix all remaining test failures and significantly improve code coverage through TDD methodology. The focus is on quality, maintainability, and establishing a robust test suite.

**Next Action**: Execute Plan 306-01 (Test Failure Analysis)

**Status**: ✅ READY TO START

---

**Last Updated**: 2026-04-30 09:40 UTC
