# Phase 219: Fix Industry Workflow Test Failures

**Status**: PENDING
**Priority**: CRITICAL (quality gate blocking)
**Estimated Time**: 2-3 hours
**Depends On**: Phase 218 (test collection errors fixed)

---

## Goal

Fix all 10 failing tests in `test_industry_workflow_endpoints.py` to achieve 98%+ test pass rate.

---

## Requirements

- **REQ-003**: 98%+ test pass rate required for coverage expansion
- **REQ-004**: All industry workflow endpoints must have passing tests

---

## Gap Closure

Closes test failures that are blocking progress on coverage goals:
- 10 failing tests in `tests/api/services/test_industry_workflow_endpoints.py`
- Test failures indicate either test issues or implementation bugs

---

## Current State

**Failing Tests** (from coverage run):
1. `TestGetSupportedIndustries::test_get_supported_industries_empty`
2. `TestGetSupportedIndustries::test_get_supported_industries_with_templates`
3. `TestGetIndustryTemplates::test_get_industry_templates_basic`
4. `TestGetIndustryTemplates::test_get_industry_templates_with_complexity_filter`
5. `TestGetTemplateDetails::test_get_template_details_found`
6. `TestSearchTemplates::test_search_templates_basic`
7. `TestSearchTemplates::test_search_templates_no_filters`
8. `TestCalculateROI::test_calculate_roi_basic`
9. `TestCalculateROI::test_calculate_roi_template_not_found`
10. `TestGetImplementationGuide::test_get_implementation_guide`

---

## Tasks

### Task 1: Investigate test failure patterns

**File**: `tests/api/services/test_industry_workflow_endpoints.py`

**Actions**:
1. Run failing tests individually to see error messages
   ```bash
   pytest tests/api/services/test_industry_workflow_endpoints.py::TestGetSupportedIndustries::test_get_supported_industries_empty -v
   ```
2. Analyze failure patterns
   - Are all failures similar (assertion vs. error)?
   - Do tests expect specific response structure?
   - Is implementation returning unexpected data?
3. Check implementation file
   ```bash
   cat core/industry_workflow_endpoints.py | head -200
   ```

**Expected Outcome**: Clear understanding of failure root cause

---

### Task 2: Fix test assertions or implementation bugs

**Decision Tree**:
- **If tests are wrong**: Update test assertions to match actual API behavior
- **If implementation is wrong**: Fix bugs in `core/industry_workflow_endpoints.py`
- **If fixtures are wrong**: Update test fixtures to provide correct data

**Actions**:
1. Apply fixes based on Task 1 investigation
2. Run tests after each fix to verify improvement
3. Document what was changed and why

**Expected Outcome**: Tests start passing

---

### Task 3: Verify all 10 tests passing

**Actions**:
1. Run full test file
   ```bash
   pytest tests/api/services/test_industry_workflow_endpoints.py -v
   ```
2. Confirm 100% pass rate (all tests green)
3. Check for regressions in nearby tests

**Expected Outcome**: All industry workflow tests passing

---

### Task 4: Update test documentation

**Actions**:
1. Document any test pattern changes
2. Add notes for future maintainers
3. Update related documentation if needed

**Expected Outcome**: Clear documentation of changes

---

## Success Criteria

- [ ] All 10 tests in `test_industry_workflow_endpoints.py` passing
- [ ] Overall test pass rate ≥98%
- [ ] No regression in other tests
- [ ] Changes documented

---

## Acceptance Tests

```bash
# Test 1: Run all industry workflow tests
pytest tests/api/services/test_industry_workflow_endpoints.py -v

# Expected: All tests pass

# Test 2: Check overall pass rate
pytest tests/ -q 2>&1 | tail -5

# Expected: Pass rate ≥98%

# Test 3: Verify no regressions
pytest tests/api/services/ -v

# Expected: Other service tests still passing
```

---

## Notes

- These failures are blocking quality gate for coverage expansion
- Tests cover industry workflow templates and ROI calculation
- Priority is CRITICAL because 98% pass rate is required for Phase 221
- After fixing, will enable execution of Phase 220 (assertion density)

---

*Created: 2026-03-21*
*Next Action: Run Task 1 after Phase 218 completes*
