# Plan 09-3: Fix Property Test TypeErrors

**Phase**: Phase 09 - Test Suite Stabilization
**Status**: 📋 PENDING
**Priority**: HIGH
**Estimated**: 1 day
**Dependencies**: None
**Wave**: 1
**File**: `.planning/phases/09-test-suite-stabilization/03-fix-property-test-errors.md`

---

## Overview

Fix TypeError issues in property tests that prevent collection. Property tests provide strong correctness guarantees using hypothesis.

**Goal**: Resolve 10 TypeErrors across property test files.

---

## Problem Statement

### Current Errors

**Property Tests** (10 TypeErrors):
1. `tests/property_tests/input_validation/test_input_validation_invariants.py`
2. `tests/property_tests/temporal/test_temporal_invariants.py`
3. `tests/property_tests/tools/test_tool_governance_invariants.py`

### Root Cause Analysis

Property test TypeErrors typically indicate:
1. **Incorrect hypothesis strategies**: @given decorators with wrong types
2. **Missing strategy imports**: hypothesis.strategies not imported
3. **Type mismatch**: Strategy doesn't match parameter type
4. **Custom strategy errors**: Incorrectly defined custom strategies

---

## Solution Approach

### Step 1: Investigate Property Test Files

1. Read each property test file
2. Identify hypothesis @given decorators
3. Check strategy definitions
4. Identify type mismatches

### Step 2: Fix Strategy Issues

Fix issues systematically:
1. Fix incorrect strategy types
2. Add missing strategy imports
3. Fix custom strategy definitions
4. Ensure type consistency

### Step 3: Verify Fixes

```bash
pytest tests/property_tests/ --collect-only
pytest tests/property_tests/ -v
```

---

## Implementation Plan

### Task 1: Fix test_input_validation_invariants.py
**Estimated**: 2 hours

**Actions**:
1. Read the property test file
2. Identify @given decorators and strategies
3. Fix type mismatches in strategies
4. Verify hypothesis strategies are correctly imported
5. Run tests to verify

**Expected Output**: 0 TypeErrors, tests collect and run

---

### Task 2: Fix test_temporal_invariants.py
**Estimated**: 3 hours

**Actions**:
1. Read the property test file
2. Identify @given decorators and strategies
3. Fix type mismatches in strategies
4. Verify hypothesis strategies are correctly imported
5. Run tests to verify

**Expected Output**: 0 TypeErrors, tests collect and run

---

### Task 3: Fix test_tool_governance_invariants.py
**Estimated**: 3 hours

**Actions**:
1. Read the property test file
2. Identify @given decorators and strategies
3. Fix type mismatches in strategies
4. Verify hypothesis strategies are correctly imported
5. Run tests to verify

**Expected Output**: 0 TypeErrors, tests collect and run

---

## Acceptance Criteria

- [ ] `pytest tests/property_tests/ --collect-only` completes with 0 errors
- [ ] All property tests collect successfully
- [ ] Property tests run without TypeError
- [ ] Hypothesis strategies properly defined
- [ ] Tests provide meaningful failure reports

---

## Testing Strategy

### Before Fix
```bash
pytest tests/property_tests/ --collect-only 2>&1 | tee /tmp/before_fix_property.log
```

### After Fix
```bash
pytest tests/property_tests/ --collect-only
pytest tests/property_tests/ -v --hypothesis-seed=0
```

### Success Criteria
- 0 collection errors
- All property tests discovered
- No TypeError during collection or execution
- Hypothesis generates valid test data

---

## Notes

### Key Files to Modify
- `tests/property_tests/input_validation/test_input_validation_invariants.py`
- `tests/property_tests/temporal/test_temporal_invariants.py`
- `tests/property_tests/tools/test_tool_governance_invariants.py`

### Common Hypothesis Pitfalls
1. **Strategy type mismatch**: Ensure strategy matches parameter type
2. **Missing imports**: Import from hypothesis.strategies
3. **Custom strategies**: Use @st.composite for complex types
4. **Type hints**: Hypothesis uses type hints for strategy inference

### Hypothesis Settings
```python
# Typical hypothesis settings
@pytest.mark.hypothesisgiven
@given(strategy=st.text())
@settings(max_examples=100, deadline=timedelta(milliseconds=100))
def test_property(input):
    assert process(input) is valid
```

### Dependencies
- None - this is in Wave 1, can run in parallel with 09-1 and 09-2

### Risk
Property tests may require significant refactoring if hypothesis usage is fundamentally incorrect.

---

## Completion

When complete, this plan will unblock all property tests, enabling strong correctness guarantees.

**Next Plan**: 09-4 - Fix Governance Test Failures (Wave 2, depends on 09-1)

---

*Plan Created: 2026-02-15*
*Estimated Completion: 2026-02-15*
