# Phase 306-01: Test Failure Analysis - Bug Catalog

**Date**: 2026-04-30
**Analysis**: Systematic analysis of 14 failing property tests
**Status**: COMPLETE

---

## Executive Summary

Analyzed all 14 failing property tests and categorized by root cause:

| Category | Count | Percentage |
|----------|-------|------------|
| **Test Design Issues** | 6 | 43% |
| **Infrastructure Issues** | 4 | 29% |
| **Real Code Bugs** | 3 | 21% |
| **Feature Missing** | 1 | 7% |

**Total**: 14 failing tests

---

## Quick Fix: Infrastructure (Wave 1)

**Fix**: Add module_path and class_name to all AgentRegistry test fixtures

**Location**: `backend/tests/property_tests/test_api_invariants.py`

**Lines to fix**: Around line 243-248 (test_agent fixture)

**Impact**: 4 tests will pass immediately

**Effort**: 15 minutes

---

## Detailed Bug Catalog

### Real Code Bugs (Fix via TDD)

1. **test_get_agents_id_rejects_invalid_uuid** (BUG-07)
   - Missing UUID validation in GET endpoint
   - Returns 404 instead of 400 for invalid UUID
   - Effort: 1-2 hours

2. **test_get_agents_id_returns_403_for_non_owned_agents** (BUG-08)
   - Missing ownership check
   - Returns 200 for any agent (security issue)
   - Effort: 2-4 hours

3. **test_post_agents_handles_large_payloads** (BUG-09)
   - No payload size limit
   - DoS vulnerability
   - Effort: 1-2 hours

### Implementation Errors (Fix Immediately)

4. **test_post_workflows_returns_workflow_with_status_field** (IMP-10)
   - Error: `WorldModelService.__init__() got an unexpected keyword argument 'tenant_id'`
   - File: `backend/core/atom_meta_agent.py:217`
   - Effort: 1-2 hours

5. **test_get_canvas_id_returns_canvas_data_structure** (IMP-11)
   - Error: `ServiceFactory() takes no arguments`
   - File: `backend/api/canvas_routes.py:146`
   - Effort: 1-2 hours

### Test Design Issues (Update Tests)

6. **test_post_agents_returns_422_on_invalid_input** (TD-01)
   - Test sends valid data but expects 422
   - Test description wrong (mentions maturity field that doesn't exist)
   - Effort: 30 minutes

7-11. Other test design issues (TD-02 through TD-06)
   - Outdated tests based on wrong API understanding
   - Effort: 1-2 hours total

---

## Fix Order (Recommended)

**Wave 1: Infrastructure** (15 min, 4 tests)
```python
# Fix test_agent fixture
agent = AgentRegistry(
    id=str(uuid.uuid4()),
    name="Test Agent",
    status=AgentStatus.STUDENT.value,
    category="testing",
    module_path="core.generic_agent",  # ADD THIS
    class_name="GenericAgent"  # ADD THIS
)
```

**Wave 2: Implementation Errors** (2-4 hours, 2 tests)
- Fix WorldModelService call (IMP-10)
- Fix ServiceFactory call (IMP-11)

**Wave 3: Real Bugs via TDD** (4-8 hours, 3 tests)
- UUID validation (BUG-07)
- Ownership check (BUG-08)
- Payload size limit (BUG-09)

**Wave 4: Test Updates** (1-2 hours, 6 tests)
- Update or remove outdated tests

---

## Success Metrics

**Before**: 90/110 tests passing (82%)
**After Wave 1**: 94/110 tests passing (85%)
**After Wave 2**: 96/110 tests passing (87%)
**After Wave 3**: 99/110 tests passing (90%)
**After Wave 4**: 105/110 tests passing (95%)

*Note: 5 tests may be removed if they test non-existent features*

---

**Last Updated**: 2026-04-30 09:55 UTC
