# Plan 09-4: Fix Governance Test Failures

**Phase**: Phase 09 - Test Suite Stabilization
**Status**: 📋 PENDING
**Priority**: CRITICAL
**Estimated**: 1 day
**Dependencies**: 09-1 (must complete first)
**Wave**: 2
**File**: `.planning/phases/09-test-suite-stabilization/04-fix-governance-failures.md`

---

## Overview

Fix all failing governance unit tests to achieve stable test suite.

**Goal**: Resolve all failures in test_supervision_service.py and test_trigger_interceptor.py.

---

## Problem Statement

### Current Failures

Governance tests have collection errors (fixed in 09-1) but will likely have failures when run:
- Incorrect test assertions
- Mock setup issues
- Wrong expected behavior
- Missing test data

---

## Solution Approach

### Step 1: Run Tests and Collect Failures

```bash
pytest tests/unit/governance/test_supervision_service.py -v
pytest tests/unit/governance/test_trigger_interceptor.py -v
```

### Step 2: Analyze Failures

For each failure:
- Read the error message
- Understand what's being tested
- Identify why it's failing

### Step 3: Fix Failures

Fix issues systematically:
1. Fix incorrect assertions
2. Fix mock setup
3. Fix test data
4. Fix test logic

---

## Implementation Plan

### Task 1: Fix test_supervision_service.py Failures
**Estimated**: 3 hours

**Actions**:
1. Run tests and collect failures
2. Analyze each failure
3. Fix issues one by one
4. Verify each fix

**Expected Output**: All supervision tests passing

---

### Task 2: Fix test_trigger_interceptor.py Failures
**Estimated**: 5 hours

**Actions**:
1. Run tests and collect failures
2. Analyze each failure
3. Fix issues one by one
4. Verify each fix

**Expected Output**: All trigger interceptor tests passing

---

## Acceptance Criteria

- [ ] `pytest tests/unit/governance/test_supervision_service.py -v` passes with 0 failures
- [ ] `pytest tests/unit/governance/test_trigger_interceptor.py -v` passes with 0 failures
- [ ] `pytest tests/unit/governance/ -v` passes with 0 failures
- [ ] All governance tests stable across multiple runs

---

## Notes

### Dependencies
- **09-1 must complete first**: Tests must collect before they can run

### Common Test Failure Causes
1. **Mock not configured**: Configure mock.return_value
2. **Wrong assertion**: Check actual vs expected behavior
3. **Missing side_effect**: Use side_effect for multiple calls
4. **Async not awaited**: Ensure async calls are awaited

---

*Plan Created: 2026-02-15*
