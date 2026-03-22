# Phase 218: Fix Test Collection Errors

**Status**: PENDING
**Priority**: CRITICAL (blocking test execution)
**Estimated Time**: 1-2 hours

---

## Goal

Fix 2 test files with collection errors that prevent the full test suite from running.

---

## Requirements

- **REQ-001**: All test files must collect without errors
- **REQ-002**: All test dependencies must be available or mocked

---

## Gap Closure

Closes collection errors that are blocking full test suite execution:
- `tests/core/test_time_expression_parser.py` - Import error
- `tests/core/test_trace_validator.py` - Missing dependency

---

## Tasks

### Task 1: Fix import error in test_time_expression_parser.py

**File**: `tests/core/test_time_expression_parser.py`

**Issue**: Cannot import `TimeExpressionParser` from `core.time_expression_parser`

**Investigation**:
```bash
# Check what's actually exported
python3 -c "from core.time_expression_parser import *; print(dir())"
```

**Actions**:
1. Read `tests/core/test_time_expression_parser.py` line 12
2. Read `core/time_expression_parser.py` to find correct class/function name
3. Update import to match actual export
4. Verify with `pytest tests/core/test_time_expression_parser.py --collect-only`

**Expected Outcome**: Test file collects successfully with 0 errors

---

### Task 2: Fix missing dependency in test_trace_validator.py

**File**: `tests/core/test_trace_validator.py`

**Issue**: Missing `aiofiles` module dependency

**Investigation**:
```bash
# Check if aiofiles is needed or test can skip
grep -r "aiofiles" core/trajectory.py
```

**Actions**:
1. Check if `aiofiles` is used in production code (`core/trajectory.py`)
2. If used: Add `aiofiles` to `requirements.txt` or `pyproject.toml`
3. If not used: Make `core/trajectory.py` import optional or skip test
4. Verify with `pytest tests/core/test_trace_validator.py --collect-only`

**Expected Outcome**: Test file collects successfully (either with dependency or skip)

---

## Success Criteria

- [ ] `pytest tests/core/test_time_expression_parser.py --collect-only` succeeds (0 errors)
- [ ] `pytest tests/core/test_trace_validator.py --collect-only` succeeds (0 errors)
- [ ] Full test suite collects with 0 collection errors
- [ ] All tests in both files can execute (may pass or fail, but must run)

---

## Acceptance Tests

```bash
# Test 1: Verify time expression parser collects
pytest tests/core/test_time_expression_parser.py --collect-only

# Test 2: Verify trace validator collects
pytest tests/core/test_trace_validator.py --collect-only

# Test 3: Verify full suite collection
pytest tests/ --collect-only 2>&1 | grep -E "collected|error"

# Expected: All tests collect, 0 errors
```

---

## Notes

- These collection errors are blocking any progress on coverage goals
- Priority is CRITICAL because full test suite cannot run
- After fixing, will enable execution of Phases 219-221

---

*Created: 2026-03-21*
*Next Action: Start Task 1 - Investigate import error*
